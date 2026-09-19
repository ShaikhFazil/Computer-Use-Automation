"""
Operator console + catalog API + human-in-the-loop handoff (FastAPI/uvicorn).

Two jobs:
  1. Agent-facing capability catalog: list/inspect/invoke saved capabilities.
  2. Human-in-the-loop handoff over ONE live browser session.

Concurrency model (documented, deliberate):
  Playwright's sync session has thread affinity, so ALL page interaction — the
  agent's replay steps AND the human's manual actions — happen on a single
  "live session" worker thread. HTTP handlers never touch the page directly;
  they enqueue operator commands and read state. While the agent is paused for a
  human, the engine's wait loop PUMPS that queue, so the operator's clicks/types
  execute on the exact same page the agent was stuck on. On resume, the agent
  continues from wherever the human left the session.

This is a minimal but real control-transfer seam. A full co-browsing UI is out
of scope; the operator console here is intentionally a thin page.
"""
from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from cua.catalog import Catalog
from cua.config import settings
from cua.escalation import STORE, Controller, HumanAction, SessionStatus
from cua.replay import ReplayEngine
from cua.schema import ElementTarget, Locator, LocatorStrategy
from cua.surface import WebSurface

app = FastAPI(title="CUA Operator Console & Catalog")
catalog = Catalog()

# One live session (single active handoff at a time in this take-home).
LIVE: dict[str, Any] = {"surface": None, "queue": queue.Queue(), "thread": None,
                        "result": None, "run_id": None}


def _pump() -> None:
    surface: Optional[WebSurface] = LIVE["surface"]
    if surface is None:
        return
    try:
        cmd = LIVE["queue"].get_nowait()
    except queue.Empty:
        return
    kind = cmd.get("kind")
    try:
        if kind == "click":
            surface.click(_target(cmd["name"]))
            STORE.session.record_human_action(HumanAction(kind="click", detail=cmd["name"]))
        elif kind == "type":
            surface.type_text(_target(cmd["name"]), cmd.get("text", ""))
            STORE.session.record_human_action(HumanAction(kind="type",
                detail=f"{cmd['name']}=«redacted»"))
        elif kind == "navigate":
            surface.navigate(cmd["url"])
            STORE.session.record_human_action(HumanAction(kind="navigate", detail=cmd["url"]))
        elif kind == "note":
            STORE.session.record_human_action(HumanAction(kind="note", detail=cmd.get("detail", "")))
    except Exception as exc:  # a failed manual action shouldn't kill the worker
        STORE.session.record_human_action(HumanAction(kind="error", detail=str(exc)))


def _target(name: str) -> ElementTarget:
    return ElementTarget(description=name, locators=[
        Locator(strategy=LocatorStrategy.ROLE_NAME, value=name, role="button"),
        Locator(strategy=LocatorStrategy.TEXT, value=name),
        Locator(strategy=LocatorStrategy.LABEL, value=name),
    ])


# --------------------------------------------------------------------------- #
# Catalog API (agent-facing)
# --------------------------------------------------------------------------- #
@app.get("/api/capabilities")
def list_capabilities():
    return catalog.list()


@app.get("/api/capabilities/{name}")
def get_capability(name: str):
    try:
        return catalog.load(name).model_dump(mode="json")
    except FileNotFoundError:
        raise HTTPException(404, f"No capability '{name}'")


class InvokeBody(BaseModel):
    params: dict[str, Any] = {}
    tenant: Optional[str] = None


@app.post("/api/capabilities/{name}/invoke")
def invoke_capability(name: str, body: InvokeBody):
    """Headless invocation — the production path an agent triggers."""
    try:
        result = catalog.invoke(name, body.params, tenant=body.tenant)
    except FileNotFoundError:
        raise HTTPException(404, f"No capability '{name}'")
    return result.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# Handoff: start a run with a live (headful) session an operator can take over
# --------------------------------------------------------------------------- #
class HandoffBody(BaseModel):
    name: str
    params: dict[str, Any] = {}
    tenant: Optional[str] = None


@app.post("/api/runs/handoff")
def start_handoff_run(body: HandoffBody):
    if LIVE["thread"] and LIVE["thread"].is_alive():
        raise HTTPException(409, "A live session is already running.")
    art = catalog.load(body.name)

    def worker():
        surface = WebSurface(headless=False)  # headful so a human can see/act
        LIVE["surface"] = surface
        engine = ReplayEngine(surface=surface, interactive=True, pump=_pump)
        try:
            LIVE["result"] = engine.replay(art, body.params, tenant=body.tenant)
        finally:
            surface.close()
            LIVE["surface"] = None
            STORE.session.finish()

    t = threading.Thread(target=worker, daemon=True)
    LIVE["thread"] = t
    LIVE["run_id"] = art.name
    t.start()
    return {"started": True, "capability": art.name}


# --------------------------------------------------------------------------- #
# Intervention queue + control transfer
# --------------------------------------------------------------------------- #
@app.get("/api/interventions")
def list_interventions():
    return [i.model_dump(mode="json") for i in STORE.list()]


