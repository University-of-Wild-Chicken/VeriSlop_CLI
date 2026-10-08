"""Strict contract recovery through fresh packages, never mutable frozen challenges.

A repair is an untrusted formalization proposal for the same recorded interpretation.
Failed packages and their verifier results remain available. Only request/interpretation
inputs cross the package boundary; every formal, proof, implementation and release gate
executes again in the new package.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from . import canonical, contract, fsutil
from .errors import Diagnostic, UsageError
from .events import EventSink
from .package import Package
from .stage import StageResult

FORMAT = "verislop.strict-recovery/0.1"
POLICY_FORMAT = "verislop.strict-recovery-policy/0.1"
REPAIRABLE_STAGES = frozenset({"formalize", "prove", "accept"})
REPAIRABLE_CODES = frozenset({"INVALID_CANDIDATE", "CANDIDATE_BUILD_FAILURE", "STATEMENT_MISMATCH",
    "PROOF_UNRESOLVED", "MISSING_WITNESS", "WITNESS_INVALID", "KERNEL_REJECTION",
    "IR_REIFICATION_MISMATCH", "SCOPE_LEAK"})
NEVER_REPAIR_CODES = frozenset({"INPUT_MUTATION", "CLAIM_MUTATION", "STALE_OR_UNBOUND_EVIDENCE",
    "UNSUPPORTED_CAPABILITY", "UNSUPPORTED_SEMANTICS", "INTERPRETATION_UNRESOLVED",
    "INADMISSIBLE_AXIOM", "UNDECLARED_DEPENDENCY", "NONDETERMINISM", "CONFIGURATION_INVALID",
    "PROVIDER_FAILURE", "INTERRUPTED", "BUDGET_EXHAUSTED"})


def budget(parameters: dict[str, Any]) -> int:
    explicit = parameters.get("repair_rounds")
    if explicit is not None and (type(explicit) is not int or not 0 <= explicit <= 8):
        raise UsageError("--repair-rounds must be an integer in 0..8")
    if not parameters.get("config"):
        return 0
    if explicit is not None:
        return explicit
    from .providers import config

    conf = config.load(Path(parameters["config"]))
    maximum = conf["review"]["budgets"]["max_repair_rounds"]
    if not 0 <= maximum <= 8:
        raise UsageError("strict recovery requires review.budgets.max_repair_rounds in 0..8; set --repair-rounds explicitly")
    return maximum


def eligible(result: StageResult, parameters: dict[str, Any], pkg: Package | None = None) -> bool:
    """Only agent-generated contract/proof defects justify a new formal proposal."""
    if result.status != "BLOCKED" or not parameters.get("config"):
        return False
    if parameters.get("formalization_candidate") or parameters.get("proof_candidate"):
        return False
    stage = result.summary.get("stopped_at")
    if stage not in REPAIRABLE_STAGES and stage != "review:formal_contract":
        return False
    diags = result.summary.get("failed_stage_diagnostics", [])
    codes = {d.get("code") for d in diags if d.get("severity") == "blocking"}
    if any(d.get("severity") == "infrastructure" for d in diags):
        return False
    # A later closure failure cannot conceal an earlier tamper/unsupported-policy result.
    if any((d.code in NEVER_REPAIR_CODES and d.severity == "blocking")
           or d.severity == "infrastructure" for d in result.diagnostics):
        return False
    if stage == "review:formal_contract":
        return bool(pkg is not None and "REVIEW_REJECTED" in codes
                    and confirmed_contract_counterexamples(pkg, result, parameters))
    return bool(codes & REPAIRABLE_CODES) and not bool(codes & NEVER_REPAIR_CODES)


def confirmed_contract_counterexamples(pkg: Package, result: StageResult,
                                      parameters: dict[str, Any]) -> list[dict[str, Any]]:
    """Recheck the full review and return only reproduced contract-claim defects.

    Reviewer opinions, unsupported behavioral probes and interpretation omissions
    cannot revise a frozen contract. Interpretation repair is deliberately outside
    this workflow: it would alter the immutable requirement bundle.
    """
    from . import review, review_counterexamples, schemas
    from .providers import config
    from .providers.broker import Broker

    campaign = result.summary.get("failed_stage_summary", {}).get("campaign")
    if not isinstance(campaign, str) or not campaign:
        return []
    try:
        fsutil.check_relpath(campaign)
        if "/" in campaign:
            return []
        directory = pkg.path("reviews") / campaign
        cert = canonical.load_file(directory / "consensus-certificate.json")
        packet = canonical.load_file(directory / "packet.json")
        if cert.get("checkpoint") != "formal_contract" or cert.get("final") != "CHANGES_REQUESTED":
            return []
        conf = config.load(Path(parameters["config"]))
        resolved = config.resolve(conf, config.load_user_profiles(None))
        if any(d.severity == "blocking" for d in resolved.diagnostics):
            return []
        broker = Broker(resolved, None)
        models = {g["agent"]: broker.model_for(g["agent"])
                  for tier in conf["review"]["review_tiers"] for g in tier["reviewers"]}
        components = review.target_components(pkg, conf, "formal_contract", packet, models)
        if cert.get("target_components") != components or cert.get("review_target_root") != canonical.digest_json(components):
            return []
        if review._recheck(pkg, cert, conf):
            return []
        confirmed = []
        for tier in cert["tiers"]:
            for ballot_ref in tier["ballots"]:
                fsutil.check_relpath(ballot_ref["ballot_ref"])
                ballot = canonical.load_file(pkg.root / ballot_ref["ballot_ref"])
                for reference in ballot["counterexample_receipts"]:
                    if reference["status"] != "CONFIRMED":
                        continue
                    rel = fsutil.check_relpath(reference["receipt_ref"])
                    path = pkg.root / rel
                    receipt = canonical.load_file(path)
                    if (not rel.startswith(f"reviews/{campaign}/counterexamples/")
                            or canonical.digest_file(path) != reference["receipt_hash"]
                            or schemas.validate("review-counterexample-receipt", receipt)
                            or receipt["status"] != "CONFIRMED" or receipt["checkpoint"] != "formal_contract"
                            or receipt["checker"] != {"id": review_counterexamples.VERIFIER,
                                "sha256": review_counterexamples.verifier_hash(review_counterexamples.VERIFIER)}):
                        return []
                    claim = receipt.get("claim") or {}
                    if (receipt["proposal"].get("kind") != "mechanical_failure"
                            or not str(claim.get("claim_id", "")).startswith(("FORMALIZED:", "TYPECHECKED:", "PROVED:"))):
                        continue
                    # _recheck independently replays each receipt and verifies its roots,
                    # declared checker, exact proposal and resulting effective ballot.
                    confirmed.append({"receipt_ref": rel, "receipt_hash": reference["receipt_hash"], "receipt": receipt})
        return confirmed
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UsageError):
        return []


def _snapshot(pkg: Package) -> dict[str, Any]:
    """Bind retained technical artifacts, excluding explicitly mutable bookkeeping."""
    excluded = {"package.json", "events.jsonl", "report.json", "obligation-view.json", ".verislop.lock", "recovery.json"}
    files = {rel: pkg.root / rel for rel in fsutil.list_files(pkg.root)
             if rel not in excluded and not rel.startswith((".tmp-", "recovery-policy/"))}
    manifest = fsutil.manifest_for(files)
    return {"manifest": manifest, "root": fsutil.manifest_root(manifest)}


def _policy(root: Package, reference: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Validate an immutable chain of supervisor-selected total round budgets."""
    current = reference
    seen = []
    last = None
    while current is not None:
        if not isinstance(current, dict) or set(current) != {"ref", "sha256"}:
            raise UsageError("invalid recovery budget binding", [Diagnostic("INPUT_MUTATION", "recovery policy reference is malformed")])
        match = re.fullmatch(r"recovery-policy/decision-([0-9]{4,})\.json", current["ref"])
        if not match or current in seen:
            raise UsageError("invalid recovery budget chain", [Diagnostic("INPUT_MUTATION", "recovery policy decision path or chain is invalid")])
        path = root.root / current["ref"]
        if path.is_symlink() or canonical.digest_file(path) != current["sha256"]:
            raise UsageError("changed recovery budget decision", [Diagnostic("INPUT_MUTATION", "selected recovery policy bytes changed")])
        data = canonical.load_file(path)
        index = int(match.group(1))
        if (data.get("format") != POLICY_FORMAT or data.get("root_run_id") != root.run_id
                or type(data.get("max_repair_rounds")) is not int or not 0 <= data["max_repair_rounds"] <= 8
                or data.get("decision") != index or data.get("source") not in
                    ("initial configuration or CLI selection", "explicit --repair-rounds override")):
            raise UsageError("invalid recovery budget decision", [Diagnostic("INPUT_MUTATION", "recovery policy does not bind this run and bounded selection")])
        previous = data.get("previous")
        if ((index == 1 and previous is not None) or (index > 1 and
                (not isinstance(previous, dict) or previous.get("ref") != f"recovery-policy/decision-{index - 1:04d}.json"))):
            raise UsageError("invalid recovery policy predecessor", [Diagnostic("INPUT_MUTATION", "selected recovery policy chain is not contiguous")])
        seen.append(current)
        if last is None:
            last = data
        current = previous
    return last, seen


