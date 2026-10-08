"""Optional fixed three-task Luna simulation; never a restart of the 100-task benchmark.

prepare preregisters a new supplemental cohort. run waits without model deadlines.
pending exposes one exact controller message; submit accepts an exact fresh-agent final.
No command here spawns agents. Identity, tools, sampling and token usage are unattested.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import os
import json
from pathlib import Path
import signal
import subprocess
import sys
from typing import Any

from verislop import canonical
from verislop.errors import VeriSlopError
from verislop.package import Package
from synthetic_dataset.tools import check_data_pipeline_poc as checker
from synthetic_dataset.tools import run_data_pipeline_poc as native
from synthetic_dataset.tools.data_pipeline_oracle import TASKS
from synthetic_dataset.tools.luna_benchmark import agent_message, stop_worker
from synthetic_dataset.tools.luna_worker import MODEL, MAX_RESPONSE_BYTES, MAX_ENVELOPE_BYTES, atomic_json, configuration as base_configuration, endpoint_profiles, validate_response
from synthetic_dataset.tools.luna_data_pipeline_worker import MAX_CALLS, cli_argv

FORMAT = "verislop.luna-data-pipeline-supplement/0.1"
ERRORS = (VeriSlopError, OSError, ValueError, KeyError, TypeError, AttributeError)
WITHHELD_MARKERS = ("expected_wire", "data-pipeline-request-oracle", "withheld/", "PREREGISTRATION.json")
RELAY_MODES = ("inline", "file")
CARRIER_FORMAT = "verislop.collaboration-carrier/0.1"
FILE_TOOL_POLICY = ("A fresh agent may read only its exact current SYSTEM/USER carrier file; no other files, "
                    "workspace, hidden material, history, delegation or other agents. Read access and tool-policy "
                    "enforcement are instruction-based and unattested.")


def configuration() -> dict[str, Any]:
    cfg = copy.deepcopy(base_configuration())
    cfg["review"]["budgets"].update(max_calls_per_instance=24, max_total_tokens=524288)
    return cfg


def source_inputs() -> dict[str, str]:
    sources = native.source_inputs()
    # Freeze transitive simulation helpers, not only the module containing the patched call.
    paths = [*native.REPO.joinpath("synthetic_dataset").glob("*.py"),
             *native.REPO.joinpath("synthetic_dataset/tools").glob("*.py")]
    sources.update({p.relative_to(native.REPO).as_posix(): canonical.digest_file(p) for p in paths if p.is_file()})
    return dict(sorted(sources.items()))


def prepare(cohort: Path, *, relay_mode: str = "inline") -> dict[str, Any]:
    if relay_mode not in RELAY_MODES:
        raise ValueError("Unsupported supplemental relay mode")
    if cohort.exists() or cohort.is_symlink():
        raise ValueError("Supplemental cohort is write-once; use a fresh identifier")
    prereg = checker.check_preregistration()
    frozen = source_inputs()
    cfg, profiles = configuration(), endpoint_profiles()
    cohort.mkdir(parents=True)
    native.write_once(cohort / "config.json", cfg)
    native.write_once(cohort / "provider-home/endpoint-profiles.json", profiles)
    protocol = {"format": FORMAT, "tasks": list(TASKS), "generation_started": False,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(), "base_preregistration_root": prereg["root"],
        "source_hashes": frozen, "source_root": canonical.digest_json(frozen),
        "config_sha256": canonical.digest_file(cohort / "config.json"),
        "endpoint_profiles_sha256": canonical.digest_file(cohort / "provider-home/endpoint-profiles.json"),
        "transport": "collaboration-agent-simulation", "requested_model": MODEL, "model_override": MODEL,
        "fork_turns": "none", "fresh_agent_per_call": True, "returned_model": None,
        "model_digest_sha256": None, "model_identity_attested": False, "token_usage_available": False,
        "input_tokens": None, "output_tokens": None, "sampling_controls_available": False,
        "output_token_limit_enforced": False, "schema_output_tokens_hint": 8192,
        "tool_policy": "No tools, files or delegation requested in exact controller message; instruction-based and unattested",
        "relay_mode": relay_mode,
        "carrier_format": CARRIER_FORMAT if relay_mode == "file" else None,
        "carrier_policy": FILE_TOOL_POLICY if relay_mode == "file" else None,
        "max_calls_per_task": MAX_CALLS, "max_calls_per_instance": 24, "max_response_bytes": MAX_RESPONSE_BYTES,
        "model_generation_deadline": None, "proof_search_deadline": None, "review_tier_deadline": None,
        "attempts_per_task": 1, "contract_repair_rounds": 2, "tier": 0, "target": "python", "required_state": "TESTED",
        "task_seed": 20261008, "generated_cases": 32, "independent_cases_per_task": 160, "independent_repeats": 2,
        "scope": "Only the same three natural-language tasks; 480 unchanged withheld cases; no raw arm or 100-task denominator",
        "hidden_test_policy": "No oracle/cases/expected values in outgoing messages; evaluate only after generation ends for a task",
        "proof_origin_policy": "Fresh-agent proposals plus unchanged deterministic supervisor registry assembly and tactic portfolio; no manual code or proofs",
        "policy_departure": "Require fixed model snapshot is false because collaboration cannot attest a provider snapshot. Mechanical and review/quorum gates are unchanged.",
        "pass_predicate": "Native CLI PASS and exit0, current audited repair lineage, Tier0 TESTED closure VERIFIED and all independent observations exact",
        "limitations": ["Actual model identity, sampling, tokens and tool-policy enforcement are not independently attested",
                        "Different transport/identity policy/call limits prevent equal-compute or causal comparison with native Qwen",
                        "Finite Tier0 observations do not establish END_TO_END_VERIFIED; privileged host and captured finals are trusted"]}
    if relay_mode == "file":
        protocol["tool_policy"] = FILE_TOOL_POLICY
        protocol["policy_departure"] += (" File relay permits reading the sole hash-bound current carrier; "
                                         "the inline no-files tool policy does not apply to that read.")
    native.write_once(cohort / "protocol.json", protocol)
    for rel in frozen:
        destination = cohort / "execution-source" / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((native.REPO / rel).read_bytes())
    native.write_once(cohort / "preregistration.json", {"format": FORMAT, "generation_started": False,
        "protocol_sha256": canonical.digest_file(cohort / "protocol.json"), "source_root": protocol["source_root"],
        "base_preregistration_root": prereg["root"], "tasks": list(TASKS)})
    verify_inputs(cohort)
    return protocol


def verify_inputs(cohort: Path) -> dict[str, Any]:
    record = canonical.load_file(cohort / "preregistration.json")
    protocol = canonical.load_file(cohort / "protocol.json")
    relay_mode = protocol.get("relay_mode")
    if (relay_mode not in RELAY_MODES
            or protocol.get("carrier_format") != (CARRIER_FORMAT if relay_mode == "file" else None)
            or protocol.get("carrier_policy") != (FILE_TOOL_POLICY if relay_mode == "file" else None)
            or protocol.get("tool_policy") != (FILE_TOOL_POLICY if relay_mode == "file" else
                "No tools, files or delegation requested in exact controller message; instruction-based and unattested")):
        raise ValueError("INPUT_MUTATION: supplemental relay mode or tool policy changed")
    if (record.get("format") != FORMAT or protocol.get("format") != FORMAT
            or record.get("protocol_sha256") != canonical.digest_file(cohort / "protocol.json")
            or record.get("tasks") != list(TASKS) or protocol.get("tasks") != list(TASKS)
            or record.get("base_preregistration_root") != checker.check_preregistration()["root"]
            or protocol.get("base_preregistration_root") != record["base_preregistration_root"]
            or protocol.get("source_hashes") != source_inputs()
            or protocol.get("source_root") != canonical.digest_json(protocol["source_hashes"])
            or record.get("source_root") != protocol["source_root"]
            or protocol.get("config_sha256") != canonical.digest_file(cohort / "config.json")
            or protocol.get("endpoint_profiles_sha256") != canonical.digest_file(cohort / "provider-home/endpoint-profiles.json")
            or canonical.load_file(cohort / "config.json") != configuration()
            or canonical.load_file(cohort / "provider-home/endpoint-profiles.json") != endpoint_profiles()):
        raise ValueError("INPUT_MUTATION: supplemental protocol, source, configuration or base preregistration changed")
    for rel, digest in protocol["source_hashes"].items():
        if canonical.digest_file(cohort / "execution-source" / rel) != digest:
            raise ValueError("INPUT_MUTATION: retained execution-source bytes changed")
    return protocol


def _relay_binding(cohort: Path, task: str, request_path: Path, request: dict[str, Any],
                   protocol: dict[str, Any], *, create_carrier: bool) -> dict[str, Any]:
    """Build exact transport instructions, never an answer or a task-specific hint."""
    mode = protocol["relay_mode"]
    if mode == "inline":
        message = agent_message(request)
        return {"relay_mode": mode, "agent_message": message,
                "spawn_message_sha256": canonical.digest(message.encode())}
    path = request_path.with_name(f"carrier-{request['request_id']}.json").absolute()
    carrier = {"format": CARRIER_FORMAT, "request_id": request["request_id"],
        "request_sha256": canonical.digest_file(request_path),
        "system": request["system"], "user": request["user"]}
    encoded = canonical.dumps(carrier)
    digest = canonical.digest(encoded)
    reference = {"path": str(path), "sha256": digest, "request_sha256": carrier["request_sha256"]}
    message = ("Handle exactly one model request. Use a read-only tool to read ONLY the absolute carrier file below. "
        "It is a JSON object: follow its exact system field as SYSTEM instructions and its exact user field as USER data. "
        "Do not read other files, inspect the workspace or history, delegate, or access other agents. "
        "Return ONLY the requested response text, without commentary. Reading this sole current carrier is explicitly "
        "allowed; no other tools or files are allowed. Verify the listed SHA-256 using a read-only tool. Read the ENTIRE "
        "carrier: if tool output is truncated, read exact successive chunks until complete before responding. "
        "The carrier must match the listed SHA-256 and native request digest.\n\n"
        "CARRIER:\n" + json.dumps(reference, sort_keys=True, ensure_ascii=True))
    binding = {"relay_mode": mode, "carrier_path": str(path), "carrier_sha256": digest,
               "agent_message": message, "spawn_message_sha256": canonical.digest(message.encode())}
    receipt_path = path.with_name(f"carrier-binding-{request['request_id']}.json")
    receipt = {"format": "verislop.collaboration-carrier-binding/0.1", "task": task,
               "request_id": request["request_id"], "request_sha256": carrier["request_sha256"],
               **{key: value for key, value in binding.items() if key != "agent_message"}}
    if path.is_symlink() or receipt_path.is_symlink():
        raise ValueError("INPUT_MUTATION: carrier and binding must not be symlinks")
    if receipt_path.exists():
        if not receipt_path.is_file() or receipt_path.read_bytes() != canonical.dumps(receipt):
            raise ValueError("INPUT_MUTATION: current carrier binding differs from its exact native request")
        if not path.is_file():
            raise ValueError("INPUT_MUTATION: recorded carrier is missing")
    else:
        if not create_carrier or path.exists():
            raise ValueError("INPUT_MUTATION: recorded carrier binding is missing")
        native.write_once(path, carrier)
        path.chmod(0o444)
        native.write_once(receipt_path, receipt)
    if not path.is_file() or path.read_bytes() != encoded:
        raise ValueError("INPUT_MUTATION: current carrier differs from its exact native request")
    return binding


def pending_request(cohort: Path) -> dict[str, Any] | None:
    protocol = verify_inputs(cohort)
    state_path = cohort / "active-task.json"
    state = canonical.load_file(state_path) if state_path.is_file() else {}
    if state.get("phase") != "generation":
        return None
    task = state.get("task")
    if task not in TASKS:
        raise ValueError("Active mailbox is outside the fixed task list")
    directory = cohort / task / "mailbox"
    paths = sorted(directory.glob("request-*.json"))
    if len(paths) > MAX_CALLS:
        raise ValueError("Supplemental logical-call budget exceeded before agent delivery")
    for index, path in enumerate(paths, 1):
        request = canonical.load_file(path)
        rid = request.get("request_id")
        if (rid != f"{index:04d}" or path.name != f"request-{rid}.json"
                or request.get("transport") != "collaboration" or request.get("requested_model") != MODEL
                or not isinstance(request.get("system"), str) or not isinstance(request.get("user"), str)):
            raise ValueError("Malformed current simulation request")
        if any(marker in request["system"] or marker in request["user"] for marker in WITHHELD_MARKERS):
            raise ValueError("Withheld evaluation material in an outgoing model request")
        if not (directory / f"response-{rid}.json").exists():
            relay = _relay_binding(cohort, task, path, request, protocol, create_carrier=True)
            return {"task": task, "request_path": str(path), "request_sha256": canonical.digest_file(path),
                "supplemental_protocol_root": canonical.digest_file(cohort / "protocol.json"),
                "request": request, **relay,
                "model_override": MODEL, "fork_turns": "none", "model_identity_attested": False}
    return None


def _check_envelope(envelope: dict[str, Any], pending: dict[str, Any]) -> tuple[str, str]:
    request = pending["request"]
    text, agent = validate_response(envelope, request["request_id"], pending["request_sha256"])
    mode = pending["relay_mode"]
    if envelope.get("relay_mode", "inline") != mode:
        raise ValueError("Response has the wrong preregistered relay mode")
    if mode == "file":
        if (envelope.get("carrier_path") != pending["carrier_path"]
                or envelope.get("carrier_sha256") != pending["carrier_sha256"]):
            raise ValueError("Response lacks the exact current carrier path and digest binding")
    elif "carrier_path" in envelope or "carrier_sha256" in envelope:
        raise ValueError("Inline response cannot claim a file carrier")
    if (envelope.get("model_override") != MODEL or envelope.get("fork_turns") != "none"
            or envelope.get("spawn_message_sha256") != pending["spawn_message_sha256"]
            or envelope.get("task") != pending["task"]
            or envelope.get("supplemental_protocol_root") != pending["supplemental_protocol_root"]
            or envelope.get("model_identity_attested") is not False):
        raise ValueError("Response lacks the exact fresh-agent/context/message/task/protocol binding")
    return text, agent


def submit_response(cohort: Path, envelope: dict[str, Any]) -> dict[str, Any]:
    pending = pending_request(cohort)
    if pending is None:
        raise ValueError("No pending request; unsolicited or repeated response rejected")
    text, agent = _check_envelope(envelope, pending)
    for task in TASKS:
        for path in (cohort / task / "mailbox").glob("response-*.json"):
            if path.name.startswith("response-receipt-"):
                continue
            if canonical.load_file(path).get("agent_task_id") == agent:
                raise ValueError("Agent task already used; every logical call requires a fresh agent")
    destination = Path(pending["request_path"]).with_name(f"response-{pending['request']['request_id']}.json")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Response path already exists; prior finals cannot be replaced")
    atomic_json(destination, envelope)
    return {"published": str(destination), "task": pending["task"], "agent_task_id": agent,
            "output_bytes": len(text.encode()), "model_identity_attested": False}


def simulation_audit(cohort: Path, task: str, packages: list[Package]) -> list[dict[str, Any]]:
    protocol = verify_inputs(cohort)
    directory = cohort / task / "mailbox"
    all_requests = sorted(directory.glob("request-*.json"))
    receipts = sorted(directory.glob("response-receipt-*.json"))
    errors, response_map, agents, instances = [], {}, set(), Counter()
    for path in all_requests:
        request = canonical.load_file(path)
        instances[request["instance"]] += 1
        if any(marker in request.get("system", "") or marker in request.get("user", "") for marker in WITHHELD_MARKERS):
            errors.append("Withheld evaluation material in an outgoing model request")
    for other_task in TASKS:
        for path in (cohort / other_task / "mailbox").glob("response-*.json"):
            if not path.name.startswith("response-receipt-"):
                agent = canonical.load_file(path).get("agent_task_id")
                if agent in agents:
                    errors.append("Agent reused across supplemental requests")
                agents.add(agent)
    for path in receipts:
        receipt = canonical.load_file(path)
        rid = receipt["request_id"]
        request_path, response_path = directory / f"request-{rid}.json", directory / f"response-{rid}.json"
        request, envelope = canonical.load_file(request_path), canonical.load_file(response_path)
        relay = _relay_binding(cohort, task, request_path, request, protocol, create_carrier=False)
        binding = {"request": request, "request_sha256": canonical.digest_file(request_path), "task": task,
            "supplemental_protocol_root": canonical.digest_file(cohort / "protocol.json"),
            **relay}
        text, agent = _check_envelope(envelope, binding)
        expected = {"request_sha256": binding["request_sha256"], "response_sha256": canonical.digest_file(response_path),
            "text_sha256": canonical.digest(text.encode()), "output_bytes": len(text.encode()), "agent_task_id": agent,
            "requested_model": MODEL, "returned_model": None, "input_tokens": None, "output_tokens": None,
            "transport": "collaboration", "model_identity_attested": False}
        if any(receipt.get(key) != value for key, value in expected.items()):
            errors.append("Mailbox receipt differs from exact request/response/final bytes")
        response_map[agent] = (request, text)
    usage = canonical.load_file(directory / "usage.json") if (directory / "usage.json").is_file() else {}
    if (usage.get("calls") != len(all_requests) or usage.get("responses") != len(receipts)
            or len(all_requests) > MAX_CALLS or any(n > 24 for n in instances.values())
            or usage.get("input_tokens") is not None or usage.get("output_tokens") is not None
            or usage.get("token_usage_available") is not False
            or usage.get("output_bytes") != sum(canonical.load_file(p)["output_bytes"] for p in receipts)):
        errors.append("Simulation usage differs from exact finite-call/byte evidence or invents token counts")
    audits, seen_responses = [], set()
    for pkg in packages:
        calls, rows, issues = [], [], list(errors)
        for path in sorted(pkg.root.rglob("transcripts/*.json")):
            entry = canonical.load_file(path)
            calls.append(entry)
            rows.append({"path": path.relative_to(pkg.root).as_posix(), "sha256": canonical.digest_file(path), "purpose": entry.get("purpose")})
            if (entry.get("system_sha256") != canonical.digest(entry.get("system", "").encode())
                    or entry.get("user_sha256") != canonical.digest(entry.get("user", "").encode())
                    or entry.get("requested_model") != MODEL or entry.get("returned_model") is not None
                    or entry.get("model_digest_sha256") is not None):
                issues.append("Native transcript prompt hashes or honest simulation identity differ")
            if entry.get("response") is not None:
                match = response_map.get(entry.get("request_id"))
                if (match is None or match[1] != entry["response"] or match[0]["system"] != entry["system"]
                        or match[0]["user"] != entry["user"] or match[0]["purpose"] != entry["purpose"]
                        or match[0]["instance"] != entry["instance"] or match[0]["agent"] != entry["agent"]):
                    issues.append("Delivered native response has no exact mailbox/fresh-agent origin")
                elif entry["request_id"] in seen_responses:
                    issues.append("One simulation final was delivered more than once")
                seen_responses.add(entry.get("request_id"))
        # Same raw/typed deterministic artifact reconstruction as the native Qwen audit.
        artifact = native.artifact_origin_audit(pkg, calls)
        issues.extend(artifact["issues"])
        audits.append({"package": str(pkg.root), "status": "PASS" if not issues else "BLOCK", "issues": sorted(set(issues)),
            "provider_calls": len(calls), "transcripts": rows, "artifact_origin": artifact,
            "identity_scope": "Recorded fresh-agent simulation only; actual model snapshot and tools are unattested"})
    if seen_responses != set(response_map):
        for audit in audits:
            audit["status"] = "BLOCK"
            audit["issues"].append("Mailbox final inventory differs from actually delivered native transcripts")
    return audits


def seal(cohort: Path, records: list[dict[str, Any]], protocol: dict[str, Any] | None, *, reason: str | None = None) -> int:
    """Seal all fixed tasks without losing a durable row at an interruption boundary."""
    by_task = {row["task"]: row for row in records}
    rows = []
    for task in TASKS:
        path = cohort / task / "result.json"
        if path.is_file():
            durable = canonical.load_file(path)
            if durable.get("task") != task or (task in by_task and durable != by_task[task]):
                raise ValueError("Stored supplemental task result does not bind its exact task")
            row = dict(durable)
        elif task in by_task:
            row = dict(by_task[task])
            native.write_once(path, row)
        else:
            usage_path = cohort / task / "mailbox/usage.json"
            usage = canonical.load_file(usage_path) if usage_path.is_file() else {}
            row = {"task": task, "status": "BLOCKED", "reason": reason or "No completed native task result",
                "cli_exit": None, "native_status": None, "package": None, "independent_cases": 160,
                "independent_cases_loaded": 0, "independent_cases_passed": 0, "observations": 0,
                "provider_calls": usage.get("calls", 0), "responses": usage.get("responses", 0),
                "origin_audit_passed": False, "model_identity_attested": False,
                "input_tokens": None, "output_tokens": None}
            native.write_once(path, row)
        if reason:
            row.update(retained_result_status=row["status"], status="BLOCKED", cohort_blocking_reason=reason)
        rows.append(row)
    verified = sum(row["status"] == "VERIFIED" for row in rows)
    status = ("BLOCKED" if reason else "VERIFIED" if verified == len(TASKS) else
              "INFRASTRUCTURE_FAILURE" if any(row["status"] == "INFRASTRUCTURE_FAILURE" for row in rows) else "BLOCKED")
    native.write_once(cohort / "SUMMARY.json", {"format": FORMAT, "status": status, "tasks": rows,
        "total_tasks": len(TASKS), "verified_tasks": verified, "sealed_tasks": len(rows), "blocking_reason": reason,
        "runtime_root": protocol.get("source_root") if protocol else None,
        "base_preregistration_root": protocol.get("base_preregistration_root") if protocol else None,
        "supplemental_protocol_root": canonical.digest_file(cohort / "protocol.json") if (cohort / "protocol.json").is_file() else None,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(), "transport": "collaboration-agent-simulation",
        "relay_mode": protocol.get("relay_mode") if protocol else None,
        "requested_model": MODEL, "returned_model": None, "model_digest_sha256": None,
        "model_identity_attested": False, "input_tokens": None, "output_tokens": None, "token_usage_available": False,
        "assurance": "Tier0 strict CLI and finite independent observations; simulation identity/tools are unattested; END_TO_END_VERIFIED excluded"})
    return 0 if verified == len(TASKS) else 2


def run(cohort: Path) -> int:
    if (cohort / "SUMMARY.json").exists() or any((cohort / task).exists() for task in TASKS):
        raise ValueError("Supplemental run cannot resume or select retries; use a new preregistered cohort")
    try:
        protocol = verify_inputs(cohort)
    except ERRORS as exc:
        return seal(cohort, [], None, reason=f"Pre-generation input failure: {exc}")
    records = []
    env = dict(os.environ, VERISLOP_CONFIG_HOME=str(cohort / "provider-home"))
    previous_handler = signal.getsignal(signal.SIGTERM)
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("Explicit controller interruption")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        for task in TASKS:
            verify_inputs(cohort)
            directory = cohort / task
            directory.mkdir()
            command = [sys.executable, "-m", "synthetic_dataset.tools.luna_data_pipeline_worker", "--cohort", str(cohort), "--task", task]
            native.write_once(directory / "invocation.json", {"argv": command, "cwd": str(native.REPO),
                "cli_argv": cli_argv(cohort, task), "transport": "collaboration-agent-simulation", "candidate_inputs": []})
            atomic_json(cohort / "active-task.json", {"task": task, "phase": "generation"})
            process, cli_exit, stdout, stderr = None, None, b"", b""
            result, package, audits, oracle = {"status": "INFRASTRUCTURE_FAILURE"}, None, [], {"status": "BLOCKED"}
            diagnostics, bound, unchanged = [], False, True
            try:
                process = subprocess.Popen(command, cwd=native.REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                # Deliberately no model-generation timeout, including waiting for controller finals.
                stdout, stderr = process.communicate()
                cli_exit = process.returncode
                result = canonical.loads(stdout)
                if (not isinstance(result, dict) or result.get("status") not in ("PASS", "BLOCKED", "INFRASTRUCTURE_FAILURE")
                        or not isinstance(result.get("summary", {}), dict) or not isinstance(result.get("artifacts", {}), dict)):
                    raise ValueError("Worker produced no valid native CLI result")
            except KeyboardInterrupt:
                if process:
                    stdout, stderr = stop_worker(process)
                (directory / "stdout.json").write_bytes(stdout)
                (directory / "stderr.log").write_bytes(stderr)
                raise
            except ERRORS as exc:
                diagnostics.append(f"Worker launch/result failure: {exc}")
                result = {"status": "INFRASTRUCTURE_FAILURE"}
            (directory / "stdout.json").write_bytes(stdout)
            (directory / "stderr.log").write_bytes(stderr)
            atomic_json(cohort / "active-task.json", {"task": task, "phase": "observation"})
            try:
                packages = [Package(path, resolve_root=False) for path in sorted((directory / "runs").glob("*")) if (path / "package.json").is_file()]
                package = native.active_package(directory, task, result, packages)
                bound = True
                audits = simulation_audit(cohort, task, packages)
                oracle = checker.run_check(package, task)
            except ERRORS as exc:
                diagnostics.append(f"Simulation provenance/package/oracle failure: {exc}")
            try:
                verify_inputs(cohort)
            except ERRORS as exc:
                unchanged = False
                diagnostics.append(str(exc))
            native.write_once(directory / "origin-audit.json", audits)
            native.write_once(directory / "independent-oracle.json", oracle)
            row = {"task": task, "status": native.task_status(result, cli_exit, oracle, audits, bound=bound, unchanged=unchanged),
                "cli_exit": cli_exit, "native_status": result.get("status"), "package": str(package) if package else None,
                "active_package_bound": bound, "provider_calls": sum(a["provider_calls"] for a in audits),
                "origin_audit_passed": bool(audits) and all(a["status"] == "PASS" for a in audits),
                "independent_cases": 160, "independent_cases_loaded": oracle.get("distinct_cases", 0),
                "independent_cases_passed": oracle.get("passed_cases", 0), "observations": oracle.get("observations", 0),
                "input_tokens": None, "output_tokens": None, "model_identity_attested": False, "diagnostics": diagnostics}
            native.write_once(directory / "result.json", row)
            records.append(row)
            if not unchanged:
                return seal(cohort, records, protocol, reason="INPUT_MUTATION: supplemental cohort invalidated")
        atomic_json(cohort / "active-task.json", {"phase": "complete"})
        return seal(cohort, records, protocol)
    except KeyboardInterrupt:
        atomic_json(cohort / "active-task.json", {"phase": "stopped"})
        return seal(cohort, records, protocol, reason="Explicitly interrupted; unfinished fixed tasks are retained unsuccessful")
    except ERRORS as exc:
        return seal(cohort, records, protocol, reason=str(exc))
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "pending", "submit"))
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--response-file", type=Path)
    parser.add_argument("--relay-mode", choices=RELAY_MODES, default="inline",
                        help="Preregister inline relay or one exact read-only current carrier file")
    args = parser.parse_args(argv)
    cohort = args.cohort.absolute()
    if args.action == "prepare":
        value = prepare(cohort, relay_mode=args.relay_mode)
    elif args.action == "run":
        return run(cohort)
    elif args.action == "pending":
        value = pending_request(cohort)
    else:
        if args.response_file is None or args.response_file.stat().st_size > MAX_ENVELOPE_BYTES:
            raise ValueError("submit requires a bounded exact captured-agent response file")
        value = submit_response(cohort, canonical.load_file(args.response_file))
    print(canonical.dumps(value).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
