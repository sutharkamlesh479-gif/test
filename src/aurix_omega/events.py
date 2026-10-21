"""Normalize JSON/JSONL event exports and build cautious timeline links."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .models import Finding, base_report, stable_id

MAX_EVENT_COUNT = 50_000
MAX_EVENT_FILE_BYTES = 20 * 1024 * 1024


def _normalize_timestamp(value: Any) -> tuple[str | None, bool]:
    if not isinstance(value, str) or not value.strip():
        return None, False
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat(), True
    except ValueError:
        return None, False


def _read_rows(path: Path) -> tuple[list[Any], list[str]]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        parsed = json.loads(text)
        rows = parsed.get("events", [parsed]) if isinstance(parsed, dict) else parsed
        if not isinstance(rows, list):
            raise ValueError("JSON root must be a list, object, or object with an events list.")
        return rows, []
    except json.JSONDecodeError:
        rows: list[Any] = []
        errors: list[str] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                errors.append(f"Line {line_number}: invalid JSON ({exc.msg}).")
        return rows, errors


def analyze_events(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Event file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Event input is not a regular file: {path}")
    size = path.stat().st_size
    if size > MAX_EVENT_FILE_BYTES:
        raise ValueError(f"Event input exceeds the {MAX_EVENT_FILE_BYTES}-byte processing limit.")
    raw_rows, errors = _read_rows(path)
    if len(raw_rows) > MAX_EVENT_COUNT:
        raise ValueError(f"Input contains more than {MAX_EVENT_COUNT} events; processing stopped.")

    events: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows, 1):
        if not isinstance(row, dict):
            errors.append(f"Record {index}: expected a JSON object; record skipped.")
            continue
        timestamp, valid_time = _normalize_timestamp(row.get("timestamp") or row.get("time"))
        kind = str(row.get("event_type") or row.get("type") or "unknown")[:120]
        process_value = row.get("process") or row.get("process_name") or row.get("image")
        process = str(process_value)[:260] if process_value is not None else None
        pid, parent_pid = row.get("pid"), row.get("parent_pid")
        events.append({
            "event_id": stable_id("event", index, timestamp, kind, process, pid),
            "record_number": index, "timestamp": timestamp, "timestamp_valid": valid_time,
            "event_type": kind, "process": process, "pid": pid, "parent_pid": parent_pid,
            "source": str(row.get("source") or path.name)[:260], "details": row,
        })

    keyed: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        identity = (f"pid:{event['pid']}" if event["pid"] is not None
                    else f"name:{event['process'].casefold()}" if event["process"] else None)
        if identity and event["timestamp"]:
            keyed.setdefault(identity, []).append(event)

    edges: list[dict[str, Any]] = []
    for identity, group in keyed.items():
        group.sort(key=lambda item: (item["timestamp"], item["record_number"]))
        for left, right in zip(group, group[1:]):
            delta = (datetime.fromisoformat(right["timestamp"]) - datetime.fromisoformat(left["timestamp"])).total_seconds()
            if 0 <= delta <= 300:
                edges.append({
                    "edge_id": stable_id("edge", left["event_id"], right["event_id"]),
                    "from_event": left["event_id"], "to_event": right["event_id"],
                    "relationship": "same_process_within_5_minutes", "process_identity": identity,
                    "seconds_apart": delta,
                    "explanation": "Events share a process identity and are close in time; this is association, not proof of causation.",
                })
    type_counts = Counter(event["event_type"] for event in events)
    process_counts = Counter(event["process"] for event in events if event["process"])
    report = base_report("event_timeline")
    report["source_artifact"] = {"supplied_path": str(file_path), "file_name": path.name, "size_bytes": size}
    report["summary"] = {
        "records_parsed": len(events), "parse_errors": len(errors),
        "events_without_valid_timestamp": sum(not item["timestamp_valid"] for item in events),
        "event_type_counts": dict(sorted(type_counts.items())),
        "top_processes_by_event_count": [{"process": name, "count": count} for name, count in process_counts.most_common(20)],
        "timeline_links": len(edges), "note": "Temporal links are not proof of causal relationships.",
    }
    report["events"] = sorted(events, key=lambda item: (item["timestamp"] is None, item["timestamp"] or "", item["record_number"]))
    report["edges"] = edges
    report["parse_errors"] = errors
    if errors:
        report["findings"].append(Finding(
            title="Input records need review", description="One or more records could not be parsed or were not event objects.",
            severity="info", confidence="high", source=f"event-file:{path.name}", evidence=errors[:20],
            recommendation="Review listed records and export the source log again if possible.",
        ).to_dict())
    missing_time = report["summary"]["events_without_valid_timestamp"]
    if missing_time:
        report["findings"].append(Finding(
            title="Some events lack a usable timestamp",
            description="Events without normalized timestamps cannot be reliably placed on the timeline.",
            severity="info", confidence="high", source=f"event-file:{path.name}", evidence=[f"count={missing_time}"],
            recommendation="Include ISO-8601 timestamps with timezone information in future exports.",
        ).to_dict())
    return report
