"""One native strict-CLI attempt for each preregistered task, with immutable receipts.

No candidate flags, model-generation deadlines, answer injection or hidden-test feedback.
All failures are retained. A source mutation blocks the cohort rather than rescoring it.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from verislop import canonical, contract, formalize, fsutil, prove, recovery
from verislop.agents import assemble_formalization_response, assemble_proof_response, extract_json
from verislop.errors import VeriSlopError
from verislop.package import Package
from synthetic_dataset.tools.check_data_pipeline_poc import PROTOCOL, REPO, check_preregistration, run_check
from synthetic_dataset.tools.data_pipeline_oracle import TASKS


def source_inputs() -> dict[str, str]:
    paths = {REPO / "pyproject.toml", REPO / "lean-toolchain"}
    paths.update((REPO / "verislop").rglob("*.py"))
    paths.update((REPO / "verislop/lean").rglob("*.lean"))
    paths.update((REPO / "formal").rglob("*.lean"))
    paths.update((REPO / "schemas").glob("*.json"))
    paths.update((REPO / "policies").glob("*.json"))
    paths.update(REPO / "synthetic_dataset/tools" / name for name in
                 ("run_data_pipeline_poc.py", "check_data_pipeline_poc.py", "data_pipeline_oracle.py", "check_reservation_poc.py"))
    return {path.relative_to(REPO).as_posix(): canonical.digest_file(path) for path in sorted(paths) if path.is_file()}


def write_once(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical.dumps(data))


def artifact_origin_audit(pkg: Package, calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconstruct positive artifacts; provider authentication is a separate check.

    Typed proposals are compiled again, without the task oracle. Raw proposals must
    match both source and bindings. Proofs come from recorded model proposals or
    exact deterministic portfolio replay. Accepted meanings remain kernel checked.
    """
    issues, formal_origins, implementation_origins, proof_origins = [], [], [], []
    proposal = pkg.path("contract") / "candidate" / "proposal.lean"
    form_path = proposal.with_name("formalization.json")
    objects = []
    for index, entry in enumerate(calls):
        try:
            objects.append((index, extract_json(entry.get("response") or ""), entry))
        except ValueError:
            continue
    if proposal.is_file():
        actual_form = canonical.load_file(form_path) if form_path.is_file() else None
        records = formalize._records(canonical.load_file(pkg.path("draft")),
                                     canonical.load_file(pkg.path("interpretation")), None)
        # A rejected response can be retained faithfully without becoming a positive
        # artifact. Replaying its deterministic error envelope must not veto a later
        # successful repair merely because the earlier response was invalid.
        negative_placeholder = (proposal.read_bytes() == b"-- unparseable formalizer response\n"
            and isinstance(actual_form, dict) and set(actual_form) == {"error"}
            and not (contract.challenge_dir(pkg) / "challenge.json").exists()
            and not (pkg.path("accepted") / "acceptance.json").exists()
            and not pkg.path("accepted_ir").exists()
            and not (pkg.path("contract") / "proofs" / "attempts.jsonl").exists()
            and not (pkg.path("implementation").is_dir() and any(p.is_file() for p in pkg.path("implementation").rglob("*"))))
        if negative_placeholder:
            for index, entry in enumerate(calls):
                if entry.get("purpose") != "formalize" or not isinstance(entry.get("response"), str):
                    continue
                try:
                    assemble_formalization_response(entry["response"], records,
                                                     entry.get("request_id") or "captured-provider-response")
                except (ValueError, KeyError, TypeError, AttributeError) as exc:
                    if actual_form == {"error": f"unparseable formalizer response: {exc}"}:
                        formal_origins.append({"call_index": index, "assembly": "deterministic-rejected-response-placeholder",
                                               "positive_artifact": False})
        from verislop.agents import CAPABILITY_MARKER
        negative_capability = (proposal.read_bytes() == CAPABILITY_MARKER
            and isinstance(actual_form, dict) and set(actual_form) == {"capability_report"}
            and not (contract.challenge_dir(pkg) / "challenge.json").exists()
            and not (pkg.path("accepted") / "acceptance.json").exists()
            and not pkg.path("accepted_ir").exists()
            and not (pkg.path("contract") / "proofs" / "attempts.jsonl").exists()
            and not (pkg.path("implementation").is_dir() and any(p.is_file() for p in pkg.path("implementation").rglob("*"))))
        if negative_capability:
            for index, entry in enumerate(calls):
                if entry.get("purpose") != "formalize" or not isinstance(entry.get("response"), str):
                    continue
                try:
                    source, form, _ = assemble_formalization_response(entry["response"], records,
                        entry.get("request_id") or "captured-provider-response")
                    if source == proposal.read_bytes() and form == actual_form:
                        formal_origins.append({"call_index": index, "assembly": "deterministic-capability-report",
                                               "positive_artifact": False})
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
        for index, obj, entry in objects:
            if not isinstance(obj, dict) or entry.get("purpose") != "formalize":
                continue
            if isinstance(obj.get("lean_source"), str):
                if (obj["lean_source"].encode() == proposal.read_bytes()
                        and obj.get("formalization") == actual_form):
                    formal_origins.append({"call_index": index, "assembly": "raw-native-source-and-bindings"})
            elif obj.get("encoding") == "verislop.formalizer-ast/0.1":
                try:
                    from verislop.formal_frontend import compile_proposal, replay_receipt
                    origin = canonical.load_file(proposal.with_name("compiler-origin.json"))
                    ast = canonical.load_file(proposal.with_name("typed-proposal.json"))
                    raw = entry["response"].encode()
                    source, form, _ = compile_proposal(obj, records, captured_response=raw,
                                                      response_ref=origin["response_ref"])
                    if (ast == obj and source == proposal.read_bytes() and form == actual_form
                            and replay_receipt(obj, records, source, form, origin, captured_response=raw)):
                        formal_origins.append({"call_index": index, "assembly": "generic-typed-AST-compiler",
                                               "receipt_sha256": canonical.digest_json(origin)})
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    continue
        if not formal_origins:
            issues.append("Formalization proposal source and bindings have no exact recorded response origin")
        composed_paths = [path for path in (proposal.with_name("Contract.lean"), contract.challenge_dir(pkg) / "Contract.lean")
                          if path.is_file()]
        if actual_form is not None and composed_paths:
            try:
                composed_records = formalize._records(canonical.load_file(pkg.path("draft")),
                                                       canonical.load_file(pkg.path("interpretation")), actual_form)
                registry = contract.registry_lean([r for r in composed_records if not r["blocked_by"]],
                                                   contract.binding_names(actual_form))
                composed, _, _ = contract.compose_challenge(proposal.read_bytes(), registry)
                for path in composed_paths:
                    if path.read_bytes() != composed:
                        issues.append("Composed challenge differs from the response-derived source and frozen registry")
                frozen_form = contract.challenge_dir(pkg) / "formalization.json"
                if frozen_form.is_file() and canonical.load_file(frozen_form) != actual_form:
                    issues.append("Frozen formalization bindings differ from the response-derived manifest")
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                issues.append("Cannot reconstruct the formalization registry and challenge")
    implemented = pkg.path("implementation")
    if implemented.is_dir() and any(path.is_file() for path in implemented.rglob("*")):
        actual = {path.relative_to(implemented).as_posix(): path.read_bytes()
                  for path in implemented.rglob("*") if path.is_file()}
        binding_path = pkg.path("bridges") / "bindings.json"
        actual_bindings = canonical.load_file(binding_path) if binding_path.is_file() else None
        for index, obj, entry in objects:
            if (entry.get("purpose") == "generate" and isinstance(obj, dict) and isinstance(obj.get("files"), dict)
                    and all(isinstance(value, str) for value in obj["files"].values())
                    and actual == {key: value.encode() for key, value in obj["files"].items()}
                    and isinstance(actual_bindings, dict)
                    and obj.get("bindings") == actual_bindings):
                implementation_origins.append(index)
        if not implementation_origins:
            issues.append("Implementation bytes have no exact complete native proposal origin")
    attempts = pkg.path("contract") / "proofs" / "attempts.jsonl"
    if attempts.is_file():
        challenge = (contract.challenge_dir(pkg) / "Contract.lean").read_text(encoding="utf-8")
        statements = contract.frozen_json(pkg, "statements.json")["statements"]
        profile = contract.frozen_json(pkg, "profile.json")
        source_hashes = set()
        for line in attempts.read_bytes().splitlines():
            row = canonical.loads(line)
            generator = row.get("generator")
            source = (attempts.parent / "attempts" / f"{row['source_sha256'].split(':')[1][:16]}.lean").read_bytes()
            submitted = (attempts.parent / "proposals" / f"{row['proposal_sha256'].split(':')[1][:16]}.lean").read_bytes()
            if canonical.digest(source) != row["source_sha256"] or canonical.digest(submitted) != row["proposal_sha256"]:
                issues.append("Proof attempt or proposal hash mismatch")
            source_hashes.add(canonical.digest(source))
            if generator == "builtin_tactic_portfolio":
                if source != prove.apply_portfolio(challenge, statements, profile).encode() or submitted != source:
                    issues.append("Builtin proof does not reconstruct from the frozen challenge")
            elif generator == "challenge_as_is":
                if source != challenge.encode() or submitted != source:
                    issues.append("Challenge proof source mismatch")
            elif generator == "agent:prover":
                matches = [index for index, entry in enumerate(calls) if entry.get("purpose") == "prove"
                           and isinstance(entry.get("response"), str)
                           and assemble_proof_response(entry["response"]).encode() == submitted]
                if not matches or source != prove.with_registry(submitted.decode(), challenge).encode():
                    issues.append("Proof bytes have no exact model response and registry origin")
            else:
                issues.append("Proof source supplied manually or by an unregistered generator")
            proof_origins.append({"generator": generator, "source_sha256": row["source_sha256"]})
        candidate = attempts.parent / "candidate.lean"
        if candidate.is_file() and canonical.digest_file(candidate) not in source_hashes:
            issues.append("Selected proof is outside the audited attempt inventory")
        certificate = pkg.path("accepted") / "acceptance.json"
        if certificate.is_file():
            cert = canonical.load_file(certificate)
            accepted = pkg.root / cert["artifacts"]["source"]["path"]
            if not candidate.is_file() or accepted.read_bytes() != candidate.read_bytes():
                issues.append("Accepted proof source differs from the audited selected proof")
    return {"issues": sorted(set(issues)), "formalization_origins": formal_origins,
            "native_implementation_origins": implementation_origins, "proof_origins": proof_origins}


