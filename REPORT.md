# REPORT

This document explains the design and the trade-offs behind it. The system
takes a natural-language goal, discovers a reusable capability by driving a real
UI once with an LLM, and then replays that capability deterministically with no
LLM in the loop, under safety guardrails, with a human able to take over the
live session when needed.

The three things the brief flags as load-bearing — the **artifact schema**, the
**determinism & error model**, and the **safety/escalation model** — are the
three things I spent the design budget on. Everything else is deliberately thin
and is called out under *Cuts*.

---

## Architecture

The shape is **discover once, replay many times**, with a hard line between the
two phases:

- **Discovery** (`cua/agent.py`) is the only place an LLM runs. It loops
  `observe → decide → act`, and *records* each committed action as a typed
  `Step`. The LLM chooses the next action from a list of perceived controls; it
  never sees a screenshot-with-coordinates and never emits code. When the goal
  is met it compiles the recorded steps into a `CapabilityArtifact`.
- **Replay** (`cua/replay.py`) takes that artifact plus typed params and
  re-executes it with **no model**, classifying every runtime condition against
  a fixed taxonomy.

The seam that makes this generalize is **perception via the accessibility
tree**, not pixels. `cua/surface/base.py` defines a `Surface` protocol
(`observe`, `click`, `type_text`, `read`, …). The web implementation
(`surface/web.py`) extracts interactable elements and read-anchors —
role, accessible name, label, test-id — in one DOM pass, and resolves targets
with Playwright. This choice is deliberate and is the backbone of the whole
design:

- It **generalizes across heterogeneous UIs**. A legacy web app and a native
  desktop app both expose an accessibility tree of role+name; a screenshot +
  coordinate approach would need vision and per-pixel brittleness for each. The
  `Surface` protocol is where `LegacyWebSurface` and a desktop
  (OS a11y tree) implementation slot in later — documented seams, not built.
- It is **cheap and stable for free models**. The LLM reasons over a small JSON
  list of named controls, not a megapixel image, so a free Groq/Gemini model is
  enough and token cost stays low.
- It makes **discovery and replay perceive the same way**, so what discovery can
  record, replay can reliably find.

Storage is local JSON (`catalog.py`, `artifacts/`), the process model is
single-process and synchronous, and the entry points are a CLI (`cua.cli`) and a
FastAPI operator server (`server/app.py`). Those are scope choices (see *Cuts*),
not architectural commitments — the boundaries (`Surface`, catalog, LLM client)
are where a real deployment would swap implementations.

---

## Artifact schema

The artifact (`cua/schema.py`, `CapabilityArtifact`, `SCHEMA_VERSION = 1.0.0`)
is the contract between discovery and replay and the unit an agent-orchestration
layer would call. It is **typed, versioned, and reviewable** — a human can read
`artifacts/member_savings_lookup.json` and see exactly what will run.

Key decisions:

- **Ranked, multi-strategy locators.** Each `Step` targets an `ElementTarget`
  that carries an *ordered* list of `Locator`s (`LocatorStrategy`, ranked
  most-robust → most-brittle: role+name → test-id → label → text → placeholder →
  alt/title → CSS → XPath). Determinism comes from the *fixed order*; resilience
  comes from the *fallbacks*. Prefer semantic anchors that survive markup churn
  and are the only thing available on legacy/desktop surfaces; treat CSS/XPath
  as last resorts. The committed evidence shows both sides of this: the real
  artifact reads the balance via role/name *and* test-id, and a drifted variant
  with a single stale locator fails cleanly (see *Determinism*).
- **Typed I/O.** `inputs`/`outputs` are named and typed (`InputParam`,
  `OutputField`) with a `sensitive` flag that drives redaction. Parameters are
  substituted purely (`{{param}}`), so the same artifact serves any member ID.
- **Business outcomes are first-class.** `BusinessOutcome` entries
  (`member_not_found`, `permission_denied`) each carry a `detect` checkpoint.
  These are *expected domain results*, encoded in the artifact, not error
  handling bolted on at runtime.
- **Checkpoints, not assumptions.** Steps and the overall run carry
  `Checkpoint`s (`ELEMENT_VISIBLE`, `TEXT_PRESENT`, `URL_MATCHES`,
  `VALUE_EQUALS`) so replay *verifies* it reached the expected state instead of
  assuming a click worked.
- **Versioning + approval.** `schema_version` and a semver artifact `version`
  allow the contract and the content to evolve independently; `ApprovalState`
  (`DRAFT` → `APPROVED`) gates whether a freshly discovered capability may run
  unattended. Discovery emits `DRAFT`; the committed sample is `APPROVED`.
