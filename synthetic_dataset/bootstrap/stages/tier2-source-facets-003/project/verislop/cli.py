"""`verislop` command-line interface (specification §11).

Conventions:
* `--json` writes one machine-readable result object to stdout; progress goes to stderr.
* `--events PATH` (or `-` for stderr) additionally streams schema-versioned JSON Lines events.
* Exit codes: 0 the command completed and its requested gate passed; 2 blocked;
  3 infrastructure failure; 64 invalid invocation. A non-verification command returning 0
  does not assert closure VERIFIED.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__, canonical, fsutil
from .errors import (
    EXIT_INTERRUPTED, EXIT_USAGE, Diagnostic, UsageError, VeriSlopError,
)
from .events import EventSink
from .package import Package
from .stage import StageResult


WRITING_COMMANDS = {"interpret", "formalize", "prove", "accept", "export", "generate", "link", "test", "verify", "review", "status"}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # invalid invocation -> 64
        self.print_usage(sys.stderr)
        sys.stderr.write(f"verislop: error: {message}\n")
        sys.exit(EXIT_USAGE)


def _wall_budget_seconds(value: str) -> int:
    """Zero explicitly disables an orchestration wall budget; negatives are invalid."""
    try:
        seconds = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("wall budget must be a nonnegative integer") from None
    if seconds < 0:
        raise argparse.ArgumentTypeError("wall budget must be nonnegative; 0 disables the deadline")
    return seconds


def _kv(values: list[str] | None, flag: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise UsageError(f"{flag} expects KEY=VALUE, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _package(args: argparse.Namespace, create: bool = True, *, resolve_root: bool = True) -> Package:
    pkg = Package(Path(args.package), resolve_root=resolve_root)
    if create:
        pkg.ensure()
    elif not pkg.exists():
        raise UsageError(f"{pkg.root} is not a VeriSlop run package; run `verislop interpret` or `verislop run` first")
    return pkg


def _events(args: argparse.Namespace, pkg: Package | None) -> EventSink:
    run_id = pkg.run_id if pkg and pkg.exists() else "no-run"
    return EventSink(run_id, pkg.root if pkg and pkg.exists() else None, args.events, quiet=args.quiet or False)


def _render(result: StageResult, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json.dumps(result.to_json(), indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        return
    head = {"PASS": "PASS", "BLOCKED": "BLOCKED", "INFRASTRUCTURE_FAILURE": "INFRASTRUCTURE FAILURE"}[result.status]
    out = [f"verislop {result.command}: {head} — gate: {result.gate}"]
    out.extend(f"  {line}" for line in result.lines)
    for d in result.diagnostics:
        if d.severity == "info":
            continue
        where = f" [{', '.join(d.obligations)}]" if d.obligations else ""
        out.append(f"  {d.severity.upper():<14} {d.code}{where}: {d.message}")
    for name, path in sorted(result.artifacts.items()):
        out.append(f"  artifact {name}: {path}")
    if result.status == "PASS" and result.command not in ("verify", "run"):
        out.append("  (this command's gate passing does not assert closure VERIFIED)")
    sys.stdout.write("\n".join(out) + "\n")


# --------------------------------------------------------------------------------------------
# command handlers
# --------------------------------------------------------------------------------------------


def cmd_classify(args: argparse.Namespace) -> StageResult:
    from . import classify

    data = Path(args.prompt_file).read_bytes()
    routing = classify.classify(data, args.prompt_file) if args.mode == "auto" else classify.forced_software(data, args.prompt_file)
    res = StageResult("classify", "PASS", "routing decision produced (advisory; not evidence)")
    res.summary = routing
    res.lines = [f"decision: {routing['decision']} -> {routing['routing_result']}", f"reason: {routing['reason']}"]
    return res


def cmd_interpret(args: argparse.Namespace) -> StageResult:
    from . import interpret
    from .agents import interpreter_agent

    pkg = _package(args)
    ev = _events(args, pkg)
    agent = interpreter_agent(args.config, pkg, ev) if (args.config and not args.candidate) else None
    return interpret.run(
        pkg, ev, Path(args.prompt_file), mode=args.mode, request_ref=args.request_ref,
        candidate=Path(args.candidate) if args.candidate else None,
        ledger_path=Path(args.ledger) if args.ledger else None,
        resolutions=_kv(args.resolve, "--resolve"),
        interactive=not args.non_interactive,
        draft_out=Path(args.out) if args.out else None,
        agent=agent,
        attachments=[Path(a) for a in args.attachment or []],
        repository_revision=args.repository_revision,
    )


def cmd_formalize(args: argparse.Namespace) -> StageResult:
    from . import formalize
    from .autonomous import critic_agent
    from .agents import formalizer_agent

    pkg = _package(args, create=False)
    ev = _events(args, pkg)
    agent = formalizer_agent(args.config, pkg, ev) if (args.config and not args.candidate) else None
    return formalize.run(
        pkg, ev,
        draft_path=Path(args.draft) if args.draft else None,
        out=Path(args.out) if args.out else None,
        candidate=Path(args.candidate) if args.candidate else None,
        policy_name=args.policy, agent=agent, max_attempts=args.max_attempts,
        critic=critic_agent(args.config, pkg, ev) if agent else None,
    )


def cmd_prove(args: argparse.Namespace) -> StageResult:
    from . import prove
    from .autonomous import critic_agent
    from .agents import prover_agent

    pkg = _package(args, create=False)
    ev = _events(args, pkg)
    agent = prover_agent(args.config, pkg, ev) if args.config else None
    return prove.run(
        pkg, ev,
        contract=Path(args.contract) if args.contract else None,
        candidate=Path(args.candidate) if args.candidate else None,
        budget_seconds=args.budget_seconds, max_attempts=args.max_attempts,
        portfolio=not args.no_portfolio, agent=agent,
        critic=critic_agent(args.config, pkg, ev) if agent else None,
    )


def cmd_accept(args: argparse.Namespace) -> StageResult:
    from . import accept

    pkg = _package(args, create=False)
    return accept.run(pkg, _events(args, pkg), contract=Path(args.contract) if args.contract else None,
                      policy_name=args.policy)


def cmd_export(args: argparse.Namespace) -> StageResult:
    from . import export

    pkg = _package(args, create=False)
    return export.run(pkg, _events(args, pkg), accepted=Path(args.accepted) if args.accepted else None,
                      out=Path(args.out) if args.out else None)


def cmd_generate(args: argparse.Namespace) -> StageResult:
    from . import generate
    from .agents import implementer_agent

    pkg = _package(args, create=False)
    ev = _events(args, pkg)
    adopting = bool(args.bridge_id and not args.candidate)
    agent = implementer_agent(args.config, pkg, ev) if (args.config and not args.candidate and not adopting) else None
    return generate.run(
        pkg, ev, ir=Path(args.ir) if args.ir else None, tier=args.tier, target=args.target,
        endpoint=args.endpoint, require_state=args.require_state, backend_version=getattr(args, "backend_version", None),
        candidate=Path(args.candidate) if args.candidate else None,
        bindings=Path(args.bindings) if args.bindings else None, agent=agent,
        require_tests=None, tests_flag=("no_tests" if args.no_tests else "require_tests" if args.require_tests else "omitted"),
        bridge_id=args.bridge_id,
    )


def cmd_link(args: argparse.Namespace) -> StageResult:
    from . import link

    pkg = _package(args, create=False)
    return link.run(pkg, _events(args, pkg), ir=Path(args.ir) if args.ir else None,
                    implementation=Path(args.implementation) if args.implementation else None)


def cmd_test(args: argparse.Namespace) -> StageResult:
    from . import testing

    pkg = _package(args, create=False)
    return testing.run(pkg, _events(args, pkg), seed=args.seed, cases=args.cases, timeout=args.timeout)


def cmd_verify(args: argparse.Namespace) -> StageResult:
    from . import closure

    pkg = _package(args, create=False)
    result = closure.run(pkg, _events(args, pkg), endpoint=args.endpoint, require_state=args.require_state,
                         config=Path(args.config) if args.config else None)
    from .run import _ensure_report

    claims = pkg.path("closure") / "implementation-claims.json"
    params = pkg.meta().get("run_parameters") or {}
    try:
        frozen = canonical.load_file(claims) if claims.is_file() else {}
        if isinstance(frozen, dict) and isinstance(frozen.get("parameters"), dict):
            params = frozen["parameters"]
    except (OSError, ValueError):
        # The closure dispatcher already reports malformed frozen claims. Reporting
        # that failure must not try to parse the same invalid bytes unguarded.
        pass
    _ensure_report(pkg, result, params)
    return result


def cmd_run(args: argparse.Namespace) -> StageResult:
    from . import run as runmod

    return runmod.run(args)


def cmd_resume(args: argparse.Namespace) -> StageResult:
    from . import run as runmod

    return runmod.resume(args)


def cmd_inspect(args: argparse.Namespace) -> StageResult:
    from . import inspection as inspectmod

    pkg = _package(args, create=False)
    return inspectmod.inspect(pkg, args.kind, args.ident)


def cmd_context(args: argparse.Namespace) -> StageResult:
    from . import agent_memory
    pkg = _package(args, create=False)
    context = agent_memory.context_for(pkg, last=args.last, stage_prefixes=args.stage_prefix)
    return StageResult("context", "PASS", "retained agent context loaded with exact byte/hash checks; no proof authority",
                       summary=context, lines=[f"loaded {len(context['snapshots'])} retained snapshot(s)"])


def cmd_explain_block(args: argparse.Namespace) -> StageResult:
    from . import inspection as inspectmod

    pkg = _package(args, create=False)
    return inspectmod.explain_block(pkg)


def cmd_status(args: argparse.Namespace) -> StageResult:
    from . import inspection as inspectmod

    pkg = _package(args, create=False)
    return inspectmod.status(pkg)


def cmd_diff(args: argparse.Namespace) -> StageResult:
    from . import inspection as inspectmod

    return inspectmod.diff(Package(Path(args.from_pkg)), Package(Path(args.to_pkg)))


def cmd_capabilities(args: argparse.Namespace) -> StageResult:
    from . import capabilities

    return capabilities.report()


def cmd_doctor(args: argparse.Namespace) -> StageResult:
    from . import capabilities

    return capabilities.doctor()


def cmd_auth(args: argparse.Namespace) -> StageResult:
    from . import auth

    return auth.dispatch(args)


def cmd_providers(args: argparse.Namespace) -> StageResult:
    if args.providers_action == "probe":
        from .providers import conformance

        return conformance.run(
            Path(args.config), args.agent, live=args.live,
            profiles=Path(args.endpoint_profiles) if args.endpoint_profiles else None,
            max_output_tokens=args.max_output_tokens,
        )
    from .providers import check

    return check.run(Path(args.config), live=args.live, profiles=Path(args.endpoint_profiles) if args.endpoint_profiles else None)


def cmd_review(args: argparse.Namespace) -> StageResult:
    from . import review

    pkg = _package(args, create=False)
    if args.review_action == "tally":
        return review.tally(pkg, args.campaign)
    return review.run(pkg, _events(args, pkg), Path(args.config), checkpoint=args.checkpoint)


def cmd_bridge(args: argparse.Namespace) -> StageResult:
    if args.bridge_action != "check":
        from .bridges import prepare

        # Validate the lexical root before Package resolves it or the lock creates paths.
        from .bridges.manifest import InvalidPackage, PackageReader

        try:
            reader = PackageReader(Path(args.package))
            reader.close()
        except InvalidPackage as exc:
            return StageResult(f"bridge {args.bridge_action}", "BLOCKED", "bridge package path integrity",
                               [Diagnostic(exc.code, str(exc))])
        pkg = _package(args, create=False, resolve_root=False)
        if args.bridge_action == "verify":
            return prepare.verify_preparation(pkg, args.bridge_id, semantic="rebuild")
        if args.bridge_action == "accept":
            with fsutil.package_lock(pkg.root):
                events = EventSink(pkg.run_id, None, args.events, quiet=args.quiet)
                try:
                    return _vscore_bridge_accept(pkg, args.bridge_id, events)
                finally:
                    events.close()
        with fsutil.package_lock(pkg.root):
            events = EventSink(pkg.run_id, None, args.events, quiet=args.quiet)
            try:
                return prepare.run(pkg, events, Path(os.path.abspath(args.proposal)),
                                   Path(os.path.abspath(args.candidate_dir)))
            finally:
                events.close()
    from .bridges.check import validate_package

    return validate_package(
        Path(args.package), Path(args.plan), Path(args.artifacts),
        certificate_paths=[Path(path) for path in args.certificate],
    )


def _vscore_bridge_accept(pkg: Package, bridge_id: str, events: EventSink) -> StageResult:
    """Select a registered checker from the frozen edge claims, never from a default version."""
    from .bridges import prepare, vscore_checker, vscore3_checker
    from .bridges.check import _schema
    from .bridges.manifest import InvalidPackage, PackageReader

    reader = None
    gate = "registered VSCore relation checker dispatch"
    try:
        reader = PackageReader(pkg.root / "bridges" / prepare._bridge_id(bridge_id))
        plan, _ = reader.json("plan.json")
        _schema("bridge-plan", plan)
        claims = {c["claim_id"]: c for c in plan["claims"]}
        verifiers = {claims[e["claim_id"]]["verifier_id"] for e in plan["edges"]}
        checkers = {vscore_checker.VERIFIER: vscore_checker, vscore3_checker.VERIFIER: vscore3_checker}
        if len(verifiers) != 1 or not verifiers <= set(checkers):
            return StageResult("bridge accept", "BLOCKED", gate, [Diagnostic(
                "UNSUPPORTED_CAPABILITY", "bridge acceptance requires one exact registered VSCore checker version")],
                summary={"bridge_id": bridge_id, "semantic_acceptance": False,
                         "assigns_end_to_end_verified": False})
        reader.recheck()
        checker = checkers[next(iter(verifiers))]
    except InvalidPackage as exc:
        return StageResult("bridge accept", "BLOCKED", gate, [Diagnostic(exc.code, str(exc))])
    except (KeyError, TypeError, ValueError) as exc:
        return StageResult("bridge accept", "BLOCKED", gate, [Diagnostic("INVALID_CANDIDATE", str(exc))])
    except OSError as exc:
        return StageResult("bridge accept", "INFRASTRUCTURE_FAILURE", gate,
                           [Diagnostic("VERIFIER_FAILURE", str(exc), severity="infrastructure")])
    finally:
        if reader is not None:
            reader.close()
    return checker.accept(pkg, bridge_id, events)


def _vscore_source_module(source: bytes):
    """Closed canonical language dispatch; a rejected version never falls back to 0.1."""
    from .targets import vscore_source, vscore2_source, vscore2_check, vscore3_source

    value = vscore_source.parse_json(source)
    if not isinstance(value, dict):
        raise vscore_source.SourceError("source must be a program object")
    language = value.get("language")
    modules = {module.LANGUAGE: module for module in (vscore_source, vscore2_source, vscore3_source)}
    if not isinstance(language, str) or language not in modules:
        raise vscore2_check.UnsupportedSource(f"unsupported VSCore language {language!r}")
    return modules[language]


def _vscore_surface_module(text: str):
    """The surface program header chooses its authoring grammar explicitly."""
    from .targets import vscore_source, vscore2_source, vscore2_check, vscore3_source, vscore3_surface

    tokens = vscore3_surface.tokenize(text)
    if len(tokens) < 3 or tokens[0].text != "program" or tokens[0].kind != "keyword" or tokens[1].kind != "string":
        raise vscore_source.SourceError("surface source needs an explicit program language header")
    language = tokens[1].text
    modules = {module.LANGUAGE: module for module in (vscore2_source, vscore3_source)}
    if language not in modules:
        raise vscore2_check.UnsupportedSource(f"unsupported VSCore surface language {language!r}")
    return modules[language]


def cmd_vscore(args: argparse.Namespace) -> StageResult:
    """Authoring helpers and standalone kernel admission; bridge milestones stay separate."""
    from . import canonical
    from .targets import vscore_source as src
    from .targets import vscore2_source as src2, vscore2_check, vscore3_source as src3, vscore3_check

    try:
        with Path(args.source).open("rb") as handle:
            source = handle.read(src.MAX_SOURCE_BYTES + 1)
        if len(source) > src.MAX_SOURCE_BYTES:
            raise src.SourceError("source exceeds the supported byte budget")
    except (OSError, src.SourceError) as exc:
        return StageResult("vscore " + args.vscore_action, "BLOCKED", "source input admission",
                           [Diagnostic("INVALID_CANDIDATE", f"cannot read VSCore source: {exc}")])
    if args.vscore_action in ("parse", "compile", "check"):
        enums: dict[str, list[str]] = {}
        profile_path = Path(args.profile) if args.profile else None
        try:
            if profile_path is None:
                # Default: the accepted registry of --package, when it is an accepted run.
                pkg = Package(Path(args.package))
                acceptance = pkg.path("accepted") / "acceptance.json"
                if pkg.exists() and acceptance.is_file():
                    accepted = canonical.load_file(acceptance)
                    artifacts = accepted.get("artifacts") if isinstance(accepted, dict) else None
                    artifact = artifacts.get("profile") if isinstance(artifacts, dict) else None
                    rel = artifact.get("path") if isinstance(artifact, dict) else None
                    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
                        raise src.SourceError("accepted run needs a relative profile artifact path")
                    profile_path = pkg.root / rel
            if profile_path is not None:
                prof = canonical.load_file(profile_path)
                if not isinstance(prof, dict) or not isinstance(prof.get("enums", {}), dict):
                    raise src.SourceError("profile must contain an enumeration registry object")
                for k, v in prof.get("enums", {}).items():
                    if not isinstance(v, dict) or not isinstance(v.get("constructors"), list):
                        raise src.SourceError("each enumeration needs a constructors array")
                    if not all(isinstance(c, str) for c in v["constructors"]):
                        raise src.SourceError("enumeration constructor IDs must be strings")
                    enums[k] = v["constructors"]
            if args.vscore_action == "compile":
                text = source.decode("ascii")
                src = _vscore_surface_module(text)
                prog = src.parse_surface(text, enums)
                encoded = src.source_bytes(prog)
                try:
                    fsutil.atomic_write(Path(args.out), encoded)
                except OSError as exc:
                    return StageResult("vscore compile", "INFRASTRUCTURE_FAILURE", "write canonical source",
                        [Diagnostic("VERIFIER_FAILURE", str(exc), severity="infrastructure")])
                return StageResult("vscore compile", "PASS", src.LANGUAGE + " surface authoring into canonical delivered JSON (advisory)",
                    summary={"out": args.out, "language": src.LANGUAGE,
                             "source_hash": canonical.digest(encoded), "required_features": src.required_features(prog),
                             "authoritative": False},
                    lines=["Canonical JSON written; use `vscore check` for kernel-checked source admission."])
            src = _vscore_source_module(source)
            if args.vscore_action == "check":
                checker = {src2: vscore2_check, src3: vscore3_check}.get(src)
                if checker is None:
                    return StageResult("vscore check", "BLOCKED", "VSCore source admission",
                        [Diagnostic("UNSUPPORTED_CAPABILITY", "this source-check command requires vscore/0.2 or vscore/0.3; use the registered bridge workflow for 0.1")])
                return checker.check(source, enums, Path(args.out) if args.out else None)
            prog = src.parse_source(source)
            sigs = src.check_program(enums, prog)
        except (src.SourceError, UnicodeError, canonical.CanonicalJSONError, OSError) as exc:
            return StageResult("vscore " + args.vscore_action, "BLOCKED", "source/profile admission",
                               [Diagnostic(getattr(exc, "code", "INVALID_CANDIDATE"), f"VSCore source rejected: {exc}")])
        return StageResult("vscore parse", "PASS", "host proposal parse and type check (advisory)",
                           summary={"program": src.program_json(prog),
                                    "signatures": [{"id": x["id"], "params": [src.ty_json(t) for t in x["params"]],
                                                    "result": src.ty_json(x["result"])} for x in sigs],
                                    "authoritative": False},
                           lines=["Advisory host parse only; acceptance needs the kernel-checked parse equation."])
    try:
        src = _vscore_source_module(source)
        if src is src2:
            return StageResult("vscore goal", "BLOCKED", "registered accepted-contract bridge capability",
                [Diagnostic("UNSUPPORTED_CAPABILITY", "vscore/0.2 source admission uses `vscore check`; accepted-contract refinement/transport is not registered for 0.2")])
    except src.SourceError as exc:
        return StageResult("vscore goal", "BLOCKED", "registered accepted-contract bridge capability",
                           [Diagnostic(getattr(exc, "code", "INVALID_CANDIDATE"), str(exc))])
    if src is src3:
        from .bridges import vscore3_checker as vc
    else:
        from .bridges import vscore_checker as vc

    pkg = _package(args, create=False)
    relation = Path(args.relation).read_bytes()
    proof = Path(args.proof).read_bytes() if args.proof else None
    if args.bridge_id and proof is None:
        raise UsageError("--bridge-id writes a complete candidate directory and therefore needs --proof")
    gate = "derive the VSCore bridge goal and its proposition hash (advisory; publishes nothing)"
    try:
        spec, _build, info = vc.preview(pkg, source, relation, proof, args.obligation or None)
    except vc.EdgeFailure as exc:
        return StageResult("vscore goal", "BLOCKED" if not any(d.severity == "infrastructure" for d in exc.diagnostics)
                           else "INFRASTRUCTURE_FAILURE", gate, exc.diagnostics)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = {"VeriSlopBridgeGoal.lean": spec.text.encode(), vc.FILES["model"]: info["model"],
             vc.FILES["profile"]: info["profile"]}
    if args.bridge_id:
        files.update(vc.candidate_files(args.bridge_id, info, source, relation, proof))
    for name, data in files.items():
        fsutil.atomic_write(out / name, data)
    summary = {k: v for k, v in info.items() if k not in ("model", "profile")}
    summary.update({"out": str(out), "written": sorted(files), "authoritative": False})
    lines = [f"proposition hash: {info['proposition_hash']}", f"goal: {out / 'VeriSlopBridgeGoal.lean'}"]
    if proof is not None:
        lines.append("candidate proof checked in one isolated build (axioms: " + ", ".join(info["edge_axioms"]) + ")")
    if args.bridge_id:
        lines.append(f"candidate directory ready: verislop bridge prepare --proposal {out / 'proposal.json'} --candidate-dir {out}")
    return StageResult("vscore goal", "PASS", gate, summary=summary, lines=lines)


# --------------------------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------------------------


def _repair_rounds(value: str) -> int:
    try:
        rounds = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("repair rounds must be an integer between 0 and 8") from None
    if not 0 <= rounds <= 8:
        raise argparse.ArgumentTypeError("repair rounds must be between 0 and 8")
    return rounds


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable result on stdout; progress on stderr")
    common.add_argument("--events", metavar="PATH", help="stream JSON Lines events to PATH ('-' for stderr)")
    common.add_argument("--quiet", action="store_true", help="suppress human progress on stderr")
    common.add_argument("--package", default=".", metavar="DIR", help="run package directory (default: current directory)")

    p = _Parser(prog="verislop", description="VeriSlop CLI — Verify the Slop. Contract-first verification of generated software.")
    p.add_argument("--version", action="version", version=f"verislop {__version__}")
    sub = p.add_subparsers(dest="command", required=True, parser_class=_Parser)

    s = sub.add_parser("run", parents=[common], help="run the full pipeline into .verislop/runs/<run-id>/")
    s.add_argument("--prompt-file", required=True)
    s.add_argument("--mode", choices=["auto", "software"], default="auto")
    s.add_argument("--tier", type=int, choices=range(0, 5), metavar="{0..4}")
    s.add_argument("--target", default="python")
    s.add_argument("--endpoint")
    s.add_argument("--backend-version", help="exact registered backend version (required for VSCore 0.3)")
    s.add_argument("--require-state", choices=["TESTED", "END_TO_END_VERIFIED"])
    s.add_argument("--policy", default="strict")
    s.add_argument("--config", help="provider/agent/review configuration (verislop.json)")
    s.add_argument("--run-id")
    s.add_argument("--runs-dir", help="default: ./.verislop/runs")
    s.add_argument("--request-ref")
    s.add_argument("--attachment", action="append", help="immutable attachment (citable by source refs); repeatable")
    s.add_argument("--repository-revision")
    s.add_argument("--draft-candidate", help="pre-authored candidate draft (instead of an interpreter agent)")
    s.add_argument("--ledger-candidate", help="interpretation ledger accompanying --draft-candidate")
    s.add_argument("--formalization-candidate", help="directory with Contract.lean and formalization.json")
    s.add_argument("--proof-candidate", help="Lean file with proofs for the frozen challenge")
    s.add_argument("--implementation-candidate", help="directory with existing/generated implementation sources")
    s.add_argument("--bridge-id", help="selected or newly generated implementation bridge")
    tests = s.add_mutually_exclusive_group()
    tests.add_argument("--require-tests", action="store_true", help="require an independent target campaign")
    tests.add_argument("--no-tests", action="store_true", help="omit the optional target campaign")
    s.add_argument("--bridge-proposal", help="optional shared bridge preparation proposal after export")
    s.add_argument("--bridge-candidate-dir", help="artifact root for --bridge-proposal")
    s.add_argument("--bindings-candidate", help="implementation binding proposal (bindings.json)")
    s.add_argument("--resolve", action="append", metavar="AMBIGUITY=ALT")
    s.add_argument("--non-interactive", action="store_true")
    s.add_argument("--budget-seconds", type=_wall_budget_seconds, default=600,
                   help="proof-search wall budget in seconds (default: 600; 0 disables the deadline); verifier and test limits remain")
    s.add_argument("--repair-rounds", type=_repair_rounds,
                   help="strict contract-repair restarts, 0..8; default uses configured repair budget; every changed frozen contract gets a fresh run package")
    s.add_argument("--seed", type=int)
    s.add_argument("--cases", type=int, default=300)
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("classify", parents=[common], help="route a prompt (SOFTWARE / NON_SOFTWARE / UNCERTAIN)")
    s.add_argument("--prompt-file", required=True)
    s.add_argument("--mode", choices=["auto", "software"], default="auto")
    s.set_defaults(func=cmd_classify)

    s = sub.add_parser("interpret", parents=[common], help="emit the draft and interpretation ledger")
    s.add_argument("--prompt-file", required=True)
    s.add_argument("--out", help="draft output path (inside the package)")
    s.add_argument("--mode", choices=["auto", "software"], default="auto")
    s.add_argument("--request-ref")
    s.add_argument("--candidate", help="pre-authored candidate draft.json")
    s.add_argument("--ledger", help="interpretation ledger for --candidate")
    s.add_argument("--attachment", action="append", help="immutable attachment (citable by source refs); repeatable")
    s.add_argument("--repository-revision", help="repository revision the request is about (recorded)")
    s.add_argument("--config")
    s.add_argument("--resolve", action="append", metavar="AMBIGUITY=ALT")
    s.add_argument("--non-interactive", action="store_true")
    s.set_defaults(func=cmd_interpret)

    s = sub.add_parser("formalize", parents=[common], help="formalize, statement-check and freeze the Lean challenge")
    s.add_argument("--draft")
    s.add_argument("--out", help="contract directory (inside the package)")
    s.add_argument("--candidate", help="directory with Contract.lean and formalization.json")
    s.add_argument("--policy", default="strict")
    s.add_argument("--config")
    s.add_argument("--max-attempts", type=int, default=3)
    s.set_defaults(func=cmd_formalize)

    s = sub.add_parser("prove", parents=[common], help="search for proofs of the frozen challenge (untrusted)")
    s.add_argument("--contract")
    s.add_argument("--policy", default="strict")
    s.add_argument("--budget-seconds", type=_wall_budget_seconds, default=600,
                   help="proof-search wall budget in seconds (default: 600; 0 disables the deadline); verifier limits remain")
    s.add_argument("--max-attempts", type=int, default=4)
    s.add_argument("--candidate", help="Lean file proposing proofs for the frozen challenge")
    s.add_argument("--no-portfolio", action="store_true", help="disable the built-in tactic portfolio")
    s.add_argument("--config")
    s.set_defaults(func=cmd_prove)

    s = sub.add_parser("accept", parents=[common], help="isolated kernel replay, statement/axiom/witness audit, certificate")
    s.add_argument("--contract")
    s.add_argument("--policy", default="strict")
    s.set_defaults(func=cmd_accept)

    s = sub.add_parser("export", parents=[common], help="reconstruct accepted-ir.json from the accepted environment")
    s.add_argument("--accepted", help="acceptance certificate (acceptance.json)")
    s.add_argument("--out")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("generate", parents=[common], help="materialize an implementation candidate for a bridge tier")
    s.add_argument("--ir")
    s.add_argument("--tier", type=int, choices=range(0, 5), metavar="{0..4}")
    s.add_argument("--target", help="target backend (defaults to the frozen target, otherwise python)")
    s.add_argument("--endpoint")
    s.add_argument("--backend-version", help="exact registered backend version (defaults to an already frozen version)")
    s.add_argument("--require-state", choices=["TESTED", "END_TO_END_VERIFIED"])
    s.add_argument("--candidate", help="directory with existing implementation sources")
    s.add_argument("--bindings", help="binding proposal for --candidate")
    tests = s.add_mutually_exclusive_group()
    tests.add_argument("--no-tests", action="store_true", help="release policy does not require TESTED")
    tests.add_argument("--require-tests", action="store_true", help="release policy requires TESTED")
    s.add_argument("--bridge-id", help="adopt a prepared bridge, or name the new candidate bridge")
    s.add_argument("--config")
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("link", parents=[common], help="structural binding of implementation objects to obligations")
    s.add_argument("--ir")
    s.add_argument("--implementation")
    s.set_defaults(func=cmd_link)

    s = sub.add_parser("test", parents=[common], help="run the frozen Tier 0 property campaign on the target artifact")
    s.add_argument("--seed", type=int)
    s.add_argument("--cases", type=int, help="cases per obligation (default 300; frozen with the campaign)")
    s.add_argument("--timeout", type=float, default=120.0)
    s.set_defaults(func=cmd_test)

    s = sub.add_parser("verify", parents=[common], help="closure: clean builds, determinism, provenance, report.json")
    s.add_argument("--endpoint")
    s.add_argument("--require-state", choices=["TESTED", "END_TO_END_VERIFIED"])
    s.add_argument("--config", help="review configuration when review is a release gate")
    s.set_defaults(func=cmd_verify)

    s = sub.add_parser("resume", parents=[common], help="resume a run after checking its complete frozen root")
    s.add_argument("--run-id", required=True)
    s.add_argument("--runs-dir")
    s.add_argument("--config")
    s.add_argument("--repair-rounds", type=_repair_rounds,
                   help="override total strict contract-repair budget, 0..8; completed restarts remain counted")
    s.set_defaults(func=cmd_resume)

    s = sub.add_parser("inspect", parents=[common], help="inspect an obligation, evidence record, or the report")
    s.add_argument("kind", choices=["obligation", "evidence", "report", "certificate", "ir"])
    s.add_argument("ident", nargs="?")
    s.set_defaults(func=cmd_inspect)

    s = sub.add_parser("context", parents=[common], help="reload exact retained JSON/Lean/model artifacts after context loss")
    s.add_argument("--last", type=int, default=3)
    s.add_argument("--stage-prefix", action="append", help="select matching stages, e.g. formalize/attempt or prove/attempt")
    s.set_defaults(func=cmd_context)

    s = sub.add_parser("explain-block", parents=[common], help="explain why a run is blocked")
    s.set_defaults(func=cmd_explain_block)

    s = sub.add_parser("status", parents=[common], help="derive the current obligation view from evidence")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("diff", parents=[common], help="compare two run packages")
    s.add_argument("--from", dest="from_pkg", required=True)
    s.add_argument("--to", dest="to_pkg", required=True)
    s.set_defaults(func=cmd_diff)

    s = sub.add_parser("capabilities", parents=[common], help="published tier/language/property support")
    s.set_defaults(func=cmd_capabilities)

    s = sub.add_parser("doctor", parents=[common], help="check toolchain, sandbox and verifier availability")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("bridge", parents=[common], help="check bridge plans, artifact integrity and certificate bindings")
    bsub = s.add_subparsers(dest="bridge_action", required=True, parser_class=_Parser)
    a = bsub.add_parser("check", parents=[common], help="read-only envelope and artifact checks; semantic acceptance requires a registered backend")
    a.add_argument("--plan", required=True, help="frozen bridge plan JSON")
    a.add_argument("--artifacts", required=True, help="artifact manifest JSON bound to the plan")
    a.add_argument("--certificate", action="append", default=[], help="semantic-edge certificate to check; repeat for several")
    a.set_defaults(func=cmd_bridge)

    a = bsub.add_parser("prepare", parents=[common], help="replay the accepted contract and freeze a structural bridge package")
    a.add_argument("--proposal", required=True, help="bridge proposal JSON; hashes and coverage are derived by the supervisor")
    a.add_argument("--candidate-dir", required=True, help="root of proposed bridge artifact files")
    a.set_defaults(func=cmd_bridge)

    a = bsub.add_parser("verify", parents=[common],
                        help="recheck a frozen preparation and re-run registered checkers on published acceptances")
    a.add_argument("--bridge-id", required=True)
    a.set_defaults(func=cmd_bridge)

    a = bsub.add_parser("accept", parents=[common],
                        help="run the registered relation checkers on a prepared bridge and publish their certificates")
    a.add_argument("--bridge-id", required=True)
    a.set_defaults(func=cmd_bridge)

    s = sub.add_parser("vscore", parents=[common], help="VSCore source authoring, kernel admission and bridge helpers")
    vsub = s.add_subparsers(dest="vscore_action", required=True, parser_class=_Parser)
    a = vsub.add_parser("parse", parents=[common], help="host proposal parse and type check of a VSCore source")
    a.add_argument("--source", required=True, help="canonical vscore/0.1, 0.2 or 0.3 source file")
    a.add_argument("--profile", help="profile registry JSON supplying enumerations (default: the accepted profile of --package)")
    a.set_defaults(func=cmd_vscore)
    a = vsub.add_parser("compile", parents=[common], help="compile VSCore 0.2/0.3 surface syntax to canonical source (authoring only)")
    a.add_argument("--source", required=True, help="VSCore .vsc surface file with an explicit 0.2 or 0.3 program header")
    a.add_argument("--profile", help="enumeration registry JSON (default: accepted profile of --package)")
    a.add_argument("--out", required=True, help="canonical delivered JSON file")
    a.set_defaults(func=cmd_vscore)
    a = vsub.add_parser("check", parents=[common], help="kernel-check exact VSCore 0.2/0.3 source admission and reconstruct its AST twice")
    a.add_argument("--source", required=True, help="canonical vscore/0.2 or 0.3 source file")
    a.add_argument("--profile", help="enumeration registry JSON (default: accepted profile of --package)")
    a.add_argument("--out", help="new directory for bound report, reconstructed IR and accepted Lean modules")
    a.set_defaults(func=cmd_vscore)
    a = vsub.add_parser("goal", parents=[common],
                        help="derive the bridge goal and proposition hash from an accepted run (optionally check a proof)")
    a.add_argument("--source", required=True, help="canonical vscore/0.1 or 0.3 source file")
    a.add_argument("--relation", required=True, help="vscore relation descriptor (symbol-to-entry bindings)")
    a.add_argument("--proof", help="candidate VeriSlopBridgeProof.lean to check in one isolated build")
    a.add_argument("--obligation", action="append", help="covered obligation (default: every required guarantee)")
    a.add_argument("--out", required=True, help="directory for the goal, descriptors and optional candidate files")
    a.add_argument("--bridge-id", help="also write proposal.json and artifacts for `bridge prepare`")
    a.set_defaults(func=cmd_vscore)

    s = sub.add_parser("auth", parents=[common], help="manage user-owned provider credentials")
    asub = s.add_subparsers(dest="auth_action", required=True, parser_class=_Parser)
    a = asub.add_parser("add", parents=[common])
    a.add_argument("--provider", required=True)
    a.add_argument("--credential-id", required=True)
    a.add_argument("--store", default="keyring", help="keyring | env:VAR | secret-manager:REF | file")
    a.add_argument("--auth-profile")
    a.add_argument("--from-stdin", action="store_true", help="read the secret from stdin instead of a masked prompt")
    a.add_argument("--allow-plaintext-file", action="store_true", help="required with --store file")
    asub.add_parser("list", parents=[common])
    a = asub.add_parser("check", parents=[common])
    a.add_argument("--credential-id", required=True)
    a.add_argument("--live", action="store_true", help="perform the documented minimal authenticated request")
    a = asub.add_parser("remove", parents=[common])
    a.add_argument("--credential-id", required=True)
    s.set_defaults(func=cmd_auth)

    s = sub.add_parser("providers", parents=[common], help="provider configuration checks")
    psub = s.add_subparsers(dest="providers_action", required=True, parser_class=_Parser)
    a = psub.add_parser("check", parents=[common])
    a.add_argument("--config", required=True)
    a.add_argument("--endpoint-profiles")
    a.add_argument("--live", action="store_true", help="also make minimal authenticated checks (networked)")
    a = psub.add_parser("probe", parents=[common], help="opt-in bounded inference and JSON-response conformance check")
    a.add_argument("--config", required=True)
    a.add_argument("--agent", action="append", required=True, help="configured agent to probe; repeat to select several")
    a.add_argument("--endpoint-profiles")
    a.add_argument("--live", action="store_true", help="explicitly permit inference requests, which may incur provider charges")
    a.add_argument("--max-output-tokens", type=int, default=128, help="per-probe output cap (default: 128)")
    s.set_defaults(func=cmd_providers)

    s = sub.add_parser("review", parents=[common], help="hierarchical adversarial review of a checkpoint")
    s.add_argument("review_action", nargs="?", choices=["run", "tally"], default="run")
    s.add_argument("--config")
    s.add_argument("--checkpoint", choices=["interpretation", "formal_contract", "implementation", "release"])
    s.add_argument("--campaign")
    s.set_defaults(func=cmd_review)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    as_json = getattr(args, "json", False)
    try:
        if args.command in WRITING_COMMANDS:
            # Concurrent writers cannot update the same run package.
            with fsutil.package_lock(Path(args.package)):
                result = args.func(args)
        else:
            result = args.func(args)
    except KeyboardInterrupt:
        sys.stderr.write("verislop: interrupted; the run is incomplete and unresolved checks remain\n")
        return EXIT_INTERRUPTED
    except VeriSlopError as exc:
        result = StageResult(args.command, "INFRASTRUCTURE_FAILURE", "command could not complete")
        if exc.exit_code == 2:
            result.status = "BLOCKED"
        result.diagnostics = exc.diagnostics or [Diagnostic(
            "CONFIGURATION_INVALID" if exc.exit_code == EXIT_USAGE else "VERIFIER_FAILURE", exc.message,
            severity="blocking" if exc.exit_code in (2, EXIT_USAGE) else "infrastructure")]
        if exc.exit_code == EXIT_USAGE:
            if as_json:
                sys.stdout.write(json.dumps({"command": args.command, "status": "INVALID_INVOCATION",
                                             "diagnostics": [d.to_json() for d in result.diagnostics]}, indent=2) + "\n")
            else:
                sys.stderr.write(f"verislop {args.command}: {exc.message}\n")
                for d in exc.diagnostics:
                    sys.stderr.write(f"  {d.code}: {d.message}\n")
            return EXIT_USAGE
        _render(result, as_json)
        return exc.exit_code
    _render(result, as_json)
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