def origin_audit(pkg: Package, argv: list[str], frozen_inputs: dict[str, str], *, effective_config: dict[str, Any] | None = None) -> dict[str, Any]:
    issues, transcript_rows = [], []
    forbidden = {"--candidate", "--interpret-candidate", "--formalize-candidate", "--proof-candidate", "--implementation", "--bindings", "--draft", "--ledger",
                 "--draft-candidate", "--ledger-candidate", "--formalization-candidate", "--implementation-candidate", "--bindings-candidate"}
    options = {arg.split("=", 1)[0] for arg in argv}
    if forbidden.intersection(options) or any(arg.startswith("--bridge-") for arg in options):
        issues.append("Supplied positive artifact argument")
    if source_inputs() != frozen_inputs:
        issues.append("INPUT_MUTATION: frozen runtime or verifier changed")
    configuration = effective_config or canonical.load_file(PROTOCOL / "qwen-config.json")
    installed = configuration["agents"]["author"]
    expected_digest = installed["model_identity"]["model_digest_sha256"]
    calls = []
    for path in sorted(pkg.root.rglob("transcripts/*.json")):
        entry = canonical.load_file(path)
        calls.append(entry)
        transcript_rows.append({"path": path.relative_to(pkg.root).as_posix(), "hash": canonical.digest_file(path),
                                "purpose": entry.get("purpose"), "error": entry.get("error")})
        expected_context = configuration["agents"].get(entry.get("agent"), {}).get("context_window_tokens")
        if entry.get("context_window_tokens") != expected_context:
            issues.append("Transcript context_window_tokens differs from the frozen effective configuration")
        if entry.get("system_sha256") != canonical.digest(entry.get("system", "").encode()) or entry.get("user_sha256") != canonical.digest(entry.get("user", "").encode()):
            issues.append("Transcript prompt digest mismatch")
        if entry.get("response") is not None and (entry.get("requested_model") != installed["model_ref"]
                or entry.get("returned_model") != installed["model_ref"] or entry.get("model_digest_sha256") != expected_digest):
            issues.append("Model identity mismatch")
        if any(marker in entry.get("user", "") for marker in ("expected_wire", "data-pipeline-request-oracle", "withheld/", "PREREGISTRATION.json")):
            issues.append("Withheld evaluation material in an outbound model prompt")
    if not calls:
        issues.append("No native provider transcript")
    artifacts = artifact_origin_audit(pkg, calls)
    issues.extend(artifacts["issues"])
    return {"status": "PASS" if not issues else "BLOCK", "issues": sorted(set(issues)),
            "transcripts": transcript_rows, "provider_calls": len(calls),
            **{key: value for key, value in artifacts.items() if key != "issues"},
            "runtime_root": canonical.digest_json(frozen_inputs), "scope": "Recorded origin and frozen-byte checks; privileged host and transcript fidelity are trusted"}


