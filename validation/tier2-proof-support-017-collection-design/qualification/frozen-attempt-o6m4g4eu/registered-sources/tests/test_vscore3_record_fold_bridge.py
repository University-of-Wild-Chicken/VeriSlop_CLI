"""Unrelated record-list mapping, filtering and fold transport kernel fixture."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from verislop import canonical, leanbridge, policy
from verislop.bridges import vscore3_checker as checker
from verislop.targets import vscore3_target as target, vscore3_source as source

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = b'''import Std
namespace RecordFoldFixture
structure Packet where
  amount : Int
  label : String
def transformed (offset : Int) (xs : List Packet) : List Packet :=
  xs.map (fun x => { amount := x.amount + offset, label := x.label })
def selected (limit : Int) (xs : List Packet) : List Packet :=
  xs.filter (fun x => decide (x.amount < limit))
def folded (initial : Int) (xs : List Packet) : Int :=
  xs.foldl (fun acc x => acc + x.amount) initial
def transformed_fold (offset initial : Int) (xs : List Packet) : Int :=
  (xs.map (fun x : Packet => Packet.mk (x.amount + offset) x.label)).foldl
    (fun acc x => acc + x.amount) initial
theorem transformed_contract : forall offset xs, transformed offset xs =
  xs.map (fun x => { amount := x.amount + offset, label := x.label }) := by intros; rfl
theorem selected_contract : forall limit xs, selected limit xs =
  xs.filter (fun x => decide (x.amount < limit)) := by intros; rfl
theorem folded_contract : forall initial xs, folded initial xs =
  xs.foldl (fun acc x => acc + x.amount) initial := by intros; rfl
theorem transformed_fold_contract : forall offset initial xs, transformed_fold offset initial xs =
  (xs.map (fun x : Packet => Packet.mk (x.amount + offset) x.label)).foldl
    (fun acc x => acc + x.amount) initial := by intros; rfl
end RecordFoldFixture
'''

PROOF = '''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
open VeriSlopBridgeGoal RecordFoldFixture
theorem edge : EdgeProp := by
  apply edge_of_refines
  · intro offset xs
    with_unfolding_all
      change ((xs.map adapter_2.to).map (fun x => (x.1 + offset, (x.2.1, ())))).map adapter_2.inv =
        xs.map (fun x => { amount := x.amount + offset, label := x.label })
    simp only [List.map_map]
    with_unfolding_all rfl
  · intro limit xs
    with_unfolding_all
      change ((xs.map adapter_2.to).filter (fun x => decide (x.1 < limit))).map adapter_2.inv =
        xs.filter (fun x => decide (x.amount < limit))
    rw [List.filter_map, List.map_map]
    with_unfolding_all
      change (xs.filter (fun x => decide (x.amount < limit))).map (fun x => adapter_2.inv (adapter_2.to x)) = _
    simp only [adapter_2.from_to, List.map_id']
  · intro initial xs
    with_unfolding_all
      change (xs.map adapter_2.to).foldl (fun acc x => acc + x.1) initial =
        xs.foldl (fun acc x => acc + x.amount) initial
    rw [List.foldl_map]
    with_unfolding_all rfl
  · intro offset initial xs
    with_unfolding_all
      change ((xs.map adapter_2.to).map (fun x => (x.1 + offset, (x.2.1, ())))).foldl (fun acc x => acc + x.1) initial =
        (xs.map (fun x : Packet => Packet.mk (x.amount + offset) x.label)).foldl (fun acc x => acc + x.amount) initial
    simp only [List.foldl_map]
    with_unfolding_all rfl
end VeriSlopBridgeProof
'''.encode()


def var(i):
    return {"tag": "var", "index": i}


def project(value, field):
    return {"tag": "project", "value": value, "field": field}


def transformed_record(offset_index):
    return {"tag": "record", "record": "Packet", "fields": [
        {"id": "amount", "value": {"tag": "add", "left": project(var(0), "amount"), "right": var(offset_index)}},
        {"id": "label", "value": project(var(0), "label")}]}


def fold(value, initial):
    return {"tag": "list_fold", "source": value, "initial": initial, "step": {
        "tag": "add", "left": var(1), "right": project(var(0), "amount")}}


def program():
    packets = {"list": {"record": "Packet"}}
    return {"language": source.LANGUAGE, "profile": source.PROFILE,
        "declarations": [{"tag": "record", "id": "Packet", "fields": [
            {"id": "amount", "type": "int"}, {"id": "label", "type": "string"}]}], "helpers": [], "entries": [
            {"id": "transformed", "params": ["int", packets], "result": packets,
             "body": {"tag": "list_map", "value": var(0), "body": transformed_record(2)}},
            {"id": "selected", "params": ["int", packets], "result": packets, "body": {
                "tag": "list_filter", "value": var(0), "body": {
                    "tag": "lt", "left": project(var(0), "amount"), "right": var(2)}}},
            {"id": "folded", "params": ["int", packets], "result": "int", "body": fold(var(0), var(1))},
            {"id": "transformed_fold", "params": ["int", "int", packets], "result": "int", "body":
                fold({"tag": "list_map", "value": var(0), "body": transformed_record(3)}, var(1))}]}


def profile():
    packets = {"list": {"record": "Packet"}}
    return {"profile_id": "record-fold-fixture", "dsl": "verislop.contract-dsl/0.2", "enums": {}, "predicates": {},
        "records": {"Packet": {"lean_decl": "RecordFoldFixture.Packet", "lean_constructor": "RecordFoldFixture.Packet.mk",
            "fields": [{"name": "amount", "lean_projection": "RecordFoldFixture.Packet.amount", "sort": "Int"},
                       {"name": "label", "lean_projection": "RecordFoldFixture.Packet.label", "sort": "String"}]}},
        "symbols": {n: {"lean_decl": "RecordFoldFixture." + n,
            "args": ["Int", "Int", packets] if n == "transformed_fold" else ["Int", packets],
            "result": packets if n in {"transformed", "selected"} else "Int"}
            for n in ("transformed", "selected", "folded", "transformed_fold")}}


def relation():
    return {"schema_version": "0.3", "format": target.RELATION_FORMAT, "template": target.TEMPLATE,
        "source_slot": "vscore-source", "proof_slot": "vscore-proof", "bindings": [
            {"symbol": n, "entry": n} for n in ("transformed", "selected", "folded", "transformed_fold")]}


def obligations():
    packet = {"record": "Packet"}
    packets = {"list": packet}
    field = lambda name: {"tag": "field", "sort": "Packet", "field": name, "value": var(0)}
    mapper = lambda offset: {"tag": "list_map", "value": var(0), "function": {"sort": packet, "body": {
        "tag": "record", "sort": "Packet", "fields": [
            {"tag": "int_add", "left": field("amount"), "right": var(offset)}, field("label")]}}}
    filtered = {"tag": "list_filter", "value": var(0), "function": {"sort": packet, "body": {
        "tag": "decide", "formula": {"tag": "lt", "left": field("amount"), "right": var(2)}}}}
    folded = lambda value: {"tag": "list_foldl", "value": value, "initial": var(1), "function": {
        "accumulator_sort": "Int", "element_sort": packet,
        "body": {"tag": "int_add", "left": var(1), "right": field("amount")}}}
    terms = {"transformed": mapper(2), "selected": filtered, "folded": folded(var(0)), "transformed_fold": folded(mapper(3))}
    out = {}
    for i, n in enumerate(("transformed", "selected", "folded", "transformed_fold"), 1):
        args = ["Int", "Int", packets] if n == "transformed_fold" else ["Int", packets]
        formula = {"tag": "eq", "left": {"tag": "call", "symbol": n,
            "args": [var(len(args) - j - 1) for j in range(len(args))]}, "right": terms[n]}
        for sort in reversed(args):
            formula = {"tag": "forall", "sort": sort, "body": formula}
        out["O" + str(i)] = {"formula": formula, "lean_symbol": "RecordFoldFixture." + n + "_contract",
                            "statement_hash": "sha256:" + str(i) * 64}
    return out


class RecordFoldBridgeTests(unittest.TestCase):
    def test_universal_record_list_and_fold_transport_two_clean_kernel_builds(self):
        tc = leanbridge.resolve_toolchain()
        data, registry, rel, obs = canonical.dumps(program()), profile(), relation(), obligations()
        spec = target.build_goal(data, rel, registry, obs)
        capture_root = ROOT / "validation/tier2-record-fold-pass"
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
            with tempfile.TemporaryDirectory(prefix="verislop-record-fold-contract-") as tmp:
                built = leanbridge.compile_module(tc, CONTRACT, Path(tmp))
                self.assertTrue(built.ok, built.errors)
                bundle = Path(built.olean).read_bytes()
                (capture / "contract.bundle").write_bytes(bundle)
                ctx = checker.EdgeContext("record-fold-fixture", {}, "", "",
                    {"edge_id": "record-fold-fixture", "expected_proposition_hash": None}, {"claim_id": "RECORD_FOLD_FIXTURE"},
                    {}, rel, {"source": ("vscore-source", data), "proof_source": ("vscore-proof", PROOF)}, {},
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
