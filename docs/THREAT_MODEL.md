# Threat Model

## Assets
- The analyst's computer and selected files.
- The integrity of imported evidence and generated reports.
- The local dashboard process.

## Untrusted inputs
- Arbitrary binary files, including malformed PE candidates.
- JSON and JSONL records with deceptive fields, malformed timestamps, or oversized content.
- Filenames, process names, source labels, event details, and report text.
- Requests sent to the local dashboard.

## Implemented controls
- Artifacts are read as data and are never launched.
- SHA-256 is computed in chunks; printable-string scanning is capped at 64 MiB.
- Event logs are capped at 20 MiB and 50,000 records.
- PE parsing checks offsets and limits section parsing.
- The dashboard binds to 127.0.0.1, bounds request and upload sizes, normalizes paths, and adds security headers.
- HTML reports escape imported content and load no external assets.
- String matches are low-confidence review signals, not malware verdicts.

## Known limitations
- This tool is not designed for a hostile multi-user environment.
- Other software on the same computer may be able to connect to loopback services; stop the dashboard when it is not needed.
- Event timestamps and process IDs can be forged in exported logs.
- Hashes identify bytes but do not prove origin or safety.
- OMEGA does not sandbox samples or provide dynamic telemetry in this version.

## Requirements for future extensions
Dynamic analysis must be opt-in, isolated, documented, and tested with synthetic inputs. Network assessments must require explicit authorization and must not silently expand scope to unrelated hosts.
