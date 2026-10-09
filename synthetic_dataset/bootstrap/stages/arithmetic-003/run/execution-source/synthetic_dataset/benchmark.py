"""Paired one-shot Qwen versus full VeriSlop CLI benchmark, with immutable inputs."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from verislop import sandbox
from verislop.providers.adapters import ollama_model_digest
from verislop.targets.python_target import python_runtime_paths
from synthetic_dataset.build_dataset import ROOT, digest, encode

REPO = ROOT.parent
DEFAULT_MODEL = "aix-qwen3.8:27b-ud-q3_k_xl"  # This benchmark fixture, never a CLI model default.


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encode(value))
    temporary.replace(path)


def load(path, default=None):
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError):
        return default


def verify_dataset():
    manifest = load(ROOT / "manifest.json")
    if not manifest:
        raise ValueError("run python -m synthetic_dataset.build_dataset first")
    for rel, expected in {**manifest["files"], **manifest["generator_hashes"]}.items():
        if digest((ROOT / rel).read_bytes()) != expected:
            raise ValueError(f"dataset mutation: {rel}")
    root = manifest["dataset_root"]
    if digest(encode({k: v for k, v in manifest.items() if k != "dataset_root"})) != root:
        raise ValueError("invalid dataset root")
    return manifest


def configuration(model, model_digest, seconds, per_call_tokens):
    conf = load(REPO / "examples/ollama-review-config.json")
    conf["bridge_tier"], conf["endpoint"] = 0, "test_campaign"
    conf["providers"]["local"]["request_timeout_seconds"] = seconds or None
    conf["agents"] = {"author": {"provider": "local", "model_ref": model, "tool_profile": "candidate_writer",
                                "max_output_tokens": per_call_tokens,
                                "model_identity": {"mode": "pinned", "resolved_model": model, "model_digest_sha256": model_digest}},
                      "critic": {"provider": "local", "model_ref": model, "tool_profile": "review_readonly",
                                 "max_output_tokens": per_call_tokens,
                                 "model_identity": {"mode": "pinned", "resolved_model": model, "model_digest_sha256": model_digest}}}
    conf["roles"] = {role: "author" for role in conf["roles"]}
    conf["review"]["require_fixed_model_snapshot"] = True
    conf["review"]["budgets"].update({"max_repair_rounds": 2, "max_provider_retries": 0, "max_calls_per_instance": 16,
                                    "max_total_tokens": 1_000_000, "max_wall_seconds_per_tier": seconds})
    conf["review"]["review_tiers"] = [{"id": "R0", "reviewers": [{"agent": "critic", "count": 1, "focus": "counterexamples"}],
                                       "consensus": {"mode": "unanimous", "require_all_responses": True,
                                                     "max_soft_rejects": 0, "max_abstentions": 0, "blocking_findings_veto": True}}]
    return conf


def resolve_cli_package(directory, pipeline=None):
    """Select the CLI's actual final package without escaping this arm's evidence."""
    directory = Path(directory).resolve()
    if pipeline is not None and not isinstance(pipeline, dict):
        raise ValueError("CLI result is not an object")
    summary = (pipeline or {}).get("summary", {})
    if not isinstance(summary, dict):
        raise ValueError("CLI summary is not an object")
    selected = summary.get("active_package")
    if selected is None:
        selected = directory / "package"
    elif not isinstance(selected, str) or not selected:
        raise ValueError("CLI active_package is not a nonempty path")
    else:
        selected = Path(selected)
        if not selected.is_absolute():
            selected = directory / selected
    if selected.is_symlink():
        raise ValueError("CLI active_package is a symlink")
    selected = selected.resolve()
    if selected.parent != directory or not re.fullmatch(r"package(?:-repair-(?:0[1-9]|[1-9][0-9]))?", selected.name):
        raise ValueError("CLI active_package is outside this arm's package lineage")
    return selected


def cli_success(pipeline, report, worker_exit_code, timed_out=False, stages=None):
    """A coding score cannot promote an incomplete or weaker strict CLI workflow."""
    if timed_out or worker_exit_code != 0 or not isinstance(pipeline, dict) or not isinstance(report, dict):
        return False
    if pipeline.get("status") != "PASS" or report.get("terminal_status") != "VERIFIED":
        return False
    tier = report.get("tier", {})
    if not isinstance(tier, dict) or any(tier.get(key) != value for key, value in
            {"requested": 0, "target": "python", "endpoint": "test_campaign", "require_state": "TESTED"}.items()):
        return False
    if report.get("blocking_reasons") or report.get("infrastructure_errors"):
        return False
    if stages is None:
        summary = pipeline.get("summary", {})
        stages = summary.get("stages", []) if isinstance(summary, dict) else []
    if not isinstance(stages, list):
        return False
    gates = {stage.get("stage"): stage.get("status") for stage in stages if isinstance(stage, dict)}
    required = {"formalize", "prove", "accept", "export", "review:formal_contract", "generate", "link", "test", "review:release"}
    if any(gates.get(gate) != "PASS" for gate in required):
        return False
    obligations = report.get("obligations", {})
    if not isinstance(obligations, dict) or not obligations:
        return False
    tested = False
    for obligation in obligations.values():
        if not isinstance(obligation, dict):
            return False
        if not obligation.get("required"):
            continue
        milestones, outcomes = obligation.get("required_milestones"), obligation.get("outcomes")
        if not isinstance(milestones, list) or not milestones or not isinstance(outcomes, dict):
            return False
        if any(outcomes.get(milestone) != "PASS" for milestone in milestones):
            return False
        tested |= "TESTED" in milestones
    return tested


def artifact_files(arm, directory, pipeline=None):
    root = directory / "artifact" if arm == "raw" else resolve_cli_package(directory, pipeline) / "implementation"
    files = {}
    entries = []
    if root.is_symlink():
        raise ValueError("artifact root is a symlink")
    if not root.is_dir():
        return files, None
    for p in sorted(root.rglob("*")):
        if p.is_symlink():
            raise ValueError("artifact contains a symlink")
        if p.is_file() and p.suffix == ".py":
            data = p.read_bytes()
            if len(data) > 1 << 20:
                raise ValueError("artifact source exceeds 1 MiB")
            rel = p.relative_to(root).as_posix()
            files[rel] = data
            try:
                tree = ast.parse(data)
                entries += [rel for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "solve"]
            except (SyntaxError, UnicodeError):
                pass
    if len(entries) != 1:
        return files, None
    return files, entries[0]


def grade(files, entry, cases, case_seconds):
    if not entry:
        return [{"id": c["id"], "status": "FAIL", "reason": "missing unambiguous solve(data) artifact"} for c in cases], {}
    with tempfile.TemporaryDirectory(prefix="verislop-benchmark-grade-") as temporary:
        root = Path(temporary)
        artifact = root / "artifact"
        artifact.mkdir()
        for rel, data in files.items():
            dest = artifact / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        worker = root / "grade_worker.py"
        shutil.copyfile(ROOT / "grade_worker.py", worker)
        request = {"root": str(artifact), "entry_file": str(artifact / entry), "case_seconds": case_seconds,
                   "cases": [{"id": c["id"], "input": c["input"]} for c in cases]}
        run = sandbox.run([str(Path(sys.executable).resolve()), "-I", "-S", "-B", str(worker)], root,
                          timeout=case_seconds * (len(cases) + 1) + 3, memory_mb=512, fsize_mb=8,
                          require_network_isolation=True, require_filesystem_isolation=True,
                          read_only_paths=python_runtime_paths(), stdin=encode(request))
        observations = None if run.timed_out else load_bytes(run.stdout)
        records = (observations or {}).get("results", [])
        if len(records) != len(cases) or [r.get("id") for r in records] != [c["id"] for c in cases]:
            return [{"id": c["id"], "status": "FAIL", "reason": "grader timeout or invalid output"} for c in cases], run.isolation
        scored = []
        for c, observed in zip(cases, records):
            passed = "error" not in observed and "observed" in observed and encode(observed["observed"]) == encode(c["expected"])
            scored.append({**observed, "status": "PASS" if passed else "FAIL", "expected": c["expected"]})
        return scored, run.isolation


def load_bytes(data):
    try:
        return json.loads(data)
    except (ValueError, UnicodeError):
        return None


def run_arm(task, arm, index, out, cfg_path, args):
    directory = out / "artifacts" / task["id"] / arm
    directory.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, "-m", "synthetic_dataset.arm_worker", "--arm", arm,
               "--task", str(ROOT / task["prompt_path"]), "--out", str(directory), "--config", str(cfg_path),
               "--seconds", str(args.arm_seconds), "--tokens", str(args.output_token_budget),
               "--calls", "1" if arm == "raw" else str(args.harness_calls)]
    env = dict(os.environ)
    env["VERISLOP_CONFIG_HOME"] = str(out / "provider-home")
    start = time.monotonic()
    timed_out = False
    proc = subprocess.Popen(command, cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=args.arm_seconds or None)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGINT)
        try:
            stdout, stderr = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
    generation_seconds = time.monotonic() - start
    (directory / "stdout.txt").write_bytes(stdout)
    (directory / "stderr.txt").write_bytes(stderr)
    pipeline = load_bytes(stdout) or {}
    if not isinstance(pipeline, dict):
        pipeline = {}
    summary = pipeline.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    package, artifact_error = None, None
    if arm == "verislop":
        try:
            package = resolve_cli_package(directory, pipeline)
        except ValueError as exc:
            artifact_error = str(exc)
    cli_report = load(package / "report.json", {}) if package else {}
    meta = load(package / "package.json", {}) if package else {}
    if not isinstance(cli_report, dict):
        cli_report = {}
    if not isinstance(meta, dict):
        meta = {}
    usage = load(directory / "usage.json", {})
    usage["unknown_usage_calls"] = max(usage.get("unknown_usage_calls", 0), usage.get("calls", 0) - usage.get("responses", 0))
    cases = load(ROOT / task["cases_path"])
    try:
        files, entry = artifact_files(arm, directory, pipeline)
    except ValueError as exc:
        files, entry, artifact_error = {}, None, str(exc)
    all_scores, isolation = grade(files, entry, cases, args.case_seconds)
    scores = [s for s, c in zip(all_scores, cases) if c["visibility"] == "hidden"]
    public = [s for s, c in zip(all_scores, cases) if c["visibility"] == "public"]
    workflow_status = ("TIMEOUT" if timed_out else (pipeline.get("status") or cli_report.get("terminal_status") or "ERROR")) if arm == "verislop" else ("TIMEOUT" if timed_out else "ARTIFACT" if entry else "ERROR")
    stages = summary.get("stages", meta.get("stage_history", []))
    requests = [load(path, {}) for path in sorted(directory.glob("request-*.json"))]
    strict_success = cli_success(pipeline, cli_report, proc.returncode, timed_out, stages) if arm == "verislop" else None
    success = bool(scores) and all(s["status"] == "PASS" for s in all_scores) and not timed_out and proc.returncode == 0 and (arm == "raw" or strict_success)
    record = {"task_id": task["id"], "title": task["title"], "category": task["category"], "arm": arm,
              "pair_index": index, "workflow_status": workflow_status, "successful_task": success,
              "artifact_present": bool(files), "entry_file": entry, "artifact_error": artifact_error,
              "source_hashes": {k: digest(v) for k, v in files.items()}, "generation_seconds": round(generation_seconds, 3),
              "worker_exit_code": proc.returncode, "timed_out": timed_out, "usage": usage,
              "hidden_passed": sum(s["status"] == "PASS" for s in scores), "hidden_total": len(scores),
              "public_passed": sum(s["status"] == "PASS" for s in public), "public_total": len(public),
              "held_out_results": scores, "public_results": public, "grader_isolation": isolation,
              "cli_stages": stages, "last_model_purpose": requests[-1].get("purpose") if requests else None,
              "cli_diagnostics": pipeline.get("diagnostics", cli_report.get("blocking_reasons", []) + cli_report.get("infrastructure_errors", [])),
              "strict_cli_success": strict_success,
              "active_package": str(package.relative_to(out)) if package else None,
              "recovery": summary.get("recovery"),
              "cli_report": str((package / "report.json").relative_to(out)) if cli_report else None,
              "artifact_path": str(directory.relative_to(out))}
    write(directory / "score.json", record)
    return record


def summarize(records, manifest, protocol):
    arms = {}
    for arm in ("raw", "verislop"):
        rows = [r for r in records if r["arm"] == arm]
        arms[arm] = {"attempted_tasks": len(rows), "successful_tasks": sum(r["successful_task"] for r in rows),
                     "artifacts": sum(r["artifact_present"] for r in rows),
                     "held_out_passed": sum(r["hidden_passed"] for r in rows), "held_out_total": sum(r["hidden_total"] for r in rows),
                     "public_passed": sum(r["public_passed"] for r in rows), "public_total": sum(r["public_total"] for r in rows),
                     "generation_seconds": round(sum(r["generation_seconds"] for r in rows), 3),
                     "model_calls": sum(r["usage"].get("calls", 0) for r in rows),
                     "input_tokens": sum(r["usage"].get("input_tokens", 0) for r in rows),
                     "output_tokens": sum(r["usage"].get("output_tokens", 0) for r in rows),
                     "unknown_usage_calls": sum(r["usage"].get("unknown_usage_calls", 0) for r in rows),
                     "last_model_purposes": dict(Counter(r["last_model_purpose"] or "none" for r in rows)),
                     "statuses": dict(Counter(r["workflow_status"] for r in rows))}
    by_id = {}
    for r in records:
        by_id.setdefault(r["task_id"], {})[r["arm"]] = r
    paired = {"both_success": 0, "raw_only": 0, "verislop_only": 0, "neither_success": 0}
    for row in by_id.values():
        if set(row) != {"raw", "verislop"}:
            continue
        a, b = row["raw"]["successful_task"], row["verislop"]["successful_task"]
        paired["both_success" if a and b else "raw_only" if a else "verislop_only" if b else "neither_success"] += 1
    categories = {}
    for category in sorted({r["category"] for r in records}):
        categories[category] = {arm: {"tasks": len(rows := [r for r in records if r["category"] == category and r["arm"] == arm]),
                                     "successes": sum(r["successful_task"] for r in rows),
                                     "passed": sum(r["hidden_passed"] for r in rows), "total": sum(r["hidden_total"] for r in rows)}
                                for arm in arms}
    return {"format": "verislop.synthetic-benchmark-summary/0.1", "dataset_root": manifest["dataset_root"],
            "dataset_tasks": manifest["tasks"], "protocol": protocol, "arms": arms, "paired": paired, "categories": categories,
            "complete_pairs": sum(paired.values()), "complete": sum(paired.values()) == manifest["tasks"]}


def report(out, summary, records):
    arms = summary["arms"]
    lines = ["# Bounded local Qwen software-engineering benchmark", "", f"Dataset: {summary['dataset_tasks']} locally authored tasks; {summary['complete_pairs']} complete pairs.", "",
             f"Model: `{summary['protocol']['model']}`; digest `{summary['protocol']['model_digest']}`.", "",
             "The raw arm uses one native coding call. The VeriSlop arm invokes the full strict Tier 0 CLI workflow; its existing prompts, validators, Lean gates and configured review gates are retained. A successful task passes both public and held-out cases and, for VeriSlop, the CLI workflow. Blocked stages and timeouts count as unsuccessful tasks. A missing artifact fails every held-out case.", ""]
    for arm, label in (("raw", "Raw Qwen"), ("verislop", "Full VeriSlop")):
        r = arms[arm]
        denominator = r["held_out_total"]
        rate = (100 * r["held_out_passed"] / denominator) if denominator else 0
        lines += [f"- **{label}:** {r['successful_tasks']}/{r['attempted_tasks']} successful tasks; {r['held_out_passed']}/{denominator} held-out cases passed ({rate:.1f}%); {r['artifacts']} artifacts; {r['model_calls']} model calls; {r['generation_seconds']:.1f} generation seconds."]
    wall_limit = (f"{summary['protocol']['arm_seconds']} seconds (up to two seconds shutdown grace)"
                  if summary['protocol']['arm_seconds'] else "no generation wall-clock deadline")
    lines += ["", "## Fixed limits and interpretation", "", f"Per arm: {wall_limit}, {summary['protocol']['per_call_output_tokens']} generated tokens per call, {summary['protocol']['output_token_budget']} generated tokens total; raw one call, VeriSlop at most {summary['protocol']['harness_calls']}. Candidate cases have a {summary['protocol']['case_seconds']} second limit and 512 MiB memory limit.", "",
              "Arm order alternates within a fixed shuffled task order. Temperature is zero, thinking is disabled and JSON mode is used by both arms. Tasks and tests were frozen before benchmark calls. Only two public examples enter each task prompt; reference implementations and held-out expected outputs are excluded from prompts and candidate execution mounts. Scores are calculated outside candidate execution.", "",
              "This is a single-model, single-run feasibility comparison on synthetic bounded Python functions. Difficulty is author assigned. The full CLI currently supports narrower formal domains than general JSON/Python tasks. Its blocked runs may measure that representation boundary or contract-generation overhead rather than coding ability. Both arms have the same wall-clock policy; prompt size, model-call count and verification work differ, so this is not an equal-token causal estimate of verification benefits. No passing score establishes universal correctness or a Lean implementation proof.", "",
              "Token totals cover received native responses only; timeout/disconnection usage is unknown and counted separately. Requested output capacity is reserved before calls, including calls with unknown usage. A nonzero global deadline is checked between pairs; zero disables it. The experiment remains bounded by the task count, call/token budgets and finite candidate evaluation limits.", "",
              "## Evidence", "", "`protocol.json` freezes model, limits, execution order and verifier identities. `results.jsonl` and `summary.json` are authoritative benchmark scores. Each artifact directory preserves request prompts, native response bodies (including rejected/truncated responses), broker transcripts, generated code or CLI package, CLI output and per-case observations. `manifest.json` binds the dataset; `run-manifest.json` binds final evidence bytes.", "", "## Workflow outcomes", ""]
    for arm in arms:
        lines.append(f"- {arm}: " + ", ".join(f"{k}={v}" for k, v in sorted(arms[arm]["statuses"].items())))
    failures = [r for r in records if r["arm"] == "verislop" and r["cli_diagnostics"]]
    if failures:
        lines += ["", "## Concrete recorded failures", ""]
        for r in failures[:5]:
            d = r["cli_diagnostics"][0]
            lines.append(f"- {r['task_id']}: `{d.get('code')}` — {d.get('message', '')[:500]}. Evidence: `{r['artifact_path']}/score.json`.")
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL))
    p.add_argument("--base-url", default="http://127.0.0.1:11435")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--arm-seconds", type=int, default=0, help="Generation wall-clock limit; 0 disables all inference and pipeline deadlines")
    p.add_argument("--per-call-output-tokens", type=int, default=8192)
    p.add_argument("--output-token-budget", type=int, default=262144)
    p.add_argument("--harness-calls", type=int, default=32)
    p.add_argument("--case-seconds", type=float, default=1)
    p.add_argument("--global-seconds", type=int, default=0, help="Admission deadline between pairs; 0 disables it")
    p.add_argument("--seed", type=int, default=20261007)
    p.add_argument("--limit", type=int, default=100)
    args = p.parse_args()
    if not (1 <= args.limit <= 100 and 0 <= args.arm_seconds <= 600 and 1 <= args.harness_calls <= 32
            and 1 <= args.per_call_output_tokens <= args.output_token_budget <= 1048576 and 0 < args.case_seconds <= 10
            and args.global_seconds >= 0):
        p.error("invalid bounded benchmark limits")
    manifest = verify_dataset()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    profile = {"adapter": "ollama", "base_url": args.base_url, "auth_scheme": "none", "families": ["ollama_chat"], "allow_insecure_loopback": True}
    model_digest = ollama_model_digest(profile, args.model, None if args.arm_seconds == 0 else 15)
    (out / "provider-home").mkdir()
    write(out / "provider-home/endpoint-profiles.json", {"schema_version": "0.1", "artifact_kind": "endpoint_profiles",
          "profiles": {"ollama-local": {**profile, "auth_check": "GET /api/tags"}}})
    cfg = configuration(args.model, model_digest, args.arm_seconds, args.per_call_output_tokens)
    write(out / "config.json", cfg)
    tasks = [json.loads(line) for line in (ROOT / "tasks.jsonl").read_text().splitlines()]
    random.Random(args.seed).shuffle(tasks)
    tasks = tasks[:args.limit]
    from verislop.verifiers import registry_snapshot, host_environment
    source_paths = [*ROOT.glob("*.py"), *REPO.joinpath("verislop").rglob("*.py"), *REPO.joinpath("verislop/lean").rglob("*.lean"), *REPO.joinpath("schemas").glob("*.json")]
    protocol = {"format": "verislop.synthetic-benchmark-protocol/0.1", "model": args.model, "model_digest": model_digest,
                "base_url": args.base_url, "dataset_root": manifest["dataset_root"], "arm_seconds": args.arm_seconds or None,
                "per_call_output_tokens": args.per_call_output_tokens, "output_token_budget": args.output_token_budget,
                "harness_calls": args.harness_calls, "case_seconds": args.case_seconds, "global_seconds": args.global_seconds or None,
                "seed": args.seed, "task_order": [t["id"] for t in tasks], "arm_order": "raw first for even pair indices; VeriSlop first for odd indices",
                "temperature": 0, "thinking": False, "native_json_mode": True, "host_environment": host_environment(),
                "verifier_registry": registry_snapshot(), "config_hash": digest(encode(cfg)),
                "source_hashes": {path.relative_to(REPO).as_posix(): digest(path.read_bytes()) for path in sorted(source_paths)},
                "budget_instrumentation": "benchmark worker records native responses and shares call/output budgets; no prompt or verifier logic changes",
                "strict_recovery_rounds": 2,
                "scoring_policy": "raw requires successful worker exit and all public/held-out cases; VeriSlop additionally requires all strict gates PASS and an active-package VERIFIED Tier 0 TESTED report; failed parent artifacts never substitute for a repaired package",
                "generation_deadline_policy": "disabled; provider, supervisor, proof search and review waits have no wall-clock deadline" if args.arm_seconds == 0 else "fixed positive per-arm generation deadline",
                "global_deadline_policy": "disabled; all selected tasks admitted" if args.global_seconds == 0 else "checked before each pair; an admitted pair finishes under both arm and grading limits",
                "user_selected_mode": "full CLI; blocked stages count as unsuccessful tasks"}
    protocol["started_at_utc"] = datetime.now(timezone.utc).isoformat()
    write(out / "protocol.json", protocol)
    for relative in protocol["source_hashes"]:
        destination = out / "execution-source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / relative, destination)
    started = time.monotonic()
    records = []
    for index, task in enumerate(tasks):
        if args.global_seconds and time.monotonic() - started >= args.global_seconds:
            break
        verify_dataset()
        arms = ("raw", "verislop") if index % 2 == 0 else ("verislop", "raw")
        for arm in arms:
            row = run_arm(task, arm, index, out, out / "config.json", args)
            records.append(row)
            with (out / "results.jsonl").open("ab") as file:
                file.write(encode(row))
            summary = summarize(records, manifest, protocol)
            write(out / "summary.json", summary)
            print(json.dumps({"pair": index + 1, "task": task["id"], "arm": arm, "status": row["workflow_status"],
                              "hidden_passed": row["hidden_passed"], "hidden_total": row["hidden_total"],
                              "seconds": row["generation_seconds"], "complete_pairs": summary["complete_pairs"]}), flush=True)
    verify_dataset()
    source_changes = [rel for rel, expected in protocol["source_hashes"].items() if digest((REPO / rel).read_bytes()) != expected]
    summary = summarize(records, manifest, protocol)
    summary.update({"wall_seconds": round(time.monotonic() - started, 3), "source_mutations": source_changes,
                    "model_digest_after": ollama_model_digest(profile, args.model, None if args.arm_seconds == 0 else 15),
                    "finished_at_utc": datetime.now(timezone.utc).isoformat()})
    summary["valid"] = not source_changes and summary["model_digest_after"] == model_digest
    write(out / "summary.json", summary)
    report(out, summary, records)
    files = {path.relative_to(out).as_posix(): digest(path.read_bytes()) for path in sorted(out.rglob("*"))
             if path.is_file() and path.name not in {"run-manifest.json"}}
    write(out / "run-manifest.json", {"format": "verislop.synthetic-benchmark-evidence/0.1", "dataset_root": manifest["dataset_root"],
                                      "protocol_hash": digest(encode(protocol)), "files": files, "complete": summary["complete"], "valid": summary["valid"]})
    return 0 if summary["complete"] and summary["valid"] else 2


if __name__ == "__main__":
    sys.exit(main())