def active_package(task_root: Path, task: str, native: dict[str, Any], packages: list[Package]) -> Path:
    """A CLI reference must name this invocation's exact validated native repair chain."""
    runs = task_root / "runs"
    run_id = task.lower()
    root = Package(runs / run_id, resolve_root=False)
    if root.root.is_symlink() or root.root.resolve() != root.root or not root.exists() or root.run_id != run_id:
        raise ValueError("Missing or mismatched current-task native root package")
    selected, rounds, _ = recovery.resolve_active(root)
    expected = {root.root} | {runs.absolute() / row["package"] for row in rounds}
    actual = {pkg.root for pkg in packages}
    if actual != expected or any(pkg.root.is_symlink() or pkg.root.resolve() != pkg.root for pkg in packages):
        raise ValueError("Native package inventory differs from this invocation's validated repair lineage")
    refs = [native.get("summary", {}).get(key) for key in ("active_package", "package")]
    refs.append(native.get("artifacts", {}).get("package"))
    refs = [ref for ref in refs if ref is not None]
    if not refs or any(not isinstance(ref, str) or not ref for ref in refs):
        raise ValueError("Native CLI result has no exact active package reference")
    for ref in refs:
        path = Path(ref)
        path = path.absolute() if path.is_absolute() else (REPO / path).absolute()
        if path != selected.root or path not in actual:
            raise ValueError("Native active package is outside the current task's audited repair lineage")
    return selected.root


