"""
Artifact schema — the typed, versioned contract for a reusable capability.

This is the focal point of the whole system. A CapabilityArtifact is what the
LLM *discovers* once and what deterministic replay *executes* forever after,
with no model in the decision loop.

Design goals baked into the schema:
  1. Decoupled from the raw model transcript. The artifact is a clean, reviewable
     flow — a human and a calling agent can both read exactly what it does, what
     it needs, and what it returns.
  2. Surface-agnostic. A `Step` targets an abstract `ElementTarget` (a ranked list
     of locator candidates), not a single brittle CSS selector. The same schema
     extends to legacy web / desktop a11y surfaces by adding locator strategies —
     the recorded *flow* does not change.
  3. Robust-by-construction. Every target carries MULTIPLE ranked locators plus
     the LLM's robustness reasoning, so replay can fall back deterministically.
  4. Multi-tenant ready. `binding` describes which app/vendor/version an artifact
     was recorded against; overrides let one base artifact be specialized per
     tenant without a re-record. (Design surfaced; not fully built — see REPORT.)
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"


# --------------------------------------------------------------------------- #
# Locators — how a control is identified, ranked by robustness
# --------------------------------------------------------------------------- #
class LocatorStrategy(str, Enum):
    """Ordered roughly most-robust -> most-brittle.

    We prefer semantic, human-visible anchors (accessible role+name, visible
    text, labels) because those survive markup churn and are the ONLY things
    available on a legacy surface with no test IDs or on a desktop a11y tree.
    CSS/XPath are last-resort fallbacks.
    """
    ROLE_NAME = "role_name"        # a11y role + accessible name  (works on desktop too)
    TEST_ID = "test_id"            # data-testid / automation id  (rare in legacy, great if present)
    LABEL = "label"                # form control by its <label> text
    TEXT = "text"                  # visible text / button caption
    PLACEHOLDER = "placeholder"    # input placeholder
    ALT_TITLE = "alt_title"        # img alt / title attribute
    CSS = "css"                    # structural CSS selector (brittle)
    XPATH = "xpath"                # positional xpath (most brittle)


class Locator(BaseModel):
    strategy: LocatorStrategy
    value: str
    # Optional scoping so a locator resolves inside a frame / region, which is
    # how we survive frameset-heavy legacy apps.
    frame: Optional[str] = None
    # For role_name we may also pin the a11y role explicitly.
    role: Optional[str] = None


class ElementTarget(BaseModel):
    """A control to act on, described by RANKED locator candidates.

    Replay tries locators in order and uses the first that resolves to exactly
    one visible, enabled element. Recording several candidates is what makes
    replay both deterministic (stable order) and resilient (graceful fallback).
    """
    description: str = Field(..., description="Human label, e.g. 'Member ID search box'")
    locators: list[Locator] = Field(..., min_length=1)
    robustness_note: str = Field(
        default="",
        description="LLM's reasoning about why these locators are stable and what could break them.",
    )


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #
class ActionType(str, Enum):
    NAVIGATE = "navigate"      # go to a URL / route
    CLICK = "click"
    TYPE = "type"              # type text into a field
    SELECT = "select"          # choose an <option> / list item
    PRESS = "press"            # keyboard key (Enter, Tab...)
    WAIT_FOR = "wait_for"      # explicit wait for a checkpoint element/state
    EXTRACT = "extract"        # read a value out of the UI into an output
    ASSERT = "assert"          # verify a checkpoint condition


# Reversibility classification drives the safety model. SAFE actions are pure
# reads/navigation; RISKY actions mutate state and are gated (see guardrails).
class Reversibility(str, Enum):
    SAFE = "safe"              # read/navigate — no side effects
    REVERSIBLE = "reversible"  # writes that can be undone (e.g. edit a draft)
    RISKY = "risky"            # irreversible / money-moving / record-creating


class Step(BaseModel):
    index: int
    action: ActionType
    target: Optional[ElementTarget] = None      # None for navigate/press
    # `value` is a literal OR a "{{param}}" reference resolved from inputs at replay.
    value: Optional[str] = None
    # For EXTRACT: which output key to populate.
    output_key: Optional[str] = None
    reversibility: Reversibility = Reversibility.SAFE
    # Per-step checkpoint: after acting, this must hold or the step fails.
    checkpoint: Optional["Checkpoint"] = None
    # Waiting/timing knobs used by the deterministic waiter.
    timeout_ms: int = 10_000
    note: str = ""


# --------------------------------------------------------------------------- #
# Checkpoints & success conditions
# --------------------------------------------------------------------------- #
class CheckpointKind(str, Enum):
    ELEMENT_VISIBLE = "element_visible"
    TEXT_PRESENT = "text_present"
    URL_MATCHES = "url_matches"
    VALUE_EQUALS = "value_equals"


class Checkpoint(BaseModel):
    """A condition we ASSERT to confirm we actually reached the expected state,
    instead of assuming a click worked."""
    kind: CheckpointKind
    target: Optional[ElementTarget] = None
    expected: Optional[str] = None
    description: str = ""


# --------------------------------------------------------------------------- #
# Typed I/O contract
# --------------------------------------------------------------------------- #
class ParamType(str, Enum):
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"


class InputParam(BaseModel):
    name: str
    type: ParamType = ParamType.STRING
    required: bool = True
    description: str = ""
    # Redaction hint: is this value sensitive (PII/secret)? Never logged raw.
    sensitive: bool = False
    example: Optional[str] = None


class OutputField(BaseModel):
    name: str
    type: ParamType = ParamType.STRING
    description: str = ""
    sensitive: bool = False


# --------------------------------------------------------------------------- #
# Known business outcomes — legitimate answers, NOT failures
# --------------------------------------------------------------------------- #
class BusinessOutcome(BaseModel):
    """A named, expected non-happy result the caller must be told about
    (e.g. 'no such member'). Detected by a signal in the UI, not a crash."""
    code: str                                  # e.g. "member_not_found"
    description: str
    detect: Checkpoint                         # how replay recognises this outcome
    terminal: bool = True                      # does hitting it end the run?


# --------------------------------------------------------------------------- #
# Surface binding (multi-tenant / heterogeneity seam)
# --------------------------------------------------------------------------- #
class SurfaceBinding(BaseModel):
    kind: Literal["web", "legacy_web", "desktop"] = "web"
    app: str = Field(..., description="Logical app name, e.g. 'core_banking'")
    vendor: Optional[str] = None               # shared vendor product across tenants
    version: Optional[str] = None
    base_url_param: str = "base_url"            # which input carries the entry URL
    tenant: Optional[str] = None               # None = base/canonical artifact


# --------------------------------------------------------------------------- #
# The artifact
# --------------------------------------------------------------------------- #
class ApprovalState(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"


class CapabilityArtifact(BaseModel):
    schema_version: str = SCHEMA_VERSION
    # --- identity / review metadata ---
    name: str = Field(..., description="Stable capability id, e.g. 'member_savings_lookup'")
    version: str = "1.0.0"                      # artifact content version (semver)
    title: str
    description: str
    goal: str = Field(..., description="The natural-language goal this was discovered from")
    binding: SurfaceBinding
    approval: ApprovalState = ApprovalState.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # --- the callable contract ---
    inputs: list[InputParam] = Field(default_factory=list)
    outputs: list[OutputField] = Field(default_factory=list)

    # --- the flow ---
    steps: list[Step]
    success: Checkpoint = Field(..., description="Overall success condition for the run")
    business_outcomes: list[BusinessOutcome] = Field(default_factory=list)

    # --- reliability signal (stretch: confidence & approval) ---
    replay_stats: "ReplayStats" = Field(default_factory=lambda: ReplayStats())

    # --- multi-tenant overrides: per-tenant locator/value patches over the base ---
    overrides: dict[str, "TenantOverride"] = Field(default_factory=dict)

    def resolved_for(self, tenant: Optional[str]) -> "CapabilityArtifact":
        """Return a copy specialized for `tenant` by applying that tenant's
        override patches over the base flow. Base is untouched — this is how one
        recording is reused across tenants running the same vendor app."""
        if not tenant or tenant not in self.overrides:
            return self
        patch = self.overrides[tenant]
        clone = self.model_copy(deep=True)
        clone.binding.tenant = tenant
        for step_patch in patch.step_locator_overrides:
            for step in clone.steps:
                if step.index == step_patch.step_index and step.target:
                    # Prepend tenant-specific locators so they win, keep base as fallback.
                    step.target.locators = step_patch.locators + step.target.locators
        return clone


class ReplayStats(BaseModel):
    runs: int = 0
    successes: int = 0
    last_run_at: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        return self.successes / self.runs if self.runs else 0.0


class StepLocatorOverride(BaseModel):
    step_index: int
    locators: list[Locator]


class TenantOverride(BaseModel):
    tenant: str
    note: str = ""
    step_locator_overrides: list[StepLocatorOverride] = Field(default_factory=list)
    # Value overrides let a tenant change a route/label without touching the base.
    param_defaults: dict[str, str] = Field(default_factory=dict)


# Resolve forward refs
Step.model_rebuild()
CapabilityArtifact.model_rebuild()
