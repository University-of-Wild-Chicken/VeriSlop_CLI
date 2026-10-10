"""Fresh actual-Lean DEVELOPMENT_ONLY private-name/binding regressions."""
from pathlib import Path
import copy
import importlib.util
import json
import shutil
import sys
from unittest.mock import patch

WORK = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("revision002_harness", WORK / "test_candidate_019.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
from verislop import contract_refutation as baseline


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


previous = load("verislop.contract_refutation_candidate001_regression_control",
                WORK.parent / "tier2-refutation-equality-support-019-implementation/contract_refutation_candidate.py")
mutant = load("verislop.contract_refutation_revision002_fixture_only_guard_mutant", WORK / "fixture_only_analysis_guard_mutant.py")
EQ_BODY = """fun a b => by
  cases a <;> cases b
  · exact isTrue rfl
  · exact isFalse (by intro equality; cases equality)
  · exact isFalse (by intro equality; cases equality)
  · exact isTrue rfl
"""


def source_for(variant):
    source = "import Std\nnamespace PrivateEqualityRevision019\n"
    source += "inductive Palette where | ochre | teal\n"
    if variant != "absent":
        source += "private def hiddenEquality : DecidableEq Palette := " + EQ_BODY
    source += """def swap (color : Palette) : Palette :=
  match color with | .ochre => .teal | .teal => .ochre
theorem wrongSwap (color : Palette) : swap color = color := by sorry
theorem rightSwap (color : Palette) : swap (swap color) = color := by
  cases color <;> rfl
end PrivateEqualityRevision019
"""
    if variant == "private-public":
        source += "def zzUsableEquality : DecidableEq PrivateEqualityRevision019.Palette := " + EQ_BODY
    return source.encode()


INPUT = {"str": "ochre"}
PROPOSALS = [{"obligation_id": "O1", "inputs": [INPUT]}]
BINDING_DIAGNOSTIC = [{"message": "source/form/records do not match the supplied kernel-derived analysis"}]


class Fresh(h.Harness):
    def prepare(self, variant, theorem="wrongSwap"):
        key = (variant, theorem)
        if key in self.cache:
            return self.cache[key]
        source = source_for(variant)
        form = {"schema_version": "0.1", "artifact_kind": "formalization_candidate", "profile_id": "private019.revision002",
                "lean_toolchain": self.tc.pin, "lean_file": "Contract.lean", "internal_obligations": [],
                "bindings": [{"obligation": "D1", "declarations": ["PrivateEqualityRevision019.Palette", "PrivateEqualityRevision019.swap"]},
                             {"obligation": "O1", "theorem": "PrivateEqualityRevision019." + theorem}]}
        base, _, problems = h.contract.compose_challenge(source, h.contract.registry_lean(h.records(), h.contract.binding_names(form)))
        assert not problems
        comp = h.leanbridge.compile_module(self.tc, base, self.directory / (variant + "-" + theorem),
                    timeout=self.pol["build_timeout_seconds"], memory_mb=self.pol["memory_mb"],
                    require_network_isolation=self.pol["require_network_isolation"], require_filesystem_isolation=self.pol["require_filesystem_isolation"])
        assert comp.ok, comp.errors
        exported = h.leanbridge.run_kernel_tool(self.tc, comp.olean, {"export": True, "axioms": True}, **h.cr._kernel_options(self.pol))
        env = h.contract.Env.from_export(exported, self.pol, "fresh private equality revision002")
        assert not env.diagnostics
        analysis = h.contract.analyze(env, h.records(), form, self.pol, self.tc.pin, "fresh private equality revision002")
        assert not analysis.diagnostics
        profile = h.dsl.Profile.from_json(analysis.profile)
        equality_names = sorted(n for n, row in env.decls.items() if row.get("type") == h.app(h.const("DecidableEq", [1]), h.const("PrivateEqualityRevision019.Palette")))
        observations = []
        for name in equality_names:
            audited_hash = h.reify._enum_equality_declaration(name, "PrivateEqualityRevision019.Palette", env.decls, env.hashes)
            try:
                reference = h.cr._qualified(name)
                printable = True
            except ValueError:
                reference, printable = None, False
            observations.append({"name": name, "actual_type": env.decls[name]["type"], "audited_hash": audited_hash,
                                 "printable": printable, "reference": reference})
        if variant != "absent":
            assert any(n.startswith("_private.") for n in equality_names), equality_names
            assert any(not row["printable"] and row["audited_hash"] == env.hashes[row["name"]] for row in observations)
        if variant == "private-public":
            assert equality_names[0].startswith("_private.") and equality_names[-1] == "zzUsableEquality", equality_names
        target = self.output / "fixtures" / variant
        target.mkdir(parents=True)
        (target / "Source.lean").write_bytes(source)
        (target / "Base.lean").write_bytes(base)
        h.save(target / "formalization.json", form)
        h.save(target / "analysis.json", analysis)
        h.save(target / "kernel.json", exported)
        h.save(target / "equality-name-observations.json", observations)
        result = (source, form, base, env, analysis, profile)
        self.cache[key] = result
        return result

    def run_check(self, label, variant="private", module=None, analysis=None, source=None):
        module = h.cr if module is None else module
        original_source, form, base, env, original_analysis, profile = self.prepare(variant)
        supplied_source = original_source if source is None else source
        supplied_analysis = original_analysis if analysis is None else analysis
        pkg = h.Package(self.output / "packages" / label)
        pkg.ensure()
        result = module.check(pkg, supplied_source, form, h.records(), supplied_analysis, proposals=PROPOSALS)
        h.save(self.output / "reports" / (label + ".json"), result)
        for receipt in result["receipts"]:
            assert receipt["refutation_sorry_dependencies"] == 0 and receipt["axioms"] == []
            assert receipt["kernel_defeq"] == {"ok": True, "typechecks": True, "defeq": True}
            assert receipt["binding"]["candidate_source_hash"] == h.canonical.digest(supplied_source)
            assert receipt["binding"]["formalization_hash"] == h.canonical.digest_json(form)
            assert receipt["binding"]["records_hash"] == h.canonical.digest_json(h.records())
            assert receipt["binding"]["analysis_hash"] == h.canonical.digest_json(module._analysis_identity(supplied_analysis))
            assert receipt["binding"]["proposals_hash"] == h.canonical.digest_json(PROPOSALS)
            for artifact in receipt["artifacts"].values():
                assert h.canonical.digest_file(pkg.root / artifact["path"]) == artifact["sha256"]
            exported = json.loads((pkg.root / receipt["artifacts"]["kernel_export"]["path"]).read_text())
            proof_env = h.contract.Env.from_export(exported, self.pol, "fresh revision002 receipt check")
            assert not proof_env.diagnostics
            assert all(proof_env.hashes.get(name) == digest for name, digest in env.hashes.items())
            assert module._clean_root(proof_env, receipt["lean_symbol"], self.pol)[0]
            assert h.decl_hash(proof_env.decls[receipt["lean_symbol"]]) == receipt["declaration_hash"]
            assert receipt["kernel_proof_hash"] == h.canonical.digest_json({
                "module": receipt["artifacts"]["compiled_module"]["sha256"], "declaration": receipt["declaration_hash"],
                "proposition": receipt["proposition_hash"], "kernel_export": receipt["artifacts"]["kernel_export"]["sha256"],
                "kernel_tool": receipt["kernel_tool_hash"], "toolchain": receipt["toolchain"]})
            stripped = dict(receipt); del stripped["receipt_hash"]
            assert h.canonical.digest_json(stripped) == receipt["receipt_hash"]
            dependencies = h.closure({receipt["lean_symbol"]}, proof_env.decls)
            assert not any(n.startswith("_private.") and n.endswith(".hiddenEquality") for n in dependencies)
        return result, pkg, env


def require_binding_rejection(result):
    h.assert_status(result, "UNKNOWN")
    assert result["diagnostics"] == BINDING_DIAGNOSTIC, result
    assert result["bounded_scan"]["proof_attempts"] == 0, result


def main():
    run = WORK / "runs/run001-private-and-binding-development"
    run.mkdir(parents=True, exist_ok=False)
    for path in (Path(__file__), WORK / "contract_refutation_candidate.py", WORK / "fixture_only_analysis_guard_mutant.py", WORK / "test_candidate_019.py"):
        shutil.copyfile(path, run / path.name)
    h.save(run / "source-freeze-at-start.json", {p.name: h.canonical.digest_file(p) for p in run.iterdir() if p.is_file()})
    evidence = h.Evidence(run)
    fresh = Fresh(run, evidence)
    with patch.object(h.sandbox, "run", side_effect=evidence.run), patch.object(h.leanbridge, "compile_module", side_effect=evidence.compile), patch.object(h.leanbridge, "run_kernel_tool", side_effect=evidence.kernel):
        def baseline_case():
            result, _, _ = fresh.run_check("baseline-private-only-refutes", module=baseline)
            h.assert_status(result, "REFUTED", "REFUTED")
        fresh.test("baseline-private-only-refutes", baseline_case)

        def previous_case():
            result, _, _ = fresh.run_check("previous-candidate-private-only-availability-regression", module=previous)
            h.assert_status(result, "UNKNOWN")
            assert result["bounded_scan"]["proof_attempts"] == 1, result
            assert any(d.get("reason") == "unsupported Lean name component" for d in result["diagnostics"]), result
        fresh.test("previous-candidate-private-only-availability-regression", previous_case)

        def revised_case(variant, label, expect_alias):
            result, pkg, _ = fresh.run_check(label, variant)
            h.assert_status(result, "REFUTED", "REFUTED")
            for receipt in result["receipts"]:
                source = (pkg.root / receipt["artifacts"]["source"]["path"]).read_text()
                tail = source.split("\nnamespace VeriSlopRefutation_", 1)[1]
                derivation = "deriving instance _root_.DecidableEq for " + h.cr._qualified("PrivateEqualityRevision019.Palette")
                if expect_alias:
                    assert derivation not in tail and " := " + h.cr._qualified("zzUsableEquality") in tail, tail
                else:
                    assert derivation in tail and "local instance" not in tail, tail
        fresh.test("revised-private-only-safe-fallback", lambda: revised_case("private", "revised-private-only-safe-fallback", False))
        fresh.test("revised-private-plus-public-reuse", lambda: revised_case("private-public", "revised-private-plus-public-reuse", True))
        fresh.test("revised-no-equality-safe-fallback", lambda: revised_case("absent", "revised-no-equality-safe-fallback", False))

        def false_closed():
            _, _, base, env, analysis, profile = fresh.prepare("private")
            sort = {"enum": "Palette"}
            value = h.dsl.enum_v("Palette", "ochre")
            call = lambda term: {"tag": "call", "symbol": "swap", "args": [term]}
            formula = {"tag": "forall", "sort": sort, "body": {"tag": "eq", "left": call(call({"tag": "var", "index": 0})), "right": {"tag": "var", "index": 0}}}
            expr = h.app(h.const("Not"), h.cr._closed_formula(formula, [value], [sort], profile))
            pkg = h.Package(run / "packages/false-closed"); pkg.ensure()
            result = h.cr._proof(pkg, base, expr, {"fixture": "false closed proposition"}, profile, fresh.tc, fresh.pol, env)
            h.save(run / "reports/false-closed-proof-stays-rejected.json", result)
            assert not result["ok"] and result["reason"] == "closed proof did not elaborate", result
        fresh.test("false-closed-proof-stays-rejected", false_closed)

        fresh.test("matching-analysis-falsifiable-guarantee", lambda: h.assert_status(fresh.run_check("matching-analysis-falsifiable-guarantee")[0], "REFUTED", "REFUTED"))
        _, _, _, _, analysis, _ = fresh.prepare("private")
        mismatched = copy.deepcopy(analysis)
        mismatched.statements["O1"]["formula_package"]["formula"] = {"tag": "true"}
        fresh.test("mismatched-semantic-analysis-exact-rejection", lambda: require_binding_rejection(fresh.run_check("mismatched-semantic-analysis-exact-rejection", analysis=mismatched)[0]))

        def mutant_case():
            result, _, _ = fresh.run_check("analysis-guard-mutant-discrimination", module=mutant, analysis=mismatched)
            h.assert_status(result, "REFUTED", "REFUTED")
            assert result["bounded_scan"]["proof_attempts"] > 0
            h.save(run / "counterfactual-guard-discrimination.json", {"status": "FIXTURE_ONLY_MUTANT_NOT_INSTALLABLE_NOT_AUTHORITY",
                "candidate_result": "UNKNOWN exact binding diagnostic, zero proof attempts/receipts",
                "mutant_result": "REFUTED genuine concrete closed proof despite mismatched supplied Analysis",
                "guard_removal_changes_outcome": True, "mutant_source_sha256": h.canonical.digest_file(WORK / "fixture_only_analysis_guard_mutant.py")})
        fresh.test("analysis-guard-mutant-discrimination", mutant_case)

        def comment_case():
            source = fresh.prepare("private")[0]
            commented = source.replace(b"import Std\n", b"import Std\n-- semantically equivalent fresh comment\n", 1)
            result, _, _ = fresh.run_check("comment-only-source-semantic-equivalence", source=commented)
            h.assert_status(result, "REFUTED", "REFUTED")
            assert result["candidate_source_hash"] == h.canonical.digest(commented)
            assert result["candidate_source_hash"] != h.canonical.digest(source)
        fresh.test("comment-only-source-semantic-equivalence", comment_case)

        def source_semantics_case():
            source = fresh.prepare("private")[0]
            changed = source.replace(b"match color with | .ochre => .teal | .teal => .ochre", b"match color with | .ochre => .ochre | .teal => .teal", 1)
            assert changed != source
            require_binding_rejection(fresh.run_check("changed-source-semantics-exact-binding-rejection", source=changed)[0])
        fresh.test("changed-source-semantics-exact-binding-rejection", source_semantics_case)
    result = {"status": "DEVELOPMENT_ONLY_RELEVANT_REGRESSIONS", "qualification_authority": False, "root003_reusable": False,
              "original44_current_root_status": "RERUN_REQUIRED", "cases": fresh.results,
              "passed": sum(c["status"] == "PASS" for c in fresh.results), "failed": sum(c["status"] == "FAIL" for c in fresh.results),
              "actual_processes": len(evidence.processes), "actual_compiler_calls": len(evidence.compiles), "actual_kernel_calls": len(evidence.kernels),
              "process_returncodes": {str(k): sum(p["result"]["returncode"] == k for p in evidence.processes) for k in sorted({p["result"]["returncode"] for p in evidence.processes})},
              "timed_out_processes": sum(p["result"]["timed_out"] for p in evidence.processes),
              "actual_wall_seconds": sum(p["result"]["wall_seconds"] for p in evidence.processes),
              "models_called": 0, "native_task_artifact_contents_read": 0, "baseline_sha256": h.canonical.digest_file(h.ROOT / "verislop/contract_refutation.py"),
              "candidate_sha256": h.canonical.digest_file(WORK / "contract_refutation_candidate.py")}
    h.save(run / "results.json", result)
    fresh.tmp.cleanup()
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}), flush=True)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
