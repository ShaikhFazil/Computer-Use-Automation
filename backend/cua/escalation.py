"""
Human-in-the-loop escalation & control transfer.

The seam the brief asks for: automation must be able to pause, cede control, and
resume on the SAME live session, and there must be an unambiguous answer to
"who is in control right now?".

We model that as an explicit state machine over one shared browser session:

    AGENT  --escalate-->  PAUSED  --take_control-->  HUMAN
      ^                                                 |
      |------------------ resume -----------------------|

Rules:
  * Only the controller may act. The replay/agent loop checks `controller ==
    AGENT` before every action; if not, it blocks and waits (or returns
    ESCALATED). The operator console checks `controller == HUMAN` before
    injecting a manual action.
  * The transition is a handoff, not a new session: the same Playwright Page is
    shared (the operator server is given the live `page`), so the human's manual
    steps land on the exact state the agent was stuck on, and the agent resumes
    from whatever the human left behind.
  * Every transition and every human action is recorded to the intervention's
    audit trail and to run evidence, so the run is fully reconstructable.

An InterventionRequest carries enough context to act on: capability/goal, the
current step, why it stopped, the live URL, and a screenshot path.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Controller(str, Enum):
    AGENT = "agent"
    HUMAN = "human"


class SessionStatus(str, Enum):
    RUNNING = "running"      # agent in control, executing
    PAUSED = "paused"        # escalation raised, awaiting a human
    HUMAN = "human"          # human has taken control of the live session
    RESUMED = "resumed"      # control handed back to agent
    DONE = "done"


class InterventionReason(str, Enum):
    STUCK_DISCOVERY = "stuck_discovery"          # agent could not decide/act safely
    REPLAY_UNRECOVERABLE = "replay_unrecoverable"  # replay hit a condition it can't handle
    RISKY_CONFIRMATION = "risky_confirmation"    # irreversible step needs sign-off
    SESSION_EXPIRED = "session_expired"          # needs human re-auth


class HumanAction(BaseModel):
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    kind: str                    # "click" | "type" | "note" | "navigate" ...
    detail: str = ""


class InterventionRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: InterventionReason
    capability: str
    goal: str
    step_index: Optional[int] = None
    why: str = ""                # human-readable explanation of the block
    url: str = ""
    screenshot_path: Optional[str] = None
    status: SessionStatus = SessionStatus.PAUSED
    controller: Controller = Controller.AGENT
    human_actions: list[HumanAction] = Field(default_factory=list)
    resolution: Optional[str] = None   # "resume" | "abort"


class SessionState:
    """Thread-safe holder of who controls the one live session, shared between
    the replay/agent thread and the operator server."""

    def __init__(self):
        self._lock = threading.RLock()
        self._controller = Controller.AGENT
        self._status = SessionStatus.RUNNING
        # A condition the agent thread waits on until a human hands control back.
        self._resume = threading.Event()
        self.active: Optional[InterventionRequest] = None

    @property
    def controller(self) -> Controller:
        with self._lock:
            return self._controller

    @property
    def status(self) -> SessionStatus:
        with self._lock:
            return self._status

    # --- agent side ------------------------------------------------------- #
    def escalate(self, req: InterventionRequest) -> InterventionRequest:
        """AGENT -> PAUSED. Records the intervention and cedes control."""
        with self._lock:
            self.active = req
            self._controller = Controller.AGENT  # still agent until a human takes it
            self._status = SessionStatus.PAUSED
            req.status = SessionStatus.PAUSED
            self._resume.clear()
        return req

    def wait_for_resume(self, timeout: Optional[float] = None, pump=None) -> bool:
        """Agent thread blocks here while a human works the session.

        If `pump` is provided, it is called repeatedly WHILE we wait. This is how
        the operator's manual actions get executed on the live page: Playwright is
        single-threaded per session, so the same worker thread that runs the agent
        must also run the human's actions. `pump` drains the operator command
        queue and applies each command to the live surface. Returns True on
        hand-back, False on timeout.
        """
        if pump is None:
            return self._resume.wait(timeout=timeout)
        import time as _t
        deadline = None if timeout is None else _t.time() + timeout
        while not self._resume.is_set():
            try:
                pump()
            except Exception:
                pass
            if self._resume.wait(0.1):
                return True
            if deadline is not None and _t.time() > deadline:
                return False
        return True

    # --- human side (driven by the operator server) ----------------------- #
    def take_control(self) -> None:
        """PAUSED -> HUMAN. The operator now owns the live session."""
        with self._lock:
            self._controller = Controller.HUMAN
            self._status = SessionStatus.HUMAN
            if self.active:
                self.active.controller = Controller.HUMAN
                self.active.status = SessionStatus.HUMAN

    def record_human_action(self, action: HumanAction) -> None:
        with self._lock:
            if self.active:
                self.active.human_actions.append(action)

    def hand_back(self, resolution: str = "resume") -> None:
        """HUMAN -> RESUMED. Control returns to the agent; unblocks the loop."""
        with self._lock:
            self._controller = Controller.AGENT
            self._status = SessionStatus.RESUMED
            if self.active:
                self.active.controller = Controller.AGENT
                self.active.status = SessionStatus.RESUMED
                self.active.resolution = resolution
            self._resume.set()

    def finish(self) -> None:
        with self._lock:
            self._status = SessionStatus.DONE


class InterventionStore:
    """In-memory registry of interventions (a DB in production). Shared by the
    engine and the operator server so both see the same live queue."""

    def __init__(self):
        self._items: dict[str, InterventionRequest] = {}
        self.session = SessionState()

    def add(self, req: InterventionRequest) -> None:
        self._items[req.id] = req

    def get(self, iid: str) -> Optional[InterventionRequest]:
        return self._items.get(iid)

    def list(self) -> list[InterventionRequest]:
        return list(self._items.values())



STORE = InterventionStore()