@app.get("/api/session")
def session_state():
    s = STORE.session
    return {"controller": s.controller.value, "status": s.status.value,
            "active": s.active.model_dump(mode="json") if s.active else None}


@app.post("/api/interventions/{iid}/take")
def take_control(iid: str):
    req = STORE.get(iid)
    if not req:
        raise HTTPException(404, "No such intervention")
    STORE.session.take_control()
    return {"controller": Controller.HUMAN.value, "status": SessionStatus.HUMAN.value}


class ActionBody(BaseModel):
    kind: str          # click | type | navigate | note
    name: Optional[str] = None
    text: Optional[str] = None
    url: Optional[str] = None
    detail: Optional[str] = None


@app.post("/api/interventions/{iid}/action")
def operator_action(iid: str, body: ActionBody):
    if STORE.session.controller != Controller.HUMAN:
        raise HTTPException(409, "You do not hold control. Take control first.")
    LIVE["queue"].put(body.model_dump())
    return {"queued": body.kind}


@app.post("/api/interventions/{iid}/resume")
def resume(iid: str):
    """Hand control back to the agent; the replay continues on the same session."""
    STORE.session.hand_back(resolution="resume")
    return {"controller": Controller.AGENT.value, "status": SessionStatus.RESUMED.value}


@app.post("/api/interventions/{iid}/abort")
def abort(iid: str):
    STORE.session.hand_back(resolution="abort")
    return {"resolution": "abort"}


# --------------------------------------------------------------------------- #
# Minimal operator console (mock UI — the handoff mechanism is what's real)
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
def console():
    return _CONSOLE_HTML


_CONSOLE_HTML = """<!doctype html><html><head><meta charset=utf-8>
<title>CUA Operator Console</title>
<style>
 body{font:14px system-ui;margin:0;background:#0f172a;color:#e2e8f0}
 header{padding:14px 20px;background:#111827;border-bottom:1px solid #1f2937}
 main{padding:20px;max-width:820px;margin:auto}
 .card{background:#111827;border:1px solid #1f2937;border-radius:10px;padding:16px;margin:12px 0}
 .badge{padding:2px 8px;border-radius:999px;font-size:12px}
 .agent{background:#064e3b;color:#6ee7b7}.human{background:#7c2d12;color:#fdba74}
 button{background:#2563eb;color:#fff;border:0;padding:8px 12px;border-radius:8px;cursor:pointer;margin:2px}
 input{background:#0b1220;border:1px solid #334155;color:#e2e8f0;padding:7px;border-radius:6px}
 pre{white-space:pre-wrap;background:#0b1220;padding:10px;border-radius:8px;overflow:auto}
</style></head><body>
<header><b>CUA Operator Console</b> &nbsp; <span id=ctl class="badge agent">agent</span></header>
<main>
 <div class=card>
   <b>Live session</b>
   <pre id=session>loading…</pre>
 </div>
 <div class=card>
   <b>Interventions</b>
   <div id=ivs></div>
 </div>
 <div class=card id=ops style="display:none">
   <b>You have control — operate the live session</b><br><br>
   <input id=cname placeholder="control name (e.g. Confirm)"> <button onclick=act('click')>Click</button><br><br>
   <input id=tname placeholder="field name"> <input id=tval placeholder="text"> <button onclick=act('type')>Type</button><br><br>
   <button onclick=resume()>Resume agent</button> <button onclick=abort() style="background:#b91c1c">Abort</button>
 </div>
</main>
<script>
let IID=null;
async function tick(){
  const s=await (await fetch('/api/session')).json();
  document.getElementById('session').textContent=JSON.stringify(s,null,2);
  const c=document.getElementById('ctl'); c.textContent=s.controller; c.className='badge '+s.controller;
  const ivs=await (await fetch('/api/interventions')).json();
  document.getElementById('ivs').innerHTML=ivs.map(i=>{
    IID=i.id;
    return `<div class=card style="margin:6px 0"><b>${i.reason}</b> — ${i.why}
      <br>capability: ${i.capability} · step ${i.step_index} · <a style=color:#93c5fd href="#">${i.url}</a>
      <br><button onclick="take('${i.id}')">Take control</button></div>`;
  }).join('') || 'none';
  document.getElementById('ops').style.display = (s.controller==='human')?'block':'none';
}
async function take(id){IID=id;await fetch(`/api/interventions/${id}/take`,{method:'POST'});tick();}
async function act(kind){
  const b={kind};
  if(kind==='click') b.name=document.getElementById('cname').value;
  if(kind==='type'){b.name=document.getElementById('tname').value;b.text=document.getElementById('tval').value;}
  await fetch(`/api/interventions/${IID}/action`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(b)});
}
async function resume(){await fetch(`/api/interventions/${IID}/resume`,{method:'POST'});tick();}
async function abort(){await fetch(`/api/interventions/${IID}/abort`,{method:'POST'});tick();}
setInterval(tick,1200); tick();
</script></body></html>"""
