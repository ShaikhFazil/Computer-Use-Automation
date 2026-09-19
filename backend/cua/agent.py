"""
Discovery agent — the LLM-in-the-loop observe -> decide -> act cycle.

This is the ONLY place the model drives. It:
  1. observes the surface (compact interactable view, not raw DOM),
  2. asks the LLM for the single next action toward the goal,
  3. enforces guardrails, acts, records the concrete step + the locator that
     actually resolved,
  4. stops when the goal checkpoint holds, or a stopping condition trips
     (max steps / dead-end / escalation).

On success it compiles the recorded steps into a typed CapabilityArtifact that
is decoupled from this transcript. From then on the artifact is replayed with
no model in the loop.
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from .config import Settings, settings as default_settings
from .escalation import (
    STORE, InterventionReason, InterventionRequest, SessionStatus,
)
from .guardrails import Guardrails
from .llm import LLMClient
from .logging_conf import EvidenceRecorder
from .result import ElementNotFound, GuardrailViolation, TransientError
from .schema import (
    ActionType, ApprovalState, CapabilityArtifact, Checkpoint, CheckpointKind,
    ElementTarget, InputParam, Locator, LocatorStrategy, OutputField, ParamType,
    Reversibility, Step, SurfaceBinding,
)
from .surface import Observation, UIElement, WebSurface

SYSTEM_PROMPT = """You drive a computer interface to accomplish a goal, one action at a time.
You are given the GOAL and a compact list of the interactable CONTROLS currently on screen
(each with a ref, role, name, and whether it is editable), plus a short text digest of the page.

Respond with ONLY a JSON object for the SINGLE next action:
{
  "thought": "one sentence of reasoning",
  "action": "navigate|click|type|select|press|extract|done|give_up",
  "ref": "<control ref to act on, when applicable>",
  "value": "<text to type / url to navigate / key to press / value to select>",
  "output_key": "<name to store an extracted value under, for action=extract>",
  "reversibility": "safe|reversible|risky",
  "reason_robust": "why this control can be re-identified reliably later"
}

Rules:
- Choose the smallest next step. Do not batch actions.
- Prefer controls by their visible name/role. Set reversibility=risky for any action that
  creates records, moves money, or is otherwise irreversible.
