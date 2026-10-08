"""Fresh paired native Qwen calls against the preregistered three-task cohort.

Preparation freezes inputs without inference. Workers use the ordinary native
Broker and strict CLI, with an additional task-wide finite call guard. There are
no generation, provider, tier or proof wall deadlines. Withheld request checks
run only after generation and never become model feedback.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import threading
from typing import Any

from verislop import canonical, cli, fsutil
from verislop.agents import extract_json
from verislop.errors import Diagnostic, InfrastructureError, VeriSlopError
from verislop.package import Package
from verislop.providers import adapters, config
from verislop.providers.broker import Broker
from verislop.targets import python_target as pt
from synthetic_dataset.arm_worker import RAW_SYSTEM
from synthetic_dataset.tools import run_data_pipeline_poc as native
from synthetic_dataset.tools.check_data_pipeline_poc import PROTOCOL, REPO, check_preregistration, run_check
from synthetic_dataset.tools.check_reservation_poc import CheckFailure, exact, require
from synthetic_dataset.tools.data_pipeline_oracle import TASKS

MODEL = "aix-qwen3.8:27b-ud-q3_k_xl"
MODEL_DIGEST = "283945d2cfdbd2646a4cfa392a55f7ba6c64c69661464f145a321fcbe976a036"
CONTEXT = 32768
CALL_LIMITS = {"raw": 1, "strict": 128}
CASES = 160
REPEATS = 2
CAUGHT = (CheckFailure, VeriSlopError, OSError, ValueError, KeyError, TypeError, AttributeError)


def source_inventory() -> dict[str, str]:
    files = native.source_inputs()
    for directory in (REPO / "synthetic_dataset", REPO / "synthetic_dataset/tools"):
        for path in sorted(directory.glob("*.py")):
            files[path.relative_to(REPO).as_posix()] = canonical.digest_file(path)
    return dict(sorted(files.items()))


def pair_order(index: int) -> tuple[str, str]:
    if type(index) is not int or index < 0:
        raise ValueError("task index must be a nonnegative integer")
    return ("raw", "strict") if index % 2 == 0 else ("strict", "raw")


def prepare(cohort: Path, frozen: dict[str, str] | None = None) -> dict[str, Any]:
    """Create a new immutable protocol/source snapshot; never calls a model."""
    cohort = cohort.absolute()
    require(not cohort.exists() and not cohort.is_symlink(), "Cohort must be new")
    prereg = check_preregistration()
    files = source_inventory()
    require(frozen is None or files == frozen, "Shared source freeze differs from current source")
    cfg = native.configuration_with_context(CONTEXT)
    require(all(agent["model_ref"] == MODEL and agent["model_identity"]["model_digest_sha256"] == MODEL_DIGEST
                and agent["max_output_tokens"] == 8192 for agent in cfg["agents"].values()), "Unexpected native model/configuration")
    require(all(provider["request_timeout_seconds"] is None for provider in cfg["providers"].values())
            and cfg["review"]["budgets"]["max_wall_seconds_per_tier"] == 0, "Generation deadlines must be disabled")
    cohort.mkdir(parents=True)
    for rel, digest in files.items():
        data = (REPO / rel).read_bytes()
        require(canonical.digest(data) == digest, "Input changed during source staging")
        target = cohort / "execution-source" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    native.write_once(cohort / "execution-config.json", cfg)
    profiles = cohort / "config-home/endpoint-profiles.json"
    profiles.parent.mkdir()
    profiles.write_bytes((PROTOCOL / "endpoint-profiles.json").read_bytes())
    freeze = {"format": "verislop.live-source-freeze/0.1", "files": files,
              "root": canonical.digest_json(files), "native_runtime_inputs": native.source_inputs(),
              "preregistration_root": prereg["root"], "frozen_at_utc": datetime.now(timezone.utc).isoformat()}
    protocol = {"format": "verislop.live-qwen-comparison/0.1", "model": MODEL, "model_digest_sha256": MODEL_DIGEST,
        "source_root": freeze["root"], "preregistration_root": prereg["root"], "tasks": list(TASKS),
        "arm_order": {task: list(pair_order(i)) for i, task in enumerate(TASKS)},
        "context_window_tokens": CONTEXT, "max_output_tokens": 8192, "max_output_tokens_enforced": True,
        "logical_call_limits": CALL_LIMITS, "native_broker_budgets": cfg["review"]["budgets"],
        "native_broker_budget_scope": "Per Broker instance, including a new budget for a new repair package; configured total tokens are not a cohort-wide token cap",
        "generation_deadlines": {"outer_seconds": None, "provider_seconds": None, "tier_seconds": 0, "cli_seconds": 0},
        "repair_rounds": 2, "withheld_cases_per_task": CASES, "fresh_withheld_runs": REPEATS,
        "candidate_execution_limits": {"per_call_seconds": 1, "memory_mb": 512, "wire_response_bytes": 8388608},
        "raw_system_sha256": canonical.digest(RAW_SYSTEM.encode()),
        "execution_config_sha256": canonical.digest_file(cohort / "execution-config.json"),
        "endpoint_profiles_sha256": canonical.digest_file(profiles),
        "raw_success_scope": "Finite request behavior only; no native formal milestone",
        "strict_success_scope": "Current strict CLI PASS and native Tier0 TESTED gates, exact recorded origin, and all finite request observations",
        "transport_trust": "Native Ollama model digest catalog checked by Broker before and after every inference; host/transcript fidelity trusted",
        "call_guard": "Counts attempted Broker.call invocations across all repair packages; does not replace native per-instance/token budgets"}
    native.write_once(cohort / "PROTOCOL.json", protocol)
    freeze["protocol_sha256"] = canonical.digest_file(cohort / "PROTOCOL.json")
    native.write_once(cohort / "source-freeze.json", freeze)
    verify_inputs(cohort)
    return protocol


def verify_inputs(cohort: Path) -> dict[str, Any]:
    freeze = canonical.load_file(cohort / "source-freeze.json")
    protocol = canonical.load_file(cohort / "PROTOCOL.json")
    files = freeze["files"]
    require(canonical.digest_file(cohort / "PROTOCOL.json") == freeze["protocol_sha256"], "INPUT_MUTATION: experiment protocol changed")
    require(source_inventory() == files and canonical.digest_json(files) == freeze["root"] == protocol["source_root"],
            "INPUT_MUTATION: shared runtime/verifier/harness source changed")
    require(native.source_inputs() == freeze["native_runtime_inputs"], "INPUT_MUTATION: native runtime subset changed")
    require(check_preregistration()["root"] == freeze["preregistration_root"] == protocol["preregistration_root"],
            "INPUT_MUTATION: preregistration changed")
    require(all(canonical.digest_file(cohort / "execution-source" / rel) == digest for rel, digest in files.items()),
            "INPUT_MUTATION: staged source changed")
    require(canonical.digest_file(cohort / "execution-config.json") == protocol["execution_config_sha256"]
            and canonical.digest_file(cohort / "config-home/endpoint-profiles.json") == protocol["endpoint_profiles_sha256"],
            "INPUT_MUTATION: effective execution configuration changed")
    return freeze


def strict_argv(cohort: Path, directory: Path, task: str) -> list[str]:
    return ["run", "--prompt-file", str(PROTOCOL / f"{task}.txt"), "--request-ref", f"data-pipelines/{task}.txt",
        "--config", str(cohort / "execution-config.json"), "--mode", "software", "--tier", "0", "--target", "python",
        "--endpoint", "test_campaign", "--require-state", "TESTED", "--require-tests", "--non-interactive",
        "--policy", "strict",
        "--budget-seconds", "0", "--repair-rounds", "2", "--seed", "20261008", "--cases", "32",
        "--run-id", task.lower(), "--runs-dir", str(directory / "runs"), "--json"]


class ObservedCalls:
    """Record exact provider objects and count calls without changing native claims."""
    def __init__(self, directory: Path, limit: int):
        self.directory, self.limit = directory, limit
        self.lock = threading.Lock()
        self.state: dict[str, Any] = {"calls": 0, "responses": 0, "input_tokens": 0, "output_tokens": 0,
            "unknown_usage_responses": 0, "logical_call_limit": limit, "call_budget_exhausted": False,
            "output_tokens_per_call_limit": 8192, "generation_deadline_seconds": None}
        self.original_call, self.original_inference = Broker.call, adapters._inference_request

    def save_usage(self) -> None:
        fsutil.write_json(self.directory / "usage.json", self.state, pretty=True)

    def call(self, broker: Broker, agent: str, instance: str, system: str, user: str, purpose: str):
        broker.validate_prompt(agent, system, user)
        with self.lock:
            if self.state["calls"] >= self.limit:
                self.state["call_budget_exhausted"] = True
                self.save_usage()
                raise InfrastructureError("live comparison logical call budget exhausted",
                    [Diagnostic("BUDGET_EXHAUSTED", f"task reached {self.limit} logical calls", severity="blocking")])
            self.state["calls"] += 1
            sequence = self.state["calls"]
            native.write_once(self.directory / f"request-{sequence:03}.json",
                {"agent": agent, "instance": instance, "purpose": purpose, "system": system, "user": user,
                 "system_sha256": canonical.digest(system.encode()), "user_sha256": canonical.digest(user.encode())})
            self.save_usage()
        return self.original_call(broker, agent, instance, system, user, purpose)

    def inference(self, *args, **kwargs):
        body, headers = self.original_inference(*args, **kwargs)
        with self.lock:
            self.state["responses"] += 1
            for key, field in (("input_tokens", "prompt_eval_count"), ("output_tokens", "eval_count")):
                value = body.get(field)
                if type(value) is int and value >= 0:
                    self.state[key] += value
            if any(type(body.get(field)) is not int for field in ("prompt_eval_count", "eval_count")):
                self.state["unknown_usage_responses"] += 1
            native.write_once(self.directory / f"native-response-{self.state['responses']:03}.json", body)
            self.save_usage()
        return body, headers

    def __enter__(self):
        observer = self
        def observed_call(broker, agent, instance, system, user, purpose):
            return observer.call(broker, agent, instance, system, user, purpose)
        Broker.call, adapters._inference_request = observed_call, self.inference
        self.save_usage()
        return self

    def __exit__(self, *exc):
        Broker.call, adapters._inference_request = self.original_call, self.original_inference
        self.save_usage()


def worker(cohort: Path, directory: Path, task: str, arm: str) -> int:
    verify_inputs(cohort)
    require(task in TASKS and arm in CALL_LIMITS and directory == cohort / task / arm, "Worker binding mismatch")
    require(directory.is_dir() and not (directory / "worker-result.json").exists(), "Worker output already exists")
    result: dict[str, Any] = {"task": task, "arm": arm, "status": "WORKER_ERROR", "exit_code": 2}
    with ObservedCalls(directory, CALL_LIMITS[arm]) as observation:
        try:
            if arm == "raw":
                conf = config.load(cohort / "execution-config.json")
                resolved = config.resolve(conf, config.load_user_profiles(None))
                completion = Broker(resolved, directory / "transcripts").call("author", "raw/1", RAW_SYSTEM,
                    (PROTOCOL / f"{task}.txt").read_text(encoding="utf-8"), "raw-coding")
                obj = extract_json(completion.text)
                require(type(obj) is dict and set(obj) == {"files"}, "Raw response must contain exactly the files object")
                files = obj.get("files")
                require(type(files) is dict and set(files) == {"solution.py"} and type(files["solution.py"]) is str,
                        "Raw response must contain exactly files.solution.py as a string")
                artifact = directory / "artifact"
                artifact.mkdir()
                (artifact / "solution.py").write_bytes(files["solution.py"].encode("utf-8"))
                result.update(status="ARTIFACT", exit_code=0, artifact=str(artifact))
            else:
                argv = strict_argv(cohort, directory, task)
                native.write_once(directory / "cli-invocation.json", {"argv": argv, "candidate_inputs": []})
                code = cli.main(argv)
                result.update(status="CLI_RETURNED", exit_code=code)
        except Exception as exc:
            result["error"] = {"type": type(exc).__name__, "message": str(exc)}
            print(canonical.dumps(result["error"]).decode(), file=sys.stderr)
        finally:
            result["usage"] = dict(observation.state)
            native.write_once(directory / "worker-result.json", result)
    return result["exit_code"]


def raw_origin_audit(directory: Path, task: str, cfg: dict[str, Any]) -> dict[str, Any]:
    issues = []
    transcripts = sorted((directory / "transcripts").glob("*.json"))
    entries = [canonical.load_file(path) for path in transcripts]
    if len(entries) != 1:
        issues.append("Raw arm must have exactly one native Broker transcript")
    prompt = (PROTOCOL / f"{task}.txt").read_text(encoding="utf-8")
    for entry in entries:
        if (entry.get("agent") != "author" or entry.get("instance") != "raw/1" or entry.get("purpose") != "raw-coding"
                or entry.get("system") != RAW_SYSTEM or entry.get("user") != prompt
                or entry.get("system_sha256") != canonical.digest(RAW_SYSTEM.encode()) or entry.get("user_sha256") != canonical.digest(prompt.encode())
                or entry.get("requested_model") != MODEL or entry.get("returned_model") != MODEL
                or entry.get("model_digest_sha256") != MODEL_DIGEST or entry.get("context_window_tokens") != CONTEXT):
            issues.append("Raw transcript differs from exact preregistered request/model/context")
        try:
            obj = extract_json(entry["response"])
            require(type(obj) is dict and set(obj) == {"files"}, "Raw response must contain exactly the files object")
            files = obj.get("files")
            require(type(files) is dict and set(files) == {"solution.py"} and type(files["solution.py"]) is str,
                    "Malformed raw artifact response")
            require((directory / "artifact/solution.py").read_bytes() == files["solution.py"].encode("utf-8"),
                    "Raw artifact is not the exact complete model output")
            require(set(path.relative_to(directory / "artifact").as_posix() for path in (directory / "artifact").rglob("*") if path.is_file()) == {"solution.py"},
                    "Raw artifact contains unrecorded files")
        except CAUGHT as exc:
            issues.append(str(exc))
    usage = canonical.load_file(directory / "usage.json")
    if usage.get("calls") != 1 or usage.get("responses") != 1 or usage.get("call_budget_exhausted"):
        issues.append("Raw arm did not complete exactly one native inference")
    return {"status": "PASS" if not issues else "BLOCK", "issues": issues, "provider_calls": len(entries),
            "transcripts": [{"path": path.relative_to(directory).as_posix(), "sha256": canonical.digest_file(path)} for path in transcripts]}


def raw_check(artifact: Path, task: str) -> dict[str, Any]:
    """Same two fresh isolated finite observations, without granting TESTED."""
    result: dict[str, Any] = {"status": "BLOCKED", "task": task, "cases": [], "isolation": [], "diagnostics": [],
        "distinct_cases": 0, "repeats": REPEATS, "observations": 0, "passed_observations": 0, "passed_cases": 0,
        "scope": "Finite natural-language request behavior only; no formal or CLI milestone"}
    before = None
    try:
        prereg = check_preregistration()
        result["preregistration_root"] = prereg["root"]
        require(task in TASKS and artifact.is_dir(), "Missing raw artifact or task")
        before = fsutil.manifest_tree(artifact)
        inventory = pt.inventory(artifact)
        require(not inventory.errors and set(inventory.files) == {"solution.py"}, "Invalid raw Python artifact")
        function = inventory.find("solution.py", "solve")
        require(function is not None and function["kind"] == "function" and function["positional"] == 1
                and not function["decorated"] and not function["varargs"] and not function["defaults"] and not function["kwonly_required"],
                "Raw solve(data) signature differs")
        cases = canonical.load_file(PROTOCOL / "withheld" / f"{task}.json")["cases"]
        require(len(cases) == CASES, "Preregistered case count differs")
        result.update(distinct_cases=len(cases), implementation_manifest=before, runtime=pt.python_identity(),
                      cases=[{**case, "observations": []} for case in cases])
        for _ in range(REPEATS):
            harness = pt.Harness(artifact, inventory.files, {"solve": ("solution.py", "solve")},
                per_call_timeout=1.0, memory_mb=512, require_network_isolation=True, require_filesystem_isolation=True)
            try:
                result["isolation"].append(harness.isolation)
                for case in result["cases"]:
                    response = harness.call("solve", [case["input_wire"]])
                    require(response.get("id") == harness.calls and response.get("op") in ("result", "exception"), "Uncorrelated raw response")
                    canonical.dumps(response)
                    passed = set(response) == {"op", "id", "value"} and response["op"] == "result" and exact(response["value"], case["expected_wire"])
                    case["observations"].append({"response": response, "passed": passed})
            finally:
                harness.close()
        result["status"] = "PASS" if cases and all(all(row["passed"] for row in case["observations"]) and len(case["observations"]) == REPEATS for case in result["cases"]) else "BLOCKED"
    except pt.HarnessError as exc:
        result["status"] = "BLOCKED" if exc.kind in {"timeout", "crash", "protocol", "import_failure", "module_resolution", "assertions_disabled", "hash_mismatch", "error"} else "INFRASTRUCTURE_FAILURE"
        result["diagnostics"].append({"kind": exc.kind, "message": str(exc)})
    except CAUGHT as exc:
        result["diagnostics"].append(str(exc))
    finally:
        for case in result["cases"]:
            case["passed"] = len(case["observations"]) == REPEATS and all(row["passed"] for row in case["observations"])
        result.update(passed_cases=sum(case["passed"] for case in result["cases"]),
            failed_cases=sum(any(not row["passed"] for row in case["observations"]) for case in result["cases"]),
            incomplete_cases=sum(len(case["observations"]) < REPEATS for case in result["cases"]),
            observations=sum(len(case["observations"]) for case in result["cases"]),
            passed_observations=sum(row["passed"] for case in result["cases"] for row in case["observations"]))
    try:
        unchanged = before is not None and before == fsutil.manifest_tree(artifact)
        result["input_bytes_unchanged"] = unchanged
        require(unchanged, "INPUT_MUTATION: raw artifact changed during read-only observation")
        require(check_preregistration()["root"] == result.get("preregistration_root"), "INPUT_MUTATION: oracle changed")
    except CAUGHT as exc:
        result["status"] = "BLOCKED"
        result["diagnostics"].append(str(exc))
    result["observations_hash"] = canonical.digest_json(result["cases"])
    return result


def score_arm(cohort: Path, directory: Path, task: str, arm: str, exit_code: int) -> dict[str, Any]:
    freeze = verify_inputs(cohort)
    cfg = canonical.load_file(cohort / "execution-config.json")
    diagnostics: list[str] = []
    audits, selected = [], None
    native_result: dict[str, Any] = {}
    oracle: dict[str, Any] = {"status": "BLOCKED", "diagnostics": ["No current artifact selected"]}
    bound = False
    try:
        if arm == "raw":
            audits = [raw_origin_audit(directory, task, cfg)]
            if exit_code == 0 and all(row["status"] == "PASS" for row in audits):
                selected = directory / "artifact"
                bound = True
                oracle = raw_check(selected, task)
        else:
            native_result = canonical.load_file(directory / "stdout.json")
            require(type(native_result) is dict and native_result.get("status") in {"PASS", "BLOCKED", "INFRASTRUCTURE_FAILURE"}, "Malformed native CLI result")
            packages = [Package(path, resolve_root=False) for path in sorted((directory / "runs").glob("*")) if (path / "package.json").is_file()]
            for pkg in packages:
                try:
                    audit = native.origin_audit(pkg, strict_argv(cohort, directory, task), freeze["native_runtime_inputs"], effective_config=cfg)
                except CAUGHT as exc:
                    audit = {"status": "BLOCK", "issues": [str(exc)], "provider_calls": 0}
                audits.append({"package": str(pkg.root), **audit})
            selected = native.active_package(directory, task, native_result, packages)
            bound = True
            oracle = run_check(selected, task)
    except CAUGHT as exc:
        diagnostics.append(str(exc))
    native.write_once(directory / "origin-audit.json", audits)
    native.write_once(directory / "independent-oracle.json", oracle)
    unchanged = True
    try:
        verify_inputs(cohort)
    except CAUGHT as exc:
        diagnostics.append(str(exc))
        unchanged = False
    if arm == "strict":
        status = native.task_status(native_result, exit_code, oracle, audits, bound=bound, unchanged=unchanged)
        success = status == "VERIFIED"
    else:
        success = unchanged and bound and exit_code == 0 and oracle.get("status") == "PASS" and bool(audits) and all(row["status"] == "PASS" for row in audits)
        status = "PASS" if success else "INFRASTRUCTURE_FAILURE" if unchanged and oracle.get("status") == "INFRASTRUCTURE_FAILURE" else "BLOCKED"
    usage = canonical.load_file(directory / "usage.json") if (directory / "usage.json").is_file() else {}
    row = {"task": task, "arm": arm, "status": status, "successful_task": success, "exit_code": exit_code,
        "native_status": native_result.get("status"), "selected_artifact": str(selected) if selected else None,
        "native_tested_gate": oracle.get("native_gate_passed") if arm == "strict" else None,
        "independent_cases": CASES, "independent_cases_loaded": oracle.get("distinct_cases", 0),
        "independent_cases_passed": oracle.get("passed_cases", 0), "observations": oracle.get("observations", 0),
        "passed_observations": oracle.get("passed_observations", 0), "logical_calls": usage.get("calls", 0),
        "native_provider_calls": sum(row.get("provider_calls", 0) for row in audits),
        "call_budget_exhausted": usage.get("call_budget_exhausted", False), "usage": usage,
        "origin_audit_passed": bool(audits) and all(row["status"] == "PASS" for row in audits),
        "active_artifact_bound": bound, "frozen_inputs_unchanged": unchanged, "diagnostics": diagnostics}
    native.write_once(directory / "result.json", row)
    return row


def comparison_summary(rows: list[dict[str, Any]], source_root: str) -> dict[str, Any]:
    aggregates = {}
    for arm in CALL_LIMITS:
        selected = [row for row in rows if row["arm"] == arm]
        aggregates[arm] = {"successful_tasks": sum(row["successful_task"] for row in selected), "total_tasks": len(TASKS),
            "completed_tasks": len(selected), "independent_cases_passed": sum(row["independent_cases_passed"] for row in selected),
            "independent_cases_expected": CASES * len(TASKS), "observations": sum(row["observations"] for row in selected),
            "passed_observations": sum(row["passed_observations"] for row in selected), "logical_calls": sum(row["logical_calls"] for row in selected)}
    paired = {"both": 0, "raw_only": 0, "strict_only": 0, "neither": 0, "incomplete": 0}
    for task in TASKS:
        pair = {row["arm"]: row for row in rows if row["task"] == task}
        if set(pair) != set(CALL_LIMITS):
            paired["incomplete"] += 1
        else:
            raw, strict = pair["raw"]["successful_task"], pair["strict"]["successful_task"]
            paired["both" if raw and strict else "raw_only" if raw else "strict_only" if strict else "neither"] += 1
    return {"format": "verislop.live-qwen-comparison-summary/0.1", "model": MODEL, "source_root": source_root,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(), "arms": aggregates, "paired_tasks": paired, "results": rows,
        "scope": "One fresh native model attempt per task/arm; raw finite behavior compared with full strict Tier0 TESTED plus same finite observations"}


def run(cohort: Path) -> dict[str, Any]:
    cohort = cohort.absolute()
    freeze = verify_inputs(cohort)
    require(not (cohort / "SUMMARY.json").exists(), "Cohort is already sealed")
    rows = []
    blocking_reason = None
    env = {**os.environ, "VERISLOP_CONFIG_HOME": str(cohort / "config-home")}
    for index, task in enumerate(TASKS):
        for arm in pair_order(index):
            try:
                verify_inputs(cohort)
            except CAUGHT as exc:
                blocking_reason = str(exc)
                break
            directory = cohort / task / arm
            directory.mkdir(parents=True, exist_ok=False)
            command = [sys.executable, "-m", "synthetic_dataset.tools.live_qwen_comparison", "worker", "--cohort", str(cohort),
                       "--directory", str(directory), "--task", task, "--arm", arm]
            native.write_once(directory / "invocation.json", {"argv": command, "cwd": str(REPO),
                "environment_override": {"VERISLOP_CONFIG_HOME": str(cohort / "config-home")},
                "source_root": freeze["root"], "generation_timeout_seconds": None, "candidate_inputs": [],
                "started_at_utc": datetime.now(timezone.utc).isoformat()})
            print(f"START Qwen {task} {arm}", flush=True)
            with (directory / "stdout.json").open("xb") as stdout, (directory / "stderr.log").open("xb") as stderr:
                process = subprocess.run(command, cwd=REPO, env=env, stdout=stdout, stderr=stderr, check=False)
            row = score_arm(cohort, directory, task, arm, process.returncode)
            rows.append(row)
            print(canonical.dumps({key: row[key] for key in ("task", "arm", "status", "independent_cases_passed", "logical_calls")}).decode(), flush=True)
            if not row["frozen_inputs_unchanged"]:
                blocking_reason = "INPUT_MUTATION: entire cohort invalidated"
                break
        if blocking_reason:
            break
    if blocking_reason:
        rows = [{**row, "retained_status": row["status"], "retained_successful_task": row["successful_task"],
                 "status": "BLOCKED", "successful_task": False, "cohort_blocking_reason": blocking_reason} for row in rows]
    summary = comparison_summary(rows, freeze["root"])
    summary["blocking_reason"] = blocking_reason
    native.write_once(cohort / "SUMMARY.json", summary)
    native.write_once(cohort / "EVIDENCE-MANIFEST.json", fsutil.manifest_tree(cohort))
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for operation in ("prepare", "run", "worker", "verify"):
        subparser = subparsers.add_parser(operation)
        subparser.add_argument("--cohort", required=True, type=Path)
        if operation == "worker":
            subparser.add_argument("--directory", required=True, type=Path)
            subparser.add_argument("--task", required=True, choices=TASKS)
            subparser.add_argument("--arm", required=True, choices=CALL_LIMITS)
    args = parser.parse_args(argv)
    if args.operation == "worker":
        return worker(args.cohort.absolute(), args.directory.absolute(), args.task, args.arm)
    value = prepare(args.cohort) if args.operation == "prepare" else run(args.cohort) if args.operation == "run" else verify_inputs(args.cohort)
    print(canonical.dumps(value).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
