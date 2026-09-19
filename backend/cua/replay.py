"""
Deterministic replay — the production execution path. No LLM in the decision loop.

Given a saved artifact + input params, it re-runs the recorded flow using stable,
ranked locator targeting, verifies checkpoints, classifies every runtime
condition against the taxonomy in result.py, and returns a structured result.

Determinism comes from:
  * Ranked locators tried in a FIXED order (same inputs -> same resolution).
  * Explicit waits on checkpoints instead of sleeps or "assume the click worked".
  * Parameter substitution ({{param}}) that is pure and side-effect free.
  * Guardrails re-enforced on every step (replay is not trusted more than
    discovery).

Robustness comes from the detector order on each step:
    1. business-outcome detectors  (member_not_found, permission_denied ...)
    2. recoverable detectors        (interstitial dialog, transient load -> retry)
    3. the intended action + checkpoint
    4. anything left over            -> HARD_FAILURE (with debug detail) or ESCALATE
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from .config import EVIDENCE_DIR, Settings, settings as default_settings
from .escalation import (
    STORE, InterventionReason, InterventionRequest,
)
from .guardrails import Guardrails
from .logging_conf import EvidenceRecorder
from .result import (
    ElementNotFound, FailureDetail, GuardrailViolation, RecoverableKind,
    RecoveredEvent, ReplayResult, ResultStatus, SessionExpired, TransientError,
)
from .schema import (
    ActionType, CapabilityArtifact, Checkpoint, CheckpointKind, Reversibility,
    Step,
)
from .surface import WebSurface


_DISMISSIBLE = ["OK", "Dismiss", "Close", "Got it", "Continue"]

# Signals that a session/timeout expired and we must re-authenticate (escalate).
_SESSION_EXPIRED_TEXT = ["session expired", "please log in", "sign in to continue", "timed out"]


class ReplayEngine:
    def __init__(self, cfg: Optional[Settings] = None, surface: Optional[WebSurface] = None,
                 allow_assisted_recovery: bool = False, pump=None, interactive: bool = False):
        self.cfg = cfg or default_settings
        self.guard = Guardrails(self.cfg.allowlist)
        self.surface = surface or WebSurface(headless=self.cfg.headless)
        self.allow_assisted_recovery = allow_assisted_recovery
        self._pump = pump
        self.interactive = interactive

    def replay(self, artifact: CapabilityArtifact, params: dict[str, Any],
               tenant: Optional[str] = None) -> ReplayResult:
        art = artifact.resolved_for(tenant)
        run_id = uuid.uuid4().hex[:12]
        ev = EvidenceRecorder(run_id, EVIDENCE_DIR, "replay")
        started = time.time()
        result = ReplayResult(status=ResultStatus.SUCCESS, capability=art.name,
                              capability_version=art.version, evidence_dir=str(ev.dir))
        ev.event("start", capability=art.name, version=art.version, tenant=tenant,
                  params={k: ("«redacted»" if _is_sensitive(art, k) else v)
                          for k, v in params.items()})

        # Sensitive param keys for redaction downstream.
        sensitive = {p.name for p in art.inputs if p.sensitive}

        try:
            base_url = params.get(art.binding.base_url_param) or params.get("base_url")
            if base_url:
                self.guard.check_url(base_url)
                self.surface.navigate(base_url)

            for step in art.steps:
                self._enforce_controller(step)
                self.guard.check_action(step.action)

                # (1) business outcomes first — a legitimate answer, not a crash.
                bo = self._detect_business_outcome(art)
                if bo is not None:
                    result.status = ResultStatus.BUSINESS_OUTCOME
                    result.business_outcome_code = bo.code
                    result.business_outcome_description = bo.description
                    ev.event("business_outcome", code=bo.code, step=step.index)
                    if bo.terminal:
                        break

                # (2) recoverable conditions — handle inline, then re-observe.
                self._maybe_recover(step, result, ev)

                # (3) risk gate for irreversible steps.
                decision = self.guard.gate_step(step)
                if not decision.allowed and decision.requires_confirmation:
                    if self.interactive and self._pump is not None:
                        # Real handoff: pause, let a human take the SAME live
                        # session, then resume and perform the authorized step.
                        req = self._raise(art, step, ev,
                                          InterventionReason.RISKY_CONFIRMATION,
                                          "Risky/irreversible step — awaiting human confirmation.")
                        STORE.session.wait_for_resume(pump=self._pump)
                        result.recovered.append(RecoveredEvent(
                            kind=RecoverableKind.WAITED_FOR_ELEMENT, step_index=step.index,
                            detail=f"Human authorized risky step via intervention {req.id}"))
                        ev.event("resumed_after_confirmation", intervention_id=req.id)
                    else:
                        return self._escalate_risky(art, step, ev, result, started)

                # (4) execute the intended action, with waits + checkpoint.
                try:
                    self._execute(step, art, params, result, ev)
                except SessionExpired as exc:
                    return self._escalate(art, step, ev, result, started,
                                          InterventionReason.SESSION_EXPIRED, str(exc))
                except TransientError as exc:
                    # one bounded retry already lives in _execute; here it's terminal
                    return self._hard_fail(step, ev, result, started,
                                           expected="page/element to load",
                                           observed=str(exc))
                except ElementNotFound as exc:
                    return self._hard_fail(step, ev, result, started,
                                           expected=step.target.description if step.target else "",
                                           observed=str(exc),
                                           hint="Locators may need a tenant override; see overrides[].")
                except GuardrailViolation as exc:
                    return self._hard_fail(step, ev, result, started,
                                           expected="action within allowlist",
                                           observed=str(exc))

                result.steps_executed += 1

            # Overall success checkpoint (unless a business outcome already set).
            if result.status == ResultStatus.SUCCESS:
                if not self._checkpoint_holds(art.success):
                    return self._hard_fail(art.steps[-1] if art.steps else _dummy(), ev, result,
                                           started, expected="success checkpoint",
                                           observed="checkpoint did not hold at end of flow")
                ev.event("success", outputs=list(result.outputs.keys()))

            result.duration_ms = int((time.time() - started) * 1000)
            _bump_stats(art, success=result.ok)
            ev.save_json("result.json", result.model_dump(mode="json"))
            return result
        finally:
            try:
                ev.screenshot_path("final").write_bytes(self.surface.screenshot())
            except Exception:
                pass
            ev.close()

    # ------------------------------------------------------------------ #
    def _execute(self, step: Step, art, params, result: ReplayResult,
                 ev: EvidenceRecorder) -> None:
        value = _resolve_value(step.value, params)
        ev.event("step", index=step.index, action=step.action.value,
                 target=step.target.description if step.target else None,
                 value=("«redacted»" if _step_sensitive(step, art) else value))

        if step.action == ActionType.NAVIGATE:
            self.guard.check_url(value)
            self._with_retry(lambda: self.surface.navigate(value), step)
        elif step.action == ActionType.CLICK:
            self._with_retry(lambda: self.surface.click(step.target), step)
        elif step.action == ActionType.TYPE:
            self._with_retry(lambda: self.surface.type_text(step.target, value or ""), step)
        elif step.action == ActionType.SELECT:
            self._with_retry(lambda: self.surface.select(step.target, value or ""), step)
        elif step.action == ActionType.PRESS:
            self.surface.press(value or "Enter")
        elif step.action == ActionType.EXTRACT:
            read = self.surface.read(step.target)
            key = step.output_key or f"value_{step.index}"
            result.outputs[key] = read
            ev.event("extract", key=key, chars=len(read or ""))
        elif step.action in (ActionType.WAIT_FOR, ActionType.ASSERT):
            pass  # checkpoint handled below

        # Detect session expiry after acting.
        if any(self.surface.text_present(t) for t in _SESSION_EXPIRED_TEXT):
            raise SessionExpired("Session/timeout expiry detected after action.")

        # Per-step checkpoint: verify we reached the expected state.
        if step.checkpoint and not self._checkpoint_holds(step.checkpoint):
            raise ElementNotFound(
                f"Step {step.index} checkpoint failed: {step.checkpoint.description}")

    def _with_retry(self, fn, step: Step) -> None:
        """One bounded retry for transient loads — a RECOVERABLE condition, not
        a hard failure. Deterministic: fixed attempt count, fixed backoff."""
        try:
            fn()
        except TransientError:
            time.sleep(0.8)
            fn()  # if this also fails, TransientError propagates -> handled by caller

    # ------------------------------------------------------------------ #
    def _detect_business_outcome(self, art: CapabilityArtifact):
        for bo in art.business_outcomes:
            if self._checkpoint_holds(bo.detect, wait=False):
                return bo
        return None

    def _maybe_recover(self, step: Step, result: ReplayResult, ev: EvidenceRecorder) -> None:
        # Dismiss a known interstitial if present.
        for label in _DISMISSIBLE:
            if self.surface.text_present(label):
                try:
                    from .schema import ElementTarget, Locator, LocatorStrategy
                    tgt = ElementTarget(description=f"interstitial:{label}",
                                        locators=[Locator(strategy=LocatorStrategy.ROLE_NAME,
                                                          value=label, role="button")])
                    self.surface.click(tgt)
                    result.recovered.append(RecoveredEvent(
                        kind=RecoverableKind.DISMISSED_INTERSTITIAL,
                        step_index=step.index, detail=f"Dismissed '{label}'"))
                    ev.event("recovered", kind="dismissed_interstitial", label=label)
                    return
                except Exception:
                    continue

    def _checkpoint_holds(self, cp: Optional[Checkpoint], wait: bool = True) -> bool:
        """Verify a checkpoint. When `wait` is True (the success/step-checkpoint
        path) we poll up to the step timeout for the expected state to appear.
        When False (detectors probing for a business outcome or interstitial) we
        check once and return immediately — a non-match must be cheap."""
        if cp is None:
            return True
        if cp.kind == CheckpointKind.ELEMENT_VISIBLE and cp.target:
            timeout = self.cfg.step_timeout_ms if wait else 0
            return self.surface.is_visible(cp.target, timeout)
        if cp.kind == CheckpointKind.TEXT_PRESENT and cp.expected:
            if not wait:
                return self.surface.text_present(cp.expected)
            deadline = time.time() + self.cfg.step_timeout_ms / 1000
            while time.time() < deadline:
                if self.surface.text_present(cp.expected):
                    return True
                time.sleep(0.3)
            return False
        if cp.kind == CheckpointKind.URL_MATCHES and cp.expected:
            return cp.expected in self.surface.current_url()
        if cp.kind == CheckpointKind.VALUE_EQUALS and cp.target and cp.expected is not None:
            return self.surface.read(cp.target).strip() == cp.expected.strip()
        # Empty/auto checkpoint: treat as satisfied (discovery emitted a stub).
        return True

    # ------------------------------------------------------------------ #
    def _enforce_controller(self, step: Step) -> None:
        # If a human currently holds the session (e.g. mid-handoff), block until
        # control is handed back. Pump operator commands while we wait so the
        # human can actually work on this thread's live page.
        from .escalation import Controller
        if STORE.session.controller != Controller.AGENT:
            STORE.session.wait_for_resume(pump=self._pump)

    def _raise(self, art, step, ev, reason, why) -> InterventionRequest:
        """Register an intervention + flip session to PAUSED (no result change)."""
        shot = ev.screenshot_path(f"escalation-step{step.index}")
        try:
            shot.write_bytes(self.surface.screenshot())
        except Exception:
            pass
        req = InterventionRequest(
            reason=reason, capability=art.name, goal=art.goal, step_index=step.index,
            why=why, url=self.surface.current_url(), screenshot_path=str(shot),
        )
        STORE.add(req)
        STORE.session.escalate(req)
        ev.event("escalated", intervention_id=req.id, reason=reason.value, why=why)
        return req

    def _escalate_risky(self, art, step, ev, result, started) -> ReplayResult:
        return self._escalate(art, step, ev, result, started,
                              InterventionReason.RISKY_CONFIRMATION,
                              "Risky/irreversible step requires human confirmation.")

    def _escalate(self, art, step, ev, result, started, reason, why) -> ReplayResult:
        shot = ev.screenshot_path(f"escalation-step{step.index}")
        try:
            shot.write_bytes(self.surface.screenshot())
        except Exception:
            pass
        req = InterventionRequest(
            reason=reason, capability=art.name, goal=art.goal, step_index=step.index,
            why=why, url=self.surface.current_url(), screenshot_path=str(shot),
        )
        STORE.add(req)
        STORE.session.escalate(req)
        ev.event("escalated", intervention_id=req.id, reason=reason.value, why=why)
        result.status = ResultStatus.ESCALATED
        result.intervention_id = req.id
        result.escalation_reason = why
        result.duration_ms = int((time.time() - started) * 1000)
        ev.save_json("result.json", result.model_dump(mode="json"))
        return result

    def _hard_fail(self, step: Step, ev, result, started, expected, observed, hint="") -> ReplayResult:
        try:
            ev.screenshot_path(f"failure-step{step.index}").write_bytes(self.surface.screenshot())
            ev.save_dom(f"failure-step{step.index}", self.surface.dom_snapshot())
        except Exception:
            pass
        result.status = ResultStatus.HARD_FAILURE
        result.failure = FailureDetail(step_index=step.index, action=step.action.value,
                                       expected=expected, observed=observed, hint=hint)
        result.duration_ms = int((time.time() - started) * 1000)
        ev.event("hard_failure", step=step.index, expected=expected, observed=observed)
        ev.save_json("result.json", result.model_dump(mode="json"))
        _bump_stats(_ArtifactRef(result.capability), success=False)
        return result


# --------------------------------------------------------------------------- #
def _resolve_value(value: Optional[str], params: dict[str, Any]) -> Optional[str]:
    """Pure {{param}} substitution."""
    if value is None:
        return None
    out = value
    for key, val in params.items():
        out = out.replace("{{" + key + "}}", str(val))
    return out


def _is_sensitive(art: CapabilityArtifact, key: str) -> bool:
    return any(p.name == key and p.sensitive for p in art.inputs)


def _step_sensitive(step: Step, art: CapabilityArtifact) -> bool:
    # Heuristic: if a step types a value referencing a sensitive param, redact it.
    if step.value and "{{" in step.value:
        for p in art.inputs:
            if p.sensitive and "{{" + p.name + "}}" in step.value:
                return True
    return False


def _bump_stats(art, success: bool) -> None:
    try:
        art.replay_stats.runs += 1
        if success:
            art.replay_stats.successes += 1
    except Exception:
        pass


class _ArtifactRef:
    """Lightweight stand-in so stats bump doesn't crash when we only have a name."""
    def __init__(self, name):
        from .schema import ReplayStats
        self.name = name
        self.replay_stats = ReplayStats()


def _dummy() -> Step:
    return Step(index=-1, action=ActionType.ASSERT)
