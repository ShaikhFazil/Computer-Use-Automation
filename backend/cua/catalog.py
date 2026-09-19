"""
Capability catalog — saved artifacts as a discoverable, callable surface.

This is the agent-facing view: an AI agent can list capabilities by name, read
each one's typed input/output contract, and invoke it by name with args. The
catalog is the boundary between "the agent-facing product decides WHAT to do"
and "this system reliably DOES it".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .config import ARTIFACTS_DIR
from .replay import ReplayEngine
from .result import ReplayResult
from .schema import CapabilityArtifact


class Catalog:
    def __init__(self, directory: Optional[Path] = None):
        self.dir = Path(directory or ARTIFACTS_DIR)
        self.dir.mkdir(parents=True, exist_ok=True)

    # --- persistence ------------------------------------------------------ #
    def save(self, artifact: CapabilityArtifact) -> Path:
        path = self.dir / f"{artifact.name}.json"
        path.write_text(json.dumps(artifact.model_dump(mode="json"), indent=2),
                        encoding="utf-8")
        return path

    def load(self, name: str) -> CapabilityArtifact:
        path = self.dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"No capability '{name}' in {self.dir}")
        return CapabilityArtifact.model_validate_json(path.read_text(encoding="utf-8"))

    # --- agent-facing discovery ------------------------------------------ #
    def list(self) -> list[dict[str, Any]]:
        """A compact, typed manifest an agent can reason over."""
        out = []
        for p in sorted(self.dir.glob("*.json")):
            try:
                art = CapabilityArtifact.model_validate_json(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            out.append({
                "name": art.name,
                "version": art.version,
                "title": art.title,
                "description": art.description,
                "approval": art.approval.value,
                "success_rate": round(art.replay_stats.success_rate, 3),
                "inputs": [{"name": i.name, "type": i.type.value, "required": i.required,
                            "sensitive": i.sensitive} for i in art.inputs],
                "outputs": [{"name": o.name, "type": o.type.value} for o in art.outputs],
            })
        return out

    # --- invocation ------------------------------------------------------- #
    def invoke(self, name: str, params: dict[str, Any], tenant: Optional[str] = None,
               engine: Optional[ReplayEngine] = None) -> ReplayResult:
        art = self.load(name)
        eng = engine or ReplayEngine()
        try:
            return eng.replay(art, params, tenant=tenant)
        finally:
            if engine is None:
                eng.surface.close()
