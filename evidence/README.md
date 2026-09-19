# Evidence

Committed sample runs, produced against the live mock bank (`mock-bank/`, served
at `http://localhost:5173`). Regenerate any time with:

```bash
cd backend
PYTHONPATH=. python make_evidence.py     # needs the mock bank running
```

Each run directory holds a structured `run.jsonl` (one JSON event per line,
already redacted), a `result.json` (the typed result), and screenshots. Hard
failures also capture a DOM snapshot at the failing step; escalations capture a
screenshot at the point control was handed off.

## discovery/member_savings_lookup/

A real discovery run: the agent loop (observe → decide → act → record →
compile) drives the live app and emits a typed `CapabilityArtifact`
(`artifact.json`). To stay reproducible without an API key, the LLM planner is
replaced by a deterministic stub that only picks the next control from what
perception reports — it never invents locators or reads values. With a real key,
`cua discover` produces an artifact of the same shape. See `run.jsonl` for the
`observe`/`decide`/`acted` trace.

## Replay runs — the full result taxonomy

| Directory | Input | Status | What it shows |
|---|---|---|---|
| `replay/success-100200/` | member 100200 | `success` | Extracts `savings_balance = $4,210.55`. No LLM in the loop. |
| `replay/business-outcome-not-found/` | member 999999 | `business_outcome` | `member_not_found` — a valid result, not a crash. Run ends cleanly with a code. |
| `replay/business-outcome-restricted/` | member 100412 | `business_outcome` | `permission_denied` on a restricted record — a second, distinct business outcome. |
| `replay/hard-failure-locator-drift/` | drifted artifact | `hard_failure` | Search button addressed by a single stale caption → `ElementNotFound` at `step_index 2`, with screenshot + DOM snapshot. Motivates ranked locators. |
| `replay/escalated-risky-transfer/` | transfer 250.00 | `escalated` | The irreversible "Confirm transfer" step is gated by policy → escalation with an `intervention_id`, context, and a screenshot. Safety model in action. |
| `replay/multi-tenant-westside/` | member 100355, tenant `westside_cu` | `success` | The base artifact specialized with a per-tenant override (button reads "Find") replays against the Westside-branded variant and reads `$18,004.10`. One recording, reused across tenants. |

## How each maps to the brief

- **Business outcome vs. failure** (the "most common design mistake" the brief
  names): the two `business-outcome-*` runs return codes, while
  `hard-failure-*` returns a debuggable error. Different directories, different
  `status` — same engine.
- **Escalation**: `escalated-risky-transfer` is the headless half (detect → gate
  → route with context). The interactive half — a human taking over the same
  live session and handing back — runs live via the operator console (root
  `README.md` → "Human handoff").
- **Multi-tenant reuse**: `multi-tenant-westside` is a real cross-variant replay,
  not just a design note.
