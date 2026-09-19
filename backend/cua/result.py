"""
Result contract + error taxonomy.

The single most common design mistake in this problem (the brief says so) is
conflating a *business outcome* with a *failure*. "No such member" is a correct
answer the caller needs — not a crash. So the replay contract distinguishes
three runtime categories explicitly:

  SUCCESS            -> goal reached, checkpoint verified, outputs returned.
  BUSINESS_OUTCOME   -> an expected, named non-happy result (member_not_found,
                        permission_denied). The caller gets a clean, typed code.
  RECOVERABLE        -> a transient/interstitial condition the engine handled
                        (dismissed a dialog, waited out a slow load, retried).
                        Recorded, but the run continues.
  HARD_FAILURE       -> something unexpected the engine cannot safely proceed
                        through. Stops and surfaces a debuggable error:
                        which step, what was expected, what was observed.
  ESCALATED          -> engine deliberately handed off to a human (stuck / a
                        risky step needs a person). Not a failure — a pause.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class ResultStatus(str, Enum):
    SUCCESS = "success"
    BUSINESS_OUTCOME = "business_outcome"
    HARD_FAILURE = "hard_failure"
    ESCALATED = "escalated"


class RecoverableKind(str, Enum):
    DISMISSED_INTERSTITIAL = "dismissed_interstitial"
    RETRIED_TRANSIENT_LOAD = "retried_transient_load"
    WAITED_FOR_ELEMENT = "waited_for_element"


class RecoveredEvent(BaseModel):
    """A recoverable condition that was handled inline; the run continued."""
    kind: RecoverableKind
    step_index: int
    detail: str = ""
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FailureDetail(BaseModel):
    step_index: int
    action: str
    expected: str
    observed: str
    hint: str = ""


class ReplayResult(BaseModel):
    status: ResultStatus
    capability: str
    capability_version: str
    # Populated on SUCCESS (or partial extracts before a business outcome).
    outputs: dict[str, Any] = Field(default_factory=dict)
    # Populated on BUSINESS_OUTCOME.
    business_outcome_code: Optional[str] = None
    business_outcome_description: Optional[str] = None
    # Populated on HARD_FAILURE.
    failure: Optional[FailureDetail] = None
    # Populated on ESCALATED.
    intervention_id: Optional[str] = None
    escalation_reason: Optional[str] = None
    # Always populated: recoverable conditions we absorbed along the way.
    recovered: list[RecoveredEvent] = Field(default_factory=list)
    # Bookkeeping.
    steps_executed: int = 0
    duration_ms: int = 0
    evidence_dir: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def ok(self) -> bool:
        return self.status == ResultStatus.SUCCESS


# Internal exceptions used by the surface/replay layers, mapped to the taxonomy.
class SurfaceError(Exception):
    """Base for anything the perception/action layer raises."""


class ElementNotFound(SurfaceError):
    """No ranked locator resolved to a unique visible element -> HARD_FAILURE
    unless a business-outcome or recoverable detector claims it first."""


class TransientError(SurfaceError):
    """Slow/failed load, navigation timeout — candidate for retry (RECOVERABLE)."""


class SessionExpired(SurfaceError):
    """Session/timeout expiry detected — typically ESCALATE (needs re-auth)."""


class GuardrailViolation(SurfaceError):
    """Action fell outside the allowlist or hit a risky-action gate."""
