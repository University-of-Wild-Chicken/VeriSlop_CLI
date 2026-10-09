"""Frozen 100-task direct versus strict VeriSlop comparison with fresh Sol agents.

The controller supplies exact final messages through hash-bound carrier mailboxes.
No native provider identity, token usage or carrier-only read enforcement is attested.
Completed scores are immutable. Resume never repeats a model arm or a recorded grader.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import random
import re
import signal
import subprocess
import sys
import tempfile
import time
from synthetic_dataset import benchmark as bench
from synthetic_dataset.build_dataset import ROOT, encode, digest
from synthetic_dataset.tools import luna_data_pipeline_poc as carriers
from synthetic_dataset.tools import run_data_pipeline_poc as origins
from synthetic_dataset.tools import sol_data_pipeline_poc as sol_origins
from synthetic_dataset.tools import sol_data_pipeline_worker as transport
from synthetic_dataset.tools import sol_full_corpus_worker as worker
from synthetic_dataset.tools.luna_benchmark import stop_worker
from verislop import canonical, recovery
from verislop.errors import VeriSlopError
from verislop.package import Package

REPO = ROOT.parent
FORMAT = "verislop.sol-full-corpus/0.1"
SEED = 20261007
ARMS = worker.ARMS
MODEL = worker.MODEL
REPEATS = 2
WITHHELD_MARKERS = ("expected_wire", "withheld/", "PREREGISTRATION.json", "synthetic_dataset/cases/",
                    "generate_algorithms.py", "generate_text_data.py", "generate_graph_systems.py")


def write_once(path: Path, value) -> None:
    write_bytes_once(path, encode(value))


def write_bytes_once(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Publish complete bytes atomically without replacing an existing receipt.
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".publish-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def task_inventory() -> dict[str, dict]:
    tasks = [json.loads(line) for line in (ROOT / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    result = {task["id"]: task for task in tasks}
    if len(result) != 100 or len(tasks) != 100:
        raise ValueError("Original corpus must contain exactly 100 unique tasks")
    return result


def pair_order() -> list[dict]:
    tasks = list(task_inventory())
    random.Random(SEED).shuffle(tasks)
    return [{"task": task, "arm": arm, "pair_index": index} for index, task in enumerate(tasks)
            for arm in (ARMS if index % 2 == 0 else tuple(reversed(ARMS)))]


def source_inventory() -> dict[str, str]:
    sources = origins.source_inputs()
    for path in [*ROOT.glob("*.py"), *ROOT.joinpath("tools").glob("*.py")]:
        sources[path.relative_to(REPO).as_posix()] = digest(path.read_bytes())
    return dict(sorted(sources.items()))


def prepare(cohort: Path) -> dict:
    if cohort.exists() or cohort.is_symlink():
        raise ValueError("Full-corpus cohort is write-once; select a fresh identifier")
    manifest = bench.verify_dataset()
    tasks, order, source = task_inventory(), pair_order(), source_inventory()
    cohort.mkdir(parents=True)
    write_once(cohort / "config.json", worker.configuration())
    write_once(cohort / "provider-home/endpoint-profiles.json", worker.endpoint_profiles())
    from verislop.verifiers import host_environment, registry_snapshot
    protocol = {"format": FORMAT, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_root": manifest["dataset_root"], "dataset_manifest_sha256": digest((ROOT / "manifest.json").read_bytes()),
        "dataset_files": {**manifest["files"], **manifest["generator_hashes"]}, "tasks": list(tasks),
        "pair_order": order, "seed": SEED, "arms": list(ARMS), "source_hashes": source,
        "source_root": canonical.digest_json(source), "config_sha256": digest((cohort / "config.json").read_bytes()),
        "endpoint_profiles_sha256": digest((cohort / "provider-home/endpoint-profiles.json").read_bytes()),
        "transport": "collaboration-agent-simulation", "requested_model": MODEL, "model_override": MODEL,
        "fork_turns": "none", "fresh_agent_per_call": True, "model_identity_attested": False,
        "returned_model": None, "input_tokens": None, "output_tokens": None,
        "token_usage_available": False, "sampling_controls_available": False,
        "output_token_limit_enforced": False, "schema_output_tokens_hint": 8192,
        "relay_mode": "file", "carrier_format": carriers.CARRIER_FORMAT, "tool_policy": carriers.FILE_TOOL_POLICY,
        "raw_calls_per_task": 1, "strict_calls_per_task": 128, "max_calls_per_instance": 24,
        "max_response_bytes": transport.MAX_RESPONSE_BYTES, "contract_repair_rounds": 2,
        "model_generation_deadline": None, "proof_search_deadline": None, "review_tier_deadline": None,
        "strict_tier": 0, "target": "python", "endpoint": "test_campaign", "required_state": "TESTED",
        "generated_cases": 32, "strict_seed": 20261008, "case_seconds": 1, "candidate_memory_mb": 512,
        "independent_repeats": REPEATS, "minimum_clean_builds": 2,
        "cases": sum(len(bench.load(ROOT / task["cases_path"])) for task in tasks.values()),
        "host_environment": host_environment(), "native_verifier_registry": registry_snapshot(),
        "outer_verifiers": [{"id": identifier, "path": rel, "sha256": source[rel]} for identifier, rel in
            (("corpus-exact-json-grader", "synthetic_dataset/benchmark.py"),
             ("corpus-candidate-runtime", "synthetic_dataset/grade_worker.py"),
             ("corpus-exact-json-encoding", "synthetic_dataset/build_dataset.py"),
             ("sol-origin-score-audit", "synthetic_dataset/tools/sol_full_corpus.py")) if rel in source],
        "trusted_components": ["Privileged controller, host OS/hardware/filesystem and exact final-message copying",
            "Frozen corpus oracle and generator outputs", "SHA-256 and exact JSON encoder",
            "Python runtime, Lean kernel and admitted native strict built-in axioms",
            "Native registered verifiers, candidate isolation mechanisms and frozen outer grader/audits"],
        "excluded_claims": ["END_TO_END_VERIFIED or universal implementation correctness",
            "Attested Sol provider/model snapshot, sampling or token usage", "Enforced carrier-only model reads",
            "Equal-compute causal benefit from verification", "Verification of trusted components themselves"],
        "pass_predicate": "All public and hidden cases pass in both independent fresh grader processes, exact response origin and exit0; strict additionally all native CLI gates PASS, Tier0 TESTED native VERIFIED closure and two successful clean builds",
        "hidden_test_policy": "Only original natural-language prompt and its public examples enter model calls; no cases, oracle, historical answers or independent score feedback supplied",
        "resume_policy": "Skip only validated immutable completed scores. Grade completed unscored worker once from recorded observations or original bytes. Never restart a partially generated arm; preserve it as infrastructure failure unless its recorded process is still live",
        "limitations": ["Actual provider identity, snapshot, tokens, sampling and read policy are unattested",
                        "Unequal call counts and formal work prevent equal-compute or causal interpretation",
                        "Finite Tier0 TESTED does not establish END_TO_END_VERIFIED; privileged controller and copied finals are trusted"]}
    write_once(cohort / "protocol.json", protocol)
    for rel in source:
        path = cohort / "execution-source" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write((REPO / rel).read_bytes())
    for rel in protocol["dataset_files"]:
        path = cohort / "frozen-corpus" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write((ROOT / rel).read_bytes())
    write_once(cohort / "preregistration.json", {"format": FORMAT,
        "protocol_sha256": digest((cohort / "protocol.json").read_bytes()), "source_root": protocol["source_root"],
        "dataset_root": manifest["dataset_root"], "pair_order": order, "generation_started": False})
    verify_inputs(cohort)
    update_progress(cohort)
    return protocol


def verify_inputs(cohort: Path) -> dict:
    record = bench.load(cohort / "preregistration.json")
    protocol = bench.load(cohort / "protocol.json")
    manifest = bench.verify_dataset()
    if (not isinstance(record, dict) or not isinstance(protocol, dict)
        or protocol.get("format") != FORMAT or record.get("format") != FORMAT
        or record.get("protocol_sha256") != digest((cohort / "protocol.json").read_bytes())
        or protocol.get("dataset_root") != manifest["dataset_root"] or record.get("dataset_root") != manifest["dataset_root"]
        or protocol.get("dataset_manifest_sha256") != digest((ROOT / "manifest.json").read_bytes())
        or protocol.get("dataset_files") != {**manifest["files"], **manifest["generator_hashes"]}
        or protocol.get("tasks") != list(task_inventory()) or protocol.get("pair_order") != pair_order()
        or record.get("pair_order") != protocol.get("pair_order")
        or protocol.get("source_hashes") != source_inventory()
        or protocol.get("source_root") != canonical.digest_json(protocol["source_hashes"])
        or record.get("source_root") != protocol.get("source_root")
        or protocol.get("config_sha256") != digest((cohort / "config.json").read_bytes())
        or protocol.get("endpoint_profiles_sha256") != digest((cohort / "provider-home/endpoint-profiles.json").read_bytes())
        or bench.load(cohort / "config.json") != worker.configuration()
        or bench.load(cohort / "provider-home/endpoint-profiles.json") != worker.endpoint_profiles()):
        raise ValueError("INPUT_MUTATION: frozen source, corpus, configuration or preregistration changed")
    for base, files in ((cohort / "execution-source", protocol["source_hashes"]), (cohort / "frozen-corpus", protocol["dataset_files"])):
        for rel, expected in files.items():
            path = base / rel
            if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
                raise ValueError("INPUT_MUTATION: retained frozen input changed: " + rel)
    return protocol


def _binding(cohort: Path, task: str, arm: str, request_path: Path, request: dict, protocol: dict, *, create: bool) -> dict:
    if (request.get("transport") != "collaboration" or request.get("requested_model") != MODEL
        or not isinstance(request.get("system"), str) or not isinstance(request.get("user"), str)):
        raise ValueError("Malformed current Sol request")
    if (any(marker in request["system"] or marker in request["user"] for marker in WITHHELD_MARKERS)
        or re.search(r"tasks/[^\s\"']+/cases\.json", request["system"] + request["user"])):
        raise ValueError("Withheld evaluation material in outbound model packet")
    relay = carriers._relay_binding(cohort, task + "/" + arm, request_path, request, protocol, create_carrier=create)
    return {"task": task, "arm": arm, "request_path": str(request_path), "request": request,
            "request_sha256": digest(request_path.read_bytes()), "supplemental_protocol_root": digest((cohort / "protocol.json").read_bytes()),
            "source_root": protocol["source_root"], "dataset_root": protocol["dataset_root"], **relay,
            "model_override": MODEL, "fork_turns": "none", "model_identity_attested": False}


def pending_request(cohort: Path) -> dict | None:
    protocol = verify_inputs(cohort)
    state = bench.load(cohort / "active-arm.json", {})
    if state.get("phase") != "generation":
        return None
    task, arm = state.get("task"), state.get("arm")
    if {"task": task, "arm": arm, "pair_index": state.get("pair_index")} not in protocol["pair_order"]:
        raise ValueError("Active task/arm is outside frozen selection")
    mailbox = cohort / "artifacts" / task / arm / "mailbox"
    requests = sorted(mailbox.glob("request-*.json"))
    if len(requests) > (1 if arm == "raw" else 128):
        raise ValueError("Logical-call budget exceeded")
    for index, path in enumerate(requests, 1):
        request = bench.load(path)
        if not isinstance(request, dict) or request.get("request_id") != f"{index:04d}" or path.name != f"request-{index:04d}.json":
            raise ValueError("Mailbox request sequence is not exact")
        if not (mailbox / f"response-{index:04d}.json").exists():
            return _binding(cohort, task, arm, path, request, protocol, create=True)
    return None


def _check_envelope(envelope: dict, pending: dict) -> tuple[str, str]:
    text, agent = transport.validate_response(envelope, pending["request"]["request_id"], pending["request_sha256"])
    expected = {key: pending[key] for key in ("task", "arm", "supplemental_protocol_root", "source_root", "dataset_root",
        "spawn_message_sha256", "carrier_path", "carrier_sha256", "model_override", "fork_turns")}
    expected.update(relay_mode="file", model_identity_attested=False)
    if envelope.get("model_identity_attested") is not False or any(envelope.get(key) != value for key, value in expected.items()):
        raise ValueError("Response lacks exact task/arm/source/corpus/protocol/carrier/fresh-model binding")
    return text, agent


def submit_response(cohort: Path, envelope: dict) -> dict:
    pending = pending_request(cohort)
    if pending is None:
        raise ValueError("No pending request; unsolicited/repeated final rejected")
    if isinstance(envelope, dict) and envelope.get("text") == "" and "transport_error" not in envelope:
        envelope = {**envelope, "transport_error": dict(transport.EMPTY_FINAL_ERROR)}
    text, agent = _check_envelope(envelope, pending)
    for path in (cohort / "artifacts").rglob("response-*.json"):
        if not path.name.startswith("response-receipt-") and bench.load(path, {}).get("agent_task_id") == agent:
            raise ValueError("Agent already used; each logical call requires a fresh agent")
    path = Path(pending["request_path"]).with_name(f"response-{pending['request']['request_id']}.json")
    write_once(path, envelope)
    return {"published": str(path), "agent_task_id": agent, "output_bytes": len(text.encode()), "task": pending["task"], "arm": pending["arm"]}


def response_audit(cohort: Path, task: dict, arm: str) -> dict:
    protocol = verify_inputs(cohort)
    directory = cohort / "artifacts" / task["id"] / arm
    mailbox = directory / "mailbox"
    requests = sorted(mailbox.glob("request-*.json"))
    receipts = sorted(mailbox.glob("response-receipt-*.json"))
    error_receipts = sorted(mailbox.glob("transport-error-receipt-*.json"))
    finals = {path.stem.removeprefix("response-"): path for path in mailbox.glob("response-*.json") if not path.name.startswith("response-receipt-")}
    issues, responses, failures, agents = [], {}, {}, []
    if arm == "raw":
        from synthetic_dataset.arm_worker import RAW_SYSTEM
        if len(requests) != 1 or any(bench.load(requests[0], {}).get(key) != value for key, value in
            {"system": RAW_SYSTEM, "user": (ROOT / task["prompt_path"]).read_text(), "agent": "author", "instance": "raw/1", "purpose": "raw-coding"}.items()):
            issues.append("Raw request differs from exact original natural-language coding call")
    receipt_ids = [bench.load(path, {}).get("request_id") for path in [*receipts, *error_receipts]]
    if len(receipt_ids) != len(set(receipt_ids)) or set(receipt_ids) != set(finals):
        issues.append("Finals do not have exactly one consumed normal/error receipt")
    if len(receipt_ids) != len(requests):
        issues.append("A model request remained undelivered at arm completion")
    invocation = bench.load(directory / "cli-invocation.json", {})
    if invocation.get("argv") != (worker.cli_argv(cohort, task) if arm == "verislop" else []):
        issues.append("CLI invocation differs from the strict frozen workflow")
    outer = bench.load(directory / "invocation.json", {})
    expected_command = [sys.executable, "-m", "synthetic_dataset.tools.sol_full_corpus_worker", "--cohort", str(cohort), "--task", task["id"], "--arm", arm]
    if (outer.get("argv") != expected_command or outer.get("cwd") != str(REPO)
        or outer.get("cli_argv") != (worker.cli_argv(cohort, task) if arm == "verislop" else []) or outer.get("candidate_inputs") != []):
        issues.append("Worker invocation differs from frozen transport-only workflow")
    for path in [*receipts, *error_receipts]:
        receipt = bench.load(path, {})
        rid = receipt.get("request_id")
        try:
            reqpath, finalpath = mailbox / f"request-{rid}.json", mailbox / f"response-{rid}.json"
            request, envelope = bench.load(reqpath), bench.load(finalpath)
            pending = _binding(cohort, task["id"], arm, reqpath, request, protocol, create=False)
            text, agent = _check_envelope(envelope, pending)
            agents.append(agent)
            empty = "transport_error" in envelope
            expected = {"request_sha256": pending["request_sha256"], "response_sha256": digest(finalpath.read_bytes()),
                "text_sha256": digest(text.encode()), "output_bytes": len(text.encode()), "agent_task_id": agent,
                "requested_model": MODEL, "returned_model": None, "input_tokens": None, "output_tokens": None,
                "transport": "collaboration", "model_identity_attested": False,
                "format": "verislop.collaboration-response-receipt/0.1"}
            if empty:
                expected.update(format="verislop.collaboration-transport-error-receipt/0.1", transport_error=transport.EMPTY_FINAL_ERROR)
            if any(receipt.get(key) != value for key, value in expected.items()) or empty != (path in error_receipts):
                issues.append("Receipt differs from exact final/request bytes")
            if empty:
                failures[transport.transport_error_message(envelope)] = request
            else:
                responses[agent] = (request, text)
        except Exception as exc:
            issues.append("Invalid final binding: " + str(exc))
    usage = bench.load(mailbox / "usage.json", {})
    instances = Counter(bench.load(path, {}).get("instance") for path in requests)
    if (usage.get("calls", 0) != len(requests) or usage.get("responses", 0) != len(receipts)
        or usage.get("transport_errors", 0) != len(error_receipts) or len(requests) > (1 if arm == "raw" else 128)
        or any(count > 24 for count in instances.values()) or usage.get("input_tokens") is not None or usage.get("output_tokens") is not None
        or usage.get("token_usage_available") is not False
        or usage.get("output_bytes", 0) != sum(bench.load(path, {})["output_bytes"] for path in [*receipts, *error_receipts])):
        issues.append("Usage differs from exact bounded receipt evidence or invents tokens")
    seen, seen_failures, all_calls, packages = set(), set(), [], []
    roots = [directory] if arm == "raw" else sorted(path for path in directory.glob("package*") if (path / "package.json").is_file())
    for root in roots:
        calls = []
        if arm == "verislop":
            pkg = Package(root, resolve_root=False)
            prompt = pkg.path("prompt")
            if not prompt.is_file() or prompt.read_bytes() != (ROOT / task["prompt_path"]).read_bytes():
                issues.append("Package request differs from original natural-language prompt")
        for path in sorted(root.rglob("transcripts/*.json")):
            call = bench.load(path, {})
            calls.append(call)
            if (call.get("system_sha256") != digest(call.get("system", "").encode()) or call.get("user_sha256") != digest(call.get("user", "").encode())
                or call.get("requested_model") != MODEL or call.get("returned_model") is not None or call.get("model_digest_sha256") is not None):
                issues.append("Transcript context hashes or honest model identity differ")
            if call.get("response") is not None:
                agent = call.get("request_id")
                match = responses.get(agent)
                if match is None or match[1] != call["response"] or any(call.get(key) != match[0].get(key) for key in ("system", "user", "purpose", "agent", "instance")) or agent in seen:
                    issues.append("Delivered completion lacks unique exact bound fresh-agent origin")
                seen.add(agent)
            elif call.get("error") in failures:
                error = call["error"]
                if error in seen_failures or any(call.get(key) != failures[error].get(key) for key in ("system", "user", "purpose", "agent", "instance")):
                    issues.append("Empty final transcript lacks unique exact error origin")
                seen_failures.add(error)
        all_calls.extend(calls)
        origin = sol_origins.raw_origin(directory, calls) if arm == "raw" else origins.artifact_origin_audit(Package(root, resolve_root=False), calls)
        issues.extend(origin["issues"])
        packages.append({"path": str(root.relative_to(cohort)), "origin": origin})
    if seen != set(responses) or seen_failures != set(failures):
        issues.append("Recorded finals differ from actual delivered transcript inventory")
    if len(agents) != len(set(agents)):
        issues.append("Agent reused within arm")
    return {"status": "PASS" if not issues else "BLOCK", "issues": sorted(set(issues)), "provider_calls": len(requests),
            "responses": len(receipts), "transport_errors": len(error_receipts), "agents": agents,
            "packages": packages, "model_identity_attested": False, "milestone_authority": False}


def active_package(directory: Path, pipeline: dict) -> Path:
    """Validate exact native recovery lineage, without replaying its verifiers."""
    root = Package(directory / "package", resolve_root=False)
    if not root.exists() or root.run_id != "package" or root.root.is_symlink() or root.root.resolve() != root.root:
        raise ValueError("Missing/mismatched current invocation root package")
    selected, rounds, _ = recovery.resolve_active(root)
    expected = {root.root} | {directory.absolute() / row["package"] for row in rounds}
    actual = {path for path in directory.glob("package*") if (path / "package.json").is_file()}
    if actual != expected or any(path.is_symlink() or path.resolve() != path for path in actual):
        raise ValueError("Package inventory differs from validated current invocation repair lineage")
    if bench.resolve_cli_package(directory, pipeline) != selected.root:
        raise ValueError("CLI active package differs from validated repair lineage")
    return selected.root


def _strict_qualified(pipeline: dict, report: dict, exit_code: int | None, stages: list) -> bool:
    return bool(bench.cli_success(pipeline, report, exit_code, stages=stages)
                and len(report.get("builds", [])) >= 2
                and all(build.get("ok") is True and not build.get("errors") for build in report["builds"]))


def _score_observations(observed: dict, cases: list[dict]) -> list[dict]:
    repeats = observed.get("repeats", [])
    if len(repeats) != REPEATS:
        raise ValueError("Missing independent grading repeat")
    for repeat in repeats:
        if [row.get("id") for row in repeat.get("results", [])] != [case["id"] for case in cases]:
            raise ValueError("Recorded observations differ from frozen case order")
    scores = []
    for index, case in enumerate(cases):
        values = [repeat["results"][index] for repeat in repeats]
        valid = []
        for row in values:
            status = "PASS" if "error" not in row and "observed" in row and encode(row["observed"]) == encode(case["expected"]) else "FAIL"
            if row.get("status") != status or ("expected" in row and encode(row["expected"]) != encode(case["expected"])):
                raise ValueError("Recorded case status/expected differs from exact frozen output")
            valid.append(status == "PASS")
        scores.append({"id": case["id"], "status": "PASS" if all(valid) else "FAIL", "observations": values})
    return scores


def score_arm(cohort: Path, selection: dict, *, _derive_only: bool = False) -> dict:
    protocol = verify_inputs(cohort)
    task = task_inventory()[selection["task"]]
    arm = selection["arm"]
    directory = cohort / "artifacts" / task["id"] / arm
    existing = directory / "score.json"
    if existing.exists() and not _derive_only:
        row = bench.load(existing)
        validate_score(cohort, selection, row)
        return row
    exit_record = bench.load(directory / "worker-result.json", {})
    pipeline = bench.load(directory / "stdout.json", {})
    if not isinstance(pipeline, dict):
        pipeline = {}
    summary = pipeline.get("summary", {})
    summary = summary if isinstance(summary, dict) else {}
    package, report, meta, error = None, {}, {}, None
    if arm == "verislop":
        try:
            package = active_package(directory, pipeline)
            report, meta = bench.load(package / "report.json", {}), bench.load(package / "package.json", {})
        except (ValueError, VeriSlopError) as exc:
            error = str(exc)
    report, meta = report if isinstance(report, dict) else {}, meta if isinstance(meta, dict) else {}
    try:
        files, entry = bench.artifact_files(arm, directory, pipeline)
    except ValueError as exc:
        files, entry, error = {}, None, str(exc)
    cases = bench.load(ROOT / task["cases_path"])
    audit_path = directory / "origin-audit.json"
    audit = response_audit(cohort, task, arm)
    if audit_path.exists() and bench.load(audit_path) != audit:
        raise ValueError("Completed response/transcript/source origin evidence changed")
    if not audit_path.exists():
        if _derive_only:
            raise ValueError("Completed origin audit is missing")
        write_once(audit_path, audit)
    obs_path = directory / "observations.json"
    if obs_path.exists():
        observed = bench.load(obs_path)
    else:
        if _derive_only:
            raise ValueError("Completed independent observations are missing")
        observed = {"repeats": [], "infrastructure_errors": []}
        for repeat in range(1, REPEATS + 1):
            start_path = directory / "grading" / f"repeat-{repeat:02d}-started.json"
            done_path = directory / "grading" / f"repeat-{repeat:02d}.json"
            if done_path.exists():
                receipt = bench.load(done_path)
            elif start_path.exists():
                receipt = {"results": [{"id": case["id"], "status": "FAIL", "reason": "unretained grading attempt"} for case in cases],
                    "isolation": {}, "infrastructure_error": {"type": "InterruptedGrader", "message": "Started grader has no retained result; ambiguous attempt is never rerun"}}
                write_once(done_path, receipt)
            else:
                write_once(start_path, {"repeat": repeat, "source_hashes": {key: digest(data) for key, data in files.items()}})
                try:
                    scores, isolation = bench.grade(files, entry, cases, protocol["case_seconds"])
                    receipt = {"results": scores, "isolation": isolation}
                except Exception as exc:
                    receipt = {"results": [{"id": case["id"], "status": "FAIL", "reason": "grading infrastructure unavailable"} for case in cases],
                        "isolation": {}, "infrastructure_error": {"type": type(exc).__name__, "message": str(exc)}}
                write_once(done_path, receipt)
            if receipt.get("infrastructure_error"):
                observed["infrastructure_errors"].append(receipt["infrastructure_error"])
            observed["repeats"].append({"results": receipt["results"], "isolation": receipt["isolation"]})
        write_once(obs_path, observed)
    scores = _score_observations(observed, cases)
    hidden = [score for score, case in zip(scores, cases) if case["visibility"] == "hidden"]
    public = [score for score, case in zip(scores, cases) if case["visibility"] == "public"]
    stages = summary.get("stages", meta.get("stage_history", []))
    qualified = _strict_qualified(pipeline, report, exit_record.get("exit_code"), stages) if arm == "verislop" else None
    successful = bool(entry and hidden and all(score["status"] == "PASS" for score in scores)
                      and exit_record.get("exit_code") == 0 and audit["status"] == "PASS"
                      and not observed["infrastructure_errors"] and (arm == "raw" or qualified))
    usage = bench.load(directory / "mailbox/usage.json", {})
    requests = sorted((directory / "mailbox").glob("request-*.json"))
    native_status = pipeline.get("status") or report.get("terminal_status") or exit_record.get("status") or "ERROR"
    native_infrastructure = native_status == "INFRASTRUCTURE_FAILURE" or bool(report.get("infrastructure_errors"))
    required = [value for value in report.get("obligations", {}).values() if value.get("required")]
    tested_required = [value for value in required if "TESTED" in value.get("required_milestones", [])]
    tested_passed = sum(value.get("outcomes", {}).get("TESTED") == "PASS" for value in tested_required)
    row = {**selection, "task_id": task["id"], "category": task["category"], "title": task["title"],
        "workflow_status": "SUCCESS" if successful else "INFRASTRUCTURE_FAILURE" if native_infrastructure or observed["infrastructure_errors"] or exit_record.get("status") in ("WORKER_ERROR", "INTERRUPTED", "CONTROLLER_INTERRUPTED") else "BLOCKED",
        "native_status": native_status, "successful_task": successful, "artifact_present": bool(files),
        "entry_file": entry, "artifact_error": error, "source_hashes": {key: digest(data) for key, data in files.items()},
        "worker_exit_code": exit_record.get("exit_code"), "timed_out": False,
        "generation_seconds": bench.load(directory / "timing.json", {}).get("generation_seconds", 0),
        "usage": usage, "hidden_passed": sum(score["status"] == "PASS" for score in hidden), "hidden_total": len(hidden),
        "public_passed": sum(score["status"] == "PASS" for score in public), "public_total": len(public),
        "executed_observations": sum("observed" in row or "error" in row for repeat in observed["repeats"] for row in repeat["results"]),
        "passed_observations": sum(row["status"] == "PASS" for repeat in observed["repeats"] for row in repeat["results"]),
        "native_tested": bool(tested_required and tested_passed == len(tested_required)),
        "required_tested_guarantees": len(tested_required), "passed_tested_guarantees": tested_passed,
        "clean_builds": len(report.get("builds", [])), "successful_clean_builds": sum(build.get("ok") is True and not build.get("errors") for build in report.get("builds", [])),
        "held_out_results": hidden, "public_results": public, "strict_cli_success": qualified,
        "origin_audit_passed": audit["status"] == "PASS", "cli_stages": stages, "last_model_purpose": bench.load(requests[-1], {}).get("purpose") if requests else None,
        "cli_diagnostics": pipeline.get("diagnostics", report.get("blocking_reasons", []) + report.get("infrastructure_errors", [])),
        "grading_infrastructure_errors": observed["infrastructure_errors"], "active_package": str(package.relative_to(cohort)) if package else None,
        "cli_report": str((package / "report.json").relative_to(cohort)) if report else None, "recovery": summary.get("recovery"),
        "artifact_path": directory.relative_to(cohort).as_posix(), "observations_sha256": digest(obs_path.read_bytes()),
        "origin_audit_sha256": digest(audit_path.read_bytes()), "protocol_sha256": digest((cohort / "protocol.json").read_bytes()),
        "source_root": protocol["source_root"], "dataset_root": protocol["dataset_root"]}
    row["arm_evidence_root"] = canonical.digest_json(arm_evidence_files(directory))
    if not _derive_only:
        write_once(existing, row)
    return row


def arm_evidence_files(directory: Path) -> dict:
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Arm evidence symlinks are unsupported")
        if path.is_file() and path != directory / "score.json":
            files[path.relative_to(directory).as_posix()] = digest(path.read_bytes())
    return files


def validate_score(cohort: Path, selection: dict, row: dict) -> None:
    protocol = verify_inputs(cohort)
    if not isinstance(row, dict) or any(row.get(key) != value for key, value in selection.items()):
        raise ValueError("Completed score is outside the exact frozen task/arm selection")
    directory = cohort / "artifacts" / selection["task"] / selection["arm"]
    if row.get("arm_evidence_root") != canonical.digest_json(arm_evidence_files(directory)):
        raise ValueError("Completed arm evidence changed")
    if encode(row) != encode(score_arm(cohort, selection, _derive_only=True)):
        raise ValueError("Completed score differs from exact retained evidence")
    return


def completed_rows(cohort: Path) -> list[dict]:
    rows = []
    for selection in pair_order():
        path = cohort / "artifacts" / selection["task"] / selection["arm"] / "score.json"
        if path.exists():
            row = bench.load(path)
            validate_score(cohort, selection, row)
            rows.append(row)
    return rows


def update_progress(cohort: Path, *, status: str = "RUNNING", _read_only: bool = False) -> dict:
    protocol = verify_inputs(cohort)
    rows = completed_rows(cohort)
    arms = {}
    for arm in ARMS:
        values = [row for row in rows if row["arm"] == arm]
        arms[arm] = {"total_tasks": 100, "completed_tasks": len(values), "successful_tasks": sum(row["successful_task"] for row in values),
            "cases_passed": sum(row["hidden_passed"] + row["public_passed"] for row in values),
            "case_slots_scored": sum(row["hidden_total"] + row["public_total"] for row in values),
            "total_case_slots": protocol["cases"], "executed_observations": sum(row["executed_observations"] for row in values),
            "passed_observations": sum(row["passed_observations"] for row in values),
            "model_calls": sum(row["usage"].get("calls", 0) for row in values), "input_tokens": None, "output_tokens": None,
            "native_tested_tasks": sum(row["native_tested"] for row in values),
            "required_tested_guarantees": sum(row["required_tested_guarantees"] for row in values),
            "passed_tested_guarantees": sum(row["passed_tested_guarantees"] for row in values),
            "clean_builds": sum(row["clean_builds"] for row in values),
            "successful_clean_builds": sum(row["successful_clean_builds"] for row in values),
            "statuses": dict(Counter(row["workflow_status"] for row in values)), "native_statuses": dict(Counter(row["native_status"] for row in values))}
    pairs = {task: {row["arm"]: row["successful_task"] for row in rows if row["task"] == task} for task in protocol["tasks"]}
    paired = Counter("both_success" if pair["raw"] and pair["verislop"] else "raw_only" if pair["raw"] else "verislop_only" if pair["verislop"] else "neither_success" for pair in pairs.values() if len(pair) == 2)
    summary = {"format": FORMAT, "status": status, "complete": len(rows) == 200, "completed_arms": len(rows),
        "complete_pairs": sum(paired.values()), "arms": arms, "paired": dict(paired), "model": MODEL,
        "model_identity_attested": False, "dataset_root": protocol["dataset_root"], "source_root": protocol["source_root"],
        "protocol_sha256": digest((cohort / "protocol.json").read_bytes()), "results": rows}
    if not _read_only:
        transport.atomic_json(cohort / "progress.json", summary)
    return summary


def _pid_alive(pid) -> bool:
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def run_arm(cohort: Path, selection: dict) -> dict:
    verify_inputs(cohort)
    directory = cohort / "artifacts" / selection["task"] / selection["arm"]
    if (directory / "score.json").exists():
        return score_arm(cohort, selection)
    if directory.exists():
        if not (directory / "worker-result.json").exists():
            state = bench.load(directory / "process.json", {})
            if _pid_alive(state.get("pid")):
                raise ValueError("A previous arm worker is still live; do not replace or duplicate its generation")
            write_once(directory / "worker-result.json", {"status": "CONTROLLER_INTERRUPTED", "exit_code": None,
                "reason": "Existing partial arm cannot be restarted silently", "model_identity_attested": False})
        return score_arm(cohort, selection)
    directory.mkdir(parents=True)
    command = [sys.executable, "-m", "synthetic_dataset.tools.sol_full_corpus_worker", "--cohort", str(cohort),
               "--task", selection["task"], "--arm", selection["arm"]]
    task = task_inventory()[selection["task"]]
    write_once(directory / "invocation.json", {"argv": command, "cwd": str(REPO),
        "cli_argv": worker.cli_argv(cohort, task) if selection["arm"] == "verislop" else [], "candidate_inputs": []})
    transport.atomic_json(cohort / "active-arm.json", {**selection, "phase": "generation"})
    start = time.monotonic()
    process = None
    with (directory / "stdout.json").open("xb") as stdout, (directory / "stderr.log").open("xb") as stderr:
        try:
            process = subprocess.Popen(command, cwd=REPO, env=dict(os.environ, VERISLOP_CONFIG_HOME=str(cohort / "provider-home")),
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            write_once(directory / "process.json", {"pid": process.pid, "started_at_utc": datetime.now(timezone.utc).isoformat()})
            process.wait()  # No model, proof-search, review or arm deadline.
        except BaseException:
            if process:
                stop_worker(process)
            raise
        finally:
            write_once(directory / "timing.json", {"generation_seconds": round(time.monotonic() - start, 3)})
    if not (directory / "worker-result.json").exists():
        write_once(directory / "worker-result.json", {"status": "WORKER_ERROR", "exit_code": process.returncode,
            "reason": "Worker terminated before its durable exit receipt", "model_identity_attested": False})
    elif bench.load(directory / "worker-result.json")["exit_code"] != process.returncode:
        raise ValueError("Worker exit receipt differs from actual subprocess return code")
    transport.atomic_json(cohort / "active-arm.json", {**selection, "phase": "grading"})
    return score_arm(cohort, selection)


def verify(cohort: Path) -> dict:
    protocol = verify_inputs(cohort)
    rows = completed_rows(cohort)
    agents = [agent for row in rows for agent in bench.load(cohort / row["artifact_path"] / "origin-audit.json")["agents"]]
    if len(agents) != len(set(agents)):
        raise ValueError("Fresh response agent reused across corpus arms")
    if (cohort / "EVIDENCE-MANIFEST.json").exists():
        if len(rows) != 200:
            raise ValueError("Sealed comparison lacks all 200 exact arm results")
        summary = bench.load(cohort / "SUMMARY.json", {})
        if summary.get("status") != "COMPLETE" or summary.get("complete") is not True or summary.get("results") != rows:
            raise ValueError("Final summary differs from complete validated scores")
        if summary != update_progress(cohort, status="COMPLETE", _read_only=True):
            raise ValueError("Final aggregate differs from exact immutable arm scores")
        result_bytes = b"".join(encode(row) for row in rows)
        if not (cohort / "results.jsonl").is_file() or (cohort / "results.jsonl").read_bytes() != result_bytes:
            raise ValueError("Final result inventory differs from validated exact arm scores")
        if bench.load(cohort / "progress.json") != summary:
            raise ValueError("Final progress and sealed summary differ")
        if (cohort / "REPORT.md").read_text(encoding="utf-8") != report_text(summary):
            raise ValueError("Final report differs from exact final score aggregation")
        manifest = bench.load(cohort / "EVIDENCE-MANIFEST.json")
        actual = evidence_files(cohort)
        if manifest.get("files") != actual or manifest.get("files_root") != canonical.digest_json(actual):
            raise ValueError("Final evidence bytes changed")
    return {"status": "PASS", "completed_arms": len(rows), "fresh_agents": len(agents),
            "source_root": protocol["source_root"], "dataset_root": protocol["dataset_root"], "model_identity_attested": False}


def evidence_files(cohort: Path) -> dict:
    files = {}
    for path in sorted(cohort.rglob("*")):
        if path.is_symlink():
            raise ValueError("Evidence symlinks are unsupported")
        if path.is_file() and path not in (cohort / "EVIDENCE-MANIFEST.json", cohort / ".controller.lock"):
            files[path.relative_to(cohort).as_posix()] = digest(path.read_bytes())
    return files


def report_text(summary: dict) -> str:
    lines = ["# Full-corpus GPT-6.1 Sol comparison", "",
        f"Status: {summary['status']}; {summary['completed_arms']}/200 arms and {summary['complete_pairs']}/100 complete pairs.", "",
        f"Frozen original dataset: `{summary['dataset_root']}`.", f"Frozen runtime and verifier source: `{summary['source_root']}`.", "",
        "Each logical model call requests a fresh gpt-6.1-sol collaboration agent with fork_turns=none. Exact current SYSTEM/USER carrier reads are instructed; actual provider identity, snapshot, sampling, token usage and carrier-only read enforcement are unattested. This is not a native OpenAI API benchmark.", ""]
    for arm, label in (("raw", "Direct generation"), ("verislop", "Strict VeriSlop")):
        value = summary["arms"][arm]
        lines += [f"- **{label}:** {value['successful_tasks']}/{value['total_tasks']} successful tasks; {value['completed_tasks']} completed arms; {value['cases_passed']}/{value['case_slots_scored']} scored public/hidden case slots passed; {value['passed_observations']}/{value['executed_observations']} executed observations passed; {value['model_calls']} logical calls."]
    value = summary["arms"]["verislop"]
    lines += ["", f"Strict native TESTED attainment: {value['native_tested_tasks']}/100 tasks; {value['passed_tested_guarantees']}/{value['required_tested_guarantees']} required TESTED guarantees passed; {value['successful_clean_builds']}/{value['clean_builds']} retained clean builds succeeded.", "",
        "Direct generation has one call. Strict generation runs the existing CLI Tier 0 Python test_campaign endpoint with TESTED required, all interpretation/Lean/review/implementation/closure gates unchanged, at most 128 logical calls per task, 24 calls per instance and two bounded fresh-package contract repairs. Native Broker token budgets reset per fresh repair package; actual Sol tokens are unknown. There are no generation, proof-search or review wall deadlines.", "",
        "Task shuffle seed 20261007 and alternating arm order match the original 100-task experiment. Original natural-language prompts include only their two public examples. The 1,157 frozen public/hidden cases, original generator references and historical answers are excluded from model carrier packets and are never repair feedback. Each generated artifact is scored in two fresh filesystem/network-isolated Python grader processes with one-second case and 512 MiB memory limits. Exact JSON output comparison runs outside the candidate sandbox.", "",
        "A raw task succeeds only with exact unedited response origin, exit0 and all cases passing in both graders. A strict task also needs actual native CLI PASS, validated current repair lineage, Tier0 TESTED VERIFIED closure, all required gates and milestones passing, and at least two successful clean builds. Native TESTED attainment is reported separately from full-task completion. Missing artifacts have unsuccessful case slots but zero executed observations; such slots are not observed concrete implementation failures.", "",
        "Completed scores and all their arm evidence are immutable. Resume skips validated completed scores, reuses retained grader receipts, and never repeats a partially generated arm or an ambiguous lost grading attempt. Infrastructure failures remain distinct from concrete candidate mismatches.", "",
        "This single synthetic run uses unequal prompt sizes, call counts and formal work. It does not establish an equal-compute causal benefit, universal correctness or END_TO_END_VERIFIED. Privileged host/OS/hardware/filesystem, Python/Lean kernel and admitted native axioms, isolation mechanisms, SHA-256, frozen oracle and exact controller copying remain trusted; protocol.json declares the finite trust boundary and registered verifier identities.", "",
        "Authoritative per-arm score.json files retain exact observations, origin audits, native reports, intermediate JSON/Lean artifacts, durable memory snapshots and model request/final receipts. SUMMARY.json and results.jsonl derive only from validated scores. EVIDENCE-MANIFEST.json seals every retained result file; protocol.json and preregistration.json bind all frozen input bytes.", ""]
    return "\n".join(lines)


def finalize(cohort: Path) -> int:
    rows = completed_rows(cohort)
    if len(rows) != 200:
        raise ValueError("Cannot seal an incomplete full-corpus result")
    transport.atomic_json(cohort / "active-arm.json", {"phase": "complete"})
    summary = update_progress(cohort, status="COMPLETE")
    if (cohort / "SUMMARY.json").exists():
        if bench.load(cohort / "SUMMARY.json") != summary:
            raise ValueError("Existing final summary differs from exact validated scores")
    else:
        write_once(cohort / "SUMMARY.json", summary)
    result_bytes = b"".join(encode(row) for row in rows)
    for path, expected in ((cohort / "results.jsonl", result_bytes), (cohort / "REPORT.md", report_text(summary).encode("utf-8"))):
        if path.exists():
            if path.read_bytes() != expected:
                raise ValueError("Existing final artifact differs from exact validated scores")
        else:
            write_bytes_once(path, expected)
    files = evidence_files(cohort)
    write_once(cohort / "EVIDENCE-MANIFEST.json", {"format": FORMAT, "files": files, "files_root": canonical.digest_json(files),
        "protocol_sha256": digest((cohort / "protocol.json").read_bytes())})
    verify(cohort)
    return 0


def run(cohort: Path) -> int:
    verify_inputs(cohort)
    if (cohort / "EVIDENCE-MANIFEST.json").exists():
        verify(cohort)
        return 0
    with (cohort / ".controller.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another full-corpus controller is running") from None
        previous = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("Explicit controller interruption")))
        try:
            if (cohort / "SUMMARY.json").exists():
                return finalize(cohort)
            for selection in pair_order():
                row = run_arm(cohort, selection)
                summary = update_progress(cohort)
                print(json.dumps({"task": selection["task"], "arm": selection["arm"], "status": row["workflow_status"],
                    "successful_task": row["successful_task"], "completed_arms": summary["completed_arms"]}), flush=True)
            verify(cohort)
            return finalize(cohort)
        except KeyboardInterrupt:
            transport.atomic_json(cohort / "active-arm.json", {"phase": "stopped"})
            update_progress(cohort, status="INTERRUPTED")
            return 130
        finally:
            signal.signal(signal.SIGTERM, previous)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "worker", "verify", "pending", "submit"))
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--response-file", type=Path)
    parser.add_argument("--task")
    parser.add_argument("--arm", choices=ARMS)
    args = parser.parse_args(argv)
    cohort = args.cohort.absolute()
    if args.action == "run":
        return run(cohort)
    if args.action == "worker":
        if args.task not in task_inventory() or args.arm not in ARMS:
            raise ValueError("Worker requires a selected task/arm")
        return worker.execute(cohort, task_inventory()[args.task], args.arm)
    if args.action == "prepare":
        value = prepare(cohort)
    elif args.action == "verify":
        value = verify(cohort)
    elif args.action == "pending":
        value = pending_request(cohort)
    else:
        if args.response_file is None or args.response_file.stat().st_size > transport.MAX_ENVELOPE_BYTES:
            raise ValueError("Submit requires a bounded exact captured-agent envelope")
        value = submit_response(cohort, bench.load(args.response_file))
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
