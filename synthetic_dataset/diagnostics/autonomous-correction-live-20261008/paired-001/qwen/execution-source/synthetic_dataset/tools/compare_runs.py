"""Independently audit and compare recorded native and simulated benchmark runs.

No model calls or candidate execution. Writes only new comparison artifacts outside
the authoritative run directories. --partial labels unfinished observations explicitly.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[2]
ARMS = ("raw", "verislop")
GATES = {"formalize", "prove", "accept", "export", "review:formal_contract",
         "generate", "link", "test", "review:release"}
STATES = ("INTERPRETED", "FORMALIZED", "TYPECHECKED", "PROVED", "IMPLEMENTED",
          "LINKED", "TESTED", "END_TO_END_VERIFIED")


class AuditFailure(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditFailure(message)


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def exact(left, right):
    return encode(left) == encode(right)


def load(path, optional=False):
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        if optional:
            return {}
        raise AuditFailure("Missing or invalid JSON: " + str(path)) from None


def inside(root, relative):
    require(isinstance(relative, str) and relative and not Path(relative).is_absolute(),
            "Invalid relative evidence path: " + repr(relative))
    root = root.resolve()
    lexical = root / relative
    path = lexical.resolve()
    require(path.is_relative_to(root), "Evidence path escapes root: " + relative)
    require(all(not p.is_symlink() for p in (lexical, *lexical.parents) if p != root.parent),
            "Evidence path has a symlink: " + relative)
    return path


def inventory(root, hashes, label):
    require(isinstance(hashes, dict), label + " is not a hash inventory")
    for relative, expected in hashes.items():
        path = inside(root, relative)
        require(path.is_file() and digest(path.read_bytes()) == expected,
                label + " hash mismatch or missing file: " + relative)
    return len(hashes)


def active_package(directory, pipeline):
    summary = pipeline.get("summary", {})
    require(isinstance(summary, dict), "CLI summary must be an object")
    selected = summary.get("active_package")
    if selected is None:
        selected = directory / "package"
    else:
        require(isinstance(selected, str) and selected, "Invalid active package path")
        selected = Path(selected)
        if not selected.is_absolute():
            selected = directory / selected
    require(not selected.is_symlink(), "Active package is a symlink")
    selected = selected.resolve()
    require(selected.parent == directory.resolve() and
            re.fullmatch(r"package(?:-repair-(?:0[1-9]|[1-9][0-9]))?", selected.name),
            "Active package escapes the recorded arm lineage")
    return selected


def inspect_artifact(root):
    hashes, entries = {}, []
    require(not root.is_symlink(), "artifact root is a symlink")
    if not root.is_dir():
        return hashes, None
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "artifact contains a symlink")
        if path.is_file() and path.suffix == ".py":
            source = path.read_bytes()
            require(len(source) <= 1 << 20, "artifact source exceeds 1 MiB")
            relative = path.relative_to(root).as_posix()
            hashes[relative] = digest(source)
            try:
                tree = ast.parse(source)
                entries.extend(relative for node in tree.body
                               if isinstance(node, ast.FunctionDef) and node.name == "solve")
            except (SyntaxError, UnicodeError):
                pass
    return hashes, entries[0] if len(entries) == 1 else None


def strict_success(pipeline, report, exit_code, stages, timed_out=False):
    if timed_out or exit_code != 0 or pipeline.get("status") != "PASS":
        return False
    if report.get("terminal_status") != "VERIFIED" or report.get("blocking_reasons") or report.get("infrastructure_errors"):
        return False
    tier = report.get("tier", {})
    if not isinstance(tier, dict) or any(tier.get(k) != v for k, v in
            {"requested": 0, "target": "python", "endpoint": "test_campaign", "require_state": "TESTED"}.items()):
        return False
    if not isinstance(stages, list):
        return False
    gates = {s.get("stage"): s.get("status") for s in stages if isinstance(s, dict)}
    if any(gates.get(g) != "PASS" for g in GATES):
        return False
    obligations = report.get("obligations", {})
    if not isinstance(obligations, dict) or not obligations:
        return False
    tested = False
    for obligation in obligations.values():
        if not isinstance(obligation, dict):
            return False
        if obligation.get("required"):
            milestones, outcomes = obligation.get("required_milestones"), obligation.get("outcomes")
            if not isinstance(milestones, list) or not milestones or not isinstance(outcomes, dict):
                return False
            if any(outcomes.get(m) != "PASS" for m in milestones):
                return False
            tested |= "TESTED" in milestones
    return tested


def audit_cases(record, cases):
    all_pass = True
    for visibility, field, prefix in (("hidden", "held_out_results", "hidden"), ("public", "public_results", "public")):
        expected = [c for c in cases if c["visibility"] == visibility]
        observed = record.get(field)
        require(isinstance(observed, list) and [c.get("id") for c in observed] == [c["id"] for c in expected],
                "Case identity/order differs: " + record["task_id"] + "/" + visibility)
        passed = 0
        for case, result in zip(expected, observed):
            ok = "observed" in result and "error" not in result and exact(result["observed"], case["expected"])
            require(result.get("status") == ("PASS" if ok else "FAIL"), "Incorrect case grade: " + case["id"])
            require("expected" not in result or exact(result["expected"], case["expected"]), "Expected output altered: " + case["id"])
            passed += ok
        require(type(record.get(prefix + "_passed")) is int and type(record.get(prefix + "_total")) is int and
                (record[prefix + "_passed"], record[prefix + "_total"]) == (passed, len(expected)),
                "Case counters differ: " + record["task_id"] + "/" + visibility)
        all_pass &= bool(expected) and passed == len(expected)
    return all_pass


def agent_message(request):
    return ("Handle exactly one model request. Return only the response text required by the "
            "SYSTEM and USER below. Do not use tools, read files, inspect the workspace, "
            "delegate, or access other agents. Do not include commentary.\n\n"
            "SYSTEM:\n" + request["system"] + "\n\nUSER:\n" + request["user"])


def audit_usage(directory, record, protocol, simulation, agents):
    usage = record["usage"]
    actual = load(directory / "usage.json", optional=True)
    if not simulation:
        actual["unknown_usage_calls"] = max(actual.get("unknown_usage_calls", 0), actual.get("calls", 0) - actual.get("responses", 0))
    require(exact(usage, actual), "Usage differs from worker: " + str(directory))
    requests = sorted(directory.glob("request-*.json"))
    calls, responses = usage.get("calls", 0), usage.get("responses", 0)
    require(type(calls) is int and type(responses) is int and
            0 <= responses <= calls <= (1 if record["arm"] == "raw" else protocol["harness_calls"]), "Invalid call accounting")
    require(len(requests) == calls, "Request count differs from call accounting")
    bodies = [load(p) for p in requests]
    require(record.get("last_model_purpose") == (bodies[-1].get("purpose") if bodies else None), "Last model purpose differs")
    if simulation:
        receipts = sorted(directory.glob("response-receipt-*.json"))
        require(len(receipts) == responses, "Simulation response count differs")
        output_bytes = 0
        for path in receipts:
            receipt = load(path)
            rid = receipt["request_id"]
            require(isinstance(rid, str) and re.fullmatch(r"[0-9]{4}", rid), "Invalid simulation request ID")
            request_path, response_path = directory / f"request-{rid}.json", directory / f"response-{rid}.json"
            request_bytes, response_bytes = request_path.read_bytes(), response_path.read_bytes()
            request, response = json.loads(request_bytes), json.loads(response_bytes)
            require(response.get("transport") == "collaboration" and response.get("requested_model") == "gpt-6-luna" and
                    response.get("model_override") == "gpt-6-luna" and response.get("fork_turns") == "none" and
                    response.get("request_id") == rid and response.get("request_sha256") == digest(request_bytes) and
                    response.get("spawn_message_sha256") == digest(agent_message(request).encode()), "Unbound simulation response")
            text, agent = response.get("text"), response.get("agent_task_id")
            require(isinstance(text, str) and text and isinstance(agent, str) and
                    re.fullmatch(r"/root(?:/[a-z0-9_]+)+", agent) and agent not in agents, "Missing or reused fresh agent")
            agents.add(agent)
            count = len(text.encode("utf-8"))
            require(count <= protocol["max_response_bytes"], "Simulation response exceeds byte cap")
            bound = {"request_sha256": digest(request_bytes), "response_sha256": digest(response_bytes),
                     "text_sha256": digest(text.encode()), "output_bytes": count, "agent_task_id": agent,
                     "requested_model": "gpt-6-luna", "returned_model": None, "input_tokens": None,
                     "output_tokens": None, "model_identity_attested": False}
            require(all(exact(receipt.get(k), v) for k, v in bound.items()), "Simulation receipt differs from exact bytes")
            output_bytes += count
        require(usage.get("input_tokens") is None and usage.get("output_tokens") is None and
                usage.get("unknown_usage_calls") == calls and usage.get("output_bytes", 0) == output_bytes,
                "Simulation invented tokens or inconsistent output bytes")
    else:
        native = [load(p) for p in sorted(directory.glob("native-response-*.json"))]
        require(len(native) == responses, "Native response count differs")
        unknown = usage.get("unknown_usage_calls", 0)
        require(type(unknown) is int and calls - responses <= unknown <= calls, "Native unknown-usage accounting differs")
        for token, field in (("input_tokens", "prompt_eval_count"), ("output_tokens", "eval_count")):
            require(type(usage.get(token, 0)) is int and usage.get(token, 0) >= 0 and
                    sum(body.get(field, 0) or 0 for body in native) == usage.get(token, 0), "Native token sum differs")
        require(usage.get("output_tokens", 0) <= usage.get("reserved_output_tokens", 0) <= protocol["output_token_budget"], "Native token budget exceeded")
        for body in native:
            count = body.get("eval_count")
            require(body.get("model") == protocol["model"] and
                    (count is None or type(count) is int and 0 <= count <= protocol["per_call_output_tokens"]), "Native model or token cap differs")
        for path in directory.rglob("transcripts/*.json"):
            log = load(path)
            if log.get("error") is None:
                require(log.get("requested_model") == log.get("returned_model") == protocol["model"] and
                        log.get("model_digest_sha256") == protocol["model_digest"], "Successful native transcript identity differs")
    return responses


def metrics(records):
    def total(rows):
        tokens_available = all(r["usage"].get("output_tokens") is not None for r in rows)
        return {"attempted_tasks": len(rows), "successful_tasks": sum(r["successful_task"] for r in rows),
                "artifacts": sum(r["artifact_present"] for r in rows),
                "held_out_passed": sum(r["hidden_passed"] for r in rows), "held_out_total": sum(r["hidden_total"] for r in rows),
                "public_passed": sum(r["public_passed"] for r in rows), "public_total": sum(r["public_total"] for r in rows),
                "generation_seconds": round(sum(r["generation_seconds"] for r in rows), 3),
                "model_calls": sum(r["usage"].get("calls", 0) for r in rows),
                "unknown_usage_calls": sum(r["usage"].get("unknown_usage_calls", 0) for r in rows),
                "input_tokens": sum(r["usage"].get("input_tokens", 0) for r in rows) if tokens_available else None,
                "output_tokens": sum(r["usage"].get("output_tokens", 0) for r in rows) if tokens_available else None,
                "statuses": dict(Counter(r["workflow_status"] for r in rows)),
                "last_model_purposes": dict(Counter(r.get("last_model_purpose") or "none" for r in rows))}
    return {arm: total([r for r in records if r["arm"] == arm]) for arm in ARMS}


def paired_ids(records):
    by_id = {}
    for row in records:
        by_id.setdefault(row["task_id"], {})[row["arm"]] = row
    return {task for task, arms in by_id.items() if set(arms) == set(ARMS)}


def paired_outcomes(records):
    by_id = {}
    for row in records:
        by_id.setdefault(row["task_id"], {})[row["arm"]] = row["successful_task"]
    counts = dict.fromkeys(("both_success", "raw_only", "verislop_only", "neither_success"), 0)
    for arms in by_id.values():
        if set(arms) == set(ARMS):
            a, b = arms["raw"], arms["verislop"]
            counts["both_success" if a and b else "raw_only" if a else "verislop_only" if b else "neither_success"] += 1
    return counts


def audit_run(repo, run_name, dataset, tasks, cases_by_task, partial=False):
    require(re.fullmatch(r"[a-zA-Z0-9_-]+", run_name), "Invalid run name")
    run = repo / "synthetic_dataset/runs" / run_name
    protocol, summary = load(run / "protocol.json"), load(run / "summary.json", optional=True)
    simulation = protocol.get("transport") == "collaboration-agent-simulation"
    require(protocol.get("dataset_root") == dataset["dataset_root"], "Run has a different corpus")
    require(protocol.get("arm_seconds") is None and protocol.get("global_seconds") is None, "Generation deadline enabled")
    order = protocol["task_order"]
    require(len(order) == len(tasks) and len(set(order)) == len(order) and set(order) == set(tasks), "Run task inventory differs from fixed corpus")
    source_files = inventory(repo, protocol["source_hashes"], "Current execution source")
    inventory(run / "execution-source", protocol["source_hashes"], "Captured execution source")
    config = load(run / "config.json")
    require(digest(encode(config)) == protocol["config_hash"], "Configuration hash differs")
    require(all(p.get("request_timeout_seconds") is None for p in config["providers"].values()) and
            config["review"]["budgets"]["max_wall_seconds_per_tier"] == 0, "Provider/review deadline enabled")
    if simulation:
        require(protocol.get("model") == "gpt-6-luna" and protocol.get("model_digest") is None and
                protocol.get("output_token_limit_enforced") is False and protocol.get("fork_turns") == "none" and
                protocol.get("fresh_agent_per_call") is True, "Simulation provenance differs")
        require(digest((run / "provider-home/endpoint-profiles.json").read_bytes()) == protocol["endpoint_profiles_hash"], "Simulation endpoint hash differs")
    evidence_path = run / "run-manifest.json"
    evidence_bytes = evidence_path.read_bytes() if evidence_path.is_file() else None
    evidence = json.loads(evidence_bytes) if evidence_bytes else None
    complete = bool(evidence and evidence.get("complete") is True and evidence.get("valid") is True and
                    summary.get("complete") is True and summary.get("valid") is True)
    require(partial or complete, "Run is not complete and valid: " + run_name + "; use --partial for an explicit snapshot")
    evidence_files = None
    if evidence:
        require(evidence["dataset_root"] == dataset["dataset_root"] and evidence["protocol_hash"] == digest(encode(protocol)), "Final manifest binding differs")
        evidence_files = inventory(run, evidence["files"], "Final run evidence")
        actual_files = {p.relative_to(run).as_posix() for p in run.rglob("*") if p.is_file() and p.name != "run-manifest.json"}
        require(actual_files == set(evidence["files"]), "Evidence inventory is incomplete or has extra files")
    result_bytes = (run / "results.jsonl").read_bytes() if (run / "results.jsonl").exists() else b""
    if result_bytes and not result_bytes.endswith(b"\n"):
        require(partial and not evidence, "Final results JSONL has an incomplete record")
        result_bytes = result_bytes.rsplit(b"\n", 1)[0] + b"\n" if b"\n" in result_bytes else b""
    records = [json.loads(line) for line in result_bytes.splitlines() if line]
    seen, agents, response_count = set(), set(), 0
    progress = {"stage_pass_tasks": Counter(), "required_obligation_passes": Counter(),
                "diagnostic_codes": Counter(), "primary_failure_codes": Counter(),
                "terminal_stages": Counter(), "repaired_tasks": 0}
    for position, row in enumerate(records):
        task_id, arm = row["task_id"], row["arm"]
        key = (task_id, arm)
        pair = position // 2
        expected_arm = (ARMS if pair % 2 == 0 else ARMS[::-1])[position % 2]
        require(key not in seen and task_id in tasks and arm in ARMS and pair < len(order) and
                task_id == order[pair] and row["pair_index"] == pair and arm == expected_arm, "Duplicate or out-of-order arm: " + str(key))
        seen.add(key)
        require(row["title"] == tasks[task_id]["title"] and row["category"] == tasks[task_id]["category"], "Task metadata differs")
        require(row.get("timed_out") is False and type(row.get("worker_exit_code")) is int and
                type(row.get("generation_seconds")) in (int, float) and math.isfinite(row["generation_seconds"]) and row["generation_seconds"] >= 0,
                "Invalid worker timing or timeout status")
        directory = inside(run, row["artifact_path"])
        require(directory == run.resolve() / "artifacts" / task_id / arm and exact(row, load(directory / "score.json")), "Per-arm score/evidence location differs")
        all_pass = audit_cases(row, cases_by_task[task_id])
        pipeline = load(directory / "stdout.txt", optional=True) if arm == "verislop" else {}
        if not isinstance(pipeline, dict):
            pipeline = {}
        package, report, meta = None, {}, {}
        artifact_error = None
        try:
            package = active_package(directory, pipeline) if arm == "verislop" else None
            hashes, entry = inspect_artifact(package / "implementation" if package else directory / "artifact")
        except AuditFailure as exc:
            hashes, entry, artifact_error = {}, None, str(exc)
        if package:
            report, meta = load(package / "report.json", optional=True), load(package / "package.json", optional=True)
        report = report if isinstance(report, dict) else {}
        meta = meta if isinstance(meta, dict) else {}
        stages = pipeline.get("summary", {}).get("stages", meta.get("stage_history", []))
        require(exact(hashes, row["source_hashes"]) and entry == row["entry_file"] and type(row["artifact_present"]) is bool and
                row["artifact_present"] == bool(hashes) and row.get("artifact_error") == artifact_error, "Artifact hashes/entry differ: " + str(key))
        require(exact(stages, row["cli_stages"]), "Stage history differs: " + str(key))
        strict = strict_success(pipeline, report, row["worker_exit_code"], stages) if arm == "verislop" else None
        success = all_pass and bool(entry) and row["worker_exit_code"] == 0 and (arm == "raw" or strict)
        require(type(row["successful_task"]) is bool and row["successful_task"] == success and row.get("strict_cli_success") == strict, "Task success or strict gates differ: " + str(key))
        status = pipeline.get("status") or report.get("terminal_status") or "ERROR" if arm == "verislop" else "ARTIFACT" if entry else "ERROR"
        require(row["workflow_status"] == status, "Workflow status differs")
        if arm == "verislop":
            require(row.get("active_package") == (package.relative_to(run).as_posix() if package else None) and
                    row.get("cli_report") == ((package / "report.json").relative_to(run).as_posix() if report else None) and
                    exact(row.get("recovery"), pipeline.get("summary", {}).get("recovery")), "Active package/report/recovery differs")
            invocation = load(directory / "cli-invocation.json", optional=True).get("argv", [])
            required_options = {"--policy": "strict", "--tier": "0", "--target": "python", "--endpoint": "test_campaign",
                                "--require-state": "TESTED", "--budget-seconds": "0", "--repair-rounds": "2",
                                "--run-id": "package", "--runs-dir": str(directory), "--config": str(run / "config.json"),
                                "--prompt-file": str(repo / "synthetic_dataset" / tasks[task_id]["prompt_path"])}
            if invocation:
                require(all(invocation.count(k) == 1 and invocation.index(k) + 1 < len(invocation) and invocation[invocation.index(k) + 1] == v
                            for k, v in required_options.items()) and "--require-tests" in invocation, "Actual CLI invocation differs")
            else:
                require(status == "ERROR" and not hashes and not stages, "Reached CLI has no invocation record")
            for stage in {s.get("stage") for s in stages if isinstance(s, dict) and s.get("status") == "PASS"}:
                progress["stage_pass_tasks"][stage] += 1
            for obligation in report.get("obligations", {}).values():
                if obligation.get("required"):
                    for state in STATES:
                        progress["required_obligation_passes"][state] += obligation.get("outcomes", {}).get(state) == "PASS"
            for diagnostic in row.get("cli_diagnostics", []):
                if isinstance(diagnostic, dict):
                    progress["diagnostic_codes"][diagnostic.get("code", "UNRECORDED")] += 1
            terminal = pipeline.get("summary", {}).get("stopped_at")
            if terminal:
                progress["terminal_stages"][terminal] += 1
            primary = pipeline.get("summary", {}).get("failed_stage_diagnostics", [])
            for code in {d.get("code", "UNRECORDED") for d in primary if isinstance(d, dict)}:
                progress["primary_failure_codes"][code] += 1
            progress["repaired_tasks"] += bool(package and package.name != "package")
        response_count += audit_usage(directory, row, protocol, simulation, agents)
    computed, pairs = metrics(records), paired_outcomes(records)
    if complete:
        require(len(records) == 2 * len(tasks) and len(paired_ids(records)) == len(tasks), "Final run omits arm records")
        require(summary.get("source_mutations") == [] and exact(summary.get("protocol"), protocol), "Final source/protocol check differs")
        if not simulation:
            require(summary.get("model_digest_after") == protocol["model_digest"], "Final native digest differs")
        else:
            require(summary.get("response_integrity_errors") == [], "Final simulation reports integrity errors")
        require(summary.get("complete_pairs") == len(tasks) and exact(summary.get("paired"), pairs), "Final pairing totals differ")
        for arm in ARMS:
            for field, value in computed[arm].items():
                require(exact(summary["arms"][arm].get(field), value), "Final aggregate differs: " + arm + "/" + field)
        categories = {}
        for category in sorted({row["category"] for row in records}):
            categories[category] = {}
            for arm in ARMS:
                selected = [row for row in records if row["category"] == category and row["arm"] == arm]
                categories[category][arm] = {"tasks": len(selected), "successes": sum(row["successful_task"] for row in selected),
                                           "passed": sum(row["hidden_passed"] for row in selected), "total": sum(row["hidden_total"] for row in selected)}
        require(exact(summary.get("categories"), categories), "Final category totals differ")
    require(not evidence_bytes or evidence_path.read_bytes() == evidence_bytes, "Manifest changed during audit")
    return {"run_id": run_name, "complete": complete, "recorded_summary": summary, "protocol": protocol,
            "results": records, "arms": computed, "paired": pairs, "complete_pairs": len(paired_ids(records)),
            "progress": {k: dict(v) if isinstance(v, Counter) else v for k, v in progress.items()},
            "audit": {"execution_sources": source_files, "evidence_files": evidence_files, "responses": response_count,
                      "fresh_agents": len(agents) if simulation else None,
                      "manifest_hash": digest(evidence_bytes) if evidence_bytes else None,
                      "results_snapshot_hash": digest(result_bytes)}}


def compare(repo=REPO, run_names=("qwen-local-003", "luna-agents-002"), partial=False):
    repo = repo.resolve()
    data = repo / "synthetic_dataset"
    dataset = load(data / "manifest.json")
    require(digest(encode({k: v for k, v in dataset.items() if k != "dataset_root"})) == dataset["dataset_root"], "Dataset root differs")
    dataset_files = inventory(data, {**dataset["files"], **dataset["generator_hashes"]}, "Frozen dataset")
    rows = [json.loads(line) for line in (data / "tasks.jsonl").read_bytes().splitlines() if line]
    tasks = {row["id"]: row for row in rows}
    require(len(rows) == len(tasks) == dataset["tasks"], "Dataset task identities differ")
    cases = {task: load(inside(data, metadata["cases_path"])) for task, metadata in tasks.items()}
    require(sum(map(len, cases.values())) == dataset["cases"] and len({c["id"] for batch in cases.values() for c in batch}) == dataset["cases"], "Dataset case identities differ")
    require(len(run_names) == 2 and len(set(run_names)) == 2, "Select two distinct runs")
    runs = [audit_run(repo, name, dataset, tasks, cases, partial) for name in run_names]
    require(runs[0]["protocol"]["task_order"] == runs[1]["protocol"]["task_order"] and
            runs[0]["protocol"]["seed"] == runs[1]["protocol"]["seed"] and
            runs[0]["protocol"]["case_seconds"] == runs[1]["protocol"]["case_seconds"] and
            runs[0]["protocol"]["harness_calls"] == runs[1]["protocol"]["harness_calls"], "Paired corpus/order/case/call settings differ")
    shared_sources = set(runs[0]["protocol"]["source_hashes"]) & set(runs[1]["protocol"]["source_hashes"])
    require(all(runs[0]["protocol"]["source_hashes"][p] == runs[1]["protocol"]["source_hashes"][p] for p in shared_sources), "Common execution-source bytes differ")
    common = sorted(paired_ids(runs[0]["results"]) & paired_ids(runs[1]["results"]))
    all_complete = all(run["complete"] for run in runs)
    common_metrics = {run["run_id"]: metrics([r for r in run["results"] if r["task_id"] in common]) for run in runs}
    return {"format": "verislop.head-to-head-comparison/0.1", "status": "COMPLETE" if all_complete else "PARTIAL_SNAPSHOT",
            "complete": all_complete, "audited_at_utc": datetime.now(timezone.utc).isoformat(),
            "dataset_root": dataset["dataset_root"], "dataset_tasks": dataset["tasks"], "dataset_files_checked": dataset_files,
            "shared_execution_sources_checked": len(shared_sources), "common_paired_tasks": common,
            "common_metrics": common_metrics, "runs": runs, "cases": [c for batch in cases.values() for c in batch],
            "scope": "Recorded-evidence audit; no candidate reruns, oracle proof, model/hardware attestation or universal correctness claim. Tier 0 cannot establish END_TO_END_VERIFIED.",
            "comparability": "Within each model: one raw call versus at most 32 full-CLI calls and two contract repairs; unequal prompt, compute and token budgets. Qwen uses native pinned-model service; Luna is a fresh-agent simulation with unobservable actual model snapshot, sampling, tokens and tool-policy enforcement. Concurrent host use affects timings. Stopped historical runs are excluded."}


def markdown(document):
    complete = document["complete"]
    lines = ["# Qwen and Luna: raw generation versus strict VeriSlop", "",
             "**" + ("Complete, independently audited recorded comparison." if complete else "Partial snapshot; no final benchmark conclusion is claimed.") + "**", "",
             f"Corpus: {document['dataset_tasks']} tasks; common completed pairs across models: {len(document['common_paired_tasks'])}. Audit: {document['audited_at_utc']}.", "",
             "Metrics below use only the common completed task pairs. All recorded arm metrics and exact observations are in `comparison.json`.", ""]
    for run in document["runs"]:
        lines.extend([f"## {run['run_id']}", "", f"Recorded {run['complete_pairs']}/{document['dataset_tasks']} complete pairs; final valid manifest: {run['complete']}.", ""])
        for arm in ARMS:
            m = document["common_metrics"][run["run_id"]][arm]
            lines.append(f"- **{'Raw coding' if arm == 'raw' else 'Full strict CLI'}:** {m['successful_tasks']}/{m['attempted_tasks']} successful tasks; {m['held_out_passed']}/{m['held_out_total']} hidden cases; {m['public_passed']}/{m['public_total']} public cases; {m['artifacts']} artifacts; {m['model_calls']} calls; {m['generation_seconds']:.3f} generation seconds.")
        lines.extend(["", "Calls with unavailable token usage on these pairs: " + "; ".join(
            f"{arm}={document['common_metrics'][run['run_id']][arm]['unknown_usage_calls']}" for arm in ARMS)
            + ". Native token totals include only known usage; simulation token totals remain null."])
        lines.extend(["", "All recorded within-model paired outcomes: " + "; ".join(f"{k}={v}" for k, v in run["paired"].items()) + ".", "",
                      "Pipeline stages passing on recorded tasks: " + json.dumps(run["progress"]["stage_pass_tasks"], sort_keys=True) + ".", "",
                      "Primary failure codes (tasks): " + json.dumps(run["progress"]["primary_failure_codes"], sort_keys=True) + ". Terminal stages: " + json.dumps(run["progress"]["terminal_stages"], sort_keys=True) + ".", "",
                      "All recorded diagnostic counts, including downstream closure effects: " + json.dumps(run["progress"]["diagnostic_codes"], sort_keys=True) + ".", ""])
        by_case = {case["id"]: case for case in document["cases"]}
        failures = [(row, result) for row in run["results"] for result in row["public_results"] + row["held_out_results"]
                    if result["status"] == "FAIL" and "observed" in result]
        if failures:
            lines.extend(["Concrete recorded counterexamples:", ""])
            for row, result in failures[:3]:
                case = by_case[result["id"]]
                lines.append(f"- `{row['task_id']}/{row['arm']}` case `{result['id']}`: input `{json.dumps(case['input'], sort_keys=True)}`; expected `{json.dumps(case['expected'])}`; observed `{json.dumps(result['observed'])}`.")
            lines.append("")
    lines.extend(["## Interpretation and audit boundary", "", document["comparability"], "", document["scope"], "",
                  "A successful raw task requires worker exit zero and every public/hidden case to pass. A successful CLI task additionally requires the returned active package, all strict stages, VERIFIED Tier 0 TESTED report and every required milestone to pass. Missing artifacts retain all failed-case denominators. Repaired package lineage is audited; failed parent artifacts cannot substitute.", "",
                  "The auditor checks frozen dataset/source/configuration hashes, complete final evidence inventories, exact case observations and Boolean/integer distinctions, artifact hashes/unique solve entry, actual CLI invocation/stages/report, task/arm order, call accounting, native identity/token evidence and hash-bound fresh-agent simulation receipts. It reads authoritative evidence without changing it.", "",
                  "[Offline viewer](viewer.html) · [Reproducible comparison JSON](comparison.json) · [Auditor](../tools/compare_runs.py).", ""])
    return "\n".join(lines)


def render_viewer(template, document):
    pattern = r'(<script\b[^>]*\bid=["\']benchmark-data["\'][^>]*>)[\s\S]*?(</script\s*>)'
    require(len(re.findall(pattern, template)) == 1, "Viewer needs exactly one embedded data block")
    payload = encode(document).decode().replace("<", "\\u003c")
    return re.sub(pattern, lambda match: match.group(1) + payload + match.group(2), template, count=1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--runs", nargs=2, default=["qwen-local-003", "luna-agents-002"])
    parser.add_argument("--partial", action="store_true", help="Audit completed arm records as a clearly labeled snapshot")
    parser.add_argument("--out", type=Path, help="New output directory outside all authoritative run directories")
    args = parser.parse_args(argv)
    try:
        document = compare(args.repo, tuple(args.runs), args.partial)
        if args.out:
            out = args.out.resolve()
            run_root = args.repo.resolve() / "synthetic_dataset/runs"
            require(not out.is_relative_to(run_root) and not run_root.is_relative_to(out), "Comparison output must be separate from run evidence")
            out.mkdir(parents=True, exist_ok=True)
            notes = [("SUPPORTED_CONTROL.md", "Separate supported-profile control"),
                     ("INFRASTRUCTURE_NOTES.md", "Observed infrastructure failures"),
                     ("INTERPRETATION_COUNTEREXAMPLES.md", "Concrete interpretation counterexample"),
                     ("PROMPT_COUNTEREXAMPLES.md", "Concrete prompt/output counterexample")]
            notes = [(name, label) for name, label in notes if (out / name).is_file()]
            document["observer_artifacts"] = {name: digest((out / name).read_bytes()) for name, _ in notes}
            text = markdown(document)
            if notes:
                text += "\nAdditional observer evidence (separate from scored task totals):\n\n"
                text += "\n".join(f"- [{label}]({name})" for name, label in notes) + "\n"
            (out / "comparison.json").write_bytes(encode(document))
            (out / ("COMPARISON.md" if document["complete"] else "PARTIAL.md")).write_text(text)
            (out / "viewer.html").write_text(render_viewer((args.repo / "synthetic_dataset/viewer.html").read_text(), document))
        print(json.dumps({"status": document["status"], "common_pairs": len(document["common_paired_tasks"]),
                          "runs": {r["run_id"]: r["complete_pairs"] for r in document["runs"]}, "out": str(args.out) if args.out else None}))
        return 0
    except (AuditFailure, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "AUDIT_FAILED", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
