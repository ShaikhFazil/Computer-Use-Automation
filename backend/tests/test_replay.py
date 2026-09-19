"""
Replay engine tests with a FAKE surface — no browser, no LLM.

These lock down the load-bearing behaviour: the error taxonomy. We prove that
the SAME artifact returns SUCCESS, a BUSINESS_OUTCOME, or a HARD_FAILURE
depending only on what the surface reports — which is the whole point of the
result contract.
"""
from __future__ import annotations

import pytest

from cua.result import ElementNotFound, ResultStatus
from cua.replay import ReplayEngine
from cua.schema import (
    ActionType, CapabilityArtifact, Checkpoint, CheckpointKind, ElementTarget,
    Locator, LocatorStrategy, OutputField, ParamType, Step, SurfaceBinding,
    BusinessOutcome,
)


class FakeSurface:
    """Scriptable surface: `texts` are 'present', reads come from `reads`,
    and `missing` targets raise ElementNotFound."""
    def __init__(self, texts=None, reads=None, missing=None, url="http://x/detail"):
        self.texts = set(texts or [])
        self.reads = reads or {}
        self.missing = set(missing or [])
        self._url = url
        self.actions = []

    def navigate(self, url): self._url = url
    def current_url(self): return self._url
    def click(self, target):
        if target.description in self.missing:
            raise ElementNotFound(target.description)
        self.actions.append(("click", target.description))
    def type_text(self, target, text): self.actions.append(("type", target.description, text))
    def select(self, target, value): self.actions.append(("select", target.description))
    def press(self, key): self.actions.append(("press", key))
    def read(self, target): return self.reads.get(target.description, "")
    def is_visible(self, target, timeout_ms): return target.description in self.texts
    def text_present(self, text): return text in self.texts
    def screenshot(self): return b""
    def dom_snapshot(self): return "<html></html>"
    def close(self): pass


def _target(desc):
    return ElementTarget(description=desc, locators=[
        Locator(strategy=LocatorStrategy.ROLE_NAME, value=desc, role="button")])


def _artifact():
    return CapabilityArtifact(
        name="member_savings_lookup", title="Lookup", description="d", goal="g",
        binding=SurfaceBinding(kind="web", app="mock_bank"),
        inputs=[], outputs=[OutputField(name="savings_balance", type=ParamType.STRING)],
        steps=[
            Step(index=0, action=ActionType.TYPE, target=_target("Member ID"), value="{{member_id}}"),
            Step(index=1, action=ActionType.CLICK, target=_target("Search")),
            Step(index=2, action=ActionType.EXTRACT, target=_target("Savings balance"),
                 output_key="savings_balance"),
        ],
        success=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="Savings"),
        business_outcomes=[BusinessOutcome(
            code="member_not_found", description="No such member",
            detect=Checkpoint(kind=CheckpointKind.TEXT_PRESENT, expected="No member found"))],
    )


def _engine(surface):
    return ReplayEngine(surface=surface)


def test_success_extracts_output():
    s = FakeSurface(texts={"Savings"}, reads={"Savings balance": "$4,210.55"})
    res = _engine(s).replay(_artifact(), {"member_id": "12345", "base_url": "http://localhost/"})
    assert res.status == ResultStatus.SUCCESS
    assert res.outputs["savings_balance"] == "$4,210.55"


def test_business_outcome_is_not_a_failure():
    s = FakeSurface(texts={"No member found"})
    res = _engine(s).replay(_artifact(), {"member_id": "99999", "base_url": "http://localhost/"})
    assert res.status == ResultStatus.BUSINESS_OUTCOME
    assert res.business_outcome_code == "member_not_found"


def test_hard_failure_has_debug_detail():
    s = FakeSurface(texts={"Savings"}, missing={"Search"})
    res = _engine(s).replay(_artifact(), {"member_id": "12345", "base_url": "http://localhost/"})
    assert res.status == ResultStatus.HARD_FAILURE
    assert res.failure.step_index == 1
    assert "Search" in res.failure.observed