def task_status(native: dict[str, Any], cli_exit: int | None, oracle: dict[str, Any],
                audits: list[dict[str, Any]], *, bound: bool, unchanged: bool) -> str:
    if not unchanged:
        return "BLOCKED"
    if (bound and native.get("status") == "PASS" and cli_exit == 0 and oracle.get("status") == "VERIFIED"
            and audits and all(row.get("status") == "PASS" for row in audits)):
        return "VERIFIED"
    if native.get("status") == "INFRASTRUCTURE_FAILURE" or (bound and oracle.get("status") == "INFRASTRUCTURE_FAILURE"):
        return "INFRASTRUCTURE_FAILURE"
    return "BLOCKED"


def _seal(cohort: Path, rows: list[dict[str, Any]], frozen: dict[str, str] | None,
          prereg: dict[str, Any] | None, *, reason: str | None = None) -> int:
    by_task = {row["task"]: row for row in rows}
    summary = []
    for task in TASKS:
        if task in by_task:
            row = dict(by_task[task])
            if reason:
                row.update(retained_result_status=row["status"], status="BLOCKED", cohort_blocking_reason=reason)
        else:
            row = {"task": task, "status": "BLOCKED", "reason": reason or "Task did not produce a result",
                   "cli_exit": None, "native_status": None, "package": None,
                   "independent_cases_passed": 0, "independent_cases": 160, "observations": 0,
                   "provider_calls": 0, "origin_audit_passed": False}
            write_once(cohort / task / "result.json", row)
        summary.append(row)
    verified = sum(row["status"] == "VERIFIED" for row in summary)
    status = ("BLOCKED" if reason else "VERIFIED" if verified == len(TASKS) else
              "INFRASTRUCTURE_FAILURE" if any(row["status"] == "INFRASTRUCTURE_FAILURE" for row in summary) else "BLOCKED")
    write_once(cohort / "SUMMARY.json", {"status": status,
        "runtime_root": canonical.digest_json(frozen) if frozen is not None else None,
        "preregistration_root": prereg.get("root") if prereg else None, "tasks": summary,
        "verified_tasks": verified, "total_tasks": len(TASKS), "blocking_reason": reason,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "assurance": "Tier 0 TESTED only, plus finite independent request cases and recorded-origin audit"})
    return 0 if verified == len(TASKS) else 2