def select_policy(root: Package, maximum: int, *, allow_override: bool = False) -> dict[str, str]:
    """Freeze a selection; explicit CLI changes get a new linked decision."""
    if type(maximum) is not int or not 0 <= maximum <= 8:
        raise UsageError("strict recovery round selection must be in 0..8")
    journal_path = root.root / "recovery.json"
    if journal_path.is_file():
        previous = canonical.load_file(journal_path).get("budget_policy")
    else:
        first = root.root / "recovery-policy/decision-0001.json"
        previous = {"ref": "recovery-policy/decision-0001.json", "sha256": canonical.digest_file(first)} if first.is_file() else None
    decision = 1
    if previous is not None:
        selected, _ = _policy(root, previous)
        if selected["max_repair_rounds"] == maximum:
            return previous
        if not allow_override:
            raise UsageError("a mutable journal/configuration cannot change the selected recovery bound",
                             [Diagnostic("INPUT_MUTATION", "change the total recovery budget explicitly with --repair-rounds")])
        decision = selected["decision"] + 1
    data = {"format": POLICY_FORMAT, "root_run_id": root.run_id, "decision": decision,
            "max_repair_rounds": maximum, "previous": previous,
            "source": "explicit --repair-rounds override" if previous else "initial configuration or CLI selection"}
    rel = f"recovery-policy/decision-{decision:04d}.json"
    fsutil.write_json(root.root / rel, data, once=True)
    return {"ref": rel, "sha256": canonical.digest_file(root.root / rel)}


