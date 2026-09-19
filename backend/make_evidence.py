"""
Generate committed evidence against the LIVE mock bank (served at BASE).

Discovery runs the REAL agent loop. To keep it reproducible without an API key,
the LLM planner is replaced by a deterministic ScriptedPlanner that only ever
picks the next control from what perception reports -- it never invents locators
or reads values. With a real key, `cua discover` produces the same shape.

Replay runs are fully real. The scenarios cover the whole result taxonomy plus
safety escalation and a multi-tenant override.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from cua.agent import DiscoveryAgent
from cua.replay import ReplayEngine
from cua.surface.web import WebSurface
from cua.catalog import Catalog
from cua.config import EVIDENCE_DIR
from cua.schema import CapabilityArtifact, ElementTarget, Locator, LocatorStrategy

BASE = "http://localhost:5173/"


class ScriptedPlanner:
    def __init__(self, member_id: str):
        self.member_id = member_id
        self.typed = self.clicked = self.extracted = False

    def complete_json(self, system: str, user: str) -> dict:
        obs = json.loads(user)
        controls, url = obs["controls"], obs["url"]
        find = lambda pred: next((c for c in controls if pred(c)), None)
        if not self.typed:
            c = find(lambda c: c["editable"] and "member id" in (c["name"] or "").lower())
            if c:
                self.typed = True
                return {"action": "type", "ref": c["ref"], "value": self.member_id,
                        "reversibility": "safe", "thought": "Enter the member ID.",
                        "reason_robust": "Labelled form control; role+name is stable."}
        if self.typed and not self.clicked:
            c = find(lambda c: c["role"] == "button" and (c["name"] or "").strip() == "Search")
            if c:
                self.clicked = True
                return {"action": "click", "ref": c["ref"], "reversibility": "safe",
                        "thought": "Submit the lookup.",
                        "reason_robust": "Primary action button, addressed by role+name."}
        if "/member/" in url and not self.extracted:
            c = find(lambda c: (c.get("name") or "").lower() == "savings balance")
            if c:
                self.extracted = True
                return {"action": "extract", "ref": c["ref"], "output_key": "savings_balance",
                        "reversibility": "safe", "thought": "Read the savings balance.",
                        "reason_robust": "aria-labelled value node; test-id fallback."}
        return {"action": "done", "thought": "Goal met: savings balance captured."}


def _relocate(run_dir, dest):
    src = Path(run_dir)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    shutil.rmtree(src)
    return dest


def discovery_run():
    surface = WebSurface(headless=True)
    try:
        agent = DiscoveryAgent(llm=ScriptedPlanner("100200"), surface=surface)
        art = agent.discover(
            goal="Find the savings account balance for a given member ID.",
            target_url=BASE, capability_name="member_savings_lookup_discovered",
            app="mock_bank", vendor="meridian_servicing")
    finally:
        surface.close()
    runs = sorted((EVIDENCE_DIR / "discovery").glob("*/"), key=lambda p: p.stat().st_mtime)
    dest = _relocate(str(runs[-1]).rstrip("/"), EVIDENCE_DIR / "discovery" / "member_savings_lookup")
    print("discovery ->", dest.name, "| steps:", len(art.steps), "| outputs:", [o.name for o in art.outputs])


def replay(label, capability, params, dest_name, tenant=None, artifact=None):
    art = artifact or Catalog().load(capability)
    surface = WebSurface(headless=True)
    try:
        res = ReplayEngine(surface=surface).replay(art, params, tenant=tenant)
    finally:
        surface.close()
    _relocate(str(res.evidence_dir), EVIDENCE_DIR / "replay" / dest_name)
    print(f"replay[{label:16}] -> {res.status.value:15} "
          f"out={res.outputs} bo={res.business_outcome_code} "
          f"esc={res.escalation_reason} "
          f"fail={(res.failure.observed[:38] if res.failure else None)}")
    return res


def drift_artifact():
    art = Catalog().load("member_savings_lookup")
    for step in art.steps:
        if step.target and step.target.description == "Search button":
            step.target = ElementTarget(
                description="Search button (stale locator)",
                locators=[Locator(strategy=LocatorStrategy.TEXT, value="Find")],
                robustness_note="Single brittle locator on purpose.")
    return art


if __name__ == "__main__":
    discovery_run()
    replay("success", "member_savings_lookup",
           {"base_url": BASE, "member_id": "100200"}, "success-100200")
    replay("not-found", "member_savings_lookup",
           {"base_url": BASE, "member_id": "999999"}, "business-outcome-not-found")
    replay("restricted", "member_savings_lookup",
           {"base_url": BASE, "member_id": "100412"}, "business-outcome-restricted")
    replay("hard-failure", "member_savings_lookup",
           {"base_url": BASE, "member_id": "100200"}, "hard-failure-locator-drift",
           artifact=drift_artifact())
    replay("risky-escalation", "transfer_funds",
           {"base_url": BASE, "member_id": "100200", "from_account": "SAV-0100200-01",
            "beneficiary": "Charles Babbage", "amount": "250.00", "memo": "September rent"},
           "escalated-risky-transfer")
    replay("multi-tenant", "member_savings_lookup",
           {"base_url": BASE + "?tenant=westside", "member_id": "100355"},
           "multi-tenant-westside", tenant="westside_cu")
