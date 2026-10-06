"""`verislop run` and `verislop resume`: the full pipeline in one run package.

    prompt -> classify/interpret -> draft + ledger -> formalize + statement check -> freeze
    -> prove (untrusted) -> accept (isolated replay + audits) -> export (accepted IR)
    -> [review formal_contract] -> generate (tier) -> link -> test -> [review release]
    -> verify (two clean builds, provenance) -> report.json

Each stage proceeds only when the artifact it needs exists and passed its own gate; independent
obligations continue where the specification allows (an ambiguity blocks only dependent
guarantees). The terminal report is always written, including for blocked, interrupted and
infrastructure-failed runs. Concurrent writers cannot update the same run.
"""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, canonical, fsutil
from .errors import Diagnostic, InfrastructureError, UsageError
from .events import EventSink
from .package import Package, find_runs_dir, new_run_id
from .stage import StageResult

STAGES = ("interpret", "formalize", "prove", "accept", "export", "review:formal_contract", "bridge:prepare", "generate", "link", "test",
          "review:release", "verify")


def _proceed(stage: str, pkg: Package, res: StageResult) -> bool:
    if res.status == "INFRASTRUCTURE_FAILURE":
        return False
    if stage == "interpret":
        evs = [e for e in pkg.evidence.for_claim("INTERPRETATION:request") if e.valid]
        return bool(evs) and evs[-1].result.get("milestone_outcome") == "PASS"
    if stage == "formalize":
        from .contract import challenge_dir

        return (challenge_dir(pkg) / "challenge.json").is_file()
    if stage == "prove":
        return (pkg.path("contract") / "proofs" / "candidate.lean").is_file()
    if stage == "accept":
        p = pkg.path("accepted") / "acceptance.json"
        return p.is_file() and canonical.load_file(p)["gate"] == "accepted_and_proved"
    if stage == "export":
        return pkg.path("accepted_ir").is_file() and res.status == "PASS"
    if stage == "bridge:prepare":
        return res.status == "PASS"
    if stage == "generate":
        fatal = {"UNSUPPORTED_CAPABILITY", "CLAIM_MUTATION", "INVALID_CANDIDATE", "STALE_OR_UNBOUND_EVIDENCE"}
        return ((pkg.path("bridges") / "bindings.json").is_file() and pkg.path("implementation").is_dir()
                and not any(d.code in fatal and d.severity == "blocking" for d in res.diagnostics))
    if stage.startswith("review:"):
        return res.status == "PASS"
    return True


def _params_from_args(args: argparse.Namespace) -> dict[str, Any]:
    def ap(x: str | None) -> str | None:
        return str(Path(x).resolve()) if x else None

    return {
        "prompt_file": ap(args.prompt_file), "mode": args.mode, "tier": args.tier, "target": args.target,
        "endpoint": args.endpoint, "require_state": args.require_state, "policy": args.policy,
        "config": ap(args.config), "request_ref": args.request_ref or args.prompt_file,
        "draft_candidate": ap(args.draft_candidate), "ledger_candidate": ap(args.ledger_candidate),
        "formalization_candidate": ap(args.formalization_candidate), "proof_candidate": ap(args.proof_candidate),
        "implementation_candidate": ap(args.implementation_candidate), "bindings_candidate": ap(args.bindings_candidate),
        "bridge_proposal": os.path.abspath(args.bridge_proposal) if getattr(args, "bridge_proposal", None) else None,
        "bridge_candidate_dir": os.path.abspath(args.bridge_candidate_dir) if getattr(args, "bridge_candidate_dir", None) else None,
        "resolve": list(args.resolve or []), "non_interactive": bool(args.non_interactive),
        "budget_seconds": args.budget_seconds, "seed": args.seed, "cases": args.cases,
        "attachments": [ap(a) for a in (args.attachment or [])], "repository_revision": args.repository_revision,
    }


