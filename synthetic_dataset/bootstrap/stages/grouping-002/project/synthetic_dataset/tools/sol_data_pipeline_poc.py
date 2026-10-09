"""Frozen, paired Sol 6.1 direct versus full strict-CLI data-pipeline experiment.

No command spawns agents. A controller delivers unedited fresh-agent finals using
hash-bound current SYSTEM/USER carriers. No generation/proof/tier deadlines apply.
Model identity, sampling, token usage and read-policy enforcement are unattested.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import Any

from verislop import canonical, fsutil
from verislop.errors import VeriSlopError
from verislop.package import Package
from verislop.targets import python_target as pt
from synthetic_dataset.tools import check_data_pipeline_poc as checker
from synthetic_dataset.tools import luna_data_pipeline_poc as carriers
from synthetic_dataset.tools import run_data_pipeline_poc as native
from synthetic_dataset.tools.check_reservation_poc import exact
from synthetic_dataset.tools.data_pipeline_oracle import TASKS
from synthetic_dataset.tools.luna_benchmark import stop_worker
from synthetic_dataset.tools.sol_data_pipeline_worker import (
    ARMS, MODEL, MAX_CALLS, MAX_RESPONSE_BYTES, MAX_ENVELOPE_BYTES, EMPTY_FINAL_ERROR,
    atomic_json, cli_argv, configuration, endpoint_profiles, transport_error_message, validate_response,
)

FORMAT = "verislop.sol-data-pipeline-paired/0.1"
ERRORS = (VeriSlopError, OSError, ValueError, KeyError, TypeError, AttributeError)
WITHHELD_MARKERS = carriers.WITHHELD_MARKERS
CARRIER_FORMAT = carriers.CARRIER_FORMAT
FILE_TOOL_POLICY = carriers.FILE_TOOL_POLICY


def pair_order() -> list[dict[str, str]]:
    return [{"task": task, "arm": arm} for index, task in enumerate(TASKS)
            for arm in (ARMS if index % 2 == 0 else tuple(reversed(ARMS)))]


def source_inventory() -> dict[str, str]:
    sources = native.source_inputs()
    paths = [*native.REPO.joinpath("synthetic_dataset").glob("*.py"),
             *native.REPO.joinpath("synthetic_dataset/tools").glob("*.py")]
    sources.update({p.relative_to(native.REPO).as_posix(): canonical.digest_file(p) for p in paths if p.is_file()})
    return dict(sorted(sources.items()))


source_inputs = source_inventory


def prepare(cohort: Path) -> dict[str, Any]:
    if cohort.exists() or cohort.is_symlink():
        raise ValueError("Paired cohort is write-once; choose a fresh identifier")
    prereg = checker.check_preregistration()
    frozen = source_inventory()
    cohort.mkdir(parents=True)
    native.write_once(cohort / "config.json", configuration())
    native.write_once(cohort / "provider-home/endpoint-profiles.json", endpoint_profiles())
    protocol = {"format": FORMAT, "tasks": list(TASKS), "arms": list(ARMS), "pair_order": pair_order(),
        "generation_started": False, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_preregistration_root": prereg["root"], "source_hashes": frozen,
        "source_root": canonical.digest_json(frozen), "config_sha256": canonical.digest_file(cohort / "config.json"),
        "endpoint_profiles_sha256": canonical.digest_file(cohort / "provider-home/endpoint-profiles.json"),
        "transport": "collaboration-agent-simulation", "requested_model": MODEL, "model_override": MODEL,
        "fork_turns": "none", "fresh_agent_per_call": True, "returned_model": None,
        "model_digest_sha256": None, "model_identity_attested": False, "token_usage_available": False,
        "input_tokens": None, "output_tokens": None, "sampling_controls_available": False,
        "output_token_limit_enforced": False, "schema_output_tokens_hint": 8192,
        "relay_mode": "file", "carrier_format": CARRIER_FORMAT, "tool_policy": FILE_TOOL_POLICY,
        "raw_calls_per_task": 1, "strict_calls_per_task": MAX_CALLS, "max_calls_per_instance": 24,
        "max_response_bytes": MAX_RESPONSE_BYTES, "model_generation_deadline": None,
        "proof_search_deadline": None, "review_tier_deadline": None,
        "attempts_per_task_arm": 1, "contract_repair_rounds": 2, "strict_tier": 0,
        "target": "python", "required_state": "TESTED", "task_seed": 20261008, "generated_cases": 32,
        "independent_cases_per_task": 160, "independent_repeats": 2,
        "hidden_test_policy": "No oracle, cases, expected values or historical artifacts supplied in outbound packets; observation starts after the arm finishes",
        "proof_origin_policy": "Exact fresh-agent proposals and unchanged deterministic compiler/registry/tactic portfolio only; no manual code or proofs",
        "raw_pass_predicate": "Exact raw proposal origin and exit0 plus all160 independent cases in both fresh harnesses; no CLI milestone",
        "strict_pass_predicate": "Native CLI PASS/exit0, validated repair lineage, accepted Tier0 TESTED closure VERIFIED, exact origin and all independent observations",
        "policy_departures": ["Collaboration cannot attest an immutable provider snapshot; require_fixed_model_snapshot=false",
                              "Strict logical-call bound128 replaces the old supplemental32 limit for the new autonomous correction workflow",
                              "8192 is a response hint, not an enforced output-token cap; actual token usage is unavailable"],
        "limitations": ["Actual model identity, sampling, token usage and read-policy enforcement are unattested",
                        "Differing prompts, call counts and formal work prevent equal-compute or causal interpretation",
                        "Finite request cases and Tier0 TESTED do not establish END_TO_END_VERIFIED; privileged host and copied finals are trusted"]}
    native.write_once(cohort / "protocol.json", protocol)
    for rel in frozen:
        destination = cohort / "execution-source" / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write((native.REPO / rel).read_bytes())
    native.write_once(cohort / "preregistration.json", {"format": FORMAT, "generation_started": False,
        "protocol_sha256": canonical.digest_file(cohort / "protocol.json"), "source_root": protocol["source_root"],
        "base_preregistration_root": prereg["root"], "tasks": list(TASKS), "pair_order": pair_order()})
    verify_inputs(cohort)
    return protocol


def verify_inputs(cohort: Path) -> dict[str, Any]:
    record = canonical.load_file(cohort / "preregistration.json")
    protocol = canonical.load_file(cohort / "protocol.json")
    if (record.get("format") != FORMAT or protocol.get("format") != FORMAT
            or record.get("protocol_sha256") != canonical.digest_file(cohort / "protocol.json")
            or record.get("tasks") != list(TASKS) or protocol.get("tasks") != list(TASKS)
            or record.get("pair_order") != pair_order() or protocol.get("pair_order") != pair_order()
            or protocol.get("arms") != list(ARMS) or protocol.get("requested_model") != MODEL
            or protocol.get("model_override") != MODEL or protocol.get("fork_turns") != "none"
            or protocol.get("relay_mode") != "file" or protocol.get("tool_policy") != FILE_TOOL_POLICY
            or protocol.get("carrier_format") != CARRIER_FORMAT
            or record.get("base_preregistration_root") != checker.check_preregistration()["root"]
            or protocol.get("base_preregistration_root") != record["base_preregistration_root"]
            or protocol.get("source_hashes") != source_inventory()
            or protocol.get("source_root") != canonical.digest_json(protocol["source_hashes"])
            or record.get("source_root") != protocol["source_root"]
            or protocol.get("config_sha256") != canonical.digest_file(cohort / "config.json")
            or protocol.get("endpoint_profiles_sha256") != canonical.digest_file(cohort / "provider-home/endpoint-profiles.json")
            or canonical.load_file(cohort / "config.json") != configuration()
            or canonical.load_file(cohort / "provider-home/endpoint-profiles.json") != endpoint_profiles()):
        raise ValueError("INPUT_MUTATION: paired protocol, source, configuration or base preregistration changed")
    for rel, digest in protocol["source_hashes"].items():
        if canonical.digest_file(cohort / "execution-source" / rel) != digest:
            raise ValueError("INPUT_MUTATION: retained execution-source bytes changed")
    return protocol


def _binding(cohort: Path, task: str, arm: str, request_path: Path, request: dict,
             protocol: dict, *, create: bool) -> dict:
    if (request.get("transport") != "collaboration" or request.get("requested_model") != MODEL
            or not isinstance(request.get("system"), str) or not isinstance(request.get("user"), str)):
        raise ValueError("Malformed current simulation request")
    if any(marker in request["system"] or marker in request["user"] for marker in WITHHELD_MARKERS):
        raise ValueError("Withheld evaluation material in an outbound model request")
    relay = carriers._relay_binding(cohort, task + "/" + arm, request_path, request, protocol, create_carrier=create)
    return {"task": task, "arm": arm, "request_path": str(request_path), "request": request,
            "request_sha256": canonical.digest_file(request_path),
            "supplemental_protocol_root": canonical.digest_file(cohort / "protocol.json"), **relay,
            "model_override": MODEL, "fork_turns": "none", "model_identity_attested": False}


def pending_request(cohort: Path) -> dict | None:
    protocol = verify_inputs(cohort)
    state_path = cohort / "active-arm.json"
    state = canonical.load_file(state_path) if state_path.is_file() else {}
    if state.get("phase") != "generation":
        return None
    task, arm = state.get("task"), state.get("arm")
    if task not in TASKS or arm not in ARMS:
        raise ValueError("Active mailbox is outside the fixed task/arm list")
    directory = cohort / "artifacts" / task / arm / "mailbox"
    requests = sorted(directory.glob("request-*.json"))
    if len(requests) > (1 if arm == "raw" else MAX_CALLS):
        raise ValueError("Paired logical-call budget exceeded before delivery")
    for index, path in enumerate(requests, 1):
        request = canonical.load_file(path)
        if request.get("request_id") != f"{index:04d}" or path.name != f"request-{index:04d}.json":
            raise ValueError("Request sequence differs from exact ordered mailbox")
        if not (directory / f"response-{index:04d}.json").exists():
            return _binding(cohort, task, arm, path, request, protocol, create=True)
    return None


def _check_envelope(envelope: dict, pending: dict) -> tuple[str, str]:
    text, agent = validate_response(envelope, pending["request"]["request_id"], pending["request_sha256"])
    expected = {key: pending[key] for key in ("task", "arm", "supplemental_protocol_root", "spawn_message_sha256",
                                             "carrier_path", "carrier_sha256", "model_override", "fork_turns")}
    expected.update(relay_mode="file", model_identity_attested=False)
    if envelope.get("model_identity_attested") is not False or any(envelope.get(key) != value for key, value in expected.items()):
        raise ValueError("Response lacks exact fresh-agent/task/arm/protocol/current-carrier binding")
    return text, agent


def submit_response(cohort: Path, envelope: dict) -> dict:
    pending = pending_request(cohort)
    if pending is None:
        raise ValueError("No pending request; unsolicited or repeated final rejected")
    if isinstance(envelope, dict) and envelope.get("text") == "" and "transport_error" not in envelope:
        envelope = {**envelope, "transport_error": dict(EMPTY_FINAL_ERROR)}
    text, agent = _check_envelope(envelope, pending)
    for path in (cohort / "artifacts").rglob("response-*.json"):
        if not path.name.startswith("response-receipt-") and canonical.load_file(path).get("agent_task_id") == agent:
            raise ValueError("Agent already used; every call in either arm needs a fresh agent")
    destination = Path(pending["request_path"]).with_name(f"response-{pending['request']['request_id']}.json")
    if destination.exists() or destination.is_symlink():
        raise ValueError("A prior response cannot be replaced")
    atomic_json(destination, envelope)
    return {"published": str(destination), "task": pending["task"], "arm": pending["arm"],
            "agent_task_id": agent, "output_bytes": len(text.encode()), "model_identity_attested": False}


def simulation_audit(cohort: Path, task: str, arm: str, packages: list[Package]) -> list[dict]:
    protocol = verify_inputs(cohort)
    directory = cohort / "artifacts" / task / arm
    mailbox = directory / "mailbox"
    requests = sorted(mailbox.glob("request-*.json"))
    receipts = sorted(mailbox.glob("response-receipt-*.json"))
    error_receipts = sorted(mailbox.glob("transport-error-receipt-*.json"))
    issues, responses, failures = [], {}, {}
    if arm == "raw":
        from synthetic_dataset.arm_worker import RAW_SYSTEM
        expected_user = (checker.PROTOCOL / f"{task}.txt").read_text(encoding="utf-8")
        if len(requests) != 1:
            issues.append("Raw arm did not make exactly one direct request")
        elif any(canonical.load_file(requests[0]).get(key) != value for key, value in
                 {"agent": "author", "instance": "raw/1", "purpose": "raw-coding", "system": RAW_SYSTEM,
                  "user": expected_user}.items()):
            issues.append("Raw outbound context differs from the preregistered natural-language request")
    finals = {path.stem.removeprefix("response-"): path for path in mailbox.glob("response-*.json")
              if not path.name.startswith("response-receipt-")}
    receipt_ids = [canonical.load_file(path)["request_id"] for path in [*receipts, *error_receipts]]
    if len(receipt_ids) != len(set(receipt_ids)) or set(receipt_ids) != set(finals):
        issues.append("Published normal/error finals do not have exactly one consumed receipt")
    global_ids = []
    for path in (cohort / "artifacts").rglob("response-*.json"):
        if not path.name.startswith("response-receipt-"):
            global_ids.append(canonical.load_file(path).get("agent_task_id"))
    if len(global_ids) != len(set(global_ids)):
        issues.append("A response agent was reused across task/arm requests")
    for path in [*receipts, *error_receipts]:
        receipt = canonical.load_file(path)
        rid = receipt["request_id"]
        request_path, response_path = mailbox / f"request-{rid}.json", mailbox / f"response-{rid}.json"
        request, envelope = canonical.load_file(request_path), canonical.load_file(response_path)
        pending = _binding(cohort, task, arm, request_path, request, protocol, create=False)
        text, agent = _check_envelope(envelope, pending)
        empty = "transport_error" in envelope
        expected = {"request_sha256": pending["request_sha256"], "response_sha256": canonical.digest_file(response_path),
            "text_sha256": canonical.digest(text.encode()), "output_bytes": len(text.encode()), "agent_task_id": agent,
            "requested_model": MODEL, "returned_model": None, "input_tokens": None, "output_tokens": None,
            "transport": "collaboration", "model_identity_attested": False,
            "format": "verislop.collaboration-response-receipt/0.1"}
        if empty:
            expected.update(format="verislop.collaboration-transport-error-receipt/0.1", transport_error=EMPTY_FINAL_ERROR)
        if any(receipt.get(key) != value for key, value in expected.items()) or empty != (path in error_receipts):
            issues.append("Mailbox receipt differs from exact request/response/final bytes")
        if empty:
            failures[transport_error_message(envelope)] = request
        else:
            responses[agent] = (request, text)
    usage = canonical.load_file(mailbox / "usage.json") if (mailbox / "usage.json").is_file() else {}
    instances = Counter(canonical.load_file(path)["instance"] for path in requests)
    if (usage.get("calls") != len(requests) or usage.get("responses") != len(receipts)
            or usage.get("transport_errors", 0) != len(error_receipts)
            or len(requests) > (1 if arm == "raw" else MAX_CALLS) or any(n > 24 for n in instances.values())
            or usage.get("input_tokens") is not None or usage.get("output_tokens") is not None
            or usage.get("token_usage_available") is not False
            or usage.get("output_bytes") != sum(canonical.load_file(path)["output_bytes"] for path in [*receipts, *error_receipts])):
        issues.append("Usage differs from bounded exact-call/byte evidence or invents tokens")
    roots = [(pkg.root, pkg) for pkg in packages] if arm == "strict" else [(directory, None)]
    audits, seen, seen_failures = [], set(), set()
    for root, pkg in roots:
        errors, calls, transcripts = list(issues), [], []
        for path in sorted(root.rglob("transcripts/*.json")):
            entry = canonical.load_file(path)
            calls.append(entry)
            transcripts.append({"path": path.relative_to(root).as_posix(), "sha256": canonical.digest_file(path),
                                "purpose": entry.get("purpose")})
            if (entry.get("system_sha256") != canonical.digest(entry.get("system", "").encode())
                    or entry.get("user_sha256") != canonical.digest(entry.get("user", "").encode())
                    or entry.get("requested_model") != MODEL or entry.get("returned_model") is not None
                    or entry.get("model_digest_sha256") is not None):
                errors.append("Transcript prompt hashes or honest simulation identity differ")
            if entry.get("response") is not None:
                identity = entry.get("request_id")
                match = responses.get(identity)
                if (match is None or match[1] != entry["response"]
                        or any(entry.get(key) != match[0][key] for key in ("system", "user", "purpose", "instance", "agent"))):
                    errors.append("Delivered response has no exact bound fresh-agent origin")
                if identity in seen:
                    errors.append("A final was delivered more than once")
                seen.add(identity)
            elif entry.get("error") in failures:
                error = entry["error"]
                if any(entry.get(key) != failures[error][key] for key in ("system", "user", "purpose", "instance", "agent")):
                    errors.append("Failure transcript differs from exact empty-final context")
                if error in seen_failures:
                    errors.append("An empty final was delivered more than once")
                seen_failures.add(error)
        origin = native.artifact_origin_audit(pkg, calls) if pkg else raw_origin(directory, calls)
        errors.extend(origin["issues"])
        audits.append({"package": str(root), "status": "PASS" if not errors else "BLOCK", "issues": sorted(set(errors)),
                       "provider_calls": len(calls), "transcripts": transcripts, "artifact_origin": origin,
                       "identity_scope": "Requested fresh Sol override only; actual model identity and read-policy enforcement unattested"})
    if seen != set(responses) or seen_failures != set(failures):
        for row in audits:
            row["status"] = "BLOCK"
            row["issues"].append("Mailbox finals differ from actually delivered transcript inventory")
    return audits


def raw_origin(directory: Path, calls: list[dict]) -> dict:
    from verislop.agents import extract_json
    path = directory / "artifact/solution.py"
    issues, origins = [], []
    if path.is_file() and not path.is_symlink():
        for index, call in enumerate(calls):
            try:
                obj = extract_json(call.get("response") or "")
                if (set(obj) == {"files"} and set(obj["files"]) == {"solution.py"}
                        and obj["files"]["solution.py"].encode() == path.read_bytes()):
                    origins.append(index)
            except (ValueError, TypeError, KeyError, AttributeError):
                pass
        if not origins or set(fsutil.list_files(path.parent)) != {"solution.py"}:
            issues.append("Raw source lacks exact complete direct-response origin")
    return {"issues": issues, "raw_implementation_origins": origins, "milestone_authority": False}


def observe_raw(artifact: Path, task: str) -> dict:
    """Same withheld wire cases and fresh target harness, without CLI milestones."""
    result = {"status": "BLOCKED", "task": task, "distinct_cases": 0, "passed_cases": 0, "observations": 0,
              "passed_observations": 0, "diagnostics": [], "cases": [], "isolation": [],
              "milestone_authority": False, "scope": "Finite direct-artifact observations only"}
    before = None
    try:
        checker.check_preregistration()
        if artifact.is_symlink() or not artifact.is_dir():
            raise ValueError("No exact raw artifact directory")
        before = fsutil.manifest_tree(artifact)
        inventory = pt.inventory(artifact)
        function = inventory.find("solution.py", "solve")
        if (inventory.errors or function is None or function["kind"] != "function" or function["positional"] != 1
                or function["varargs"] or function["defaults"] or function["kwonly_required"] or function["decorated"]):
            raise ValueError("Raw artifact has no unambiguous one-argument solve function")
        cases = canonical.load_file(checker.PROTOCOL / "withheld" / f"{task}.json")["cases"]
        result.update(distinct_cases=len(cases), cases=[{**case, "observations": []} for case in cases],
                      implementation_manifest=before, runtime=pt.python_identity())
        for _ in range(2):
            harness = pt.Harness(artifact, inventory.files, {"solve": ("solution.py", "solve")}, per_call_timeout=1.0,
                                 memory_mb=512, require_network_isolation=True, require_filesystem_isolation=True)
            try:
                result["isolation"].append(harness.isolation)
                for case in result["cases"]:
                    response = harness.call("solve", [case["input_wire"]])
                    canonical.dumps(response)
                    passed = (set(response) == {"op", "id", "value"} and response["op"] == "result"
                              and response["id"] == harness.calls and exact(response["value"], case["expected_wire"]))
                    case["observations"].append({"response": response, "passed": passed})
            finally:
                harness.close()
        if cases and all(len(case["observations"]) == 2 and all(row["passed"] for row in case["observations"]) for case in result["cases"]):
            result["status"] = "OBSERVATIONS_PASSED"
    except (pt.HarnessError, *ERRORS) as exc:
        result["diagnostics"].append(str(exc))
        if isinstance(exc, pt.HarnessError) and exc.kind not in ("timeout", "crash", "protocol", "import_failure", "error"):
            result["status"] = "INFRASTRUCTURE_FAILURE"
    finally:
        for case in result["cases"]:
            case["passed"] = len(case["observations"]) == 2 and all(row["passed"] for row in case["observations"])
        result["passed_cases"] = sum(case["passed"] for case in result["cases"])
        result["observations"] = sum(len(case["observations"]) for case in result["cases"])
        result["passed_observations"] = sum(row["passed"] for case in result["cases"] for row in case["observations"])
        result["input_bytes_unchanged"] = before is not None and before == fsutil.manifest_tree(artifact)
        if before is not None and not result["input_bytes_unchanged"]:
            result["status"] = "BLOCKED"
            result["diagnostics"].append("INPUT_MUTATION: direct artifact changed during observation")
    return result


def seal(cohort: Path, records: list[dict], protocol: dict | None, *, reason: str | None = None) -> int:
    inventory = {(row["task"], row["arm"]): row for row in records}
    rows = []
    for selection in pair_order():
        task, arm = selection["task"], selection["arm"]
        path = cohort / "artifacts" / task / arm / "result.json"
        if path.is_file():
            row = canonical.load_file(path)
            if (row.get("task"), row.get("arm")) != (task, arm) or ((task, arm) in inventory and row != inventory[task, arm]):
                raise ValueError("Durable paired row differs from the exact task/arm result")
        elif (task, arm) in inventory:
            row = inventory[task, arm]
            native.write_once(path, row)
        else:
            usage_path = path.parent / "mailbox/usage.json"
            usage = canonical.load_file(usage_path) if usage_path.is_file() else {}
            row = {"task": task, "arm": arm, "status": "INTERRUPTED" if usage.get("calls") else "UNSTARTED",
                   "successful_task": False, "reason": reason or "No completed arm result", "provider_calls": usage.get("calls", 0),
                   "independent_cases_passed": 0, "observations": 0, "cli_exit": None, "origin_audit_passed": False}
            native.write_once(path, row)
        rows.append(row)
    arms = {arm: {"successful_tasks": sum(row.get("successful_task", False) for row in rows if row["arm"] == arm),
                  "total_tasks": len(TASKS), "provider_calls": sum(row.get("provider_calls", 0) for row in rows if row["arm"] == arm),
                  "cases_passed": sum(row.get("independent_cases_passed", 0) for row in rows if row["arm"] == arm),
                  "observations": sum(row.get("observations", 0) for row in rows if row["arm"] == arm)} for arm in ARMS}
    paired = dict.fromkeys(("both_success", "raw_only", "strict_only", "neither_success"), 0)
    for task in TASKS:
        raw, strict = (next(row.get("successful_task", False) for row in rows if row["task"] == task and row["arm"] == arm) for arm in ARMS)
        paired["both_success" if raw and strict else "raw_only" if raw else "strict_only" if strict else "neither_success"] += 1
    summary = {"format": FORMAT, "requested_model": MODEL, "model_identity_attested": False,
               "source_root": protocol.get("source_root") if protocol else None,
               "tasks": rows, "arms": arms, "paired": paired,
               "complete": not reason and all(row.get("status") not in ("INTERRUPTED", "UNSTARTED") for row in rows),
               "blocking_reason": reason, "completed_at_utc": datetime.now(timezone.utc).isoformat(),
               "assurance": "Raw finite cases versus native Tier0 TESTED plus independent finite cases; no E2V"}
    native.write_once(cohort / "SUMMARY.json", summary)
    manifest = {path.relative_to(cohort).as_posix(): canonical.digest_file(path)
                for path in sorted(cohort.rglob("*")) if path.is_file() and path.name != "EVIDENCE-MANIFEST.json"}
    native.write_once(cohort / "EVIDENCE-MANIFEST.json", {"format": "verislop.paired-evidence/0.1", "files": manifest,
                                                         "files_root": canonical.digest_json(manifest)})
    return 0 if all(row.get("successful_task", False) for row in rows) else 2


def run(cohort: Path) -> int:
    if (cohort / "SUMMARY.json").exists() or (cohort / "active-arm.json").exists():
        raise ValueError("Paired run is write-once; it cannot rerun a started cohort")
    protocol = verify_inputs(cohort)
    records = []
    env = dict(os.environ, VERISLOP_CONFIG_HOME=str(cohort / "provider-home"))
    previous = signal.getsignal(signal.SIGTERM)
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("Explicit controller interruption")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        for selection in pair_order():
            verify_inputs(cohort)
            task, arm = selection["task"], selection["arm"]
            directory = cohort / "artifacts" / task / arm
            directory.mkdir(parents=True)
            command = [sys.executable, "-m", "synthetic_dataset.tools.sol_data_pipeline_worker", "--cohort", str(cohort), "--task", task, "--arm", arm]
            native.write_once(directory / "invocation.json", {"argv": command, "cwd": str(native.REPO),
                               "cli_argv": cli_argv(cohort, task) if arm == "strict" else [], "candidate_inputs": []})
            atomic_json(cohort / "active-arm.json", {**selection, "phase": "generation"})
            process, stdout, stderr, exit_code = None, b"", b"", None
            result, package, audits, observation = {}, None, [], {"status": "BLOCKED"}
            errors, unchanged = [], True
            try:
                process = subprocess.Popen(command, cwd=native.REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                stdout, stderr = process.communicate()  # no generation deadline
                exit_code = process.returncode
                result = canonical.loads(stdout)
                if not isinstance(result, dict):
                    raise ValueError("Worker produced no result object")
            except KeyboardInterrupt:
                if process:
                    stdout, stderr = stop_worker(process)
                (directory / "stdout.json").write_bytes(stdout)
                (directory / "stderr.log").write_bytes(stderr)
                raise
            except ERRORS as exc:
                errors.append("Worker launch/result failure: " + str(exc))
                result = {"status": "INFRASTRUCTURE_FAILURE"}
            (directory / "stdout.json").write_bytes(stdout)
            (directory / "stderr.log").write_bytes(stderr)
            atomic_json(cohort / "active-arm.json", {**selection, "phase": "observation"})
            try:
                if arm == "strict":
                    packages = [Package(path, resolve_root=False) for path in sorted((directory / "runs").glob("*")) if (path / "package.json").is_file()]
                    package = native.active_package(directory, task, result, packages)
                    audits = simulation_audit(cohort, task, arm, packages)
                    observation = checker.run_check(package, task)
                else:
                    audits = simulation_audit(cohort, task, arm, [])
                    observation = observe_raw(directory / "artifact", task)
            except ERRORS as exc:
                errors.append("Origin/package/observation failure: " + str(exc))
            try:
                verify_inputs(cohort)
            except ERRORS as exc:
                unchanged = False
                errors.append(str(exc))
            origin_pass = bool(audits) and all(row["status"] == "PASS" for row in audits)
            successful = bool(unchanged and origin_pass and exit_code == 0
                and ((arm == "raw" and result.get("status") == "ARTIFACT" and observation.get("status") == "OBSERVATIONS_PASSED")
                     or (arm == "strict" and result.get("status") == "PASS" and observation.get("status") == "VERIFIED")))
            native.write_once(directory / "origin-audit.json", audits)
            native.write_once(directory / "independent-oracle.json", observation)
            usage_path = directory / "mailbox/usage.json"
            usage = canonical.load_file(usage_path) if usage_path.is_file() else {}
            row = {**selection, "status": "SUCCESS" if successful else "INFRASTRUCTURE_FAILURE" if result.get("status") in ("INFRASTRUCTURE_FAILURE", "WORKER_ERROR") else "BLOCKED",
                   "successful_task": successful, "cli_exit": exit_code, "native_status": result.get("status"),
                   "package": str(package) if package else None, "provider_calls": usage.get("calls", 0),
                   "responses": usage.get("responses", 0), "origin_audit_passed": origin_pass,
                   "independent_cases": 160, "independent_cases_loaded": observation.get("distinct_cases", 0),
                   "independent_cases_passed": observation.get("passed_cases", 0), "observations": observation.get("observations", 0),
                   "model_identity_attested": False, "input_tokens": None, "output_tokens": None, "diagnostics": errors}
            native.write_once(directory / "result.json", row)
            records.append(row)
            if not unchanged:
                return seal(cohort, records, protocol, reason="INPUT_MUTATION: paired source changed")
        atomic_json(cohort / "active-arm.json", {"phase": "complete"})
        return seal(cohort, records, protocol)
    except KeyboardInterrupt:
        atomic_json(cohort / "active-arm.json", {"phase": "stopped"})
        return seal(cohort, records, protocol, reason="Explicitly interrupted; pending/unvisited arms unsuccessful")
    except ERRORS as exc:
        return seal(cohort, records, protocol, reason=str(exc))
    finally:
        signal.signal(signal.SIGTERM, previous)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "pending", "submit"))
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--response-file", type=Path)
    args = parser.parse_args(argv)
    cohort = args.cohort.absolute()
    if args.action == "prepare":
        value = prepare(cohort)
    elif args.action == "run":
        return run(cohort)
    elif args.action == "pending":
        value = pending_request(cohort)
    else:
        if args.response_file is None or args.response_file.stat().st_size > MAX_ENVELOPE_BYTES:
            raise ValueError("Submit requires a bounded captured-agent final envelope")
        value = submit_response(cohort, canonical.load_file(args.response_file))
    print(canonical.dumps(value).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
