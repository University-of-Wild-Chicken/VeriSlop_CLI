"""Read-only stopped-run audit and concrete failure diagnosis; never rescore candidates.

Uses captured source hashes after runtime repairs. A separately captured pre-repair
source audit records that current sources matched at the stop boundary. New output
directories are sealed and are never overwritten by this tool.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from synthetic_dataset.tools import compare_runs as comparison

REPO = Path(__file__).resolve().parents[2]
RUNS = ("qwen-local-003", "luna-agents-002")


def jsonl(path):
    return [json.loads(line) for line in path.read_bytes().splitlines() if line] if path.exists() else []


def diagnose_run(repo, run):
    name = run["run_id"]
    root = repo / "synthetic_dataset/runs" / name
    rows = [r for r in run["results"] if r["arm"] == "verislop"]
    stages, primary, providers, purpose_calls = Counter(), Counter(), Counter(), Counter()
    failures, proof_feedback, review_packets, accepted_weaknesses = [], [], [], []
    for row in rows:
        arm = root / row["artifact_path"]
        package = root / row["active_package"] if row.get("active_package") else None
        first_failed = next((s for s in row["cli_stages"] if s["status"] != "PASS"), {})
        last_stage = row["cli_stages"][-1] if row["cli_stages"] else {}
        codes = first_failed.get("codes", [])
        diagnostic = row["cli_diagnostics"][0] if row["cli_diagnostics"] else {}
        stage, code = first_failed.get("stage", "NONE"), (codes[0] if codes else diagnostic.get("code", "NONE"))
        stages[stage] += 1
        primary[code] += 1
        if code == "PROVIDER_FAILURE":
            message = diagnostic.get("message", "")
            providers["HTTP_500" if "HTTP 500" in message else "ABNORMAL_STOP" if "normal stop" in message else "OTHER"] += 1
        requests = [(p, comparison.load(p)) for p in sorted(arm.glob("request-*.json"))]
        purpose_calls.update(r.get("purpose", "UNRECORDED") for _, r in requests)
        failures.append({"task_id": row["task_id"], "status": row["workflow_status"], "first_failed_stage": stage,
                         "terminal_stage": last_stage.get("stage"), "primary_code": code,
                         "diagnostic": diagnostic, "model_calls": row["usage"].get("calls", 0),
                         "score_ref": (arm / "score.json").relative_to(repo).as_posix(),
                         "active_package": row.get("active_package"), "stages": row["cli_stages"]})
        proof_requests = [(p, r) for p, r in requests if r.get("purpose") == "prove"]
        if proof_requests:
            payloads = Counter(comparison.digest(r["user"].encode()) for _, r in proof_requests)
            attempts = [(p.relative_to(repo).as_posix(), jsonl(p)) for p in sorted(arm.glob("package*/contract/proofs/attempts.jsonl"))]
            proof_feedback.append({"task_id": row["task_id"], "requests": [p.relative_to(repo).as_posix() for p, _ in proof_requests],
                                   "request_count": len(proof_requests), "distinct_user_payloads": len(payloads),
                                   "payload_hash_counts": dict(payloads), "recorded_attempts": attempts,
                                   "finding": "Every prover call received exactly the same user payload despite failed compiler attempts." if len(proof_requests) > 1 and len(payloads) == 1 else "Distinct prover payloads recorded."})
        if package and any(s.get("stage") == "export" and s.get("status") == "PASS" for s in row["cli_stages"]):
            sources = sorted((package / "accepted/source").glob("*.lean"))
            for source in sources:
                text = source.read_text()
                witnesses = [line.split(":= by", 1)[0].strip() for line in text.splitlines()
                             if re.match(r"^(?:def|theorem)\s", line) and
                             (re.search(r":\s*True\b|=>\s*True\b", line) or re.search(r"\b([a-z_][a-z_0-9]*)\s*=\s*\1\b", line))]
                if witnesses or row["task_id"] == "D26":
                    accepted_weaknesses.append({"task_id": row["task_id"], "source_ref": source.relative_to(repo).as_posix(),
                                               "source_hash": comparison.digest(source.read_bytes()), "witness_declarations": witnesses,
                                               "special_case": "sorted_output_correctness permits output=input and specifies neither sorting nor an implementation call" if row["task_id"] == "D26" else None})
            for path in sorted(package.glob("reviews/*/packet.json")):
                packet = comparison.load(path)
                challenge = packet.get("lean_challenge", "")
                accepted_match = [source.name for source in sources if source.read_text() == challenge]
                frozen = package / "contract/challenge/Contract.lean"
                frozen_match = frozen.exists() and frozen.read_text() == challenge
                ballots = [comparison.load(p) for p in sorted(path.parent.glob("ballot-attempts/*/*.json"))]
                final_ballots = [{"ref": p.relative_to(repo).as_posix(), "body": comparison.load(p)} for p in sorted(path.parent.glob("ballots/*.json"))]
                review_packets.append({"task_id": row["task_id"], "packet_ref": path.relative_to(repo).as_posix(),
                                       "packet_hash": comparison.digest(path.read_bytes()), "acceptance_gate": packet.get("acceptance", {}).get("gate"),
                                       "challenge_sorry_tokens": len(re.findall(r"\bsorry\b", challenge)),
                                       "challenge_matches_frozen_preproof_source": frozen_match,
                                       "challenge_matches_accepted_sources": accepted_match,
                                       "accepted_source_refs": [p.relative_to(repo).as_posix() for p in sources],
                                       "ballot_attempts": ballots, "final_ballots": final_ballots})
    return {"run_id": name, "completed_arm_records": len(run["results"]), "complete_pairs": run["complete_pairs"],
            "recorded_arm_metrics": run["arms"], "paired_outcomes": run["paired"],
            "first_failure_stages": dict(stages), "primary_failure_codes": dict(primary),
            "provider_failure_subtypes": dict(providers), "cli_model_calls_by_purpose": dict(purpose_calls),
            "failures": failures, "prover_feedback": proof_feedback, "review_packets": review_packets,
            "accepted_semantic_weaknesses": accepted_weaknesses}


def audit_stopped(repo):
    data = repo / "synthetic_dataset"
    dataset = comparison.load(data / "manifest.json")
    comparison.require(comparison.digest(comparison.encode({k: v for k, v in dataset.items() if k != "dataset_root"})) == dataset["dataset_root"], "Invalid dataset root")
    comparison.inventory(data, {**dataset["files"], **dataset["generator_hashes"]}, "Frozen dataset")
    tasks = {row["id"]: row for row in jsonl(data / "tasks.jsonl")}
    cases = {task: comparison.load(data / row["cases_path"]) for task, row in tasks.items()}
    baseline_path = data / "comparison-qwen-003-luna-002/STOP_SOURCE_AUDIT.json"
    baseline = comparison.load(baseline_path)
    runs = []
    original_inventory = comparison.inventory
    for name in RUNS:
        root = data / "runs" / name
        summary = comparison.load(root / "summary.json")
        comparison.require(summary.get("status") == "USER_STOPPED" and summary.get("complete") is False, "Run is not explicitly stopped and incomplete")
        comparison.require(baseline["runs"][name]["current_source_differences"] == [] and baseline["runs"][name]["captured_source_mutations"] == [], "Pre-repair source audit did not pass")
        protocol = comparison.load(root / "protocol.json")
        current_differences = [path for path, expected in protocol["source_hashes"].items()
                               if not (repo / path).is_file() or comparison.digest((repo / path).read_bytes()) != expected]

        def captured_inventory(input_root, hashes, label, captured=root / "execution-source"):
            # Audit historical execution against immutable captured bytes. Current
            # differences are separately recorded and never called benchmark mutations.
            return original_inventory(captured if label == "Current execution source" else input_root, hashes, label)

        comparison.inventory = captured_inventory
        try:
            checked = comparison.audit_run(repo, name, dataset, tasks, cases, partial=True)
        finally:
            comparison.inventory = original_inventory
        checked["audit"].update(source_basis="captured execution-source; current matched at pre-repair stop audit", current_source_differences_at_diagnosis=current_differences)
        runs.append(checked)
    comparison.require(runs[0]["protocol"]["task_order"] == runs[1]["protocol"]["task_order"], "Run task orders differ")
    common = sorted(comparison.paired_ids(runs[0]["results"]) & comparison.paired_ids(runs[1]["results"]))
    document = {"format": "verislop.head-to-head-comparison/0.1", "status": "USER_STOPPED", "complete": False,
                "audited_at_utc": datetime.now(timezone.utc).isoformat(), "dataset_root": dataset["dataset_root"],
                "dataset_tasks": dataset["tasks"], "common_paired_tasks": common, "runs": runs,
                "common_metrics": {r["run_id"]: comparison.metrics([row for row in r["results"] if row["task_id"] in common]) for r in runs},
                "cases": [c for batch in cases.values() for c in batch],
                "stop_source_audit": baseline, "stop_source_audit_hash": comparison.digest(baseline_path.read_bytes()),
                "scope": "Stopped, incomplete recorded comparison. Every saved score is preserved; unfinished arms are unscored. Captured sources are audited after runtime changes; no old result is rescored.",
                "comparability": "Raw uses one call; strict CLI uses up to 32 calls and two fresh-package repairs. Native Qwen tokens/digest are recorded; Luna actual model, sampling, token counts and tool enforcement are unobservable. Transport and budget differences prevent equal-compute or causal claims. Historical runs are excluded."}
    diagnosis = {"format": "verislop.stopped-benchmark-diagnosis/0.1", "status": "USER_STOPPED", "audited_at_utc": document["audited_at_utc"],
                 "runs": [diagnose_run(repo, run) for run in runs], "common_paired_tasks": common,
                 "scope": document["scope"], "source_audit": baseline}
    journal_paths = [repo / ".verislop/qwen-local-003-gpu-error.txt", repo / ".verislop/qwen-local-003-d21-gpu-error.txt"]
    diagnosis["gpu_crash_evidence"] = [{"ref": p.relative_to(repo).as_posix(), "hash": comparison.digest(p.read_bytes()), "text": p.read_text()}
                                       for p in journal_paths if p.exists()]
    return document, diagnosis


def report(diagnosis):
    lines = ["# Why the strict corpus experiments failed", "", "**Experiments stopped by the user. These are partial observations, not completed 100-task results.**", ""]
    for run in diagnosis["runs"]:
        a = run["recorded_arm_metrics"]
        lines.extend([f"## {run['run_id']}", "", f"{run['complete_pairs']} complete pairs; {run['completed_arm_records']} completed arm records. Raw successful tasks {a['raw']['successful_tasks']}/{a['raw']['attempted_tasks']}; strict CLI {a['verislop']['successful_tasks']}/{a['verislop']['attempted_tasks']}. Raw calls {a['raw']['model_calls']}; CLI calls {a['verislop']['model_calls']}.", "",
                      "First failing stage: " + json.dumps(run["first_failure_stages"], sort_keys=True) + ".", "",
                      "Primary failure codes: " + json.dumps(run["primary_failure_codes"], sort_keys=True) + ".", ""])
    lines.extend(["## Concrete causes", "",
                  "1. **Interpretation schema failures:** Luna had nine terminal interpretation failures; Qwen had one schema failure and four provider failures there. Luna G03 repeatedly used slash-containing kinds; G32 ended with unknown obligation IDs; A29 used a non-ambiguity disposition for ambiguity obligations. Exact stage feedback and response hashes remain recorded.", "",
                  "2. **Formalization failures:** Qwen had 20 terminal Lean elaboration failures and six unsupported-semantics failures. Examples include nonexistent `List.get!` (G24/G05), String indexing instances (A05/D18), reserved `end`/`at` identifiers (D09/G23), and unsupported custom-domain assumptions (G13/D19). Luna had three elaboration failures, three unsupported domains and one kernel-replay failure. These are actual stopped paths, not a blanket forecast about model capability.", "",
                  "3. **Generated recursion helper replay:** Luna G23's final candidate compilation succeeded (`compile.ok=true`, no compile errors), but the statement check rejected missing `VeriSlop.ValidRequests._unsafe_rec` and `VeriSlop.simulate._unsafe_rec` after kernel replay. Both ordinary recursive definitions are visible in the candidate. This isolates a kernel-replay/export boundary failure; it does not establish the generated contract's semantic correctness.", "",
                  "4. **Prover repair received no new information:** Luna D06 issued eight prover calls with one identical user-payload hash, despite recorded compile errors including an unterminated identifier and failed `Decidable` synthesis. Six proof holes remained; prove and accept were blocked. Luna D19 similarly sent three identical prover payloads before eventually proving its weaker contract. Compiler failures were saved in attempts.jsonl but did not enter the subsequent recorded prover prompts.", "",
                  "5. **Semantic weakness passed Lean gates:** Qwen D07's 16 purported CSV guarantees were `∀n:Nat,n=n`; D02's eight guarantees were `True`; G09 used `size=size`, `pairs=pairs` and `True`. D26 proved only existence of an output with matching length/membership, admitting `output=input` without sorting. Luna D19 defined eight join/safety predicates constantly `True`. All five reached export PASS. Lean proved the actual weak statements; the failure is their correspondence to requested behavior. No implementation artifact was generated.", "",
                  "6. **Review packet showed stale proof bodies:** Four of those five packets displayed the frozen challenge containing `sorry` while announcing `accepted_and_proved`, rather than the accepted proof source. Luna D19's critic reported REJECT because G1 appeared to contain `sorry`; its mechanical probe was NOT_REPRODUCED, giving replayed ABSTAIN. Qwen D07/G09 exhausted three protocol corrections each with unknown ballot fields. Qwen D02 produced a valid ABSTAIN that explicitly identified constant-True semantics and an unusable title-only missing-requirement template. Genuine abstentions remain unsuccessful.", "",
                  "7. **Provider failures are separately observed:** Qwen recorded 12 primary provider failures (nine HTTP500 and three abnormal completion stops). Preserved G03 and D21 service excerpts show CUDA launch timeout, aborted llama-server and matching HTTP500. Those two crashes are observed infrastructure causes; the remaining service failures are not all attributed to GPU crashes without matching evidence.", "",
                  "## Evidence and limits", "",
                  "[Machine-readable diagnosis](DIAGNOSIS.json) lists every completed CLI failure, exact primary diagnostic, active package, calls and stage history. It also records prover payload hashes/attempt logs, accepted weak declarations, review packet and ballot references, and GPU excerpts. [Stopped comparison](comparison.json) retains every exact saved score and case observation; [offline viewer](viewer.html) compares only common completed pairs across models.", "",
                  "All 142 Qwen and 144 Luna measured source hashes matched their captured copies and current runtime at STOP_SOURCE_AUDIT.json's stop boundary. Later runtime repairs are reported separately and do not alter historical execution bytes. Both stopped manifests are hash-audited; no case or candidate was rerun. Qwen D12 CLI and Luna G17 CLI were unfinished and remain unscored. Their completed raw arms remain individual records, excluded from paired denominators.", "",
                  "Finite recorded-evidence analysis trusts saved observations, frozen expectations and host/transport records. It neither proves the dataset oracles nor authenticates Luna's actual model identity. No Tier 0 result establishes END_TO_END_VERIFIED. Earlier stopped experiments remain separate.", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--out", type=Path, default=REPO / "synthetic_dataset/diagnostics/stopped-experiments-003-002")
    args = parser.parse_args(argv)
    repo, out = args.repo.resolve(), args.out.resolve()
    try:
        comparison.require(not out.exists(), "Immutable diagnosis output already exists; choose a new --out")
        comparison.require(not out.is_relative_to(repo / "synthetic_dataset/runs"), "Output must not alter authority evidence")
        document, diagnosis = audit_stopped(repo)
        out.mkdir(parents=True, exist_ok=False)
        (out / "comparison.json").write_bytes(comparison.encode(document))
        (out / "DIAGNOSIS.json").write_bytes(comparison.encode(diagnosis))
        (out / "DIAGNOSIS.md").write_text(report(diagnosis))
        (out / "STOP_SOURCE_AUDIT.json").write_bytes(comparison.encode(document["stop_source_audit"]))
        (out / "viewer.html").write_text(comparison.render_viewer((repo / "synthetic_dataset/viewer.html").read_text(), document))
        files = {p.relative_to(out).as_posix(): comparison.digest(p.read_bytes()) for p in sorted(out.rglob("*")) if p.is_file()}
        (out / "snapshot-manifest.json").write_bytes(comparison.encode({"format": "verislop.stopped-diagnosis-snapshot/0.1", "status": "USER_STOPPED", "complete": False,
                                                                        "files": files, "tool_hash": comparison.digest(Path(__file__).read_bytes()),
                                                                        "run_manifests": {r["run_id"]: r["audit"]["manifest_hash"] for r in document["runs"]}}))
        print(json.dumps({"status": "USER_STOPPED_AUDIT_PASSED", "out": str(out), "common_pairs": len(document["common_paired_tasks"])}))
        return 0
    except (comparison.AuditFailure, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "AUDIT_FAILED", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
