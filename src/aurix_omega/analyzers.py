"""Read-only static artifact analysis; unknown files are never executed."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import struct
from typing import Any

from .models import Finding, base_report

MAX_STRING_SCAN_BYTES = 64 * 1024 * 1024
MAX_PRINTABLE_STRINGS = 500
MAX_PE_SECTIONS = 96

REVIEW_RULES: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    ("encoded-powershell", re.compile(r"(?i)(?:-enc(?:odedcommand)?\s+[a-z0-9+/=]{16,}|frombase64string\s*\()"),
     "Encoded PowerShell or Base64-decoding reference",
     "Review context and verify the behavior is expected."),
    ("persistence-run-key", re.compile(r"(?i)currentversion\\run(?:once)?"),
     "Windows Run-key persistence reference",
     "Check whether the application legitimately configures startup behavior."),
    ("process-memory-api", re.compile(r"(?i)\b(?:writeprocessmemory|createremotethread|virtualalloc)\b"),
     "Process-memory manipulation API reference",
     "Review imports and context; these APIs also have legitimate debugging uses."),
    ("script-host", re.compile(r"(?i)\b(?:wscript\.shell|mshta\.exe|rundll32\.exe)\b"),
     "Script host or proxy-execution utility reference",
     "Verify why the application references this utility."),
)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_file_type(data: bytes, suffix: str = "") -> str:
    if data.startswith(b"MZ"):
        return "Windows PE candidate (MZ header; validation partial)"
    if data.startswith(b"\x7fELF"):
        return "ELF executable or shared object"
    if data.startswith(b"PK\x03\x04"):
        return "ZIP-based container"
    if data.startswith(b"\x1f\x8b"):
        return "GZIP-compressed data"
    if data.startswith(b"%PDF-"):
        return "PDF document"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG image"
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG image"
    if data.startswith(b"#!"):
        return "Script with interpreter shebang"
    if data and b"\x00" not in data[:4096]:
        return "Text-like data (heuristic)"
    return f"Unknown or binary data (extension: {suffix or 'none'})"


def extract_printable_strings(data: bytes, min_length: int = 5, limit: int = MAX_PRINTABLE_STRINGS) -> list[str]:
    if min_length < 1 or limit < 1:
        return []
    ascii_pattern = re.compile(rb"[\x20-\x7e]{" + str(min_length).encode() + rb",}")
    utf16_pattern = re.compile(rb"(?:[\x20-\x7e]\x00){" + str(min_length).encode() + rb",}")
    output: list[str] = []
    seen: set[str] = set()
    for pattern, encoding in ((ascii_pattern, "ascii"), (utf16_pattern, "utf-16le")):
        for match in pattern.finditer(data):
            value = match.group().decode(encoding, errors="replace").strip()
            if value and value not in seen:
                seen.add(value)
                output.append(value)
                if len(output) >= limit:
                    return output
    return output


def inspect_pe_headers(data: bytes) -> dict[str, Any] | None:
    """Read a bounded subset of PE metadata without loading the image."""
    try:
        if len(data) < 64 or data[:2] != b"MZ":
            return None
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        if pe_offset < 64 or pe_offset > len(data) - 24:
            return {"valid_header": False, "reason": "PE header offset out of bounds"}
        if data[pe_offset:pe_offset + 4] != b"PE\x00\x00":
            return {"valid_header": False, "reason": "PE signature absent at declared offset"}
        machine, section_count, timestamp, _, _, optional_size, characteristics = struct.unpack_from(
            "<HHIIIHH", data, pe_offset + 4
        )
        opt_start = pe_offset + 24
        if opt_start + optional_size > len(data):
            return {"valid_header": False, "reason": "Optional header exceeds scanned bytes"}
        magic = struct.unpack_from("<H", data, opt_start)[0] if optional_size >= 2 else 0
        section_start = opt_start + optional_size
        sections: list[dict[str, Any]] = []
        for index in range(min(section_count, MAX_PE_SECTIONS)):
            offset = section_start + index * 40
            if offset + 40 > len(data):
                break
            name = data[offset:offset + 8].split(b"\x00", 1)[0].decode("ascii", errors="replace")
            virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from("<IIII", data, offset + 8)
            sections.append({"name": name, "virtual_size": virtual_size, "virtual_address": virtual_address,
                             "raw_size": raw_size, "raw_pointer": raw_pointer})
        return {
            "valid_header": True,
            "machine": {0x014C: "x86", 0x8664: "x86_64", 0x01C0: "ARM", 0xAA64: "ARM64"}.get(machine, f"unknown (0x{machine:04x})"),
            "section_count_declared": section_count, "section_count_parsed": len(sections),
            "timestamp_epoch": timestamp,
            "optional_header": {0x10B: "PE32", 0x20B: "PE32+", 0x107: "ROM"}.get(magic, f"unknown (0x{magic:04x})"),
            "characteristics_hex": f"0x{characteristics:04x}",
            "sections": sections, "section_list_truncated": section_count > len(sections),
        }
    except (struct.error, ValueError):
        return {"valid_header": False, "reason": "Could not parse bounded PE metadata"}


def analyze_file(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Artifact does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Artifact is not a regular file: {path}")
    size = path.stat().st_size
    digest = sha256_file(path)
    with path.open("rb") as handle:
        sample = handle.read(MAX_STRING_SCAN_BYTES)
    strings = extract_printable_strings(sample)
    file_type = detect_file_type(sample[:8192], path.suffix.lower())
    artifact: dict[str, Any] = {
        "supplied_path": str(file_path), "file_name": path.name, "size_bytes": size,
        "sha256": digest, "detected_type": file_type,
        "string_scan_bytes": len(sample), "string_scan_truncated": size > len(sample),
        "printable_strings": strings, "printable_string_count": len(strings),
    }
    if file_type.startswith("Windows PE candidate"):
        artifact["pe_headers"] = inspect_pe_headers(sample)

    report = base_report("artifact_inspection")
    report["artifact"] = artifact
    joined = "\n".join(strings)
    for rule_id, pattern, title, recommendation in REVIEW_RULES:
        match = pattern.search(joined)
        if match:
            report["findings"].append(Finding(
                title=title,
                description="A conservative string heuristic matched. This signal alone does not establish malicious behavior.",
                severity="low", confidence="low", source=f"artifact:{path.name}",
                evidence=[f"matched indicator: {rule_id}", match.group(0)[:160]],
                recommendation=recommendation,
            ).to_dict())
    report["summary"] = {
        "result": "Review indicators found" if report["findings"] else "No configured static review heuristics matched",
        "warning": "Validate indicators in context; absence of matches does not prove safety.",
    }
    return report


def compare_files(old_path: str | Path, new_path: str | Path) -> dict[str, Any]:
    old, new = analyze_file(old_path), analyze_file(new_path)
    old_strings, new_strings = set(old["artifact"]["printable_strings"]), set(new["artifact"]["printable_strings"])
    report = base_report("artifact_diff")
    report["artifacts"] = {
        label: {key: source["artifact"][key] for key in ("supplied_path", "size_bytes", "sha256", "detected_type")}
        for label, source in (("before", old), ("after", new))
    }
    report["diff"] = {
        "identical_sha256": old["artifact"]["sha256"] == new["artifact"]["sha256"],
        "size_delta_bytes": new["artifact"]["size_bytes"] - old["artifact"]["size_bytes"],
        "added_printable_strings": sorted(new_strings - old_strings),
        "removed_printable_strings": sorted(old_strings - new_strings),
        "common_printable_string_count": len(old_strings & new_strings),
        "note": "Not a complete semantic binary diff; changes are not automatically benign or malicious.",
    }
    return report
