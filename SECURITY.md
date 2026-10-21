# Security Policy

## Scope and reporting

Please report vulnerabilities in OMEGA itself, including unsafe parsing, report injection, local dashboard exposure, or accidental execution of inspected files. Use GitHub's private vulnerability reporting feature if enabled. Otherwise open a minimal issue asking for a private reporting channel; do not attach confidential logs, credentials, personal data, or real malware samples.

Include the affected commit/version, impact, reproducible steps, operating system, Python version, and a synthetic proof of concept where possible.

## Safety commitments

- Inspected files are read as data; the core never launches them.
- The dashboard binds to 127.0.0.1 and caps request and upload sizes.
- Reports escape untrusted text and load no external scripts.
- Findings distinguish observations from hypotheses; string matches are not verdicts.
- Exploitation, credential theft, persistence, and remote-target attack features are outside project scope.

Please allow reasonable time to investigate before public disclosure.
