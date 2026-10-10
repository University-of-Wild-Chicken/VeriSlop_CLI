"""`verislop run` and `verislop resume`: the full pipeline in one run package.

    prompt -> classify/interpret -> draft + ledger -> formalize + statement check -> freeze
    -> prove (untrusted) -> accept (isolated replay + audits) -> export (accepted IR)
    -> [review formal_contract] -> generate (tier) -> link -> [review implementation]
    -> test -> [review release] (with interpretation review immediately after interpretation)
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
from .errors import Diagnostic, InfrastructureError, UsageError, VeriSlopError
from .events import EventSink
from .package import Package, find_runs_dir, new_run_id
from .stage import StageResult
from .bridges.vscore_checker import EdgeFailure
from .bridges.vscore3_checker import EdgeFailure as EdgeFailure3

STAGES = ("interpret", "review:interpretation", "formalize", "prove", "accept", "export", "review:formal_contract",
          "bridge:prepare", "generate", "link", "review:implementation", "test",
          "review:release", "verify")


def _proceed(stage: str, pkg: Package, res: StageResult) -> bool:
    if res.status == "INFRASTRUCTURE_FAILURE":
        return False
    if stage in ("generate", "link", "bridge:accept"):
        from .backends.registry import is_vscore

        if is_vscore(pkg):
            return res.status == "PASS"
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
    if type(args.budget_seconds) is not int or args.budget_seconds < 0:
        raise UsageError("--budget-seconds must be a nonnegative integer; 0 disables the proof-search deadline")

    def ap(x: str | None) -> str | None:
        return str(Path(x).resolve()) if x else None

    return {
        "prompt_file": ap(args.prompt_file), "mode": args.mode, "tier": args.tier, "target": args.target,
        "endpoint": args.endpoint, "require_state": args.require_state, "policy": args.policy,
        "backend_version": getattr(args, "backend_version", None),
        "source_policy": os.path.abspath(args.source_policy) if getattr(args, "source_policy", None) else None,
        "config": ap(args.config), "request_ref": args.request_ref or args.prompt_file,
        "draft_candidate": ap(args.draft_candidate), "ledger_candidate": ap(args.ledger_candidate),
        "formalization_candidate": ap(args.formalization_candidate), "proof_candidate": ap(args.proof_candidate),
        "implementation_candidate": ap(args.implementation_candidate), "bindings_candidate": ap(args.bindings_candidate),
        "bridge_proposal": os.path.abspath(args.bridge_proposal) if getattr(args, "bridge_proposal", None) else None,
        "bridge_candidate_dir": os.path.abspath(args.bridge_candidate_dir) if getattr(args, "bridge_candidate_dir", None) else None,
        "bridge_id": getattr(args, "bridge_id", None),
        "tests_flag": ("no_tests" if getattr(args, "no_tests", False) else "require_tests"
                       if getattr(args, "require_tests", False) else "omitted"),
        "resolve": list(args.resolve or []), "non_interactive": bool(args.non_interactive),
        "budget_seconds": args.budget_seconds, "seed": args.seed, "cases": args.cases,
        "repair_rounds": getattr(args, "repair_rounds", None),
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
        from .autonomous import critic_agent
        agent = agents.formalizer_agent(cfg, pkg, ev) if (cfg and not p["formalization_candidate"]) else None
        return formalize.run(pkg, ev, candidate=Path(p["formalization_candidate"]) if p["formalization_candidate"] else None,
                             policy_name=p["policy"], agent=agent,
                             critic=critic_agent(cfg, pkg, ev) if agent else None,
                             recovery_critique=p.get("recovery_context", {}).get("autonomous_critique"),
                             recovery_feedback=p.get("recovery_context", {}).get("feedback"),
                             previous_candidate=p.get("recovery_context", {}).get("previous_candidate"))
    if name == "prove":
        from .autonomous import critic_agent
        agent = agents.prover_agent(cfg, pkg, ev) if cfg else None
        return prove.run(pkg, ev, candidate=Path(p["proof_candidate"]) if p["proof_candidate"] else None,
                         budget_seconds=p["budget_seconds"], agent=agent,
                         critic=critic_agent(cfg, pkg, ev) if agent else None)
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
        adopting = p.get("target") == "vscore" and p.get("bridge_id") and not p["implementation_candidate"]
        agent = agents.implementer_agent(cfg, pkg, ev) if (cfg and not p["implementation_candidate"] and not adopting) else None
        return generate.run(pkg, ev, tier=p["tier"], target=p["target"], endpoint=p["endpoint"], require_state=p["require_state"],
                            candidate=Path(p["implementation_candidate"]) if p["implementation_candidate"] else None,
                            bindings=Path(p["bindings_candidate"]) if p["bindings_candidate"] else None, agent=agent,
                            bridge_id=p.get("bridge_id"), tests_flag=p.get("tests_flag", "omitted"),
                            backend_version=p.get("backend_version"))
    if name == "link":
        return link.run(pkg, ev)
    if name == "bridge:accept":
        from .backends.registry import implementation_backend, semantic_backend
        selection = implementation_backend(pkg).selection
        bridge_accept = semantic_backend(pkg).accept

        return bridge_accept(pkg, selection(pkg)["bridge_id"], ev)
    if name == "release:finalize":
        from .backends.registry import closure_backend
        mechanical_snapshot = closure_backend(pkg).mechanical_snapshot
        from .backends.registry import frozen_backend, VSCORE3_ID
        backend, _ = frozen_backend(pkg)
        if backend and backend["id"] == VSCORE3_ID:
            from .backends.vscore3_release import finalize
        else:
            from .backends.vscore_release import finalize

        snapshot = mechanical_snapshot(pkg)
        return finalize(pkg, ev, snapshot, config=Path(cfg) if cfg else None,
                        endpoint=p["endpoint"], require_state=p["require_state"])
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
    if p.get("tier") == 2 and p.get("target") == "vscore":
        ordered = ["interpret", "review:interpretation", "formalize", "prove", "accept", "export",
                   "review:formal_contract", "bridge:prepare", "generate", "link", "bridge:accept",
                   "review:implementation", "verify", "review:release", "release:finalize"]
        return [s for s in ordered if (s != "bridge:prepare" or p.get("bridge_proposal"))
                and (not s.startswith("review:") or _review_configured(p.get("config"), s.split(":", 1)[1]))]
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


def _execute_once(pkg: Package, ev: EventSink, p: dict[str, Any], start_after: set[str]) -> StageResult:
    history: list[dict[str, Any]] = list(pkg.meta().get("stage_history", []))
    collected: list[Diagnostic] = []
    final: StageResult | None = None
    stopped_at = None
    failed_stage: StageResult | None = None
    stage = None
    vscore_pipeline = p.get("tier") == 2 and p.get("target") == "vscore"
    if vscore_pipeline:
        # A resume is a fresh verification request, even after an earlier success.
        # Recorded completion never substitutes for the two clean executions.
        start_after = start_after - {"verify", "review:release", "release:finalize"}
    try:
        for stage in _stages_for(p):
            if stage in start_after:
                continue
            if stage == "verify" and not vscore_pipeline:
                break
            t0 = time.time()
            res = _run_stage(stage, pkg, ev, p)
            history.append({"stage": stage, "status": res.status, "codes": sorted({d.code for d in res.diagnostics}),
                            "seconds": int(time.time() - t0)})
            pkg.set_meta("stage_history", history)
            mechanical_pass = (stage == "verify" and vscore_pipeline and res.summary.get("mechanical_status") == "VERIFIED")
            if not mechanical_pass:
                collected.extend(d for d in res.diagnostics if d.severity in ("blocking", "infrastructure"))
            if stage in ("verify", "release:finalize"):
                final = res
            if stage == "verify" and vscore_pipeline and not mechanical_pass:
                stopped_at = stage
                failed_stage = res
                break
            if not _proceed(stage, pkg, res):
                stopped_at = stage
                failed_stage = res
                ev.emit("diagnostic", "run", f"pipeline stops after {stage}: {res.status}")
                break
            pkg.set_meta("completed_stages", sorted(_completed(pkg) | {stage}))
        if final is None:
            final = _run_stage("verify", pkg, ev, p)
        elif vscore_pipeline and final.summary.get("mechanical_status") == "VERIFIED" and stopped_at:
            # Preserve the mechanical fact when a separately required review rejects it.
            final = _run_stage("release:finalize", pkg, ev, p)
    except KeyboardInterrupt:
        ev.emit("diagnostic", "run", "interrupted; recording an incomplete run")
        _interrupted_report(pkg, collected, p)
        raise
    except (VeriSlopError, EdgeFailure, EdgeFailure3) as exc:
        collected.extend(exc.diagnostics)
        if not exc.diagnostics:
            collected.append(Diagnostic("INVALID_CANDIDATE", str(exc)))
        stopped_at = stage
        from .stage import status_from

        failed_stage = StageResult(stage or "run", status_from(exc.diagnostics or collected), "candidate stage did not complete",
                                   diagnostics=list(exc.diagnostics or collected))
        if not history or history[-1]["stage"] != stage:
            history.append({"stage": stage, "status": failed_stage.status,
                            "codes": sorted({d.code for d in failed_stage.diagnostics}), "seconds": 0})
            pkg.set_meta("stage_history", history)
        try:
            final = _run_stage("verify", pkg, ev, p)
        except (VeriSlopError, EdgeFailure, EdgeFailure3) as verify_error:
            from .stage import status_from

            collected.extend(verify_error.diagnostics)
            final = StageResult("verify", status_from(collected), "pipeline did not complete verification")
            final.diagnostics = list(collected)
    assert final is not None
    seen = {(d.code, d.message) for d in final.diagnostics}
    final.diagnostics = [d for d in collected if (d.code, d.message) not in seen] + final.diagnostics
    if any(d.severity == "infrastructure" for d in final.diagnostics):
        final.status = "INFRASTRUCTURE_FAILURE"
    _ensure_report(pkg, final, p)
    _record_aggregate_infrastructure(pkg, final, p)
    if stopped_at:
        final.lines.insert(0, f"pipeline stopped after `{stopped_at}`; downstream stages did not run")
    final.command = "run"
    final.summary["run_id"] = pkg.run_id
    final.summary["package"] = str(pkg.root)
    final.summary["stages"] = history
    final.summary["stopped_at"] = stopped_at
    if failed_stage is not None:
        final.summary["failed_stage_diagnostics"] = [d.to_json() for d in failed_stage.diagnostics]
        final.summary["failed_stage_summary"] = failed_stage.summary
    final.artifacts["package"] = str(pkg.root)
    return final


def _execute(root: Package, ev: EventSink, p: dict[str, Any], start_after: set[str]) -> StageResult:
    """Run strict gates; a rejected agent contract can restart in a fresh package."""
    from . import recovery

    active, rounds, recorded_maximum = recovery.resolve_active(root)
    override = p.get("_repair_rounds_override")
    selected_parameters = {**p, "repair_rounds": override} if override is not None else p
    maximum = recovery.budget(selected_parameters) if override is not None or not rounds else recorded_maximum
    if maximum < len(rounds):
        raise UsageError("--repair-rounds cannot be lower than the already consumed recovery rounds")
    budget_policy = (recovery.select_policy(root, maximum, allow_override=override is not None)
                     if rounds else None)
    if rounds:
        # Publish an authorized budget decision before the next untrusted stage.
        # Cancellation must not leave a durable decision unlinked by the journal,
        # causing the following override to reuse its immutable decision number.
        recovery.write_journal(root, active, rounds, maximum, budget_policy=budget_policy)
    parameters = dict(p)
    parameters.pop("_repair_rounds_override", None)
    parameters["repair_rounds"] = maximum
    while True:
        if active.root == root.root:
            result = _execute_once(active, ev, parameters, start_after)
        else:
            with fsutil.package_lock(active.root):
                child_events = EventSink(active.run_id, active.root, quiet=ev.quiet)
                try:
                    result = _execute_once(active, child_events, parameters, start_after)
                finally:
                    child_events.close()
        if len(rounds) >= maximum or not recovery.eligible(result, parameters, active):
            break
        if budget_policy is None:
            budget_policy = recovery.select_policy(root, maximum, allow_override=override is not None)
        if active.root == root.root:
            child, parameters, record = recovery.create(root, active, parameters, result, len(rounds) + 1, ev,
                                                        budget_policy=budget_policy)
        else:
            with fsutil.package_lock(active.root):
                child, parameters, record = recovery.create(root, active, parameters, result, len(rounds) + 1, ev,
                                                            budget_policy=budget_policy)
        rounds = [*rounds, record]
        active = child
        recovery.write_journal(root, active, rounds, maximum, budget_policy=budget_policy)
        start_after = {"interpret"}
    if rounds:
        recovery.write_journal(root, active, rounds, maximum, result, budget_policy=budget_policy)
        result.artifacts["recovery_journal"] = str(root.root / "recovery.json")
    result.summary["active_package"] = str(active.root)
    result.summary["root_package"] = str(root.root)
    result.summary["recovery"] = {"enabled": bool(maximum and parameters.get("config")),
                                  "max_rounds": maximum, "consumed_rounds": len(rounds),
                                  "packages": [str(root.root), *[str(root.root.parent / r["package"]) for r in rounds]],
                                  "exhausted": bool(len(rounds) >= maximum and maximum
                                                    and recovery.eligible(result, parameters, active))}
    return result


def _record_aggregate_infrastructure(pkg: Package, result: StageResult, parameters: dict[str, Any]) -> None:
    """Earlier provider failures retain their classification after final verification.

    The final verifier may report missing downstream inputs as BLOCKED; that does
    not convert the earlier operational failure into a contract counterexample.
    A validated VSCore mechanical result remains separate from release failure.
    """
    if not any(d.severity == "infrastructure" for d in result.diagnostics):
        return
    from . import report as reportmod

    record = canonical.load_file(pkg.path("report"))
    record["terminal_status"] = "INFRASTRUCTURE_FAILURE"
    record["infrastructure_errors"] = [d.to_json() for d in result.diagnostics if d.severity == "infrastructure"]
    record["blocking_reasons"] = [d.to_json() for d in result.diagnostics if d.severity == "blocking"]
    if "release_status" in record:
        record["release_status"] = "INFRASTRUCTURE_FAILURE"
        result.summary["release_status"] = "INFRASTRUCTURE_FAILURE"
    if record.get("mechanical_status") == "VERIFIED":
        record["qualified_result"] = ("VERIFIED closure; END_TO_END_VERIFIED "
                                      f"[restricted_source; {record.get('language', parameters.get('language', 'vscore/0.1'))}]; release infrastructure_failure")
    else:
        record["qualified_result"] = reportmod._qualified("INFRASTRUCTURE_FAILURE", parameters, result.diagnostics)
    reportmod.validate(record)
    fsutil.write_json(pkg.path("report"), record, pretty=True)
    result.status = "INFRASTRUCTURE_FAILURE"
    result.summary["terminal_status"] = "INFRASTRUCTURE_FAILURE"
    result.summary["qualified_result"] = record["qualified_result"]
    result.lines = reportmod.render_lines(record)


def _ensure_report(pkg: Package, result: StageResult, parameters: dict[str, Any]) -> None:
    """Even admission/infrastructure exits before a closure freeze get a bounded report."""
    if "report" in result.artifacts and pkg.path("report").is_file():
        return
    from . import report as reportmod, view

    terminal = "INFRASTRUCTURE_FAILURE" if result.status == "INFRASTRUCTURE_FAILURE" else "BLOCKED"
    record = reportmod.build(pkg, view.derive(pkg), terminal, result.diagnostics, [],
        {"compared": [], "mismatches": []}, parameters, parameters.get("endpoint"),
        parameters.get("require_state"), None, [], {"configured": bool(parameters.get("config"))}, pkg.file_digest("accepted_ir"))
    reportmod.validate(record)
    fsutil.write_json(pkg.path("report"), record, pretty=True)


def _interrupted_report(pkg: Package, diags: list[Diagnostic], parameters: dict[str, Any] | None = None) -> None:
    from . import report as reportmod, view

    try:
        v = view.derive(pkg)
        d = diags + [Diagnostic("INTERRUPTED", "the run was cancelled; required checks remain unresolved")]
        params = parameters or {}
        rep = reportmod.build(pkg, v, "BLOCKED", d, [], {"compared": [], "mismatches": []}, params,
                              params.get("endpoint"), params.get("require_state"), None, [],
                              {"configured": bool(params.get("config"))}, None)
        rep["qualified_result"] = "INTERRUPTED: incomplete run; no verification success"
        reportmod.validate(rep)
        fsutil.write_json(pkg.path("report"), rep, pretty=True)
    except Exception:  # noqa: BLE001 - best effort while handling cancellation
        pass


def run(args: argparse.Namespace) -> StageResult:
    params = _params_from_args(args)
    if bool(params["bridge_proposal"]) != bool(params["bridge_candidate_dir"]):
        raise UsageError("--bridge-proposal and --bridge-candidate-dir must be supplied together")
    if params.get("tier") == 2 and params.get("target") == "vscore" and params["bridge_proposal"]:
        if params["implementation_candidate"]:
            raise UsageError("choose either a prepared bridge proposal or an implementation candidate")
        proposal_id = canonical.load_file(Path(params["bridge_proposal"]))["bridge_id"]
        if params["bridge_id"] and params["bridge_id"] != proposal_id:
            raise UsageError("--bridge-id must match the selected proposal")
        params["bridge_id"] = proposal_id
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
               "require_state": args.require_state, "policy": args.policy,
               "backend_version": getattr(args, "backend_version", None)}
        pkg.set_meta("requested", req)
        if params.get("source_policy"):
            from . import source_policy

            source_policy.stage(pkg, Path(params["source_policy"]))
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
    root = Package(runs / args.run_id, resolve_root=False)
    if not root.exists():
        raise UsageError(f"no run {args.run_id} under {runs}")
    with fsutil.package_lock(root.root):
        from . import recovery

        pkg, rounds, _ = recovery.resolve_active(root)
        params = dict(pkg.meta().get("run_parameters") or {})
        if not params:
            raise UsageError("this package was not created by `verislop run`; resume the individual stages instead")
        if args.config:
            params["config"] = str(Path(args.config).resolve())
        if getattr(args, "repair_rounds", None) is not None:
            params["repair_rounds"] = args.repair_rounds
            params["_repair_rounds_override"] = args.repair_rounds
            if args.repair_rounds < len(rounds):
                raise UsageError("--repair-rounds cannot be lower than the already consumed recovery rounds")
        else:
            params.pop("_repair_rounds_override", None)
        ev = EventSink(pkg.run_id, pkg.root, args.events, quiet=args.quiet)
        ev.emit("run_started", "resume", f"resuming {pkg.run_id}: checking the complete frozen root")
        problems: list[Diagnostic] = []
        from . import source_policy

        _, source_policy_diags = source_policy.load(pkg)
        problems.extend(source_policy_diags)
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
        if params.get("tier") == 2 and params.get("target") == "vscore":
            from .backends.registry import implementation_backend
            selection = implementation_backend(pkg).selection
            from .backends.registry import closure_backend
            validate_frozen = closure_backend(pkg).validate_frozen
            from .bridges.manifest import InvalidPackage

            if (pkg.root / "closure/selection.json").is_file():
                try:
                    selection(pkg)
                except (EdgeFailure, EdgeFailure3, InvalidPackage, VeriSlopError, OSError, ValueError, KeyError) as exc:
                    problems.extend(getattr(exc, "diagnostics", None) or
                                    [Diagnostic(getattr(exc, "code", "INPUT_MUTATION"), str(exc))])
            if (pkg.root / "closure/manifest.json").is_file():
                problems.extend(validate_frozen(pkg))
        if problems:
            from .stage import status_from

            res = StageResult("resume", status_from(problems), "frozen root verified before resuming")
            res.diagnostics = problems
            _ensure_report(pkg, res, params)
            return res
        done = _completed(pkg)
        res = _execute(root, ev, params, done)
        res.command = "resume"
        return res