def _run_stage(name: str, pkg: Package, ev: EventSink, p: dict[str, Any]) -> StageResult:
    from . import accept, agents, closure, export, formalize, generate, interpret, link, prove, testing

    cfg = p.get("config")
    if name == "interpret":
        kv = dict(x.split("=", 1) for x in p["resolve"])
        agent = agents.interpreter_agent(cfg, pkg, ev) if (cfg and not p["draft_candidate"]) else None
        return interpret.run(pkg, ev, Path(p["prompt_file"]), mode=p["mode"], request_ref=p["request_ref"],
                             candidate=Path(p["draft_candidate"]) if p["draft_candidate"] else None,
                             ledger_path=Path(p["ledger_candidate"]) if p["ledger_candidate"] else None,
                             resolutions=kv, interactive=not p["non_interactive"], agent=agent,
                             attachments=[Path(a) for a in p.get("attachments", [])],
                             repository_revision=p.get("repository_revision"))
    if name == "formalize":
        agent = agents.formalizer_agent(cfg, pkg, ev) if (cfg and not p["formalization_candidate"]) else None
        return formalize.run(pkg, ev, candidate=Path(p["formalization_candidate"]) if p["formalization_candidate"] else None,
                             policy_name=p["policy"], agent=agent)
    if name == "prove":
        agent = agents.prover_agent(cfg, pkg, ev) if cfg else None
        return prove.run(pkg, ev, candidate=Path(p["proof_candidate"]) if p["proof_candidate"] else None,
                         budget_seconds=p["budget_seconds"], agent=agent)
    if name == "accept":
        return accept.run(pkg, ev, policy_name=p["policy"])
    if name == "export":
        return export.run(pkg, ev)
    if name == "bridge:prepare":
        from .bridges import prepare
        from .capabilities import normalize_endpoint

        return prepare.run(pkg, ev, Path(p["bridge_proposal"]), Path(p["bridge_candidate_dir"]),
                           expected_tier=p.get("tier"),
                           expected_endpoint=normalize_endpoint(p["endpoint"], p.get("tier", 0))
                           if p.get("endpoint") else None)
    if name.startswith("review:"):
        from . import review

        return review.run(pkg, ev, Path(cfg), checkpoint=name.split(":", 1)[1])
    if name == "generate":
        agent = agents.implementer_agent(cfg, pkg, ev) if (cfg and not p["implementation_candidate"]) else None
        return generate.run(pkg, ev, tier=p["tier"], target=p["target"], endpoint=p["endpoint"], require_state=p["require_state"],
                            candidate=Path(p["implementation_candidate"]) if p["implementation_candidate"] else None,
                            bindings=Path(p["bindings_candidate"]) if p["bindings_candidate"] else None, agent=agent)
    if name == "link":
        return link.run(pkg, ev)
    if name == "test":
        return testing.run(pkg, ev, seed=p["seed"], cases=p["cases"])
    if name == "verify":
        return closure.run(pkg, ev, endpoint=p["endpoint"], require_state=p["require_state"],
                           config=Path(cfg) if cfg and _review_configured(cfg, "release") else None)
    raise UsageError(name)


def _review_configured(cfg: str | None, checkpoint: str) -> bool:
    if not cfg:
        return False
    try:
        conf = canonical.load_file(cfg)
    except Exception:  # noqa: BLE001
        return False
    return checkpoint in conf.get("review", {}).get("checkpoints", [])


def _stages_for(p: dict[str, Any]) -> list[str]:
    out = []
    for s in STAGES:
        if s == "bridge:prepare" and not p.get("bridge_proposal"):
            continue
        if s.startswith("review:") and not _review_configured(p.get("config"), s.split(":", 1)[1]):
            continue
        out.append(s)
    return out


def _completed(pkg: Package) -> set[str]:
    return set(pkg.meta().get("completed_stages", []))


def _execute(pkg: Package, ev: EventSink, p: dict[str, Any], start_after: set[str]) -> StageResult:
    history: list[dict[str, Any]] = list(pkg.meta().get("stage_history", []))
    collected: list[Diagnostic] = []
    final: StageResult | None = None
    stopped_at = None
    try:
        for stage in _stages_for(p):
            if stage in start_after:
                continue
            if stage == "verify":
                break
            t0 = time.time()
            res = _run_stage(stage, pkg, ev, p)
            history.append({"stage": stage, "status": res.status, "codes": sorted({d.code for d in res.diagnostics}),
                            "seconds": int(time.time() - t0)})
            pkg.set_meta("stage_history", history)
            collected.extend(d for d in res.diagnostics if d.severity in ("blocking", "infrastructure"))
            if not _proceed(stage, pkg, res):
                stopped_at = stage
                ev.emit("diagnostic", "run", f"pipeline stops after {stage}: {res.status}")
                break
            pkg.set_meta("completed_stages", sorted(_completed(pkg) | {stage}))
        final = _run_stage("verify", pkg, ev, p)
    except KeyboardInterrupt:
        ev.emit("diagnostic", "run", "interrupted; recording an incomplete run")
        _interrupted_report(pkg, collected)
        raise
    except InfrastructureError as exc:
        collected.extend(exc.diagnostics)
        final = _run_stage("verify", pkg, ev, p)
    assert final is not None
    seen = {(d.code, d.message) for d in final.diagnostics}
    final.diagnostics = [d for d in collected if (d.code, d.message) not in seen] + final.diagnostics
    if stopped_at:
        final.lines.insert(0, f"pipeline stopped after `{stopped_at}`; downstream stages did not run")
    final.command = "run"
    final.summary["run_id"] = pkg.run_id
    final.summary["package"] = str(pkg.root)
    final.summary["stages"] = history
    final.artifacts["package"] = str(pkg.root)
    return final