def _check_snapshot(pkg: Package, snapshot: dict[str, Any]) -> None:
    if (not isinstance(snapshot, dict) or "manifest" not in snapshot
            or fsutil.manifest_root(snapshot["manifest"]) != snapshot.get("root")
            or _snapshot(pkg) != snapshot):
        raise UsageError("a retained recovery package changed after handoff",
                         [Diagnostic("INPUT_MUTATION", f"recovery lineage for {pkg.root} no longer matches its retained inputs")])


def seed(pkg: Package, result: StageResult, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Exact rejected proposal and concrete diagnostics; no invented counterexample."""
    candidate = pkg.path("contract") / "candidate"
    source = candidate / "proposal.lean"
    if not source.is_file():
        source = candidate / "Contract.lean"
    form_path = candidate / "formalization.json"
    if not source.is_file():
        source = contract.challenge_dir(pkg) / "Contract.lean"
    if not form_path.is_file():
        form_path = contract.challenge_dir(pkg) / "formalization.json"
    previous = None
    if source.is_file() and form_path.is_file():
        previous = {"lean_source": source.read_text(encoding="utf-8"),
                    "formalization": canonical.load_file(form_path)}
        typed = candidate / "typed-proposal.json"
        if typed.is_file():
            previous["typed_proposal"] = canonical.load_file(typed)
    feedback = [f"{d.code}: {d.message}" for d in result.diagnostics
                if d.severity in ("blocking", "infrastructure")]
    feedback.extend(str(error) for error in result.summary.get("failed_stage_summary", {}).get("errors", []))
    # Preserve detailed Lean errors even when the stop occurred at acceptance.
    attempts = pkg.path("contract") / "proofs" / "attempts.jsonl"
    if attempts.is_file():
        lines = attempts.read_bytes().splitlines()
        for line in lines[-4:]:
            entry = canonical.loads(line)
            feedback.extend(str(error) for error in entry.get("errors", []))
    counterexamples = (confirmed_contract_counterexamples(pkg, result, parameters)
                      if parameters and result.summary.get("stopped_at") == "review:formal_contract" else [])
    feedback.extend("CONFIRMED CONTRACT COUNTEREXAMPLE: " + canonical.dumps(case["receipt"]).decode("utf-8")
                    for case in counterexamples)
    return {"feedback": list(dict.fromkeys(feedback)), "previous_candidate": previous,
            "counterexamples": counterexamples,
            "rejected_stage": result.summary.get("stopped_at"),
            "interpretation_root": pkg.interpretation_root()}


def _input_paths(pkg: Package) -> dict[str, Path]:
    out = {"request/prompt.txt": pkg.path("prompt"), "request/request.json": pkg.path("request"),
           "request/routing.json": pkg.path("routing"),
           "draft.json": pkg.path("draft"), "interpretation.json": pkg.path("interpretation")}
    attachments = pkg.root / "request" / "attachments"
    if attachments.is_dir():
        out.update({"request/attachments/" + rel: attachments / rel for rel in fsutil.list_files(attachments)})
    if not all(path.is_file() and not path.is_symlink() for path in out.values()):
        raise UsageError("strict recovery requires intact recorded request and interpretation inputs",
                         [Diagnostic("INPUT_MUTATION", "a recovery input is missing or is a symlink")])
    return out


def create(root: Package, parent: Package, parameters: dict[str, Any], result: StageResult,
           round_number: int, events: EventSink, *, budget_policy: dict[str, str] | None = None) -> tuple[Package, dict[str, Any], dict[str, Any]]:
    """Create a sibling and mechanically revalidate exact interpretation bytes."""
    from . import formalize, interpret

    _, _, diags = formalize.require_interpretation(parent)
    if diags:
        raise UsageError("the recorded interpretation is not eligible for strict recovery", diags)
    context = seed(parent, result, parameters)
    budget_policy = budget_policy or select_policy(root, budget(parameters))
    selected, _ = _policy(root, budget_policy)
    if round_number > selected["max_repair_rounds"]:
        raise UsageError("strict recovery cannot exceed its frozen total round selection")
    before = _snapshot(parent)
    child = Package(root.root.parent / f"{root.root.name}-repair-{round_number:02d}", resolve_root=False)
    if child.root.exists():
        raise UsageError(f"repair package already exists: {child.root}",
                         [Diagnostic("INPUT_MUTATION", "strict recovery never overwrites an existing repair package")])
    inputs = _input_paths(parent)
    with fsutil.package_lock(child.root):
        child.ensure(child.root.name)
        for rel, path in sorted(inputs.items()):
            fsutil.write_once(child.root / rel, path.read_bytes())
        child_params = dict(parameters)
        child_params["prompt_file"] = str(child.path("prompt"))
        child_params["attachments"] = []
        child_params["draft_candidate"] = str(child.path("draft"))
        child_params["ledger_candidate"] = str(child.path("interpretation"))
        child_params["resolve"] = []
        child_params["non_interactive"] = True
        child_params["recovery_context"] = context
        child.set_meta("run_parameters", child_params)
        child.set_meta("requested", parent.meta().get("requested", {}))
        if (parent.path("closure") / "review-config.json").is_file():
            fsutil.write_once(child.path("closure") / "review-config.json",
                              (parent.path("closure") / "review-config.json").read_bytes())
        child_events = EventSink(child.run_id, child.root, quiet=events.quiet)
        try:
            req = canonical.load_file(child.path("request"))
            routing = canonical.load_file(child.path("routing"))
            routing_resolutions = {}
            if routing.get("resolution", {}).get("selected") == "software":
                routing_resolutions["routing"] = "software"
            checked = interpret.run(child, child_events, child.path("prompt"), mode=req["mode"],
                                    request_ref=req["request_ref"], candidate=child.path("draft"),
                                    ledger_path=child.path("interpretation"), interactive=False,
                                    resolutions=routing_resolutions)
        finally:
            child_events.close()
        if checked.status != "PASS" or child.interpretation_root() != context["interpretation_root"]:
            raise UsageError("recovery must preserve the exact recorded interpretation",
                             checked.diagnostics or [Diagnostic("INPUT_MUTATION", "interpretation bytes changed while creating a repair package")])
        # Mechanical interpretation recording must not normalize or alter any original bytes.
        for rel, path in inputs.items():
            if (child.root / rel).read_bytes() != path.read_bytes():
                raise UsageError("recovery altered an original request/interpretation input",
                                 [Diagnostic("INPUT_MUTATION", f"recovery changed {rel}")])
        child.set_meta("completed_stages", ["interpret"])
        child.set_meta("stage_history", [{"stage": "interpret", "status": "PASS", "codes": [], "seconds": 0,
                                          "source": "mechanical revalidation of unchanged recorded interpretation"}])
        copied = fsutil.manifest_for({rel: child.root / rel for rel in inputs})
        lineage = {"format": FORMAT, "root_package": root.root.name, "parent_package": parent.root.name,
                   "root_run_id": root.run_id, "parent_run_id": parent.run_id, "child_run_id": child.run_id,
                   "round": round_number, "interpretation_root": context["interpretation_root"],
                   "copied_inputs": copied, "parent_snapshot": before,
                   "budget_policy": budget_policy,
                   "context_hash": canonical.digest_json(context)}
        fsutil.write_json(child.root / "recovery-lineage.json", lineage, once=True)
        fsutil.write_json(child.root / "recovery-context.json", context, once=True)
        child.set_meta("recovery_root", root.root.name)
    _check_snapshot(parent, before)
    record = {"round": round_number, "package": child.root.name, "parent_package": parent.root.name,
              "lineage_hash": canonical.digest_file(child.root / "recovery-lineage.json"),
              "rejected_stage": context["rejected_stage"],
              "diagnostics": [d.to_json() for d in result.diagnostics], "parent_snapshot": before}
    events.emit("progress", "run", f"strict recovery round {round_number}: new package {child.root.name}; rejected frozen artifacts retained")
    return child, child_params, record


def write_journal(root: Package, active: Package, rounds: list[dict[str, Any]], maximum: int,
                  result: StageResult | None = None, *, budget_policy: dict[str, str] | None = None) -> None:
    budget_policy = budget_policy or select_policy(root, maximum)
    selected, _ = _policy(root, budget_policy)
    if selected["max_repair_rounds"] != maximum or maximum < len(rounds):
        raise UsageError("strict recovery journal cannot alter the frozen budget decision")
    data = {"format": FORMAT, "root_run_id": root.run_id, "root_package": root.root.name,
            "active_package": active.root.name, "max_repair_rounds": maximum, "rounds": rounds,
            "budget_policy": budget_policy,
            "active_status": result.status if result else "RUNNING"}
    fsutil.write_json(root.root / "recovery.json", data, pretty=True)


def _resolve_active(root: Package) -> tuple[Package, list[dict[str, Any]], int]:
    """Read-only lineage validation before resume can follow an active sibling."""
    path = root.root / "recovery.json"
    if not path.is_file():
        return root, [], 0
    journal = canonical.load_file(path)
    if (journal.get("format") != FORMAT or journal.get("root_run_id") != root.run_id
            or journal.get("root_package") != root.root.name or not isinstance(journal.get("rounds"), list)):
        raise UsageError("invalid strict recovery journal", [Diagnostic("INPUT_MUTATION", "recovery journal does not bind this run")])
    current = root
    original_root = root.interpretation_root()
    selected, budget_chain = _policy(root, journal["budget_policy"])
    if journal.get("max_repair_rounds") != selected["max_repair_rounds"]:
        raise UsageError("changed recovery budget journal", [Diagnostic("INPUT_MUTATION", "journal round bound differs from its frozen selection")])
    for number, record in enumerate(journal["rounds"], 1):
        name = record.get("package", "")
        if (name != f"{root.root.name}-repair-{number:02d}" or record.get("round") != number
                or record.get("parent_package") != current.root.name):
            raise UsageError("invalid strict recovery lineage", [Diagnostic("INPUT_MUTATION", "recovery chain is not contiguous")])
        _check_snapshot(current, record["parent_snapshot"])
        child = Package(root.root.parent / name, resolve_root=False)
        lineage_path = child.root / "recovery-lineage.json"
        if not child.exists() or canonical.digest_file(lineage_path) != record.get("lineage_hash"):
            raise UsageError("changed recovery lineage", [Diagnostic("INPUT_MUTATION", "a recovery package or lineage binding changed")])
        lineage = canonical.load_file(lineage_path)
        if (lineage.get("parent_snapshot") != record["parent_snapshot"]
                or lineage.get("root_package") != root.root.name or lineage.get("parent_package") != current.root.name
                or lineage.get("root_run_id") != root.run_id or lineage.get("parent_run_id") != current.run_id
                or lineage.get("child_run_id") != child.run_id or lineage.get("round") != number
                or lineage.get("interpretation_root") != original_root
                or child.interpretation_root() != original_root or lineage.get("budget_policy") not in budget_chain):
            raise UsageError("changed recovery binding", [Diagnostic("INPUT_MUTATION", "recovery lineage no longer binds the unchanged interpretation")])
        creation_policy, _ = _policy(root, lineage["budget_policy"])
        if number > creation_policy["max_repair_rounds"]:
            raise UsageError("invalid recovery round", [Diagnostic("INPUT_MUTATION", "repair exceeded the total budget selected at its creation")])
        copied = lineage["copied_inputs"]
        actual = fsutil.manifest_for({row["path"]: child.root / fsutil.check_relpath(row["path"])
                                     for row in copied["entries"]})
        if actual != copied or canonical.digest_file(child.root / "recovery-context.json") != lineage.get("context_hash"):
            raise UsageError("changed recovery inputs", [Diagnostic("INPUT_MUTATION", "copied request or recovery diagnostics changed")])
        if canonical.digest_json(child.meta().get("run_parameters", {}).get("recovery_context")) != lineage.get("context_hash"):
            raise UsageError("changed recovery context", [Diagnostic("INPUT_MUTATION", "repair parameters do not match the retained diagnostics")])
        current = child
    if journal.get("active_package") != current.root.name:
        raise UsageError("invalid active recovery package", [Diagnostic("INPUT_MUTATION", "active package does not match the last linked repair")])
    maximum = journal.get("max_repair_rounds")
    if type(maximum) is not int or not 0 <= maximum <= 8 or maximum < len(journal["rounds"]):
        raise UsageError("invalid recovery budget", [Diagnostic("INPUT_MUTATION", "recovery journal exceeds its bound")])
    return current, journal["rounds"], maximum


def resolve_active(root: Package) -> tuple[Package, list[dict[str, Any]], int]:
    """Malformed or missing lineage data is a blocked binding, never a fresh start."""
    try:
        return _resolve_active(root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise UsageError("cannot validate strict recovery lineage",
                         [Diagnostic("INPUT_MUTATION", f"recovery lineage validation failed: {exc}")]) from None
