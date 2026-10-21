# Architecture

## Design principles

1. Local-first core with no required external service.
2. Inspected artifacts are treated as bytes and are never executed.
3. Findings describe evidence and limits rather than asserting certainty.
4. Input sizes and expensive parsing paths are bounded.
5. Reports escape untrusted text.

## Modules

- `analyzers.py`: SHA-256, file-format hints, bounded printable-string extraction, conservative indicators, partial PE metadata parsing.
- `events.py`: JSON/JSONL ingestion, timestamp normalization, parse-error reporting, summaries, and nearby-event links for shared process identity.
- `models.py`: structured findings, stable identifiers, and report metadata.
- `report.py`: self-contained HTML rendering and JSON report compatibility.
- `web.py`: standard-library HTTP server bound to 127.0.0.1, upload validation, request limits, security headers, and browser UI.
- `cli.py`: command-line interface.

## Evidence model

A finding includes title, description, severity, confidence, source, evidence, and recommendation. Severity estimates possible impact if the concern is real. Confidence describes how strongly current evidence supports the finding.

Event links identify events sharing a process identity within five minutes. They are temporal associations, not proof of cause.

## Current limits

PE support covers basic header and section-table metadata only. OMEGA does not currently disassemble code, resolve all imports, reconstruct original source, execute samples, or collect OS telemetry on its own.