def configuration_with_context(tokens: int) -> dict[str, Any]:
    """Only a caller-selected inference parameter; never a model or task change."""
    if type(tokens) is not int or not 1024 <= tokens <= 262144:
        raise ValueError("Ollama context tokens must be an integer from 1024 to 262144")
    cfg = canonical.load_file(PROTOCOL / "qwen-config.json")
    for agent in cfg["agents"].values():
        if cfg["providers"][agent["provider"]]["api_family"] != "ollama_chat":
            raise ValueError("The native context override is supported only for Ollama agents")
        agent["context_window_tokens"] = tokens
    return cfg


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, type=Path, help="New, nonexistent cohort directory")
    parser.add_argument("--ollama-context-tokens", type=int, help="Explicit per-request context; preregistered as a configuration departure")
    args = parser.parse_args(argv)
    cohort = args.cohort.absolute()
    if cohort.exists() or cohort.is_symlink():
        raise ValueError("Cohort is write-once; preserve prior attempts under their existing IDs")
    cohort.mkdir(parents=True)
    prereg, frozen, summary = None, None, []
    effective_config, config_digest = None, None
    config_path = PROTOCOL / "qwen-config.json"
    caught = (VeriSlopError, OSError, ValueError, KeyError, TypeError, AttributeError)
    try:
        prereg = check_preregistration()
        frozen = source_inputs()
        if args.ollama_context_tokens is not None:
            effective_config = configuration_with_context(args.ollama_context_tokens)
            config_path = cohort / "execution-config.json"
            write_once(config_path, effective_config)
            config_digest = canonical.digest_file(config_path)
        for rel in frozen:
            target = cohort / "execution-source" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO / rel).read_bytes())
        write_once(cohort / "source-freeze.json", {"format": "verislop.data-pipeline-source-freeze/0.1",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(), "files": frozen,
            "root": canonical.digest_json(frozen), "preregistration_root": prereg["root"], "tasks": list(TASKS),
            "execution_configuration": ({"path": "execution-config.json", "sha256": config_digest,
                "context_window_tokens": args.ollama_context_tokens,
                "departure": "Explicit context override of the base preregistered configuration; same models, output/call budgets, tasks and test cases"}
                if effective_config is not None else None)})
        profiles = cohort / "config-home" / "endpoint-profiles.json"
        profiles.parent.mkdir()
        profiles.write_bytes((PROTOCOL / "endpoint-profiles.json").read_bytes())
    except caught as exc:
        return _seal(cohort, summary, frozen, prereg, reason=f"Pre-generation input failure: {exc}")
    env = {**os.environ, "VERISLOP_CONFIG_HOME": str(profiles.parent)}
    for task in TASKS:
        try:
            if (check_preregistration()["root"] != prereg["root"] or source_inputs() != frozen
                    or (config_digest is not None and canonical.digest_file(config_path) != config_digest)):
                raise ValueError("INPUT_MUTATION: frozen preregistration, runtime or verifier changed")
        except caught as exc:
            return _seal(cohort, summary, frozen, prereg, reason=str(exc))
        task_root = cohort / task
        task_root.mkdir()
        run_id = task.lower()
        command = [sys.executable, "-m", "verislop", "run", "--prompt-file", str(PROTOCOL / f"{task}.txt"),
                   "--request-ref", f"data-pipelines/{task}.txt", "--config", str(config_path),
                   "--mode", "software", "--tier", "0", "--target", "python", "--endpoint", "test_campaign",
                   "--require-state", "TESTED", "--require-tests", "--non-interactive", "--budget-seconds", "0",
                   "--repair-rounds", "2", "--seed", "20261008", "--cases", "32", "--run-id", run_id,
                   "--runs-dir", str(task_root / "runs"), "--json"]
        write_once(task_root / "invocation.json", {"argv": command, "cwd": str(REPO),
                   "environment_override": {"VERISLOP_CONFIG_HOME": str(profiles.parent)}, "runtime_root": canonical.digest_json(frozen),
                   "started_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_inputs": []})
        print(f"START {task}", flush=True)
        cli_exit, package, audits = None, None, []
        diagnostics = []
        native = {"status": "INFRASTRUCTURE_FAILURE"}
        oracle = {"status": "BLOCKED", "diagnostics": ["No current native package selected"]}
        bound = False
        try:
            with (task_root / "stdout.json").open("xb") as stdout, (task_root / "stderr.log").open("xb") as stderr:
                process = subprocess.run(command, cwd=REPO, env=env, stdout=stdout, stderr=stderr, check=False)
                cli_exit = process.returncode
            native = canonical.load_file(task_root / "stdout.json")
            if (not isinstance(native, dict) or native.get("status") not in ("PASS", "BLOCKED", "INFRASTRUCTURE_FAILURE")
                    or not isinstance(native.get("summary", {}), dict) or not isinstance(native.get("artifacts", {}), dict)):
                raise ValueError("Native CLI result has no valid stage status")
        except caught as exc:
            native = {"status": "INFRASTRUCTURE_FAILURE", "diagnostics": [{"message": f"Native launch/result failure: {exc}"}]}
            diagnostics.append(f"Native launch/result failure: {exc}")
        try:
            packages = [Package(path, resolve_root=False) for path in sorted((task_root / "runs").glob("*")) if (path / "package.json").is_file()]
            for pkg in packages:
                try:
                    audit = (origin_audit(pkg, command, frozen, effective_config=effective_config)
                             if effective_config is not None else origin_audit(pkg, command, frozen))
                except caught as exc:
                    audit = {"status": "BLOCK", "issues": [str(exc)], "provider_calls": 0}
                audits.append({"package": str(pkg.root), **audit})
            package = active_package(task_root, task, native, packages)
            bound = True
            oracle = run_check(package, task)
        except caught as exc:
            diagnostics.append(f"Current native package/oracle binding failure: {exc}")
        write_once(task_root / "origin-audit.json", audits)
        write_once(task_root / "independent-oracle.json", oracle)
        try:
            unchanged = (source_inputs() == frozen and check_preregistration()["root"] == prereg["root"]
                         and (config_digest is None or canonical.digest_file(config_path) == config_digest))
        except caught as exc:
            diagnostics.append(f"Frozen input recheck failed: {exc}")
            unchanged = False
        status = task_status(native, cli_exit, oracle, audits, bound=bound, unchanged=unchanged)
        row = {"task": task, "status": status, "cli_exit": cli_exit, "package": str(package) if package else None,
               "native_status": native.get("status"), "independent_cases_passed": oracle.get("passed_cases", 0),
               "independent_cases": 160, "independent_cases_loaded": oracle.get("distinct_cases", 0), "observations": oracle.get("observations", 0),
               "provider_calls": sum(a["provider_calls"] for a in audits), "origin_audit_passed": bool(audits) and all(a["status"] == "PASS" for a in audits),
               "active_package_bound": bound, "diagnostics": diagnostics}
        write_once(task_root / "result.json", row)
        summary.append(row)
        print(canonical.dumps(row).decode(), flush=True)
        if not unchanged:
            return _seal(cohort, summary, frozen, prereg, reason="INPUT_MUTATION: cohort invalidated; no prior result is promoted")
    return _seal(cohort, summary, frozen, prereg)


if __name__ == "__main__":
    raise SystemExit(main())
