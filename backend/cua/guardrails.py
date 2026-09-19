"""
Safety & policy guardrails.

Enforced identically on BOTH paths — the LLM discovery loop and deterministic
replay — because the model can hallucinate an action just as a bad param can
drive replay somewhere it shouldn't go.

Three checks:
  1. Domain / route allowlist  — the agent must not navigate outside it.
  2. Action-type allowlist      — only permitted action kinds may run.
  3. Risk gate                  — RISKY (irreversible) steps are blocked or
                                  flagged; blocking routes them to a human via
                                  the escalation path rather than acting blindly.
"""
from __future__ import annotations

from urllib.parse import urlparse

from .config import Allowlist
from .result import GuardrailViolation
from .schema import ActionType, Reversibility, Step


class Guardrails:
    def __init__(self, allowlist: Allowlist):
        self.allow = allowlist

    # --- URL / navigation ------------------------------------------------- #
    def check_url(self, url: str) -> None:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host and host not in self.allow.domains:
            raise GuardrailViolation(
                f"Navigation to '{host}' is not on the domain allowlist "
                f"{self.allow.domains}."
            )
        if self.allow.route_prefixes:
            path = parsed.path or "/"
            if not any(path.startswith(p) for p in self.allow.route_prefixes):
                raise GuardrailViolation(
                    f"Route '{path}' is not on the route allowlist "
                    f"{self.allow.route_prefixes}."
                )

    # --- action type ------------------------------------------------------ #
    def check_action(self, action: ActionType) -> None:
        if action.value not in self.allow.action_types:
            raise GuardrailViolation(
                f"Action '{action.value}' is not permitted by the action allowlist."
            )

    # --- risk gate -------------------------------------------------------- #
    def gate_step(self, step: Step) -> "RiskDecision":
        """Return whether a step may proceed unattended.

        RISKY steps are conservatively handled: with block_risky=True they must
        be confirmed by a human (escalation) before executing. This is the
        'money-moving / record-creating' class — we never do it silently.
        """
        self.check_action(step.action)
        if step.reversibility == Reversibility.RISKY:
            if self.allow.block_risky:
                return RiskDecision(allowed=False, requires_confirmation=True,
                                    reason="Risky/irreversible step requires human confirmation.")
            return RiskDecision(allowed=True, requires_confirmation=False,
                                reason="Risky step flagged (block_risky disabled).")
        return RiskDecision(allowed=True, requires_confirmation=False, reason="")


class RiskDecision:
    def __init__(self, allowed: bool, requires_confirmation: bool, reason: str):
        self.allowed = allowed
        self.requires_confirmation = requires_confirmation
        self.reason = reason
