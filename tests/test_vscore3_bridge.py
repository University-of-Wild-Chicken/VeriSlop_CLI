"""Independent Tier 2 fixtures; no retained benchmark answers or graders."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import TempDir
from verislop import canonical, leanbridge, policy
from verislop.bridges import vscore3_checker as checker
from verislop.exprjson import constants, name_str
from verislop.targets import vscore3_target as target, vscore3_source as source


CONTRACT = b'''import Std
namespace Fixture
structure Packet where
  amount : Int
  words : List String
  extra : Option Int
def shift (x : Int) : Int := x + (-3)
def solve (x : Packet) : Int := x.amount + (-3)
theorem value_contract : forall x : Packet, solve x = x.amount + (-3) := by intro x; rfl
theorem binder_contract : forall xs : List Int, xs.map (fun x => shift x) = xs.map (fun x => x + (-3)) := by intro xs; rfl
end Fixture
'''


def profile():
    return {"profile_id": "fixture-data", "dsl": "verislop.contract-dsl/0.2", "enums": {}, "predicates": {},
            "records": {"Packet": {"lean_decl": "Fixture.Packet", "lean_constructor": "Fixture.Packet.mk",
                "fields": [{"name": "amount", "lean_projection": "Fixture.Packet.amount", "sort": "Int"},
                           {"name": "words", "lean_projection": "Fixture.Packet.words", "sort": {"list": "String"}},
                           {"name": "extra", "lean_projection": "Fixture.Packet.extra", "sort": {"option": "Int"}}]}},
            "symbols": {"solve": {"lean_decl": "Fixture.solve", "args": [{"record": "Packet"}], "result": "Int"},
                        "shift": {"lean_decl": "Fixture.shift", "args": ["Int"], "result": "Int"}}}


def program():
    return {"language": source.LANGUAGE, "profile": source.PROFILE,
            "declarations": [{"tag": "record", "id": "Packet", "fields": [
                {"id": "amount", "type": "int"}, {"id": "words", "type": {"list": "string"}},
                {"id": "extra", "type": {"option": "int"}}]}], "helpers": [], "entries": [
                {"id": "shift", "params": ["int"], "result": "int", "body": {
                    "tag": "add", "left": {"tag": "var", "index": 0}, "right": {"tag": "int", "value": "-3"}}},
                {"id": "solve", "params": [{"record": "Packet"}], "result": "int", "body": {
                    "tag": "add", "left": {"tag": "project", "value": {"tag": "var", "index": 0}, "field": "amount"},
                    "right": {"tag": "int", "value": "-3"}}}]}


def relation():
    return {"schema_version": "0.3", "format": target.RELATION_FORMAT, "template": target.TEMPLATE,
            "source_slot": "vscore-source", "proof_slot": "vscore-proof",
            "bindings": [{"symbol": "shift", "entry": "shift"}, {"symbol": "solve", "entry": "solve"}]}


def obligations():
    v = {"tag": "var", "index": 0}
    arithmetic = {"tag": "int_add", "left": v, "right": {"tag": "int", "value": "-3"}}
    map_call = {"tag": "list_map", "value": v, "function": {"sort": "Int", "body": {"tag": "call", "symbol": "shift", "args": [v]}}}
    map_value = {"tag": "list_map", "value": v, "function": {"sort": "Int", "body": arithmetic}}
    value = {"tag": "forall", "sort": {"record": "Packet"}, "body": {"tag": "eq",
        "left": {"tag": "call", "symbol": "solve", "args": [v]}, "right": {
            "tag": "int_add", "left": {"tag": "field", "sort": "Packet", "field": "amount", "value": v},
            "right": {"tag": "int", "value": "-3"}}}}
    binder = {"tag": "forall", "sort": {"list": "Int"}, "body": {"tag": "eq", "left": map_call, "right": map_value}}
    return {"O1": {"formula": value, "lean_symbol": "Fixture.value_contract", "statement_hash": "sha256:" + "1" * 64},
            "O2": {"formula": binder, "lean_symbol": "Fixture.binder_contract", "statement_hash": "sha256:" + "2" * 64}}


PROOF = b'''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  all_goals intro x; with_unfolding_all rfl
end VeriSlopBridgeProof
'''


class BridgeDerivationTests(unittest.TestCase):
    def test_binder_calls_keep_local_scope(self):
        spec = target.build_goal(canonical.dumps(program()), relation(), profile(), obligations())
        names = constants(spec.expected["Transfer_O2"]["value"])
        self.assertIn("VeriSlopBridgeGoal.source_fn_shift", names)
        self.assertNotIn("Fixture.shift", names)
        self.assertIn("VSCore3.RawLaws", spec.text)
        self.assertIn("RawEval_shift", spec.text)
        self.assertIn("InputsCover_solve", spec.text)

    def test_wrong_nominal_layout_is_rejected(self):
        obj = program()
        obj["declarations"][0]["fields"].reverse()
        with self.assertRaisesRegex(target.BridgeInvalid, "exact accepted nominal layout"):
            target.build_goal(canonical.dumps(obj), relation(), profile(), obligations())

    def test_wrong_result_type_is_rejected(self):
        obj = program()
        obj["entries"][0].update(result="nat", body={"tag": "nat", "value": "0"})
        with self.assertRaisesRegex(target.BridgeInvalid, "signature differs"):
            target.build_goal(canonical.dumps(obj), relation(), profile(), obligations())

    def test_unbound_function_beneath_binder_is_rejected(self):
        rel = relation()
        rel["bindings"] = rel["bindings"][1:]
        obj = program()
        obj["entries"] = obj["entries"][1:]
        with self.assertRaisesRegex(target.BridgeInvalid, "unbound function"):
            target.build_goal(canonical.dumps(obj), rel, profile(), obligations())


class KernelBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TempDir()
        cls.tc = leanbridge.resolve_toolchain()
        built = leanbridge.compile_module(cls.tc, CONTRACT, cls.tmp.path / "contract")
        if not built.ok:
            raise AssertionError(built.errors)
        cls.contract_module = Path(built.olean).read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def context(self, source_bytes=None, proof=PROOF):
        data = source_bytes or canonical.dumps(program())
        return checker.EdgeContext("fixture", {}, "", "", {"edge_id": "fixture", "expected_proposition_hash": None},
            {"claim_id": "FIXTURE"}, {}, relation(), {"source": ("vscore-source", data),
            "proof_source": ("vscore-proof", proof)}, {}, {"toolchain": {"pin": leanbridge.DEFAULT_TOOLCHAIN}},
            profile(), "sha256:" + "0" * 64, self.contract_module, policy.get("strict"), obligations())

    def test_universal_bridge_two_clean_builds_and_accepted_ast(self):
        ctx = self.context()
        spec = target.build_goal(ctx.inputs["source"][1], ctx.relation, ctx.accepted_profile, ctx.obligations)
        first = checker.run_build(self.tc, ctx, spec)
        second = checker.run_build(self.tc, ctx, spec)
        self.assertEqual(first.observation, second.observation)
        self.assertEqual(canonical.dumps(first.ir["program"]), ctx.inputs["source"][1])
        self.assertNotIn("sorryAx", first.axioms)

    def test_wrong_implementation_cannot_prove_refinement(self):
        obj = program()
        obj["entries"][0]["body"]["right"]["value"] = "-4"
        ctx = self.context(canonical.dumps(obj))
        spec = target.build_goal(ctx.inputs["source"][1], ctx.relation, ctx.accepted_profile, ctx.obligations)
        with self.assertRaises(checker.EdgeFailure) as cm:
            checker.run_build(self.tc, ctx, spec)
        self.assertIn("CANDIDATE_BUILD_FAILURE", {d.code for d in cm.exception.diagnostics})


if __name__ == "__main__":
    unittest.main()
