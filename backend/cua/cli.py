"""
CLI entrypoint — the operator/developer surface.

  cua discover --goal "..." --url URL --name CAP     run the LLM discovery loop, save artifact
  cua replay   --name CAP --param k=v ...             deterministic replay of a saved artifact
  cua catalog                                         list saved capabilities (agent-facing view)
  cua serve                                           start the operator/handoff + catalog API

Run without live LLM: `discover` needs a model key; `replay`, `catalog`, `serve`
do NOT call any LLM.
"""
from __future__ import annotations

import argparse
import json
import sys

from .agent import DiscoveryAgent
from .catalog import Catalog
from .config import settings
from .replay import ReplayEngine


def _parse_params(pairs: list[str]) -> dict:
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise SystemExit(f"--param must be key=value, got '{p}'")
        k, v = p.split("=", 1)
        out[k] = v
    return out


def cmd_discover(args) -> int:
    agent = DiscoveryAgent()
    try:
        artifact = agent.discover(goal=args.goal, target_url=args.url,
                                  capability_name=args.name, app=args.app)
    finally:
        if not agent.cfg.headless:
            input("\n[discovery finished — browser left open] Press Enter to close it... ")
        agent.surface.close()
    path = Catalog().save(artifact)
    print(f"\n✔ Discovered capability '{artifact.name}' → {path}")
    print(f"  steps={len(artifact.steps)} outputs={[o.name for o in artifact.outputs]}")
    print(f"  approval={artifact.approval.value} (review + approve before unattended replay)")
    return 0


def cmd_replay(args) -> int:
    cat = Catalog()
    art = cat.load(args.name)
    params = _parse_params(args.param)

    if args.repeat > 1:
        return _replay_stability(art, params, args)

    engine = ReplayEngine(allow_assisted_recovery=args.assisted)
    try:
        result = engine.replay(art, params, tenant=args.tenant)
    finally:
        engine.surface.close()
    print(json.dumps(result.model_dump(mode="json"), indent=2, default=str))
    return 0 if result.status.value in ("success", "business_outcome") else 2


def _replay_stability(art, params, args) -> int:
    """Stretch: replay N times and report a stability/flakiness signal — the same
    status and outputs every run is what we want from a deterministic capability."""
    statuses, output_sets = [], set()
    for _ in range(args.repeat):
        engine = ReplayEngine(allow_assisted_recovery=args.assisted)
        try:
            r = engine.replay(art, params, tenant=args.tenant)
        finally:
            engine.surface.close()
        statuses.append(r.status.value)
        output_sets.add(json.dumps(r.outputs, sort_keys=True))
    stable = len(set(statuses)) == 1 and len(output_sets) == 1
    print(json.dumps({
        "capability": art.name, "runs": args.repeat,
        "status_counts": {s: statuses.count(s) for s in set(statuses)},
        "distinct_output_sets": len(output_sets),
        "stable": stable,
    }, indent=2))
    return 0 if stable else 2


def cmd_catalog(args) -> int:
    print(json.dumps(Catalog().list(), indent=2))
    return 0


def cmd_serve(args) -> int:
    import uvicorn
    uvicorn.run("server.app:app", host=args.host, port=args.port, reload=False)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="cua", description="Computer-Use Automation System")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("discover", help="LLM discovery run -> capability artifact")
    d.add_argument("--goal", required=True)
    d.add_argument("--url", required=True)
    d.add_argument("--name", required=True)
    d.add_argument("--app", default="mock_bank")
    d.set_defaults(func=cmd_discover)

    r = sub.add_parser("replay", help="Deterministic replay of a saved artifact")
    r.add_argument("--name", required=True)
    r.add_argument("--param", action="append", default=[], help="key=value (repeatable)")
    r.add_argument("--tenant", default=None)
    r.add_argument("--assisted", action="store_true", help="allow bounded LLM recovery")
    r.add_argument("--repeat", type=int, default=1,
                   help="replay N times and report a stability signal instead of one result")
    r.set_defaults(func=cmd_replay)

    c = sub.add_parser("catalog", help="List saved capabilities")
    c.set_defaults(func=cmd_catalog)

    s = sub.add_parser("serve", help="Operator console + catalog API (FastAPI/uvicorn)")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
