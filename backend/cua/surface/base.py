"""
Surface abstraction — the seam between "how we perceive/act on a surface" and
"the recorded flow".

The artifact schema and replay engine speak ONLY to this interface. They never
touch Playwright, coordinates, or a DOM directly. That is the whole point: the
recorded flow is a list of (action, ElementTarget, value) tuples over an
*abstract* surface. To support a new surface kind you implement this Protocol —
the flow, schema, replay engine, guardrails and evidence are unchanged.

  WebSurface     (built)  -> Playwright over a real browser; perception via the
                            accessibility tree + interactable-element extraction.
  LegacyWebSurface (seam) -> same, but locator resolution walks framesets and
                            falls back harder to text/role because there are no
                            test IDs. Reuses ~all of WebSurface.
  DesktopSurface (seam)   -> OS accessibility tree (UIA / AX / AT-SPI). The
                            Observation/ElementTarget/role_name locator map 1:1
                            onto a11y nodes, which is exactly why we made
                            role+name the top-ranked locator strategy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

from ..schema import ElementTarget


@dataclass
class UIElement:
    """One perceivable, actionable control on the surface (surface-agnostic)."""
    ref: str                      
    role: str                   
    name: str                   
    value: Optional[str] = None
    enabled: bool = True
    editable: bool = False
    test_id: Optional[str] = None
    placeholder: Optional[str] = None
    label: Optional[str] = None
    css: Optional[str] = None
    frame: Optional[str] = None


@dataclass
class Observation:
    """What the agent 'sees' each turn — a compact, model-friendly view of state.
    Deliberately NOT a raw screenshot or full DOM: it is the interactable slice
    plus page context. Works identically for web a11y tree and desktop a11y tree.
    """
    url: str
    title: str
    elements: list[UIElement] = field(default_factory=list)
    text_digest: str = ""         
    screenshot_png: Optional[bytes] = None  


@runtime_checkable
class Surface(Protocol):
    """The only contract the flow/replay layer depends on."""

    def navigate(self, url: str) -> None: ...
    def observe(self) -> Observation: ...

    def click(self, target: ElementTarget) -> UIElement: ...
    def type_text(self, target: ElementTarget, text: str) -> UIElement: ...
    def select(self, target: ElementTarget, value: str) -> UIElement: ...
    def press(self, key: str) -> None: ...

    def read(self, target: ElementTarget) -> str: ...
    def is_visible(self, target: ElementTarget, timeout_ms: int) -> bool: ...
    def text_present(self, text: str) -> bool: ...
    def current_url(self) -> str: ...

    # Evidence.
    def screenshot(self) -> bytes: ...
    def dom_snapshot(self) -> str: ...

    def close(self) -> None: ...
