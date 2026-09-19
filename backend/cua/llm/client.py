"""
LLM client — a thin, pluggable wrapper over FREE-tier providers.

Supported (no Ollama, no local models required):
  * groq     — Llama 3.3 70B etc. Genuinely free, very fast. DEFAULT.
  * gemini   — gemini-2.0-flash. Free tier, supports vision if you extend it.
  * deepseek — deepseek-chat. OpenAI-compatible endpoint, very cheap.
  * openai   — gpt-4o-mini (if you have credit).

All providers except gemini expose an OpenAI-compatible /chat/completions API,
so we implement one HTTP path for those three and a small separate path for
Gemini. We only need chat-completion + JSON output for the agent loop, so the
surface area is deliberately tiny.

The client is used ONLY during discovery and (optionally) for bounded single-step
recovery. Deterministic replay never calls it.
"""
from __future__ import annotations

import json
from typing import Optional

import httpx

from ..config import LLMConfig

_OPENAI_COMPATIBLE = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
}


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, cfg: Optional[LLMConfig] = None):
        self.cfg = cfg or LLMConfig()
        if not self.cfg.api_key:
            raise LLMError(
                f"No API key for provider '{self.cfg.provider}'. Set the matching "
                f"env var (e.g. GROQ_API_KEY) in your .env."
            )

    def complete_json(self, system: str, user: str) -> dict:
        """Return a parsed JSON object. We instruct the model to emit ONLY JSON
        and parse defensively (strip code fences)."""
        text = self._complete(system, user, json_mode=True)
        return _parse_json(text)

    def complete_text(self, system: str, user: str) -> str:
        return self._complete(system, user, json_mode=False)

    # ------------------------------------------------------------------ #
    def _complete(self, system: str, user: str, json_mode: bool) -> str:
        if self.cfg.provider == "gemini":
            return self._gemini(system, user, json_mode)
        return self._openai_compatible(system, user, json_mode)

    def _openai_compatible(self, system: str, user: str, json_mode: bool) -> str:
        url = _OPENAI_COMPATIBLE[self.cfg.provider]
        body = {
            "model": self.cfg.resolved_model,
            "temperature": self.cfg.temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.cfg.api_key}"}
        resp = httpx.post(url, json=body, headers=headers, timeout=60)
        if resp.status_code >= 400:
            raise LLMError(f"{self.cfg.provider} error {resp.status_code}: {resp.text[:300]}")
        return resp.json()["choices"][0]["message"]["content"]

    def _gemini(self, system: str, user: str, json_mode: bool) -> str:
        model = self.cfg.resolved_model
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={self.cfg.api_key}")
        gen_cfg = {"temperature": self.cfg.temperature}
        if json_mode:
            gen_cfg["responseMimeType"] = "application/json"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": gen_cfg,
        }
        resp = httpx.post(url, json=body, timeout=60)
        if resp.status_code >= 400:
            raise LLMError(f"gemini error {resp.status_code}: {resp.text[:300]}")
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1:
            return json.loads(cleaned[start:end + 1])
        raise LLMError(f"Model did not return valid JSON: {text[:200]}")
