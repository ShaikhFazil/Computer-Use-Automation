# Computer-Use Automation System

A natural-language goal is turned into a **reusable, typed capability** that an
agent discovers once by driving a real UI, and then **replays deterministically**
(no LLM in the loop) with real error handling, safety guardrails, and a
human-in-the-loop handoff that takes over the *same* live browser session.

```
   NL goal ──▶ Discovery agent (LLM)            observe → decide → act
                        │  records every step
                        ▼
              Capability artifact  ◀── typed, versioned, reviewable JSON
                        │
                        ▼
              Deterministic replay (NO LLM) ──▶ success | business outcome | failure
                        │  on risky/unrecoverable step
                        ▼
              Escalation ──▶ human takes over the SAME live session ──▶ hands back
```

The three load-bearing pieces the brief calls out are the parts to read first:

- **Artifact schema** — `backend/cua/schema.py`
- **Determinism & error taxonomy** — `backend/cua/replay.py`, `backend/cua/result.py`
- **Safety & escalation** — `backend/cua/guardrails.py`, `backend/cua/escalation.py`

Design rationale for every decision is in **[REPORT.md](REPORT.md)**.

---

## Repository layout

```
backend/
  cua/
    schema.py          # the capability artifact contract (typed, versioned)
    result.py          # result + error taxonomy (success / business / failure / escalated)
    agent.py           # discovery loop (observe → decide → act → record → compile)
    replay.py          # deterministic replay engine (no LLM)
    guardrails.py      # allowlist + risk gating, enforced on discovery AND replay
    escalation.py      # control-transfer state machine (agent ⇄ human)
    catalog.py         # save/load/list/invoke capabilities
    redaction.py       # secret/PII scrubbing for all logs + evidence
    surface/           # the UI seam: Surface protocol + Playwright WebSurface
    llm/               # pluggable LLM client (Groq / Gemini / DeepSeek / OpenAI)
    cli.py             # `cua discover | replay | catalog | serve`
  server/app.py        # FastAPI operator console + catalog API + live handoff
  artifacts/           # committed capability artifacts (savings lookup, sub-account, transfer)
  tests/               # taxonomy tests with a fake surface (no browser, no LLM)
mock-bank/             # React servicing console — the default target surface
                       #   13 members, multiple accounts + transactions, a member
                       #   directory, and two multi-field form flows (open
                       #   sub-account, transfer funds) with confirmation screens.
                       #   ?tenant=westside relabels the search action for the
                       #   multi-tenant demo.
evidence/              # committed sample discovery + replay runs (see evidence/README.md)
```

---

## Prerequisites

- **Python 3.11+**
- **Node 18+** (for the mock bank)
- A **free LLM API key** — Groq is the default. Only needed for *discovery*;
  replay, the catalog, the server, and the tests all run without one.

---

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    
pip install -r requirements.txt
playwright install chromium
```

### 2. Mock bank (default target)

```bash
cd mock-bank
npm install
```

### 3. Configure the LLM key (discovery only)

Copy `.env.example` to `.env` in the repo root and set one key. Groq is free and
fast:

```bash
cp .env.example .env
# then edit .env:
CUA_LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here
```
---

## Run the demo end to end

Open two terminals.

**Terminal 1 — the target app:**

```bash
cd mock-bank
npm run dev            # serves http://localhost:5173
```

**Terminal 2 — the agent** (`cd backend`, venv active):

### a. Discover a capability (uses the LLM)

```bash
python -m cua.cli discover \
  --goal "Find the savings account balance for a given member ID" \
  --url  "http://localhost:5173/" \
  --name "member_savings_lookup"
```

The agent drives the live app, records each step, and writes a typed artifact to
`backend/artifacts/member_savings_lookup.json` plus an evidence trace under
`evidence/discovery/`.

### b. Replay it deterministically (NO LLM)

```bash
# success — reads Ada Lovelace's savings balance
python -m cua.cli replay --name member_savings_lookup \
  --param base_url=http://localhost:5173/ --param member_id=100200

# business outcome — "no such member" is a RESULT, not a failure
python -m cua.cli replay --name member_savings_lookup \
  --param base_url=http://localhost:5173/ --param member_id=999999
```

Try `member_id=100412` for the `permission_denied` business outcome (restricted
record). Every run drops a structured trace + screenshots under
`evidence/replay/`.

**A second capability — a multi-field form with an irreversible step.** The
transfer flow fills From account / Beneficiary / Amount / Memo, reaches a
confirmation screen, and stops at the risky "Confirm" step (headless replay
escalates rather than moving money):

```bash
python -m cua.cli replay --name transfer_funds \
  --param base_url=http://localhost:5173/ --param member_id=100200 \
  --param from_account=SAV-0100200-01 --param beneficiary="Charles Babbage" \
  --param amount=250.00 --param memo="September rent"
# -> status: escalated (risky step gated by policy)
```

`open_sub_account` is the same shape (form → confirmation → risky confirm).

**Multi-tenant reuse.** The same base artifact, specialized for a tenant whose
UI relabels the action "Find":

```bash
python -m cua.cli replay --name member_savings_lookup --tenant westside_cu \
  --param base_url="http://localhost:5173/?tenant=westside" --param member_id=100355
```

**Multi-run stability** (stretch): replay N times and report a flakiness signal:

```bash
python -m cua.cli replay --name member_savings_lookup --repeat 5 \
  --param base_url=http://localhost:5173/ --param member_id=100200
```

### c. List the catalog

```bash
python -m cua.cli catalog     # member_savings_lookup, open_sub_account, transfer_funds
```

### d. Operator console + human handoff

```bash
python -m cua.cli serve            # http://localhost:8000
```

---

## Running without a live LLM

Everything except discovery needs no API key:

```bash
cd backend
pytest                 # taxonomy tests — fake surface, no browser, no LLM
PYTHONPATH=. python make_evidence.py   # regenerate evidence (mock bank must be running)
```

---

## Deployment (uvicorn)

The operator server is a standard ASGI app (`server.app:app`):

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

---