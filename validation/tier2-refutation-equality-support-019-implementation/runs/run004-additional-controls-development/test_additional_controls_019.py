"""Supplementary fresh actual-Lean DEVELOPMENT_ONLY admission/wire controls."""
from pathlib import Path
import copy
import importlib.util
import json
import shutil
from unittest.mock import patch

WORK = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fresh_equality019_harness", WORK / "test_candidate_019.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def main():
    run = WORK / "runs/run004-additional-controls-development"
    run.mkdir(parents=True, exist_ok=False)
    for path in (Path(__file__), WORK / "test_candidate_019.py", WORK / "contract_refutation_candidate.py"):
        shutil.copyfile(path, run / path.name)
    h.save(run / "source-freeze-at-start.json", {p.name: h.canonical.digest_file(p) for p in run.iterdir() if p.is_file()})
    evidence = h.Evidence(run)
    harness = h.Harness(run, evidence)
    with patch.object(h.sandbox, "run", side_effect=evidence.run), patch.object(h.leanbridge, "compile_module", side_effect=evidence.compile), patch.object(h.leanbridge, "run_kernel_tool", side_effect=evidence.kernel):
        def unsupported():
            source = b'''import Std
namespace AdmissionEquality019
structure Indexed where
  amount : Nat
  index : Fin amount
inductive Recursive where
  | base
  | step (previous : Recursive)
theorem reflexive (x : Indexed) : x = x := by rfl
end AdmissionEquality019
'''
            form = {"schema_version": "0.1", "artifact_kind": "formalization_candidate", "profile_id": "equality019.unsupported",
                    "lean_toolchain": harness.tc.pin, "lean_file": "Contract.lean", "internal_obligations": [],
                    "bindings": [{"obligation": "D1", "declarations": ["AdmissionEquality019.Indexed", "AdmissionEquality019.Recursive"]},
                                 {"obligation": "O1", "theorem": "AdmissionEquality019.reflexive"}]}
            base, _, problems = h.contract.compose_challenge(source, h.contract.registry_lean(h.records(), h.contract.binding_names(form)))
            assert not problems
            comp = h.leanbridge.compile_module(harness.tc, base, harness.directory / "unsupported", timeout=harness.pol["build_timeout_seconds"], memory_mb=harness.pol["memory_mb"],
                    require_network_isolation=harness.pol["require_network_isolation"], require_filesystem_isolation=harness.pol["require_filesystem_isolation"])
            assert comp.ok, comp.errors
            exported = h.leanbridge.run_kernel_tool(harness.tc, comp.olean, {"export": True, "axioms": True}, **h.cr._kernel_options(harness.pol))
            env = h.contract.Env.from_export(exported, harness.pol, "fresh unsupported admission control")
            assert not env.diagnostics
            profile, notes = h.reify.derive_profile("unsupported019", env.decls, env.hashes, {"AdmissionEquality019.Indexed", "AdmissionEquality019.Recursive"})
            assert not profile["records"] and not profile["enums"], (profile, notes)
            analysis = h.contract.analyze(env, h.records(), form, harness.pol, harness.tc.pin, "fresh unsupported admission control")
            pkg = h.Package(run / "packages/unsupported"); pkg.ensure()
            result = h.cr.check(pkg, source, form, h.records(), analysis)
            h.assert_status(result, "UNKNOWN")
            (run / "Unsupported.lean").write_bytes(source)
            h.save(run / "unsupported-profile.json", {"profile": profile, "notes": notes, "analysis": analysis, "result": result})
        harness.test("dependent-and-recursive-carriers-not-admitted", unsupported)

        def record_wires():
            bad = copy.deepcopy(h.PARCEL_WIRE)
            del bad["dict"]["leaf"]
            extra = copy.deepcopy(h.PARCEL_WIRE)
            extra["dict"]["unregistered"] = {"int": "0"}
            wrong = copy.deepcopy(h.PARCEL_WIRE)
            wrong["dict"]["leaf"]["dict"]["token"] = {"str": "unadmitted"}
            proposals = [{"obligation_id": "O1", "inputs": [value]} for value in (bad, extra, wrong)]
            result = harness.check("malformed-record-wires", "structured", "rightParcel", proposals)
            h.assert_status(result, "UNKNOWN")
            assert sum(row.get("kind") == "INVALID_PROPOSAL" for row in result["diagnostics"]) == 3, result
        harness.test("malformed-record-wires", record_wires)

        def root_collision():
            _, _, base, env, _, profile = harness.prepare("all", "wrongToken")
            expr = h.app(h.const("Not"), h.const("False"))
            binding = {"fresh": "root collision"}
            ns = "VeriSlopRefutation_" + h.canonical.digest_json({"binding": binding, "proposition": expr}).split(":")[1][:24]
            modified = copy.deepcopy(env)
            modified.decls[ns + ".closed_check"] = {"name": [ns, "closed_check"]}
            before = len(evidence.processes)
            pkg = h.Package(run / "packages/root-collision"); pkg.ensure()
            result = h.cr._proof(pkg, base, expr, binding, profile, harness.tc, harness.pol, modified)
            assert result == {"ok": False, "reason": "generated proof name already exists"}, result
            assert len(evidence.processes) == before
            h.save(run / "root-collision-synthetic-env.json", result)
        harness.test("existing-root-name-collision-synthetic-env", root_collision)

        def stale_closure_hash():
            _, _, base, env, _, profile = harness.prepare("all", "wrongToken")
            modified = copy.deepcopy(env)
            carrier = "RefutationEquality019.Token"
            equality = next(n for n, row in modified.decls.items() if row.get("type") == h.app(h.const("DecidableEq", [1]), h.const(carrier)))
            modified.hashes[equality] = h.canonical.digest(b"stale semantic identity")
            prelude = h.cr._derivations(profile, modified, namespace="FreshHashNegative019")
            assert "deriving instance _root_.DecidableEq for " + h.cr._qualified(carrier) in prelude
            assert ":= " + h.cr._qualified(equality) not in prelude
            pkg = h.Package(run / "packages/stale-equality-env"); pkg.ensure()
            result = h.cr._proof(pkg, base, h.app(h.const("Not"), h.const("False")), {"fresh": "stale equality Env"}, profile, harness.tc, harness.pol, modified)
            assert not result["ok"], result
            h.save(run / "stale-equality-env-synthetic-boundary.json", {"prelude": prelude, "result": result})
        harness.test("stale-equality-closure-hash-synthetic-env", stale_closure_hash)
    result = {"status": "DEVELOPMENT_ONLY", "root003_reusable": False, "qualification_authority": False,
              "cases": harness.results, "passed": sum(r["status"] == "PASS" for r in harness.results),
              "failed": sum(r["status"] == "FAIL" for r in harness.results), "actual_processes": len(evidence.processes),
              "actual_compiler_calls": len(evidence.compiles), "actual_kernel_calls": len(evidence.kernels),
              "timed_out_processes": sum(p["result"]["timed_out"] for p in evidence.processes),
              "actual_wall_seconds": sum(p["result"]["wall_seconds"] for p in evidence.processes),
              "models_called": 0, "native_tasks_read": 0}
    h.save(run / "results.json", result)
    harness.tmp.cleanup()
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}), flush=True)
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