def _interrupted_report(pkg: Package, diags: list[Diagnostic]) -> None:
    from . import report as reportmod, view

    try:
        v = view.derive(pkg)
        d = diags + [Diagnostic("INTERRUPTED", "the run was cancelled; required checks remain unresolved")]
        rep = reportmod.build(pkg, v, "BLOCKED", d, [], {"compared": [], "mismatches": []}, {}, None, None, None, [], {"configured": False}, None)
        rep["qualified_result"] = "INTERRUPTED: incomplete run; no verification success"
        fsutil.write_json(pkg.path("report"), rep, pretty=True)
    except Exception:  # noqa: BLE001 - best effort while handling cancellation
        pass


def run(args: argparse.Namespace) -> StageResult:
    params = _params_from_args(args)
    if bool(params["bridge_proposal"]) != bool(params["bridge_candidate_dir"]):
        raise UsageError("--bridge-proposal and --bridge-candidate-dir must be supplied together")
    if args.tier is not None and args.tier not in range(5):
        raise UsageError("--tier must be 0..4")
    runs = Path(args.runs_dir) if args.runs_dir else find_runs_dir()
    run_id = args.run_id or new_run_id()
    root = runs / run_id
    if (root / "package.json").exists():
        raise UsageError(f"run {run_id} already exists; use `verislop resume --run-id {run_id}`")
    pkg = Package(root, resolve_root=False)
    with fsutil.package_lock(root):
        pkg.ensure(run_id)
        pkg.set_meta("run_parameters", params)
        req = {"schema_version": SCHEMA_VERSION, "tier": args.tier, "target": args.target, "endpoint": args.endpoint,
               "require_state": args.require_state, "policy": args.policy}
        pkg.set_meta("requested", req)
        if args.config:
            from .providers import config as pconfig

            conf = pconfig.load(Path(args.config))
            fsutil.write_json(pkg.path("closure") / "review-config.json", conf, pretty=True)
        ev = EventSink(run_id, pkg.root, args.events, quiet=args.quiet)
        ev.emit("run_started", "run", f"run {run_id} in {pkg.root}")
        return _execute(pkg, ev, params, set())


def resume(args: argparse.Namespace) -> StageResult:
    from . import contract
    from .export import verify_certificate

    runs = Path(args.runs_dir) if args.runs_dir else find_runs_dir()
    pkg = Package(runs / args.run_id, resolve_root=False)
    if not pkg.exists():
        raise UsageError(f"no run {args.run_id} under {runs}")
    with fsutil.package_lock(pkg.root):
        params = dict(pkg.meta().get("run_parameters") or {})
        if not params:
            raise UsageError("this package was not created by `verislop run`; resume the individual stages instead")
        if args.config:
            params["config"] = str(Path(args.config).resolve())
        ev = EventSink(pkg.run_id, pkg.root, args.events, quiet=args.quiet)
        ev.emit("run_started", "resume", f"resuming {pkg.run_id}: checking the complete frozen root")
        problems: list[Diagnostic] = []
        if (contract.challenge_dir(pkg) / "challenge.json").is_file():
            _, fd = contract.load_frozen(pkg)
            problems.extend(fd)
        cert = pkg.path("accepted") / "acceptance.json"
        if cert.is_file():
            _, _, cd = verify_certificate(pkg, cert)
            problems.extend(cd)
        from .bridges.prepare import verify_preparations

        _, preparation_diags = verify_preparations(pkg)
        problems.extend(preparation_diags)
        if problems:
            from .stage import status_from

            res = StageResult("resume", status_from(problems), "frozen root verified before resuming")
            res.diagnostics = problems
            return res
        done = _completed(pkg)
        res = _execute(pkg, ev, params, done)
        res.command = "resume"
        return res
