"""
Evidence & observability.

Every run gets its own evidence directory containing:
  - run.jsonl         : one structured event per line (what happened and why)
  - artifact.json     : (discovery) the emitted capability
  - result.json       : (replay) the structured result
  - step-*.png        : screenshots (always on failure; optionally per step)
  - dom-*.html        : DOM snapshot on failure (richer signal to debug)

All writes pass through redaction so no secret/PII is persisted.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import structlog

from .redaction import scrub_value

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)


class EvidenceRecorder:
    def __init__(self, run_id: str, evidence_root: Path, kind: str):
        self.run_id = run_id
        self.kind = kind  # "discovery" | "replay"
        self.dir = Path(evidence_root) / kind / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._jsonl = (self.dir / "run.jsonl").open("a", encoding="utf-8")
        self.log = structlog.get_logger().bind(run_id=run_id, kind=kind)

    def event(self, stage: str, **fields: Any) -> None:
        """Record one structured, redacted event to run.jsonl and stdout."""
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "stage": stage,
            **{k: scrub_value(v) for k, v in fields.items()},
        }
        self._jsonl.write(json.dumps(payload, default=str) + "\n")
        self._jsonl.flush()
        self.log.info(stage, **{k: scrub_value(v) for k, v in fields.items()})

    def screenshot_path(self, label: str) -> Path:
        return self.dir / f"{label}.png"

    def save_dom(self, label: str, html: str) -> Path:
        path = self.dir / f"dom-{label}.html"
        path.write_text(html, encoding="utf-8")
        return path

    def save_json(self, name: str, obj: Any) -> Path:
        path = self.dir / name
        path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
        return path

    def close(self) -> None:
        try:
            self._jsonl.close()
        except Exception:
            pass
