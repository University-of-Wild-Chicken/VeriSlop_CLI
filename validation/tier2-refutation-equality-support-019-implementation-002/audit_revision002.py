"""Deterministic audit of frozen generic development evidence; no Lean execution."""
from pathlib import Path
import ast
import collections
import hashlib
import json
import sys

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[1]
sys.path.insert(0, str(ROOT))
from verislop import canonical


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


def function_text(source, name):
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return "\n".join(source.splitlines()[node.lineno - 1:node.end_lineno])


def main():
    checks = []

    def check(label, action):
        try:
            details = action()
            checks.append({"label": label, "status": "PASS", "details": details})
        except BaseException as exc:
            checks.append({"label": label, "status": "FAIL", "exception": repr(exc)})

    frozen = load(WORK / "AUDIT_INPUT_MANIFEST.json")
    def inputs():
        for row in frozen["files"]:
            path = Path(row["absolute_path"])
            assert digest(path) == row["sha256"], path
        return {"files_bound": len(frozen["files"]), "input_root_hash": digest(WORK / "AUDIT_INPUT_MANIFEST.json")}
    check("frozen-audit-input-identities", inputs)

    def exact_sources():
        old = (WORK.parent / "tier2-refutation-equality-support-019-implementation/contract_refutation_candidate.py").read_text()
        new = (WORK / "contract_refutation_candidate.py").read_text()
        needle = "        for equality_name in candidates:\n            try:\n                # This existing audit"
        replacement = ("        for equality_name in candidates:\n            try:\n"
            "                equality_reference = _qualified(equality_name)\n"
            "            except ValueError:\n"
            "                # Private kernel names can contain numeric components that the\n"
            "                # existing printer cannot express. Try other audited definitions.\n"
            "                continue\n            try:\n                # This existing audit")
        assert old.count(needle) == 1
        expected = old.replace(needle, replacement).replace(
            '+ _qualified(name) + " := " + _qualified(equality_name))',
            '+ _qualified(name) + " := " + equality_reference)')
        assert new == expected
        assert function_text(old, "_proof") == function_text(new, "_proof")
        marker = '    extra = (f"\\nnamespace {ns}\\n{derives}\\n"'
        production = (ROOT / "verislop/contract_refutation.py").read_text()
        assert new[new.index(marker):] == old[old.index(marker):] == production[production.index(marker):]
        guard = "_analysis_identity(fresh) != _analysis_identity(analysis)"
        assert new.count(guard) == 1
        assert (WORK / "fixture_only_analysis_guard_mutant.py").read_text() == new.replace(guard, "False")
        return {"changed_candidate_functions_from_001": ["_derivations"], "proof_function_unchanged_from_001": True,
                "final_theorem_acceptance_receipt_suffix_unchanged_from_production": True,
                "fixture_mutant_changes_only_analysis_identity_comparison": True}
    check("exact-minimal-source-boundary", exact_sources)

    def registered():
        pre = load(WORK / "PREIMPLEMENTATION_MANIFEST.json")
        for name, expected in pre["files"].items():
            assert digest(WORK / name) == expected
        assert digest(ROOT / "verislop/contract_refutation.py") == pre["production_source_sha256"]
        oldroot = WORK.parent / "tier2-refutation-equality-support-019-implementation"
        assert digest(oldroot / "manifest.json") == pre["prior_manifest_sha256"]
        required = load(WORK / "ORIGINAL_CONTROL_REQUIREMENTS.json")
        assert len(required["requirements"]) == 44
        assert len({r["label"] for r in required["requirements"]}) == 44
        assert all(r["revision002_status"] == "RERUN_REQUIRED" and not r["authority"] for r in required["requirements"])
        assert digest(oldroot / "contract_refutation_candidate.py") == required["prior_candidate_sha256"]
        assert digest(WORK / "SOURCE_REVIEW_001.md") == required["review_sha256"]
        assert digest(WORK.parent / "tier2-support019-equality-source-review-001/REVIEW.md") == required["review_sha256"]
        return {"original_requirements": 44, "original_requirements_authority": False, "all_current_root_status": "RERUN_REQUIRED",
                "registered_new_requirements": len(required["new_requirements"])}
    check("registered-boundaries-and-no-pass-promotion", registered)

    all_runs = []
    def run_evidence(run_name, grouped=False):
        run = WORK / "runs" / run_name
        results = load(run / "results.json")
        assert results["qualification_authority"] is False and results["root003_reusable"] is False
        assert results["failed"] == 0
        assert all(row["status"] == "PASS" for row in results["cases"])
        if grouped:
            assert [r["label"] for r in results["cases"]] == ["source-analysis-wire-binding-negatives"]
            snap = load(run / "source-freeze-at-start.json")
            assert snap["candidate_sha256"] == digest(WORK / "contract_refutation_candidate.py") == digest(run / "candidate_at_start.py")
            assert snap["test_sha256"] == digest(WORK / "test_candidate_019.py") == digest(run / "test_candidate_019_at_start.py")
        else:
            assert {r["label"] for r in results["cases"]} == set(load(WORK / "ORIGINAL_CONTROL_REQUIREMENTS.json")["new_requirements"])
            assert results["original44_current_root_status"] == "RERUN_REQUIRED"
            for name, expected in load(run / "source-freeze-at-start.json").items():
                assert digest(WORK / name) == expected == digest(run / name)
        env = load(run / "environment.json")
        assert env["policy"]["build_timeout_seconds"] == 300 == env["policy"]["kernel_timeout_seconds"]
        assert env["policy"]["memory_mb"] == 8192
        assert env["policy"]["require_kernel_replay"] is True
        assert env["toolchain"]["pin"] == "leanprover/lean4:v4.34.1"
        processes = sorted((run / "processes").iterdir())
        assert len(processes) == results["actual_processes"]
        kinds, codes, timeouts = collections.Counter(), collections.Counter(), 0
        for index, process in enumerate(processes, 1):
            assert not (process / "interrupted.json").exists()
            row, invocation = load(process / "process.json"), load(process / "invocation.json")
            assert row["id"] == index == invocation["id"]
            for key in ("id", "kind", "label", "requested_argv", "requested_options", "working_directory"):
                assert row[key] == invocation[key]
            options, returned = row["requested_options"], row["result"]
            assert options["timeout"] == 300 and options["cpu_seconds"] == 305
            assert options["require_network_isolation"] and options["require_filesystem_isolation"]
            assert "-M8192" in row["requested_argv"]
            assert returned["isolation"]["network_namespace"] and returned["isolation"]["filesystem_read_isolation"]
            assert returned["argv"][-len(row["requested_argv"]):] == row["requested_argv"]
            for stream in ("stdout", "stderr"):
                path = process / (stream + ".bin")
                assert digest(path) == returned[stream]["sha256"]
                assert path.stat().st_size == returned[stream]["bytes"]
            if row["kind"] == "kernel":
                assert options["memory_mb"] == 8192
                for name in ("request.json", "response.json", "VeriSlopKernel.lean"):
                    assert (process / name).is_file()
                assert (process / "stage").is_dir()
                assert digest(process / "VeriSlopKernel.lean") == env["kernel_tool_hash"]
            else:
                assert options["memory_mb"] == 24576
                assert (process / "VeriSlopContract.lean").is_file()
            kinds[row["kind"]] += 1
            codes[str(returned["returncode"])] += 1
            timeouts += returned["timed_out"]
        compiles = list((run / "compiles").glob("*.json"))
        kernels = list((run / "kernels").glob("*.json"))
        assert len(compiles) == kinds["compiler"] == results["actual_compiler_calls"]
        assert len(kernels) == kinds["kernel"] == results["actual_kernel_calls"]
        assert dict(codes) == results["process_returncodes"] and timeouts == results["timed_out_processes"] == 0
        for path in compiles:
            row = load(path)
            assert row["result"]["process_evidence"]
        for path in kernels:
            row = load(path)
            assert row["options"]["timeout"] == 300 and row["options"]["memory_mb"] == 8192
        summary = {"run": run_name, "passed": results["passed"], "failed": 0, "actual_processes": len(processes),
                   "compiler": kinds["compiler"], "kernel": kinds["kernel"], "timeouts": timeouts,
                   "process_returncodes": dict(codes), "actual_wall_seconds": results["actual_wall_seconds"]}
        all_runs.append(summary)
        return summary
    check("actual-private-binding-process-evidence", lambda: run_evidence("run001-private-and-binding-development"))
    check("actual-grouped-binding-process-evidence", lambda: run_evidence("run002-grouped-binding-development", True))

    def regressions():
        run = WORK / "runs/run001-private-and-binding-development"
        report = lambda label: load(run / "reports" / (label + ".json"))
        assert report("baseline-private-only-refutes")["status"] == "REFUTED"
        old = report("previous-candidate-private-only-availability-regression")
        assert old["status"] == "UNKNOWN" and not old["receipts"]
        assert any(row.get("reason") == "unsupported Lean name component" for row in old["diagnostics"])
        for label in ("revised-private-only-safe-fallback", "revised-private-plus-public-reuse",
                      "revised-no-equality-safe-fallback", "matching-analysis-falsifiable-guarantee"):
            assert report(label)["status"] == "REFUTED" and report(label)["receipts"]
        diagnostic = [{"message": "source/form/records do not match the supplied kernel-derived analysis"}]
        for label in ("mismatched-semantic-analysis-exact-rejection", "changed-source-semantics-exact-binding-rejection"):
            result = report(label)
            assert result["status"] == "UNKNOWN" and not result["receipts"]
            assert result["bounded_scan"]["proof_attempts"] == 0 and result["diagnostics"] == diagnostic
        assert report("analysis-guard-mutant-discrimination")["status"] == "REFUTED"
        assert load(run / "counterfactual-guard-discrimination.json")["guard_removal_changes_outcome"] is True
        commented = report("comment-only-source-semantic-equivalence")
        assert commented["status"] == "REFUTED"
        assert commented["candidate_source_hash"] != report("matching-analysis-falsifiable-guarantee")["candidate_source_hash"]
        count = 0
        for runname in ("run001-private-and-binding-development", "run002-grouped-binding-development"):
            current = WORK / "runs" / runname
            for path in (current / "reports").glob("*.json"):
                result = load(path)
                for receipt in result.get("receipts", []):
                    assert receipt["refutation_sorry_dependencies"] == 0 and receipt["axioms"] == []
                    assert receipt["kernel_defeq"] == {"ok": True, "typechecks": True, "defeq": True}
                    package = current / "packages" / path.stem
                    for artifact in receipt["artifacts"].values():
                        assert digest(package / artifact["path"]) == artifact["sha256"]
                    stripped = dict(receipt); del stripped["receipt_hash"]
                    assert canonical.digest_json(stripped) == receipt["receipt_hash"]
                    assert receipt["binding"]["candidate_source_hash"] == result["candidate_source_hash"]
                    count += 1
        return {"retained_actual_closed_proof_receipts": count, "exact_binding_negatives": 2,
                "guard_mutant_discriminates": True, "comment_source_semantic_equivalence_accepted": True}
    check("actual-regression-and-proof-receipt-bindings", regressions)

    failures = [row for row in checks if row["status"] != "PASS"]
    result = {"format": "verislop.equality-support019-revision002-development-evidence-audit/1",
        "closure_id": "support019-equality-revision002-development-audit", "status": "BLOCKED",
        "audit_checks": checks, "audit_checks_passed": len(checks) - len(failures), "audit_checks_failed": len(failures),
        "input_root_hash": digest(WORK / "AUDIT_INPUT_MANIFEST.json"), "verifier_hash": digest(Path(__file__)),
        "source_review_handoff_ready": not failures, "qualification_authority": False, "root003_reusable": False,
        "tested": all_runs, "proved": "Only exact retained closed Lean negations under recorded kernel/toolchain; no universal claim.",
        "checked": "Frozen source boundary, identities, process receipts, artifact bindings and registered requirements.",
        "trusted": ["Lean v4.34.1 kernel/compiler", "VeriSlop kernel exporter/parser", "Python/standard libraries/canonical JSON",
                    "SHA-256", "bubblewrap/resource-limit implementation", "OS/hardware"],
        "out_of_scope": ["production installation", "native task artifacts/answers/builds/probes/models", "all44 current-root qualification",
                         "whole-root build determinism", "general result equality support", "arbitrary future roots"],
        "claims": {"original44_required": 44, "original44_qualification_unresolved": 44, "new_relevant_tested_passed": 11},
        "builds": {"fresh_actual_compiler_processes": sum(r["compiler"] for r in all_runs), "whole_root_required": 2,
                   "whole_root_qualified": 0},
        "determinism": {"whole_root_required": True, "status": "NOT_RUN"},
        "blocking_reasons": [{"code": "VERIFIER_NOT_RUN", "surface": "all44 frozen current-root qualification"},
                             {"code": "VERIFIER_NOT_RUN", "surface": "whole-root two-build/determinism qualification"}]
                            + [{"code": "VERIFIER_FAILURE", "check": row["label"], "exception": row["exception"]} for row in failures],
        "infrastructure_errors": [], "manual_override_allowed": False}
    save(WORK / "DEVELOPMENT_AUDIT.json", result)
    print(json.dumps({"status": result["status"], "source_review_handoff_ready": result["source_review_handoff_ready"],
                      "audit_checks_passed": result["audit_checks_passed"], "audit_checks_failed": len(failures),
                      "actual_processes": sum(r["actual_processes"] for r in all_runs)}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