- **Multi-tenant overrides live in the artifact** (`overrides`,
  `resolved_for()`) — covered below.

---

## Determinism & error handling

**Determinism.** Replay has no LLM. Given the same artifact + params + surface
state it does the same thing, because: locators resolve in a fixed order;
parameter substitution is pure; every wait is an explicit checkpoint rather than
a sleep; and guardrails are re-checked identically each run. Bounded transient
retry is fixed (one attempt, fixed backoff), so it does not introduce
nondeterminism.

**Error taxonomy** (`cua/result.py`, `ResultStatus`). Every step is classified,
in this order, and this order is the whole point:

1. **Business outcome** — a `detect` checkpoint matches (`member_not_found`).
   Terminal, **not** a failure: the run returns `BUSINESS_OUTCOME` + a code. This
   is the single most important distinction in the system — "the member doesn't
   exist" is a valid answer, and conflating it with a crash is what makes naive
   automations untrustworthy.
2. **Recoverable** — a known interstitial is present, or a transient load fails.
   Replay dismisses the dialog / retries once (`RecoveredEvent`) and continues.
   No human needed.
3. **Risk gate** — the step is irreversible (`Reversibility.RISKY`). Headless,
   this returns `ESCALATED`; interactive, it blocks for a human (see *Escalation*).
4. **Hard failure** — nothing above applies and the action can't complete
   (element not found, checkpoint fails). Returns `HARD_FAILURE` with a
   `FailureDetail` (`step_index`, `expected`, `observed`, `hint`) **plus a
   screenshot and DOM snapshot** at the failing step, so a human can diagnose it.
5. **Session expiry** is detected explicitly and escalates (re-auth needs a
   human), rather than being mis-classified as a hard failure.

The committed evidence exercises the whole taxonomy against the live app:
`success` (extracts `$4,210.55`), two distinct business outcomes
(`member_not_found` and `permission_denied` on a restricted record), and a
`hard-failure` (locator drift → `ElementNotFound` at `step_index=2`, with DOM +
screenshot). Two more runs cover the safety and multi-tenant paths: a risky
transfer that `escalated` at the irreversible confirm step, and a Westside-tenant
replay that succeeded through a per-tenant locator override. The unit tests
(`tests/test_replay.py`) lock the three core outcomes down with a fake surface —
no browser, no LLM — so the classification logic is tested in isolation and in
milliseconds.

---

## Heterogeneity & multi-tenant

**Heterogeneity across apps** is handled at the `Surface` seam and the locator
ranking, not with per-app code. Because perception is role+name/label/test-id,
the same agent and the same replay engine drive any web app, and the same
artifact shape describes a legacy web screen or a desktop window once those
surfaces are implemented. Only two things change per app: the artifact and the
allowlist.

**Multi-tenant** (same vendor product, different tenants) is handled by
**base artifact + override patches**, not by re-recording per tenant.
`SurfaceBinding` records `vendor`/`app`/`version`/`tenant`; a base artifact
(`tenant = None`) carries a map of `TenantOverride`s. `resolved_for(tenant)`
applies a tenant's patches — per-step locator overrides and parameter defaults —
over the base at invoke time (`catalog.invoke(..., tenant=...)`). So when tenant
B's instance renames a button or sits behind a different subdomain, you patch
one locator instead of maintaining N copies of the flow. This keeps a fleet of
near-identical tenant UIs maintainable from a single reviewed capability. This
is **demonstrated, not just designed**: `member_savings_lookup` carries a
`westside_cu` override that relabels the search action "Find", and the committed
`multi-tenant-westside` evidence run replays the specialized artifact against the
tenant-branded variant (`?tenant=westside`) and reads the balance. Note the
override *prepends* its locators and keeps the base ones as fallback, so a
tenant-specialized artifact still degrades gracefully if run against the base
app. Per-tenant/version drift is caught the same way any drift is — a failing
checkpoint or an unresolved locator surfaces as a hard failure with evidence,
which is the signal to add or fix an override rather than silently mis-click.

---

## Escalation & handoff

Escalation is a **control-transfer state machine** (`cua/escalation.py`), not a
notification. The design requirement is that a human takes over the **same live
session** — the agent's browser, mid-flow — and hands back.

- `SessionState` tracks the controller (`AGENT`/`HUMAN`) and status
  (`RUNNING`/`PAUSED`/`HUMAN`/`RESUMED`). When replay hits a risky or
  unrecoverable step it raises an `InterventionRequest` (reason, capability,
  step, why, url, screenshot) and **pauses**.
