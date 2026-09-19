"""
WebSurface — a concrete Surface backed by Playwright.

Perception strategy: we do NOT dump raw HTML at the model. We build an
accessibility-oriented view — the interactable controls (role, accessible name,
value, editability) plus a short visible-text digest. Reasons:
  * It generalises. role+name is available on legacy web AND on desktop a11y
    trees, so the same perception shape ports to those surfaces.
  * It's cheap and stable. The model reasons over ~dozens of controls, not
    thousands of DOM nodes, which keeps the loop fast on a free model.

Action strategy: every action takes a ranked ElementTarget. We resolve locators
in priority order and act on the first that yields exactly one visible element.
This is the core of deterministic-yet-resilient replay.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import (
    Browser, Locator as PWLocator, Page, TimeoutError as PWTimeout, sync_playwright,
)

from ..result import ElementNotFound, TransientError
from ..schema import ElementTarget, Locator, LocatorStrategy
from .base import Observation, Surface, UIElement

# Roles we treat as "interactable" and surface to the agent.
_INTERACTABLE = {
    "button", "link", "textbox", "combobox", "checkbox", "radio",
    "menuitem", "tab", "option", "searchbox", "spinbutton", "switch",
}


class WebSurface(Surface):
    def __init__(self, headless: bool = True, browser: Optional[Browser] = None,
                 page: Optional[Page] = None):
        self._own = browser is None
        if browser is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=headless)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
        else:
            self._pw = None
            self._browser = browser
            self._context = page.context
            self._page = page

    @property
    def page(self) -> Page:
        return self._page

    # ---------------------------------------------------------------- nav --- #
    def navigate(self, url: str) -> None:
        try:
            self._page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        except PWTimeout as exc:
            raise TransientError(f"Navigation to {url} timed out") from exc

    def current_url(self) -> str:
        return self._page.url

    # ------------------------------------------------------------ observe --- #
    def observe(self) -> Observation:
        elements: list[UIElement] = []
        # One synchronous DOM pass extracts attributes for interactables.
        raw = self._page.evaluate(_EXTRACT_JS)
        for i, node in enumerate(raw):
            interactable = node["role"] in _INTERACTABLE
            read_target = bool(node.get("ariaLabel") or node.get("testId"))
            if not interactable and not read_target:
                continue
            elements.append(UIElement(
                ref=f"e{i}",
                role=node["role"],
                name=node["name"] or "",
                value=node.get("value"),
                enabled=not node.get("disabled", False),
                editable=node.get("editable", False),
                test_id=node.get("testId"),
                placeholder=node.get("placeholder"),
                label=node.get("label"),
                css=node.get("css"),
            ))
        text_digest = self._page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 1500) : ''"
        )
        return Observation(
            url=self._page.url,
            title=self._page.title(),
            elements=elements,
            text_digest=text_digest,
        )

    # ------------------------------------------------- locator resolution --- #
    def _resolve(self, target: ElementTarget, timeout_ms: int = 4000) -> PWLocator:
        """Try ranked locators; return the first that yields a unique element."""
        last_err: Optional[str] = None
        for loc in target.locators:
            pw = self._to_pw(loc)
            if pw is None:
                continue
            try:
                count = pw.count()
            except Exception as exc:  
                last_err = str(exc)
                continue
            if count == 1:
                return pw
            if count > 1:
                
                visible = pw.filter(has=None)
                try:
                    pw.first.wait_for(state="visible", timeout=timeout_ms)
                    return pw.first
                except PWTimeout:
                    last_err = f"{loc.strategy}='{loc.value}' matched {count} (none visible)"
                    continue
            last_err = f"{loc.strategy}='{loc.value}' matched 0"
        raise ElementNotFound(
            f"No locator resolved for '{target.description}'. Tried "
            f"{[l.strategy.value for l in target.locators]}. Last: {last_err}"
        )

    def _to_pw(self, loc: Locator) -> Optional[PWLocator]:
        scope = self._page
        if loc.frame:
            scope = self._page.frame_locator(loc.frame)  # frameset support
        s = LocatorStrategy(loc.strategy)
        if s == LocatorStrategy.ROLE_NAME:
            role = loc.role or "button"
            return scope.get_by_role(role, name=loc.value, exact=False)
        if s == LocatorStrategy.TEST_ID:
            return scope.locator(f"[data-testid='{loc.value}']")
        if s == LocatorStrategy.LABEL:
            return scope.get_by_label(loc.value, exact=False)
        if s == LocatorStrategy.TEXT:
            return scope.get_by_text(loc.value, exact=False)
        if s == LocatorStrategy.PLACEHOLDER:
            return scope.get_by_placeholder(loc.value, exact=False)
        if s == LocatorStrategy.ALT_TITLE:
            return scope.get_by_alt_text(loc.value, exact=False)
        if s == LocatorStrategy.CSS:
            return scope.locator(loc.value)
        if s == LocatorStrategy.XPATH:
            return scope.locator(f"xpath={loc.value}")
        return None

    # -------------------------------------------------------------- act ---- #
    def click(self, target: ElementTarget) -> UIElement:
        pw = self._resolve(target)
        pw.scroll_into_view_if_needed(timeout=4000)
        pw.click(timeout=6000)
        return self._describe(pw, target)

    def type_text(self, target: ElementTarget, text: str) -> UIElement:
        pw = self._resolve(target)
        pw.fill(text, timeout=6000)
        return self._describe(pw, target)

    def select(self, target: ElementTarget, value: str) -> UIElement:
        pw = self._resolve(target)
        try:
            
            pw.select_option(value, timeout=3000)
            return self._describe(pw, target)
        except Exception:
            pass
        
        options = pw.evaluate(
            "el => Array.from(el.options).map(o => ({value: o.value, label: o.label}))"
        )
        needle = value.strip().lower()
        match = next(
            (o for o in options if needle in (o["label"] or "").lower()
            or needle in (o["value"] or "").lower()),
            None,
        )
        if match is None:
            raise ElementNotFound(
                f"No <option> on '{target.description}' matches '{value}'. "
                f"Available: {[o['label'] for o in options]}"
            )
        pw.select_option(match["value"], timeout=6000)
        return self._describe(pw, target)

    def press(self, key: str) -> None:
        self._page.keyboard.press(key)

    def read(self, target: ElementTarget) -> str:
            pw = self._resolve(target)
            
            try:
                val = pw.input_value(timeout=2000)
                if val:
                    return val
            except Exception:
                pass
            return (pw.inner_text(timeout=4000) or "").strip()

    # ------------------------------------------------------- checkpoints --- #
    def is_visible(self, target: ElementTarget, timeout_ms: int) -> bool:
        try:
            pw = self._resolve(target, timeout_ms=timeout_ms)
            pw.wait_for(state="visible", timeout=timeout_ms)
            return True
        except (ElementNotFound, PWTimeout):
            return False

    def text_present(self, text: str) -> bool:
        try:
            return self._page.get_by_text(text, exact=False).first.is_visible(timeout=2000)
        except Exception:
            return False

    # --------------------------------------------------------- evidence --- #
    def screenshot(self) -> bytes:
        return self._page.screenshot(full_page=False)

    def dom_snapshot(self) -> str:
        return self._page.content()

    def close(self) -> None:
        if self._own:
            try:
                self._browser.close()
                self._pw.stop()
            except Exception:
                pass

    # ---------------------------------------------------------- helpers --- #
    def _describe(self, pw: PWLocator, target: ElementTarget) -> UIElement:
        return UIElement(ref="acted", role="", name=target.description)


# JS executed in-page to extract interactable controls with attributes.
_EXTRACT_JS = r"""
() => {
  const roleFor = (el) => {
    const explicit = el.getAttribute('role');
    if (explicit) return explicit;
    const tag = el.tagName.toLowerCase();
    if (tag === 'a' && el.hasAttribute('href')) return 'link';
    if (tag === 'button') return 'button';
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'input') {
      const t = (el.getAttribute('type') || 'text').toLowerCase();
      if (['button','submit','reset'].includes(t)) return 'button';
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      if (t === 'search') return 'searchbox';
      return 'textbox';
    }
    return tag;
  };
  const nameFor = (el) => {
    const aria = el.getAttribute('aria-label');
    if (aria) return aria.trim();
    if (el.id) {
      const lbl = document.querySelector(`label[for='${el.id}']`);
      if (lbl) return lbl.innerText.trim();
    }
    const ph = el.getAttribute('placeholder');
    if (ph) return ph.trim();
    return (el.innerText || el.value || '').trim().slice(0, 80);
  };
  const cssFor = (el) => {
    if (el.getAttribute('data-testid')) return `[data-testid='${el.getAttribute('data-testid')}']`;
    if (el.id) return `#${el.id}`;
    return el.tagName.toLowerCase();
  };
  // Interactable controls PLUS semantically-labelled anchors. aria-label and
  // data-testid nodes are included because they are stable read targets (e.g. a
  // balance field) that replay can locate — discovery must be able to see them
  // too, or it could never record an extract step for them.
  const sel = 'a[href],button,input,select,textarea,[role],[onclick],[aria-label],[data-testid]';
  const nodes = Array.from(document.querySelectorAll(sel));
  return nodes.map(el => {
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    const visible = rect.width > 0 && rect.height > 0 &&
                    style.visibility !== 'hidden' && style.display !== 'none';
    if (!visible) return null;
    const tag = el.tagName.toLowerCase();
    return {
      role: roleFor(el),
      name: nameFor(el),
      value: el.value ?? null,
      disabled: el.disabled ?? false,
      editable: (tag === 'input' || tag === 'textarea' || el.isContentEditable),
      testId: el.getAttribute('data-testid'),
      ariaLabel: el.getAttribute('aria-label'),
      placeholder: el.getAttribute('placeholder'),
      label: (el.id && document.querySelector(`label[for='${el.id}']`)?.innerText.trim()) || null,
      css: cssFor(el),
    };
  }).filter(Boolean);
}
"""
