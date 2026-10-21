# AURIX OMEGA

**Evidence-first cyber investigation and reverse-engineering workbench.**

OMEGA is a local-first Python toolkit for inspecting artifacts without executing them, analyzing exported security events, comparing builds, correlating timelines, and generating portable reports.

> OMEGA is an investigation aid, not an antivirus verdict. A lack of findings does not prove that a file or computer is safe.

## Features

- SHA-256 fingerprints, file-format hints, bounded printable strings, and basic PE header metadata.
- Conservative static review heuristics, labelled as low-confidence signals.
- JSON and JSONL event ingestion, timestamp normalization, parse-error reporting, and cautious temporal links.
- File comparison using hashes, sizes, format hints, and printable strings.
- Structured JSON and self-contained HTML reports that escape untrusted content.
- Local browser dashboard bound to 127.0.0.1; no API key or external runtime service required.
- Python tests and GitHub Actions CI.

## Requirements and install

Python 3.11+; Windows, Linux, or macOS.

Windows PowerShell:

    py -3.11 -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -e ".[dev]"
    omega --help

Linux/macOS:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -e ".[dev]"
    omega --help

## Try it

Inspect a file as data; it is never executed:

    omega inspect path/to/sample.bin --output reports/inspection.json

Analyze synthetic or authorized JSON/JSONL event exports:

    omega events examples/sample_events.jsonl --output reports/timeline.json

Compare two builds without launching either:

    omega diff build-old.exe build-new.exe --output reports/diff.json

Export an existing JSON report as HTML:

    omega report reports/timeline.json --html reports/timeline.html

Start the local dashboard:

    omega serve

Then open http://127.0.0.1:8765. The browser dashboard accepts files up to 12 MiB each. It uploads to the OMEGA server on the same computer, bound to loopback only. Stop it with Ctrl+C.

## Event format

OMEGA accepts a JSON array, an object with an events array, a single event object, or JSONL (one JSON object per line). Useful fields include timestamp/time, event_type/type, process/process_name/image, pid, parent_pid, and source. The included example is synthetic.

    {"timestamp":"2026-01-02T10:11:12Z","event_type":"process_start","process":"demo.exe","pid":120,"source":"synthetic-lab"}
    {"timestamp":"2026-01-02T10:11:14Z","event_type":"file_created","process":"demo.exe","pid":120,"source":"synthetic-lab"}

## Understand the output

- **Severity** estimates impact if a concern is real.
- **Confidence** describes how strongly evidence supports the observation.
- A printable string or API reference may be legitimate; it is not a malware verdict.
- Timeline links indicate temporal association, not proof of causation.
- “No configured heuristic matched” does not prove a file is safe.

## Project structure

    src/aurix_omega/   analysis engine, CLI, local browser dashboard
    tests/             automated unit tests
    examples/          synthetic event evidence
    .github/workflows/ continuous integration

## Development

    python -m pip install -e ".[dev]"
    python -m compileall -q src tests
    python -m pytest

## Safety boundaries

Analyze only files and logs you own or are authorized to inspect. The core opens artifacts as data and does not launch them. OMEGA is not a complete malware sandbox, antivirus, decompiler, or guarantee that a system is clean. Imported records can be misleading or forged. Dynamic analysis is out of scope for this initial version.

See [SECURITY.md](SECURITY.md) for reporting and safe-use notes.

## Roadmap

- [x] Static fingerprinting, strings, basic PE header parser
- [x] JSON/JSONL event normalization and cautious timeline links
- [x] Build comparison, JSON/HTML report, localhost dashboard
- [x] Tests and CI
- [ ] Optional platform-specific telemetry adapters
- [ ] Interactive evidence graph and timeline UI
- [ ] Integrity-checked portable investigation bundles
- [ ] Optional AI summaries with source citations

Unchecked items are future work, not existing functionality.

MIT License. Created by Kamlesh Suthar.
