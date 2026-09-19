"""
Configuration — env-driven, with an explicit, configurable safety allowlist.

Secrets are read ONLY from the environment (.env is git-ignored). Nothing here
hardcodes a key. The allowlist is data, not code, so an operator can tighten it
per deployment without touching the engine.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception: 
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = Path(os.getenv("CUA_ARTIFACTS_DIR", REPO_ROOT / "backend" / "artifacts"))
EVIDENCE_DIR = Path(os.getenv("CUA_EVIDENCE_DIR", REPO_ROOT / "evidence"))


# --------------------------------------------------------------------------- #
# LLM provider selection
# --------------------------------------------------------------------------- #
@dataclass
class LLMConfig:
    provider: str = os.getenv("CUA_LLM_PROVIDER", "groq").lower()
    model: str = os.getenv("CUA_LLM_MODEL", "")
    temperature: float = float(os.getenv("CUA_LLM_TEMPERATURE", "0"))

    @property
    def api_key(self) -> Optional[str]:
        return {
            "groq": os.getenv("GROQ_API_KEY"),
            "gemini": os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
            "deepseek": os.getenv("DEEPSEEK_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
        }.get(self.provider)

    @property
    def resolved_model(self) -> str:
        if self.model:
            return self.model
        return {
            "groq": "llama-3.1-8b-instant",
            "gemini": "gemini-2.0-flash",
            "deepseek": "deepseek-chat",
            "openai": "gpt-4o-mini",
        }[self.provider]


# --------------------------------------------------------------------------- #
# Safety allowlist
# --------------------------------------------------------------------------- #
@dataclass
class Allowlist:
    """What the agent is permitted to touch. Enforced on every action."""
    # Domains the agent may navigate to. localhost defaults for the mock bank.
    domains: list[str] = field(default_factory=lambda: _csv_env(
        "CUA_ALLOWED_DOMAINS", "localhost,127.0.0.1"))
    # Route prefixes (path allowlist). Empty = any path on an allowed domain.
    route_prefixes: list[str] = field(default_factory=lambda: _csv_env(
        "CUA_ALLOWED_ROUTES", ""))
    # Which action types the agent may perform at all.
    action_types: list[str] = field(default_factory=lambda: _csv_env(
        "CUA_ALLOWED_ACTIONS",
        "navigate,click,type,select,press,wait_for,extract,assert"))
    # If True, RISKY (irreversible) steps are blocked unless an operator confirms
    # via the escalation path. If False, they are merely flagged.
    block_risky: bool = os.getenv("CUA_BLOCK_RISKY", "true").lower() == "true"


def _csv_env(key: str, default: str) -> list[str]:
    raw = os.getenv(key, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


@dataclass
class Settings:
    llm: LLMConfig = field(default_factory=LLMConfig)
    allowlist: Allowlist = field(default_factory=Allowlist)
    headless: bool = os.getenv("CUA_HEADLESS", "true").lower() == "true"
    max_steps: int = int(os.getenv("CUA_MAX_STEPS", "20"))
    step_timeout_ms: int = int(os.getenv("CUA_STEP_TIMEOUT_MS", "10000"))
    operator_base_url: str = os.getenv("CUA_OPERATOR_URL", "http://localhost:8000")


settings = Settings()
