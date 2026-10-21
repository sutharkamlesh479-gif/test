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
from .investigation import run_investigation

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_REQUEST_BYTES = 4 * MAX_UPLOAD_BYTES + 1024 * 1024

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURIX OMEGA</title><style>
:root{color-scheme:dark;--bg:#080e0c;--panel:#101a16;--line:#294237;--text:#eef7f1;--muted:#a4b9ad;--green:#75f0ab;--red:#ff7878}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 70% -10%,#173e2d,transparent 45%),var(--bg);color:var(--text);font:15px/1.6 system-ui,Segoe UI,sans-serif}
main{max-width:1100px;margin:auto;padding:32px 18px 60px}.top{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}.brand,.eyebrow{color:var(--green);font-size:.8rem;font-weight:800;letter-spacing:.16em}.hero{padding:25px 0 15px}h1{font-size:clamp(2.4rem,7vw,4.6rem);letter-spacing:-.045em;line-height:1;margin:16px 0}h1 span{color:var(--green)}p{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:14px}.panel{background:linear-gradient(150deg,#13211a,#0e1713);border:1px solid var(--line);border-radius:16px;padding:20px;margin:12px 0}.panel h2{margin-top:0}
label{display:block;font-weight:650;margin:10px 0 6px}input[type=file]{width:100%;border:1px dashed #547564;border-radius:10px;padding:12px;background:#0a120e;color:var(--muted)}
button{background:var(--green);color:#062014;border:0;border-radius:10px;padding:11px 15px;font-weight:800;cursor:pointer;margin-top:12px}button:disabled{opacity:.6;cursor:wait}.hint{font-size:.86rem}.status{min-height:24px;color:var(--green);overflow-wrap:anywhere}.risk{color:var(--red)}
pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:580px;overflow:auto;background:#070b09;border:1px solid var(--line);border-radius:12px;padding:15px;color:#d7eadf}.output{display:none}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px;margin:16px 0}.metric,.viz-panel{background:#09120d;border:1px solid var(--line);border-radius:12px;padding:13px;min-width:0}.metric small{display:block;color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.1em}.metric strong{display:block;color:var(--green);font-size:1.05rem;overflow-wrap:anywhere}.viz-panel{margin:14px 0}.viz-panel h3{margin:0 0 8px}.event-graph{width:100%;height:auto;display:block;overflow:visible}.timeline{padding-left:24px}.timeline li{margin:8px 0;color:var(--muted)}.timeline b{color:var(--text)}.finding-row{padding:12px 0;border-top:1px solid var(--line)}.finding-row strong{color:var(--green)}
footer{border-top:1px solid var(--line);padding-top:16px;margin-top:30px;color:var(--muted);font-size:.85rem}</style></head><body><main>
<header class="top"><div class="brand">AURIX / OMEGA</div><div class="hint">LOCAL-FIRST · EVIDENCE-FOCUSED</div></header>
<section class="hero"><div class="eyebrow">Cyber investigation workbench</div><h1>Observe the evidence.<br><span>Question the verdict.</span></h1>
<p>Inspect files without executing them, normalize exported security events, and compare artifacts. No AI key or external API is required.</p></section>
<div class="grid"><section class="panel"><div class="eyebrow">01 / Artifact</div><h2>Inspect a file</h2><p>SHA-256, format hints, printable strings and review indicators.</p>
<label for="inspectFile">Choose file</label><input id="inspectFile" type="file"><button id="inspectBtn">Inspect safely</button></section>
<section class="panel"><div class="eyebrow">02 / Timeline</div><h2>Analyze events</h2><p>Import JSON/JSONL logs. Time links are not proof of causation.</p>
<label for="eventsFile">Choose JSON / JSONL</label><input id="eventsFile" type="file"><button id="eventsBtn">Build timeline</button></section>
<section class="panel"><div class="eyebrow">03 / Compare</div><h2>Compare two files</h2><p>Review hash, size and printable-string changes.</p>
<label for="beforeFile">Baseline file</label><input id="beforeFile" type="file"><label for="afterFile">Newer file</label><input id="afterFile" type="file"><button id="diffBtn">Compare artifacts</button></section>
<section class="panel"><div class="eyebrow">04 / Case</div><h2>Combined investigation</h2><p>Run a bounded evidence-led workflow across selected inputs in one report.</p>
<label for="caseArtifact">Target artifact (optional)</label><input id="caseArtifact" type="file">
<label for="caseEvents">Event export (optional)</label><input id="caseEvents" type="file" accept=".json,.jsonl,.txt,application/json">
<label for="caseBaseline">Baseline file (requires target)</label><input id="caseBaseline" type="file">
<button id="caseBtn">Investigate selected evidence</button></section></div>
<section class="panel"><div class="eyebrow">Investigation output</div><div id="status" class="status" role="status">Ready. Select a task above.</div>
<div id="output" class="output"><div id="visual"></div><details><summary>Raw JSON evidence</summary><pre id="result"></pre></details><button id="downloadBtn">Download JSON report</button></div>
<p class="hint">OMEGA treats selected files as data and never launches them. Review indicators are not malware verdicts. Maximum upload: 12 MiB per file.</p></section>
<footer>Loopback only. Stop the server with Ctrl+C. Created by Kamlesh Suthar.</footer></main>
<script>(function(){"use strict";var statusEl=document.getElementById("status"),out=document.getElementById("output"),result=document.getElementById("result"),last=null;
function status(t,bad){statusEl.textContent=t;statusEl.className=bad?"status risk":"status";}
function fileData(file){return new Promise(function(resolve,reject){if(!file){reject(new Error("Choose all required file(s) first."));return;}if(file.size>12*1024*1024){reject(new Error("Dashboard upload limit is 12 MiB per file."));return;}
var r=new FileReader();r.onerror=function(){reject(new Error("Could not read selected file."));};r.onload=function(){var v=String(r.result);resolve({filename:file.name,data_base64:v.slice(v.indexOf(",")+1)});};r.readAsDataURL(file);});}
function optionalFileData(file){return file?fileData(file):Promise.resolve(null);}
async function post(route,payload){var r=await fetch(route,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});var d=await r.json();if(!r.ok)throw new Error(d.error||"Request failed.");return d;}
function make(tag,cls,text){var n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n;}
function metric(parent,label,value){var card=make("div","metric"),small=make("small","",label),strong=make("strong","",value);card.appendChild(small);card.appendChild(strong);parent.appendChild(card);}
function show(data){
 last=data;result.textContent=JSON.stringify(data,null,2);out.style.display="block";
 var visual=document.getElementById("visual");visual.replaceChildren();
 var metrics=make("div","metrics");
 var artifactData=data.artifact||(data.analyses&&data.analyses.target_artifact&&data.analyses.target_artifact.artifact);
 var eventData=(data.analyses&&data.analyses.event_timeline)?data.analyses.event_timeline:data;
 var diffReport=(data.analyses&&data.analyses.baseline_comparison)?data.analyses.baseline_comparison:data;
 var diffData=diffReport.diff||data.diff;
 if(artifactData){metric(metrics,"SHA-256",String(artifactData.sha256||"").slice(0,18)+"…");metric(metrics,"Size",String(artifactData.size_bytes||0)+" bytes");metric(metrics,"Format",artifactData.detected_type||"Unknown");metric(metrics,"Strings",artifactData.printable_string_count||0);}
 if(data.summary){if(data.summary.steps_completed!==undefined)metric(metrics,"Steps completed",data.summary.steps_completed);if(data.summary.findings_count!==undefined)metric(metrics,"Findings",data.summary.findings_count);if(data.summary.evidence_items!==undefined)metric(metrics,"Evidence items",data.summary.evidence_items);if(data.summary.records_parsed!==undefined)metric(metrics,"Events",data.summary.records_parsed);if(data.summary.timeline_links!==undefined)metric(metrics,"Timeline links",data.summary.timeline_links);if(data.summary.parse_errors!==undefined)metric(metrics,"Parse issues",data.summary.parse_errors);if(data.summary.result!==undefined)metric(metrics,"Static result",data.summary.result);}
 if(diffData){metric(metrics,"Identical bytes",diffData.identical_sha256?"Yes":"No");metric(metrics,"Size delta",String(diffData.size_delta_bytes)+" bytes");metric(metrics,"Added strings",(diffData.added_printable_strings||[]).length);metric(metrics,"Removed strings",(diffData.removed_printable_strings||[]).length);}
 if(metrics.childElementCount)visual.appendChild(metrics);
 if(Array.isArray(data.findings)&&data.findings.length){var box=make("section","viz-panel");box.appendChild(make("h3","","Findings to review"));data.findings.slice(0,50).forEach(function(f){var row=make("div","finding-row"),head=make("strong","",String(f.severity||"info").toUpperCase()+" · "+(f.title||"Observation")),desc=make("p","",f.description||""),evidence=make("p","hint","Evidence: "+JSON.stringify(f.evidence||[]));row.appendChild(head);row.appendChild(desc);row.appendChild(evidence);box.appendChild(row);});visual.appendChild(box);}
 if(Array.isArray(eventData.events)&&eventData.events.length){
   var box=make("section","viz-panel");box.appendChild(make("h3","","Observed event relationships"));box.appendChild(make("p","hint","Edges indicate temporal association only—not causation. Graph shows at most 20 events."));
   var shown=eventData.events.slice(0,20),coords=new Map(),ns="http://www.w3.org/2000/svg",rows=Math.ceil(shown.length/4),height=Math.max(100,rows*68+24),svg=document.createElementNS(ns,"svg");
   svg.setAttribute("viewBox","0 0 720 "+height);svg.setAttribute("role","img");svg.setAttribute("aria-label","Event relationship graph");svg.classList.add("event-graph");
   shown.forEach(function(e,i){coords.set(e.event_id,{x:45+(i%4)*180,y:30+Math.floor(i/4)*68});});
   (eventData.edges||[]).forEach(function(edge){var a=coords.get(edge.from_event),b=coords.get(edge.to_event);if(!a||!b)return;var line=document.createElementNS(ns,"line");line.setAttribute("x1",a.x);line.setAttribute("y1",a.y);line.setAttribute("x2",b.x);line.setAttribute("y2",b.y);line.setAttribute("stroke","#527766");line.setAttribute("stroke-width","2");svg.appendChild(line);});
   shown.forEach(function(e){var c=coords.get(e.event_id),circle=document.createElementNS(ns,"circle");circle.setAttribute("cx",c.x);circle.setAttribute("cy",c.y);circle.setAttribute("r","7");circle.setAttribute("fill","#75f0ab");svg.appendChild(circle);var label=document.createElementNS(ns,"text");label.setAttribute("x",c.x+10);label.setAttribute("y",c.y+4);label.setAttribute("fill","#eaf5ee");label.setAttribute("font-size","11");label.textContent=String(e.event_type||"event").slice(0,22);svg.appendChild(label);});
   box.appendChild(svg);box.appendChild(make("h3","","Chronological timeline"));var list=make("ol","timeline");list.start=1;
   shown.forEach(function(e){var item=make("li","");item.textContent=(e.timestamp||"time unknown")+" · "+(e.event_type||"event")+" · "+(e.process||"unknown process")+" · PID "+(e.pid===null||e.pid===undefined?"?":e.pid);list.appendChild(item);});
   box.appendChild(list);visual.appendChild(box);
 }
 if(diffData){var box=make("section","viz-panel");box.appendChild(make("h3","","Build comparison"));box.appendChild(make("p","","Added printable strings: "+JSON.stringify(diffData.added_printable_strings||[])));box.appendChild(make("p","","Removed printable strings: "+JSON.stringify(diffData.removed_printable_strings||[])));visual.appendChild(box);}
}
async function run(id,fn){var b=document.getElementById(id);b.disabled=true;status("Analyzing locally…",false);try{show(await fn());status("Analysis finished. Review evidence before conclusions.",false);}catch(e){status(e.message||"Unexpected error.",true);}finally{b.disabled=false;}}
document.getElementById("inspectBtn").onclick=function(){run("inspectBtn",async function(){return post("/api/inspect",await fileData(document.getElementById("inspectFile").files[0]));});};
document.getElementById("eventsBtn").onclick=function(){run("eventsBtn",async function(){return post("/api/events",await fileData(document.getElementById("eventsFile").files[0]));});};
document.getElementById("diffBtn").onclick=function(){run("diffBtn",async function(){var a=await fileData(document.getElementById("beforeFile").files[0]),b=await fileData(document.getElementById("afterFile").files[0]);return post("/api/diff",{before:a,after:b});});};
document.getElementById("caseBtn").onclick=function(){run("caseBtn",async function(){var artifact=await optionalFileData(document.getElementById("caseArtifact").files[0]);var events=await optionalFileData(document.getElementById("caseEvents").files[0]);var baseline=await optionalFileData(document.getElementById("caseBaseline").files[0]);if(!artifact&&!events)throw new Error("Select at least a target artifact or event export.");if(baseline&&!artifact)throw new Error("A baseline requires a target artifact.");return post("/api/investigate",{artifact:artifact,events:events,baseline:baseline});});};
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
        if route not in {"/api/inspect", "/api/events", "/api/diff", "/api/investigate"}:
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
            if route == "/api/investigate":
                with tempfile.TemporaryDirectory(prefix="aurix-omega-case-") as folder:
                    def save_optional(field: str, safe_name: str):
                        upload = payload.get(field)
                        if upload is None:
                            return None
                        filename, data = _decode_upload(upload)
                        path = Path(folder) / (safe_name + Path(filename).suffix[:16])
                        path.write_bytes(data)
                        return path
                    artifact_path = save_optional("artifact", "target")
                    events_path = save_optional("events", "events")
                    baseline_path = save_optional("baseline", "baseline")
                    report = run_investigation(artifact_path, events_path, baseline_path)
            elif route == "/api/inspect":
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
