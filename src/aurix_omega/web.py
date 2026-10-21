"""Loopback-only, dependency-free dashboard."""
from __future__ import annotations

import base64
import binascii
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import urlparse, urlsplit

from .analyzers import analyze_file, compare_files
from .events import analyze_events

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_REQUEST_BYTES = 2 * MAX_UPLOAD_BYTES + 1024 * 1024

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURIX OMEGA</title><style>
:root{color-scheme:dark;--bg:#080e0c;--panel:#101a16;--line:#294237;--text:#eef7f1;--muted:#a4b9ad;--green:#75f0ab;--red:#ff7878}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 70% -10%,#173e2d,transparent 45%),var(--bg);color:var(--text);font:15px/1.6 system-ui,Segoe UI,sans-serif}
main{max-width:1100px;margin:auto;padding:32px 18px 60px}.top{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}.brand,.eyebrow{color:var(--green);font-size:.8rem;font-weight:800;letter-spacing:.16em}.hero{padding:25px 0 15px}h1{font-size:clamp(2.4rem,7vw,4.6rem);letter-spacing:-.045em;line-height:1;margin:16px 0}h1 span{color:var(--green)}p{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:14px}.panel{background:linear-gradient(150deg,#13211a,#0e1713);border:1px solid var(--line);border-radius:16px;padding:20px;margin:12px 0}.panel h2{margin-top:0}
label{display:block;font-weight:650;margin:10px 0 6px}input[type=file]{width:100%;border:1px dashed #547564;border-radius:10px;padding:12px;background:#0a120e;color:var(--muted)}
button{background:var(--green);color:#062014;border:0;border-radius:10px;padding:11px 15px;font-weight:800;cursor:pointer;margin-top:12px}button:disabled{opacity:.6;cursor:wait}.hint{font-size:.86rem}.status{min-height:24px;color:var(--green);overflow-wrap:anywhere}.risk{color:var(--red)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:580px;overflow:auto;background:#070b09;border:1px solid var(--line);border-radius:12px;padding:15px;color:#d7eadf}.output{display:none}
footer{border-top:1px solid var(--line);padding-top:16px;margin-top:30px;color:var(--muted);font-size:.85rem}</style></head><body><main>
<header class="top"><div class="brand">AURIX / OMEGA</div><div class="hint">LOCAL-FIRST · EVIDENCE-FOCUSED</div></header>
<section class="hero"><div class="eyebrow">Cyber investigation workbench</div><h1>Observe the evidence.<br><span>Question the verdict.</span></h1>
<p>Inspect files without executing them, normalize exported security events, and compare artifacts. No AI key or external API is required.</p></section>
<div class="grid"><section class="panel"><div class="eyebrow">01 / Artifact</div><h2>Inspect a file</h2><p>SHA-256, format hints, printable strings and review indicators.</p>
<label for="inspectFile">Choose file</label><input id="inspectFile" type="file"><button id="inspectBtn">Inspect safely</button></section>
<section class="panel"><div class="eyebrow">02 / Timeline</div><h2>Analyze events</h2><p>Import JSON/JSONL logs. Time links are not proof of causation.</p>
<label for="eventsFile">Choose JSON / JSONL</label><input id="eventsFile" type="file"><button id="eventsBtn">Build timeline</button></section>
<section class="panel"><div class="eyebrow">03 / Compare</div><h2>Compare two files</h2><p>Review hash, size and printable-string changes.</p>
<label for="beforeFile">Baseline file</label><input id="beforeFile" type="file"><label for="afterFile">Newer file</label><input id="afterFile" type="file"><button id="diffBtn">Compare artifacts</button></section></div>
<section class="panel"><div class="eyebrow">Investigation output</div><div id="status" class="status" role="status">Ready. Select a task above.</div>
<div id="output" class="output"><pre id="result"></pre><button id="downloadBtn">Download JSON report</button></div>
<p class="hint">OMEGA treats selected files as data and never launches them. Review indicators are not malware verdicts. Maximum upload: 12 MiB per file.</p></section>
<footer>Loopback only. Stop the server with Ctrl+C. Created by Kamlesh Suthar.</footer></main>
<script>(function(){"use strict";var statusEl=document.getElementById("status"),out=document.getElementById("output"),result=document.getElementById("result"),last=null;
function status(t,bad){statusEl.textContent=t;statusEl.className=bad?"status risk":"status";}
function fileData(file){return new Promise(function(resolve,reject){if(!file){reject(new Error("Choose all required file(s) first."));return;}if(file.size>12*1024*1024){reject(new Error("Dashboard upload limit is 12 MiB per file."));return;}
var r=new FileReader();r.onerror=function(){reject(new Error("Could not read selected file."));};r.onload=function(){var v=String(r.result);resolve({filename:file.name,data_base64:v.slice(v.indexOf(",")+1)});};r.readAsDataURL(file);});}
async function post(route,payload){var r=await fetch(route,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});var d=await r.json();if(!r.ok)throw new Error(d.error||"Request failed.");return d;}
function show(data){last=data;result.textContent=JSON.stringify(data,null,2);out.style.display="block";}
async function run(id,fn){var b=document.getElementById(id);b.disabled=true;status("Analyzing locally…",false);try{show(await fn());status("Analysis finished. Review evidence before conclusions.",false);}catch(e){status(e.message||"Unexpected error.",true);}finally{b.disabled=false;}}
document.getElementById("inspectBtn").onclick=function(){run("inspectBtn",async function(){return post("/api/inspect",await fileData(document.getElementById("inspectFile").files[0]));});};
document.getElementById("eventsBtn").onclick=function(){run("eventsBtn",async function(){return post("/api/events",await fileData(document.getElementById("eventsFile").files[0]));});};
document.getElementById("diffBtn").onclick=function(){run("diffBtn",async function(){var a=await fileData(document.getElementById("beforeFile").files[0]),b=await fileData(document.getElementById("afterFile").files[0]);return post("/api/diff",{before:a,after:b});});};
document.getElementById("downloadBtn").onclick=function(){if(!last)return;var blob=new Blob([JSON.stringify(last,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="aurix-omega-report.json";a.click();URL.revokeObjectURL(url);};
})();</script></body></html>"""


def _decode_upload(value: Any) -> tuple[str, bytes]:
    if not isinstance(value, dict):
        raise ValueError("Upload must include filename and data_base64.")
    filename = Path(str(value.get("filename") or "upload.bin")).name
    encoded = value.get("data_base64")
    if not isinstance(encoded, str):
        raise ValueError("data_base64 must be a string.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Uploaded file is not valid Base64 data.") from exc
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File exceeds the {MAX_UPLOAD_BYTES}-byte upload limit.")
    return filename, data


def _temporary_analysis(filename: str, data: bytes, analyzer):
    suffix = Path(filename).suffix[:16]
    with tempfile.TemporaryDirectory(prefix="aurix-omega-") as folder:
        path = Path(folder) / ("artifact" + suffix)
        path.write_bytes(data)
        return analyzer(path)


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "AURIX-OMEGA"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:
        print("OMEGA dashboard: " + (format % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, value: dict[str, Any]) -> None:
        self._send(code, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_allowed(self) -> bool:
        """Reject DNS-rebinding-style hostnames and non-loopback Host values."""
        try:
            parsed = urlsplit("//" + self.headers.get("Host", ""))
            return parsed.hostname in {"127.0.0.1", "localhost"} and parsed.port == self.server.server_port
        except ValueError:
            return False

    def _origin_allowed(self) -> bool:
        """If supplied, Origin must match this exact local host and port."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed_origin = urlsplit(origin)
            parsed_host = urlsplit("//" + self.headers.get("Host", ""))
            return (
                parsed_origin.scheme == "http"
                and parsed_origin.username is None
                and parsed_origin.password is None
                and parsed_origin.hostname in {"127.0.0.1", "localhost"}
                and parsed_origin.hostname == parsed_host.hostname
                and parsed_origin.port == self.server.server_port
                and parsed_host.port == self.server.server_port
            )
        except ValueError:
            return False

    def _guard_request(self) -> bool:
        if not self._host_allowed():
            self._json(421, {"error": "This local dashboard only accepts localhost Host headers."})
            return False
        if not self._origin_allowed():
            self._json(403, {"error": "Cross-origin requests are not accepted."})
            return False
        return True

    def do_GET(self) -> None:
        if not self._guard_request():
            return
        route = urlparse(self.path).path
        if route == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif route == "/health":
            self._json(200, {"ok": True, "application": "AURIX OMEGA"})
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if not self._guard_request():
            return
        route = urlparse(self.path).path
        if route not in {"/api/inspect", "/api/events", "/api/diff"}:
            self._json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Invalid Content-Length"})
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self._json(413, {"error": "Request body is empty or too large."})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request JSON must be an object.")
            if route == "/api/inspect":
                filename, data = _decode_upload(payload)
                report = _temporary_analysis(filename, data, analyze_file)
            elif route == "/api/events":
                filename, data = _decode_upload(payload)
                report = _temporary_analysis(filename, data, analyze_events)
            else:
                name_a, data_a = _decode_upload(payload.get("before"))
                name_b, data_b = _decode_upload(payload.get("after"))
                with tempfile.TemporaryDirectory(prefix="aurix-omega-diff-") as folder:
                    path_a = Path(folder) / ("before" + Path(name_a).suffix[:16])
                    path_b = Path(folder) / ("after" + Path(name_b).suffix[:16])
                    path_a.write_bytes(data_a)
                    path_b.write_bytes(data_b)
                    report = compare_files(path_a, path_b)
            self._json(200, report)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, OSError) as exc:
            self._json(400, {"error": str(exc)})


def serve(port: int = 8765) -> None:
    """Run server on loopback only; do not expose it to a LAN."""
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    print(f"AURIX OMEGA: http://127.0.0.1:{port}")
    print("Loopback-only server. Stop with Ctrl+C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AURIX OMEGA.")
    finally:
        server.server_close()
