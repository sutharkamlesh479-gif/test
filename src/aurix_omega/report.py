"""Generate self-contained HTML reports and escape imported content."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def render_html(report: dict[str, Any]) -> str:
    title = html.escape(str(report.get("tool", "AURIX OMEGA")) + " — Investigation Report")
    findings = report.get("findings", [])
    metadata = {key: report.get(key) for key in ("schema_version", "tool", "tool_version", "analysis_type", "generated_at") if key in report}
    meta = html.escape(json.dumps(metadata, indent=2, ensure_ascii=False))
    summary = html.escape(json.dumps(report.get("summary", {}), indent=2, ensure_ascii=False))
    cards: list[str] = []
    for item in findings if isinstance(findings, list) else []:
        if not isinstance(item, dict):
            continue
        fields = {key: html.escape(str(item.get(key, default))) for key, default in (
            ("severity", "info"), ("confidence", "unknown"), ("source", "unknown"),
            ("title", "Untitled finding"), ("description", ""), ("recommendation", ""))}
        evidence = html.escape(json.dumps(item.get("evidence", []), indent=2, ensure_ascii=False))
        cards.append('<article class="finding"><div class="meta"><b>' + fields["severity"] +
            '</b><span>confidence: ' + fields["confidence"] + '</span><span>source: ' + fields["source"] +
            '</span></div><h3>' + fields["title"] + '</h3><p>' + fields["description"] +
            '</p><h4>Evidence</h4><pre>' + evidence + '</pre><h4>Next step</h4><p>' +
            fields["recommendation"] + '</p></article>')
    finding_html = "\n".join(cards) or "<p>No findings were recorded. This does not prove safety.</p>"
    raw = html.escape(json.dumps(report, indent=2, ensure_ascii=False))
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>""" + title + """</title>
<style>:root{color-scheme:dark;--bg:#0b1110;--panel:#121c19;--line:#263d34;--fg:#e9f3ee;--muted:#a4b8ae;--accent:#67e5a5}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,sans-serif}
main{max-width:1050px;margin:auto;padding:32px 18px 60px}h1{font-size:clamp(2rem,4vw,3rem)}p,.muted{color:var(--muted)}
.panel,.finding{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;margin:14px 0}
.meta{display:flex;flex-wrap:wrap;gap:10px;color:var(--muted);font-size:.85rem}.meta b{color:var(--accent);text-transform:uppercase}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#080d0c;border:1px solid var(--line);border-radius:10px;padding:14px;max-height:520px;overflow:auto}
footer{border-top:1px solid var(--line);margin-top:36px;padding-top:18px;color:var(--muted);font-size:.9rem}</style></head>
<body><main><p class="muted">AURIX OMEGA · Evidence-first security triage</p><h1>""" + title + """</h1>
<p>Review evidence and limitations before drawing conclusions. A finding is not a verdict of compromise.</p>
<section class="panel"><h2>Report metadata</h2><pre>""" + meta + """</pre></section>
<section class="panel"><h2>Summary</h2><pre>""" + summary + """</pre></section>
<section><h2>Findings (""" + str(len(findings) if isinstance(findings, list) else 0) + """)</h2>""" + finding_html + """</section>
<details><summary>Full structured report</summary><pre>""" + raw + """</pre></details>
<footer>Generated locally by AURIX OMEGA. No external scripts or tracking assets.</footer></main></body></html>"""


def write_html(report: dict[str, Any], destination: str | Path) -> Path:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(report), encoding="utf-8")
    return target