- The operator server (`server/app.py`) runs the live replay on a **single
  worker thread** and drives all manual operator actions through a **command
  pump** on that same thread. This is the crux: Playwright's sync API is
  thread-affine, so the human's clicks must execute on the thread that owns the
  page. `wait_for_resume(pump=…)` lets the paused agent thread drain and apply
  operator commands to the live page, then continue when control is handed back.
  The human is genuinely operating the agent's session, not a copy.
- Handoff flow: `take` (PAUSED→HUMAN) → `action` (recorded `HumanAction`s on the
  live page) → `resume` (HUMAN→RESUMED, agent continues) or `abort`. Every
  transition is evidence-logged.

The operator console served at `/` is deliberately thin — enough to prove the
loop (see a live intervention, take control, act, resume). The **mechanism** is
real; the **UI** is mock. The detect-and-route half is also captured statically:
the committed `escalated-risky-transfer` run shows a replay pausing at the
irreversible confirm step with an `intervention_id`, context, and a screenshot.
The interactive half — a human operating the same live session — is demonstrated
live via the console rather than as a static log.

---

## Safety

Guardrails (`cua/guardrails.py`) are enforced on **both** discovery and replay —
replay is not trusted more than discovery just because it's deterministic.

- **Allowlist.** Navigation is checked against a domain allowlist (and optional
  route-prefix allowlist); actions are checked against an allowed action-type
  list. Off-allowlist navigation raises `GuardrailViolation`.
- **Reversibility gating.** Every step is classified `SAFE` / `REVERSIBLE` /
  `RISKY`. `RISKY` (irreversible: money movement, record creation — the "Confirm"
  that opens a sub-account or submits a transfer) is **blocked pending human
  confirmation** by default (`CUA_BLOCK_RISKY=true`); the guardrail returns a
  `RiskDecision` that requires confirmation, which routes into escalation rather
  than silently proceeding. Both risky flows (`open_sub_account`,
  `transfer_funds`) carry a `RISKY` final step, and the transfer escalation is in
  the committed evidence.
- **Redaction everywhere.** `cua/redaction.py` scrubs card numbers, SSNs,
  emails, and token-shaped secrets (sk-/rzp-/gsk-/Bearer/opaque 32-char) from
  *all* logs and evidence, and `sensitive` inputs/outputs are masked by
  contract. Nothing sensitive reaches disk in the clear.
- **Secrets are environment-only.** No key is ever hardcoded, logged, or
  committed; `.env` is git-ignored and `.env.example` ships placeholders.
- **Least authority by default.** Headless replay will *not* perform a risky
  action on its own — it escalates. Autonomy over irreversible actions is opt-in
  and human-gated, which is the safe default for financial workflows.

---

## Cuts

Conscious scope choices, so the load-bearing parts could be done properly:

- **Operator console UI is minimal.** The handoff *mechanism* (live session,
  pump, state machine) is real and complete; the HTML console is just enough to
  drive it. A production console would stream the live view and richer controls.
- **Storage is local JSON.** `Catalog` reads/writes files. The interface
  (`save`/`load`/`list`/`invoke`) is what a DB-backed store would implement;
  swapping it is isolated.
- **Single-process / synchronous.** One live session at a time in the server.
  Concurrency (a session pool, a queue, per-tenant workers) is a deployment
  concern the seams already anticipate but that I didn't build.
- **Discovery parameterization is basic.** The compiler surfaces the obvious
  searched value as a parameter and leaves other literals inline; a fuller
  canonicalizer (diffing multiple discovery runs to infer parameters and
  optional branches) is the natural next step. The committed
  `member_savings_lookup.json` is hand-finalized to show the intended typed
  shape; the raw discovered artifact under `evidence/discovery/` shows the
  automatic output.
- **Legacy-web and desktop surfaces are seams, not implementations.** The
  `Surface` protocol and the role+name-first locator ranking exist precisely so
  they can be added without touching the agent or replay engine — but only the
  `WebSurface` is built.
- **Vision is a documented fallback, not built.** Perception is the a11y tree.
  A vision-based `observe()` would drop in behind the same protocol for canvas
  or image-only UIs; it wasn't needed for the target and would have cost far
  more per step on free models.
- **AuthN/session bootstrap is out of scope.** The system detects session
  expiry and escalates for re-auth; it does not itself log in.

**Stretch goals attempted** (kept small, per the brief's "at most one or two"):
an agent-facing capability **catalog** (`cua catalog` / the server's
`/api/capabilities`), **confidence/approval** gating (`ApprovalState`,
`ReplayStats`), a real **cross-tenant override** demo (Westside), and a
**multi-run stability** signal (`replay --repeat N`). These earned their place
because each exercises the core abstractions rather than adding surface area.
