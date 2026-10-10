"""Exact-source facets on an unrelated pure fixture, separate from benchmark runs."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from verislop import canonical, leanbridge, policy, source_contract
from verislop.bridges import vscore3_checker as checker
from verislop.exprjson import constants
from verislop.targets import vscore3_target as target
from tests.test_vscore3_bridge import CONTRACT, PROOF, obligations, profile, program, relation
from tests.helpers import TempDir


REQUIREMENTS = [{"tag": "entry", "file": "program.vscore.json", "entry": "solve", "arity": 1}] + [
    {"tag": tag} for tag in ("typed_total", "deterministic", "input_preserved", "no_external_io",
                            "no_floating_point", "pure_data", "restricted_runtime_only")]


def facet():
    return {"requirement_id": "source", "definition": "Fixture.source", "definition_hash": "sha256:" + "1" * 64,
            "symbol": "solve", "lean_decl": "Fixture.solve", "decl_hash": "sha256:" + "2" * 64,
            "requirements": copy.deepcopy(REQUIREMENTS), "model_version": source_contract.MODEL_VERSION,
            "model_source_hash": source_contract.model_source_hash()}


def source_obligations():
    rows = obligations()
    rows["O3"] = {"formula": rows["O1"]["formula"], "source_facets": [facet()],
                  "lean_symbol": "Fixture.mixed", "statement_hash": "sha256:" + "3" * 64}
    rows["S1"] = {"formula": None, "source_facets": [facet()], "lean_symbol": "Fixture.source_only",
                  "statement_hash": "sha256:" + "4" * 64}
    return rows


def source_contract_bytes():
    requirements = source_contract.render_requirements(REQUIREMENTS, __import__(
        "verislop.targets.vscore3_source", fromlist=["lean_string"]).lean_string)
    return source_contract.library_source() + CONTRACT.replace(b"import Std\n", b"", 1) + f'''
namespace Fixture
def source : VeriSlop.Source.SourceDefinition (Packet → Int) :=
  {{ endpoint := solve, requirements := {requirements} }}
theorem mixed : (∀ x : Packet, solve x = x.amount + (-3)) ∧ VeriSlop.Source.Contract source :=
  ⟨value_contract, VeriSlop.Source.contract_sound source⟩
theorem source_only : VeriSlop.Source.Contract source := VeriSlop.Source.contract_sound source
end Fixture
'''.encode()


class SourceFacetDerivationTests(unittest.TestCase):
    def test_distinct_source_model_and_exact_evaluator_laws_are_in_edge(self):
        spec = target.build_goal(canonical.dumps(program()), relation(), profile(), source_obligations())
        names = constants(spec.expected["EdgeProp"]["value"])
        self.assertIn(target.GOAL_MODULE + ".SourceAdequate_solve", names)
        self.assertIn("VSCore3.exactSourceFacts profile rawProgram", spec.text)
        self.assertNotIn("modelWitness", spec.text)
        self.assertIn("VSCore3.exactSourceFacts_adequate compiled_ok find_solve", spec.text)
        self.assertIn("VeriSlop.Source.HoldsBoundary", spec.text)
        self.assertIsNone(next(o for o in spec.obligations if o.oid == "S1").formula)

    def test_wrong_source_entry_is_rejected_before_proof_authoring(self):
        rows = source_obligations()
        rows["S1"]["source_facets"][0]["requirements"][0]["entry"] = "shift"
        with self.assertRaisesRegex(target.BridgeInvalid, "source entry differs"):
            target.build_goal(canonical.dumps(program()), relation(), profile(), rows)

    def test_wrong_source_arity_and_model_pin_are_rejected(self):
        for key, value in (("arity", 2), ("model_source_hash", "sha256:" + "f" * 64)):
            with self.subTest(key=key):
                rows = source_obligations()
                row = rows["S1"]["source_facets"][0]
                if key == "arity":
                    row["requirements"][0][key] = value
                else:
                    row[key] = value
                with self.assertRaises(target.BridgeInvalid):
                    target.build_goal(canonical.dumps(program()), relation(), profile(), rows)


class SourceFacetKernelTests(unittest.TestCase):
    def run_fixture(self, data, rel, registry, rows, contract_source, proof):
        capture_root = Path(__file__).resolve().parents[1] / "synthetic_dataset/bootstrap/validation/tier2-source-facets-pass"
        capture_root.mkdir(parents=True, exist_ok=True)
        capture = Path(tempfile.mkdtemp(prefix="attempt-", dir=capture_root))
        spec = target.build_goal(data, rel, registry, rows)
        for name, payload in {"program.vscore.json": data, "relation.json": canonical.dumps(rel),
                "profile.json": canonical.dumps(registry), "obligations.json": canonical.dumps(rows),
                "VeriSlopContract.lean": contract_source, "VeriSlopBridgeGoal.lean": spec.text.encode(),
                "VeriSlopBridgeProof.lean": proof, "expected.json": canonical.dumps(spec.expected)}.items():
            (capture / name).write_bytes(payload)
        for module, payload in target.library_sources().items():
            path = capture / "library" / (module.replace(".", "/") + ".lean")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        tmp = TempDir()
        self.addCleanup(tmp.cleanup)
        tc = leanbridge.resolve_toolchain()
        try:
            contract = leanbridge.compile_module(tc, contract_source, tmp.path / "contract")
            self.assertTrue(contract.ok, contract.errors)
            bundle = Path(contract.olean).read_bytes()
            (capture / "contract.bundle").write_bytes(bundle)
            ctx = checker.EdgeContext("fixture", {}, "", "", {"edge_id": "fixture", "expected_proposition_hash": None},
                {"claim_id": "FIXTURE"}, {}, rel, {"source": ("vscore-source", data),
                "proof_source": ("vscore-proof", proof)}, {}, {"toolchain": {"pin": leanbridge.DEFAULT_TOOLCHAIN}},
                registry, "sha256:" + "0" * 64, bundle, policy.get("strict"), rows)
            builds = []
            for index in (1, 2):
                result = checker.run_build(tc, ctx, spec)
                builds.append(result)
                out = capture / ("build-" + str(index))
                out.mkdir()
                for name, obj in {"observation.json": result.observation, "ir.json": result.ir,
                                  "declarations.json": result.decls, "axioms.json": result.axioms}.items():
                    (out / name).write_bytes(canonical.dumps(obj))
                for module, parts in result.modules.items():
                    for suffix, payload in parts.items():
                        path = out / "modules" / (module.replace(".", "/") + suffix)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(payload)
            self.assertEqual(builds[0].observation, builds[1].observation)
            self.assertEqual(builds[0].ir, builds[1].ir)
            self.assertEqual(data, canonical.dumps(builds[0].ir["program"]))
            (capture / "status.json").write_bytes(canonical.dumps({"status": "PASS", "builds": 2,
                "source_hash": canonical.digest(data), "goal_hash": canonical.digest(spec.text.encode()),
                "proof_hash": canonical.digest(proof), "proposition_hash": builds[0].proposition_hash}))
            return spec
        except Exception as exc:
            (capture / "status.json").write_bytes(canonical.dumps({"status": "FAIL", "error": str(exc)}))
            raise

    def test_pure_mixed_source_and_functional_facets_two_clean_builds(self):
        spec = self.run_fixture(canonical.dumps(program()), relation(), profile(), source_obligations(),
                                source_contract_bytes(), PROOF)
        self.assertIn("import VSCore3.SourceFacts", spec.text)

    def test_generic_enum_and_source_only_does_not_invent_functional_refinement(self):
        registry = {"profile_id": "fixture-source-only-enum", "dsl": "verislop.contract-dsl/0.2",
            "predicates": {}, "records": {},
            "enums": {"Mode": {"lean_decl": "Other.Mode", "constructors": ["left", "right"],
                               "lean_constructors": ["Other.Mode.left", "Other.Mode.right"]}},
            "symbols": {"identity": {"lean_decl": "Other.identity", "args": [{"enum": "Mode"}], "result": {"enum": "Mode"}},
                        "unconstrained": {"lean_decl": "Other.unconstrained", "args": ["Int"], "result": "Int"}}}
        prog = {"language": "vscore/0.3", "profile": "data-pipeline/0.3", "declarations": [], "helpers": [], "entries": [
            {"id": "identity", "params": [{"enum": "Mode"}], "result": {"enum": "Mode"}, "body": {"tag": "var", "index": 0}},
            {"id": "unconstrained", "params": ["int"], "result": "int", "body": {"tag": "int", "value": "17"}}]}
        rel = relation()
        rel["bindings"] = [{"symbol": name, "entry": name} for name in ("identity", "unconstrained")]
        source_row = facet()
        source_row.update(definition="Other.source", symbol="unconstrained", lean_decl="Other.unconstrained")
        source_row["requirements"][0]["entry"] = "unconstrained"
        variable = {"tag": "var", "index": 0}
        rows = {"O1": {"formula": {"tag": "forall", "sort": {"enum": "Mode"}, "body": {"tag": "eq",
            "left": {"tag": "call", "symbol": "identity", "args": [variable]}, "right": variable}},
            "lean_symbol": "Other.identity_contract", "statement_hash": "sha256:" + "5" * 64},
            "S1": {"formula": None, "source_facets": [source_row], "lean_symbol": "Other.source_only",
            "statement_hash": "sha256:" + "6" * 64}}
        from verislop.targets.vscore3_source import lean_string
        requirements = source_contract.render_requirements(source_row["requirements"], lean_string)
        contract = source_contract.library_source() + f'''
namespace Other
inductive Mode where | left | right
def identity (x : Mode) : Mode := x
def unconstrained (_ : Int) : Int := 0
theorem identity_contract (x : Mode) : identity x = x := rfl
def source : VeriSlop.Source.SourceDefinition (Int → Int) :=
  {{ endpoint := unconstrained, requirements := {requirements} }}
theorem source_only : VeriSlop.Source.Contract source := VeriSlop.Source.contract_sound source
end Other
'''.encode()
        enum_proof = PROOF.replace(b"all_goals intro x; with_unfolding_all rfl",
                                   b"all_goals intro x; cases x <;> with_unfolding_all rfl")
        spec = self.run_fixture(canonical.dumps(prog), rel, registry, rows, contract, enum_proof)
        names = constants(spec.expected["EdgeProp"]["value"])
        self.assertNotIn(target.GOAL_MODULE + ".Refines_unconstrained", names)
        self.assertIn(target.GOAL_MODULE + ".Refines_identity", names)
        self.assertIn(target.GOAL_MODULE + ".SourceAdequate_unconstrained", names)


if __name__ == "__main__":
    unittest.main()
