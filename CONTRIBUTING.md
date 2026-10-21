# Contributing to AURIX OMEGA

Thanks for helping improve OMEGA.

## Before a pull request
1. Open an issue for substantial behavior changes.
2. Keep analysis read-only and evidence-focused.
3. Add tests for new parsers, report fields, and error paths.
4. Use synthetic test fixtures only; do not commit private logs, credentials, personal data, or real malware samples.
5. Document limits and false-positive possibilities.

## Local checks
    python -m pip install -e ".[dev]"
    python -m compileall -q src tests
    python -m pytest

## Code expectations
- Prefer the Python standard library for core functionality.
- Validate imported data and cap expensive processing.
- Never execute a file being inspected.
- Keep observations, hypotheses, severity, and confidence distinct.
- Do not describe time correlation as proof of causation.
- Avoid network calls and telemetry by default.
