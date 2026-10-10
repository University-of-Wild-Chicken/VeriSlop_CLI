"""Universal map/filter/sum bridge fixture, unrelated to retained task instances."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from verislop import canonical, leanbridge, policy
from verislop.bridges import vscore3_checker as checker
from verislop.targets import vscore3_target as target, vscore3_source as source


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = b'''import Std
namespace PrimitiveFixture
def shifted (offset : Int) (xs : List Int) : List Int := xs.map (fun x => x + offset)
def selected (limit : Int) (xs : List Int) : List Int := xs.filter (fun x => decide (x < limit))
def total (limit : Int) (xs : List Int) : Int :=
  ((xs.filter (fun x => decide (x < limit))).map (fun x => x + limit)).sum
theorem shifted_contract : forall offset xs, shifted offset xs = xs.map (fun x => x + offset) := by intros; rfl
theorem selected_contract : forall limit xs, selected limit xs = xs.filter (fun x => decide (x < limit)) := by intros; rfl
theorem total_contract : forall limit xs, total limit xs =
  ((xs.filter (fun x => decide (x < limit))).map (fun x => x + limit)).sum := by intros; rfl
end PrimitiveFixture
'''

PROOF = '''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  · intro offset xs
    with_unfolding_all
      change ((xs.map (fun x : Int => x)).map (fun x => x + offset)).map (fun x => x) = xs.map (fun x => x + offset)
    simp
  · intro limit xs
    with_unfolding_all
      change ((xs.map (fun x : Int => x)).filter (fun x => decide (x < limit))).map (fun x => x) = xs.filter (fun x => decide (x < limit))
    simp
  · intro limit xs
    with_unfolding_all
      change (((xs.map (fun x : Int => x)).filter (fun x => decide (x < limit))).map (fun x => x + limit)).sum =
        ((xs.filter (fun x => decide (x < limit))).map (fun x => x + limit)).sum
    simp
end VeriSlopBridgeProof
'''.encode()


def program():
    v = lambda i: {"tag": "var", "index": i}
    mapper = {"tag": "add", "left": v(0), "right": v(2)}
    predicate = {"tag": "lt", "left": v(0), "right": v(2)}
    filtered = {"tag": "list_filter", "value": v(0), "body": predicate}
    return {"language": source.LANGUAGE, "profile": source.PROFILE,
            "declarations": [], "helpers": [], "entries": [
                {"id": "shifted", "params": ["int", {"list": "int"}], "result": {"list": "int"},
                 "body": {"tag": "list_map", "value": v(0), "body": mapper}},
                {"id": "selected", "params": ["int", {"list": "int"}], "result": {"list": "int"}, "body": filtered},
                {"id": "total", "params": ["int", {"list": "int"}], "result": "int", "body": {
                    "tag": "list_sum", "value": {"tag": "list_map", "value": filtered, "body": mapper}}}]}


def profile():
    return {"profile_id": "primitive-fixture", "dsl": "verislop.contract-dsl/0.2",
            "enums": {}, "records": {}, "predicates": {}, "symbols": {
                n: {"lean_decl": "PrimitiveFixture." + n, "args": ["Int", {"list": "Int"}],
                    "result": "Int" if n == "total" else {"list": "Int"}}
                for n in ("shifted", "selected", "total")}}


def relation():
    return {"schema_version": "0.3", "format": target.RELATION_FORMAT, "template": target.TEMPLATE,
            "source_slot": "vscore-source", "proof_slot": "vscore-proof", "bindings": [
                {"symbol": n, "entry": n} for n in ("shifted", "selected", "total")]}


def obligations():
    v = lambda i: {"tag": "var", "index": i}
    mapper = {"tag": "list_map", "value": v(0), "function": {"sort": "Int", "body": {
        "tag": "int_add", "left": v(0), "right": v(2)}}}
    filtered = {"tag": "list_filter", "value": v(0), "function": {"sort": "Int", "body": {
        "tag": "decide", "formula": {"tag": "lt", "left": v(0), "right": v(2)}}}}
    mapped_filter = copy.deepcopy(mapper)
    mapped_filter["value"] = filtered
    terms = {"shifted": mapper, "selected": filtered, "total": {"tag": "list_sum", "value": mapped_filter}}
    return {"O" + str(i): {"formula": {"tag": "forall", "sort": "Int", "body": {
        "tag": "forall", "sort": {"list": "Int"}, "body": {"tag": "eq", "left": {
            "tag": "call", "symbol": n, "args": [v(1), v(0)]}, "right": terms[n]}}},
        "lean_symbol": "PrimitiveFixture." + n + "_contract", "statement_hash": "sha256:" + str(i) * 64}
        for i, n in enumerate(("shifted", "selected", "total"), 1)}


class PrimitiveBridgeTests(unittest.TestCase):
    def test_exact_primitive_refinement_two_clean_kernel_builds(self):
        tc = leanbridge.resolve_toolchain()
        data, registry, rel, obs = canonical.dumps(program()), profile(), relation(), obligations()
        spec = target.build_goal(data, rel, registry, obs)
        capture_root = ROOT / "validation/tier2-primitives-pass"
        capture_root.mkdir(parents=True, exist_ok=True)
        capture = Path(tempfile.mkdtemp(prefix="attempt-", dir=capture_root))
        for name, payload in {"program.vscore.json": data, "VeriSlopContract.lean": CONTRACT,
                              "VeriSlopBridgeGoal.lean": spec.text.encode(), "VeriSlopBridgeProof.lean": PROOF,
                              "profile.json": canonical.dumps(registry), "relation.json": canonical.dumps(rel),
                              "obligations.json": canonical.dumps(obs), "expected.json": canonical.dumps(spec.expected)}.items():
            (capture / name).write_bytes(payload)
        for module, payload in target.library_sources().items():
            path = capture / "library" / (module.replace(".", "/") + ".lean")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        try:
            with tempfile.TemporaryDirectory(prefix="verislop-primitive-contract-") as tmp:
                built = leanbridge.compile_module(tc, CONTRACT, Path(tmp))
                self.assertTrue(built.ok, built.errors)
                bundle = Path(built.olean).read_bytes()
                (capture / "contract.bundle").write_bytes(bundle)
                ctx = checker.EdgeContext("primitive-fixture", {}, "", "",
                    {"edge_id": "primitive-fixture", "expected_proposition_hash": None},
                    {"claim_id": "PRIMITIVE_FIXTURE"}, {}, rel,
                    {"source": ("vscore-source", data), "proof_source": ("vscore-proof", PROOF)}, {},
                    {"toolchain": {"pin": leanbridge.DEFAULT_TOOLCHAIN}}, registry, "sha256:" + "0" * 64,
                    bundle, policy.get("strict"), obs)
                builds = []
                for index in (1, 2):
                    result = checker.run_build(tc, ctx, spec)
                    builds.append(result)
                    out = capture / ("build-" + str(index))
                    out.mkdir()
                    for name, value in {"observation.json": result.observation, "ir.json": result.ir,
                                        "axioms.json": result.axioms, "declarations.json": result.decls}.items():
                        (out / name).write_bytes(canonical.dumps(value))
                    for module, parts in result.modules.items():
                        for suffix, payload in parts.items():
                            path = out / "modules" / (module.replace(".", "/") + suffix)
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_bytes(payload)
                self.assertEqual(builds[0].observation, builds[1].observation)
                self.assertEqual(canonical.dumps(builds[0].ir["program"]), data)
                self.assertNotIn("sorryAx", builds[0].axioms)
                (capture / "status.json").write_bytes(canonical.dumps({"status": "PASS", "builds": 2,
                    "source_hash": canonical.digest(data), "goal_hash": canonical.digest(spec.text.encode()),
                    "proof_hash": canonical.digest(PROOF), "proposition_hash": builds[0].proposition_hash}))
        except Exception as exc:
            (capture / "status.json").write_bytes(canonical.dumps({"status": "FAIL", "error": str(exc)}))
            raise


if __name__ == "__main__":
    unittest.main()
