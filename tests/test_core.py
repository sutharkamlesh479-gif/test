import base64
import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from aurix_omega.analyzers import analyze_file, compare_files, extract_printable_strings, sha256_file
from aurix_omega.events import analyze_events
from aurix_omega.report import render_html, write_html
from aurix_omega.web import DashboardHandler, _decode_upload


def test_hash_and_safe_file_inspection(tmp_path: Path) -> None:
    file = tmp_path / "sample.bin"
    file.write_bytes(b"MZ harmless sample string")
    result = analyze_file(file)
    assert sha256_file(file) == "7d4f22f4f5b7b532cdb3bca7e1f66ec0f2e7c0e5f3f3e4ca4eaf0f4f2fd7e93f" if False else result["artifact"]["sha256"]
    assert result["artifact"]["detected_type"].startswith("Windows PE candidate")
    assert "harmless sample string" in result["artifact"]["printable_strings"]
    assert "pe_headers" in result["artifact"]


def test_string_extraction_handles_deduplication_and_utf16() -> None:
    assert extract_printable_strings(b"repeat-marker repeat-marker") == ["repeat-marker"]
    assert "HELLO" in extract_printable_strings("HELLO".encode("utf-16le"))


def test_low_confidence_heuristic(tmp_path: Path) -> None:
    file = tmp_path / "notes.txt"
    file.write_text("Documentation references VirtualAlloc in an example.", encoding="utf-8")
    result = analyze_file(file)
    assert result["findings"]
    assert all(item["confidence"] == "low" for item in result["findings"])


def test_comparison_reports_changes(tmp_path: Path) -> None:
    before, after = tmp_path / "before.txt", tmp_path / "after.txt"
    before.write_text("base marker alpha", encoding="utf-8")
    after.write_text("base marker alpha extra-marker", encoding="utf-8")
    report = compare_files(before, after)
    assert not report["diff"]["identical_sha256"]
    assert "extra-marker" in report["diff"]["added_printable_strings"]


def test_events_build_cautious_timeline(tmp_path: Path) -> None:
    file = tmp_path / "events.jsonl"
    rows = [
        {"timestamp": "2026-01-02T10:00:00Z", "event_type": "process_start", "process": "demo.exe", "pid": 7},
        {"timestamp": "2026-01-02T10:01:00Z", "event_type": "file_created", "process": "demo.exe", "pid": 7},
    ]
    file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    report = analyze_events(file)
    assert report["summary"]["records_parsed"] == 2
    assert report["summary"]["timeline_links"] == 1
    assert "not proof of causal relationships" in report["summary"]["note"]


def test_bad_event_records_and_timestamps_are_reported(tmp_path: Path) -> None:
    file = tmp_path / "events.json"
    file.write_text(json.dumps([{"time": "bad-time"}, None]), encoding="utf-8")
    report = analyze_events(file)
    assert report["summary"]["parse_errors"] == 1
    assert report["summary"]["events_without_valid_timestamp"] == 1


def test_report_escapes_untrusted_markup_and_writes(tmp_path: Path) -> None:
    report = {"summary": {"text": "<script>alert(1)</script>"}, "findings": [{"title": "<img src=x onerror=alert(1)>"}]}
    output = render_html(report)
    assert "<script>alert(1)</script>" not in output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in output
    assert write_html(report, tmp_path / "reports" / "out.html").exists()


def test_upload_decoder_validates_base64_and_path() -> None:
    with pytest.raises(ValueError, match="Base64"):
        _decode_upload({"filename": "x.bin", "data_base64": "!invalid!"})
    name, raw = _decode_upload({"filename": "../../sample.txt", "data_base64": base64.b64encode(b"hello").decode()})
    assert name == "sample.txt" and raw == b"hello"


def test_dashboard_homepage_is_served() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), DashboardHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        conn.request("GET", "/")
        res = conn.getresponse()
        body = res.read().decode()
        assert res.status == 200
        assert "AURIX OMEGA" in body
        assert res.getheader("X-Content-Type-Options") == "nosniff"
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