- Use action "extract" to read a value the goal asks for (e.g. a balance) BEFORE finishing.
- Use action "done" only when the goal is fully achieved and any required value is extracted.
- Use action "give_up" if you are stuck and a human is needed.
Return JSON only, no prose."""


class DiscoveryAgent:
    def __init__(self, cfg: Optional[Settings] = None, llm: Optional[LLMClient] = None,
                 surface: Optional[WebSurface] = None):
        self.cfg = cfg or default_settings
        self.llm = llm or LLMClient(self.cfg.llm)
        self.guard = Guardrails(self.cfg.allowlist)
        self.surface = surface or WebSurface(headless=self.cfg.headless)

    def discover(self, goal: str, target_url: str, capability_name: str,
                 app: str = "mock_bank", vendor: Optional[str] = None) -> CapabilityArtifact:
        run_id = uuid.uuid4().hex[:12]
        ev = EvidenceRecorder(run_id, self.cfg.__dict__.get("evidence_dir") or _evidence_dir(), "discovery")
        ev.event("start", goal=goal, target_url=target_url, provider=self.cfg.llm.provider,
                  model=self.cfg.llm.resolved_model)

        # Guardrail the entry URL before we touch it.
        self.guard.check_url(target_url)
        self.surface.navigate(target_url)

        recorded: list[Step] = []
        outputs: dict[str, str] = {}
        step_idx = 0

        try:
            for turn in range(self.cfg.max_steps):
                obs = self.surface.observe()
                ev.event("observe", turn=turn, url=obs.url, title=obs.title,
                         n_controls=len(obs.elements))
                decision = self._decide(goal, obs, outputs)
                ev.event("decide", turn=turn, **{k: decision.get(k) for k in
                         ("thought", "action", "ref", "value", "reversibility")})

                action = decision.get("action")
                if action == "done":
                    break
                if action == "give_up":
                    self._escalate(ev, capability_name, goal, step_idx,
                                   decision.get("thought", "agent gave up"), obs)
                    raise RuntimeError("Discovery escalated to human (agent gave up).")

                try:
                    step = self._apply(action, decision, obs, step_idx, outputs)
                except (ElementNotFound, TransientError, GuardrailViolation) as exc:
                    ev.event("action_error", turn=turn, error=str(exc))
                    # One transient retry; otherwise escalate.
                    if isinstance(exc, TransientError):
                        self.surface.observe()
                        continue
                    self._escalate(ev, capability_name, goal, step_idx, str(exc), obs)
                    raise
                if step is not None:
                    recorded.append(step)
                    step_idx += 1
                    ev.event("acted", step_index=step.index, action=step.action.value)
            else:
                # Loop exhausted without "done".
                self._escalate(ev, capability_name, goal, step_idx,
                               "max steps reached without meeting goal", self.surface.observe())
                raise RuntimeError("Discovery hit max steps without success.")

            artifact = self._compile(goal, target_url, capability_name, app, vendor,
                                     recorded, outputs)
            path = ev.save_json("artifact.json", artifact.model_dump(mode="json"))
            ev.event("artifact_emitted", path=str(path), steps=len(recorded),
                     outputs=list(outputs.keys()))
            ev.event("success")
            return artifact
        finally:
            try:
                png = self.surface.screenshot()
                ev.screenshot_path("final").write_bytes(png)
            except Exception:
                pass
            ev.close()

    # ------------------------------------------------------------------ #
    def _decide(self, goal: str, obs: Observation, outputs: dict) -> dict:
            controls = [
                {"ref": e.ref, "role": e.role, "name": e.name,
                "editable": e.editable, "value": e.value}
                for e in obs.elements
            ]
            user = json.dumps({
                "goal": goal,
                "url": obs.url,
                "title": obs.title,
                "controls": controls,
                "text_digest": obs.text_digest[:1200],
                "already_extracted": outputs,
            }, default=str)
            return self.llm.complete_json(SYSTEM_PROMPT, user)

    def _apply(self, action: str, decision: dict, obs: Observation, idx: int,
               outputs: dict) -> Optional[Step]:
        value = decision.get("value")
        rev = Reversibility(decision.get("reversibility", "safe"))

        if action == "navigate":
            self.guard.check_url(value)
            self.surface.navigate(value)
            return Step(index=idx, action=ActionType.NAVIGATE, value=value,
                        reversibility=rev, note=decision.get("thought", ""))

        if action == "press":
            self.surface.press(value or "Enter")
            return Step(index=idx, action=ActionType.PRESS, value=value or "Enter",
                        reversibility=rev)

        
        el = self._element_for(decision.get("ref"), obs)
        if el is None:
            raise ElementNotFound(f"Agent referenced unknown control '{decision.get('ref')}'")
        target = _target_from_element(el, decision.get("reason_robust", ""))

        step = Step(index=idx, action=ActionType(_map_action(action, el)),
                    target=target, value=value, reversibility=rev,
                    note=decision.get("thought", ""))

        
        self.guard.gate_step(step)

        if action == "click":
            self.surface.click(target)
        elif action == "type":
            self.surface.type_text(target, value or "")
        elif action == "select":
            self.surface.select(target, value or "")
        elif action == "extract":
            read = self.surface.read(target)
            key = decision.get("output_key") or f"value_{idx}"
            outputs[key] = read
            step.action = ActionType.EXTRACT
            step.output_key = key
        return step

    def _element_for(self, ref: Optional[str], obs: Observation) -> Optional[UIElement]:
        if not ref:
            return None
        for e in obs.elements:
            if e.ref == ref:
                return e
        return None

    def _escalate(self, ev: EvidenceRecorder, capability: str, goal: str,
                  step_idx: int, why: str, obs: Observation) -> InterventionRequest:
        shot = ev.screenshot_path(f"escalation-step{step_idx}")
        try:
            shot.write_bytes(self.surface.screenshot())
        except Exception:
            pass
        req = InterventionRequest(
            reason=InterventionReason.STUCK_DISCOVERY, capability=capability,
            goal=goal, step_index=step_idx, why=why, url=obs.url,
            screenshot_path=str(shot),
        )
        STORE.add(req)
        STORE.session.escalate(req)
        ev.event("escalated", intervention_id=req.id, why=why)
        return req

    def _compile(self, goal, target_url, name, app, vendor, steps, outputs) -> CapabilityArtifact:
        
        inputs = [InputParam(name="base_url", type=ParamType.STRING, required=True,
                             description="Entry URL of the app", example=target_url)]
        typed_values = {s.value for s in steps if s.action == ActionType.TYPE and s.value}
        for i, v in enumerate(sorted(typed_values)):
            inputs.append(InputParam(name=f"input_{i}", type=ParamType.STRING,
                                     required=True, description=f"Typed value '{v}'",
                                     example=v))
        out_fields = [OutputField(name=k, type=ParamType.STRING, description=f"Extracted {k}")
                      for k in outputs]
        success = Checkpoint(
            kind=CheckpointKind.URL_MATCHES if not out_fields else CheckpointKind.TEXT_PRESENT,
            expected="", description="Goal reached (auto-generated; refine on review).",
        )
        return CapabilityArtifact(
            name=name, title=name.replace("_", " ").title(), description=goal, goal=goal,
            binding=SurfaceBinding(kind="web", app=app, vendor=vendor, base_url_param="base_url"),
            approval=ApprovalState.DRAFT, inputs=inputs, outputs=out_fields,
            steps=steps, success=success,
        )


# --------------------------------------------------------------------------- #
def _target_from_element(el: UIElement, robustness_note: str) -> ElementTarget:
    """Build a RANKED locator list from a perceived element — most robust first."""
    locs: list[Locator] = []
    if el.test_id:
        locs.append(Locator(strategy=LocatorStrategy.TEST_ID, value=el.test_id))
    if el.name:
        locs.append(Locator(strategy=LocatorStrategy.ROLE_NAME, value=el.name, role=el.role))
    if el.label:
        locs.append(Locator(strategy=LocatorStrategy.LABEL, value=el.label))
    if el.placeholder:
        locs.append(Locator(strategy=LocatorStrategy.PLACEHOLDER, value=el.placeholder))
    if el.name and el.role in ("button", "link"):
        locs.append(Locator(strategy=LocatorStrategy.TEXT, value=el.name))
    if el.css:
        locs.append(Locator(strategy=LocatorStrategy.CSS, value=el.css))
    if not locs:
        locs.append(Locator(strategy=LocatorStrategy.TEXT, value=el.name or "?"))
    return ElementTarget(
        description=el.name or el.role or "control",
        locators=locs,
        robustness_note=robustness_note or "Ranked semantic locators; test_id/role+name preferred.",
    )


def _map_action(action: str, el: UIElement) -> str:
    return {"click": "click", "type": "type", "select": "select",
            "extract": "extract"}.get(action, "click")


def _evidence_dir():
    from .config import EVIDENCE_DIR
    return EVIDENCE_DIR
