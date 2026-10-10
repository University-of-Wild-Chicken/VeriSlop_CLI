"""Fresh generic kernel fixtures for exact generated and accepted Lean Names."""
from __future__ import annotations

import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import canonical, fsutil, leanbridge, policy
from verislop.bridges import vscore3_checker as checker
from verislop.exprjson import const, name_str, parse_name
from verislop.targets import vscore3_replay as replay, vscore3_source as source, vscore3_target as target


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "validation/tier2-proof-support-017-name-design"
CONTRACT = b'''import Std
namespace NameFixture
def bump (x : Int) : Int := x + 5
theorem plain_law (x : Int) : bump x = x + 5 := by rfl
theorem \xc2\xabbump-law\xc2\xbb (x : Int) : bump x = x + 5 := by rfl
theorem \xc2\xabbump.law\xc2\xbb (x : Int) : bump x = x + 5 := by rfl
theorem \xc2\xabbump:law\xc2\xbb (x : Int) : bump x = x + 5 := by rfl
theorem \xc2\xab7\xc2\xbb (x : Int) : bump x = x + 5 := by rfl
end NameFixture
'''
PROOF = b'''import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  intro x
  with_unfolding_all rfl
end VeriSlopBridgeProof
'''


def program():
    return {"language": source.LANGUAGE, "profile": source.PROFILE, "declarations": [], "helpers": [],
            "entries": [{"id": "bump", "params": ["int"], "result": "int", "body": {
                "tag": "add", "left": {"tag": "var", "index": 0}, "right": {"tag": "int", "value": "5"}}}]}


def registry():
    return {"profile_id": "fresh-name-identity", "dsl": "verislop.contract-dsl/0.2", "enums": {},
            "records": {}, "predicates": {}, "symbols": {
                "bump": {"lean_decl": "NameFixture.bump", "args": ["Int"], "result": "Int"}}}


def relation():
    return {"schema_version": "0.3", "format": target.RELATION_FORMAT, "template": target.TEMPLATE,
            "source_slot": "name-source", "proof_slot": "name-proof", "bindings": [{"symbol": "bump", "entry": "bump"}]}


def obligations():
    formula = {"tag": "forall", "sort": "Int", "body": {"tag": "eq", "left": {
        "tag": "call", "symbol": "bump", "args": [{"tag": "var", "index": 0}]}, "right": {
        "tag": "int_add", "left": {"tag": "var", "index": 0}, "right": {"tag": "int", "value": "5"}}}}
    symbols = {"N_bump": "NameFixture.«plain_law»", "N-bump": "NameFixture.«bump-law»",
               "N.bump": "NameFixture.«bump.law»", "N:bump": "NameFixture.«bump:law»", "N:7": "NameFixture.«7»"}
    return {oid: {"formula": copy.deepcopy(formula), "lean_symbol": symbol, "revision": 1,
                  "statement_hash": canonical.digest_json({"formula": formula, "symbol": symbol})}
            for oid, symbol in symbols.items()}


class NameComponentTests(unittest.TestCase):
    def test_reserved_readable_namespace_and_literal_dotted_obligation_leaf(self):
        self.assertEqual(target.expected_decl_name("Readable.RunEquals_entry_0"),
                         [target.GOAL_MODULE, "Readable", "RunEquals_entry_0"])
        self.assertEqual(target.expected_decl_name("Transfer_N.bump"), [target.GOAL_MODULE, "Transfer_N.bump"])
        self.assertEqual(name_str(target.expected_decl_name("Transfer_N_bump")), target.GOAL_MODULE + ".Transfer_N_bump")
        self.assertNotEqual(name_str(target.gname("transfer_N.bump")), target.GOAL_MODULE + ".transfer_N.bump")

    def test_dependency_comparison_preserves_numeric_and_string_components(self):
        numeric = {"value_constants": [["NameFixture", 7]]}
        string = {"value_constants": [["NameFixture", "7"]]}
        self.assertTrue(target.references_theorem(numeric, "NameFixture.7"))
        self.assertFalse(target.references_theorem(numeric, "NameFixture.«7»"))
        self.assertTrue(target.references_theorem(string, "NameFixture.«7»"))
        self.assertFalse(target.references_theorem(string, "NameFixture.7"))
        self.assertFalse(target.references_theorem(string, "NameFixture.«unterminated"))
        self.assertTrue(target.references_theorem({"value_constants": [["NameFixture", "plain_law"]]},
                                                "NameFixture.«plain_law»"))
        self.assertFalse(target.references_theorem({"value_constants": [["NameFixture", "bump", "law"]]},
                                                 "NameFixture.«bump.law»"))


class NameKernelTests(unittest.TestCase):
    @classmethod
    def retain(cls, name, value):
        path = cls.capture / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else canonical.dumps(value))
        return path

    @classmethod
    def capture_kernel(cls, phase, calls):
        original = leanbridge.run_kernel_tool_modules

        def actual(*args, **kwargs):
            result = original(*args, **kwargs)
            index = len(calls)
            calls.append(copy.deepcopy(result))
            cls.goal_parts[phase] = dict(args[1][target.GOAL_MODULE])
            cls.retain(f"{phase}/kernel-{index}.json", result)
            cls.retain(f"{phase}/request-{index}.json", args[3])
            for module, parts in args[1].items():
                for suffix, data in parts.items():
                    cls.retain(f"{phase}/modules/{leanbridge.module_relpath(module)}{suffix}", data)
            return result

        return actual

    @classmethod
    def setUpClass(cls):
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        cls.capture = Path(tempfile.mkdtemp(prefix="kernel-names-", dir=EVIDENCE))
        cls.goal_parts = {}
        cls.addClassCleanup(cls.write_manifest)
        cls.tmp = tempfile.TemporaryDirectory(prefix="verislop-name-contract-")
        cls.addClassCleanup(cls.cleanup)
        cls.tc = leanbridge.resolve_toolchain()
        data, profile, rel, obs = canonical.dumps(program()), registry(), relation(), obligations()
        cls.spec = target.build_goal(data, rel, profile, obs)
        for name, value in {"fixtures/VeriSlopContract.lean": CONTRACT, "fixtures/VeriSlopBridgeProof.lean": PROOF,
                            "fixtures/program.vscore.json": data, "fixtures/profile.json": profile,
                            "fixtures/relation.json": rel, "fixtures/obligations.json": obs,
                            "fixtures/VeriSlopBridgeGoal.lean": cls.spec.text.encode(),
                            "fixtures/expected.json": cls.spec.expected}.items():
            cls.retain(name, value)
        for module, value in target.library_sources().items():
            cls.retain("inputs/library/" + target.module_path(module), value)
        for path in ("docs/bootstrap-tier2-collection-proof-support.md", "verislop/targets/vscore3_target.py",
                     "verislop/targets/vscore3_replay.py", "verislop/bridges/vscore3_checker.py",
                     "verislop/exprjson.py", "tests/test_vscore3_name_identity.py"):
            cls.retain("inputs/" + path, (ROOT / path).read_bytes())
        built = leanbridge.compile_module(cls.tc, CONTRACT, Path(cls.tmp.name))
        cls.retain("contract-compile.json", {"ok": built.ok, "errors": built.errors, "messages": built.messages,
                   "sorry_positions": built.sorry_positions, "process_evidence": leanbridge.compile_process_details(built)})
        if not built.ok or built.sorry_positions:
            raise AssertionError(built.errors)
        bundle = Path(built.olean).read_bytes()
        cls.retain("fixtures/contract.bundle", bundle)
        plan = {"accepted_ir": canonical.digest_json(obs), "acceptance_certificate": canonical.digest(bundle)}
        cls.ctx = checker.EdgeContext("fresh-name-identity", plan, canonical.digest_json(plan), canonical.digest(data),
            {"edge_id": "fresh-name-identity", "expected_proposition_hash": None}, {"claim_id": "FRESH_NAME_IDENTITY"}, {},
            rel, {"source": ("name-source", data), "proof_source": ("name-proof", PROOF)}, {},
            {"toolchain": {"pin": leanbridge.DEFAULT_TOOLCHAIN}}, profile, canonical.digest_json(profile), bundle,
            policy.get("strict"), obs)
        calls = []
        try:
            with patch.object(leanbridge, "run_kernel_tool_modules", cls.capture_kernel("build-A", calls)):
                cls.first = checker.run_build(cls.tc, cls.ctx, cls.spec)
            cls.response = calls[0]
            cls.retain("build-A/observation.json", cls.first.observation)
            cls.retain("build-A/process-evidence.json", cls.first.process_evidence)
            cls.retain("build-A/implementation-ir.json", cls.first.ir)
            calls = []
            with patch.object(leanbridge, "run_kernel_tool_modules", cls.capture_kernel("build-B", calls)):
                cls.second = checker.run_build(cls.tc, cls.ctx, cls.spec)
            cls.retain("build-B/observation.json", cls.second.observation)
            cls.retain("build-B/process-evidence.json", cls.second.process_evidence)
        except checker.EdgeFailure as exc:
            cls.retain("setup-failure.json", [d.to_json() for d in exc.diagnostics])
            raise
        cls.ctx.edge["expected_proposition_hash"] = cls.first.proposition_hash

    @classmethod
    def cleanup(cls):
        fsutil.make_writable_tree(Path(cls.tmp.name))
        cls.tmp.cleanup()

    @classmethod
    def write_manifest(cls):
        files = {str(p.relative_to(cls.capture)): canonical.digest(p.read_bytes())
                 for p in cls.capture.rglob("*") if p.is_file() and p.name != "manifest.json"}
        cls.retain("manifest.json", {"format": "verislop.generic-name-identity-evidence/1", "artifacts": files,
            "boundary_mutations": "Changed export records are host-audit tests, not kernel-replayed edited records."})

    def audit_response(self, response):
        return checker._audit(self.tc, self.ctx, self.spec, response, self.first.modules,
                              self.first.observation["compiles"], self.first.observation["isolation"], True)

    def test_two_clean_bridges_and_certificate_names_match_actual_exports(self):
        self.assertEqual(self.first.observation, self.second.observation)
        self.assertEqual(canonical.dumps(self.first.ir["program"]), self.spec.source_bytes)
        goal = {name: row for name, row in self.first.decls.items() if row.get("module") == [target.GOAL_MODULE]}
        self.assertEqual(target.statement_mismatches(self.spec, goal), [])
        descriptor = checker._semantic_descriptor(self.ctx, self.spec, self.first.axioms)
        self.retain("certificate-descriptor.json", descriptor)
        for row in descriptor["obligations"]:
            oid = row["id"]
            for field, prefix in (("transfer", "Transfer_"), ("transfer_theorem", "transfer_")):
                expected = [target.GOAL_MODULE, prefix + oid]
                self.assertEqual(parse_name(row[field]), expected)
                self.assertEqual(goal[row[field]]["name"], expected)
            transfer = goal[row["transfer_theorem"]]
            accepted = parse_name(row["accepted_theorem"])
            self.assertIn(accepted, transfer["value_constants"])
            self.assertTrue(target.references_theorem(transfer, row["accepted_theorem"]))
        self.assertEqual(descriptor["statement_identity"], sorted(name_str(target.expected_decl_name(n)) for n in self.spec.expected))
        for name in descriptor["statement_identity"]:
            self.assertEqual(parse_name(name), goal[name]["name"])

    def test_actual_concrete_review_replay_audits_all_punctuation_ids(self):
        for index, oid in enumerate(("N-bump", "N.bump", "N:bump")):
            with self.subTest(oid=oid):
                expression = replay.ground(self.spec, self.ctx.obligations[oid]["formula"], [index - 2])
                calls = []
                with patch.object(leanbridge, "run_kernel_tool_modules", self.capture_kernel(f"probe-{index}", calls)):
                    result = replay.check(self.tc, self.ctx, self.spec, expression, deadline=time.monotonic() + 30,
                                          goal_parts=self.first.modules[target.GOAL_MODULE])
                self.assertTrue(result["predicate"])
                self.assertTrue(result["kernel_replay"])
                self.assertEqual(len(calls), 1)
                self.retain(f"probe-{index}/result.json", {"obligation_id": oid, "expression": expression, "result": result})

    def test_actual_kernel_readable_expected_names_keep_nested_namespace(self):
        readable = target.enrich_readable(self.spec)
        calls = []
        with patch.object(leanbridge, "run_kernel_tool_modules", self.capture_kernel("readable", calls)):
            build = checker.run_build(self.tc, self.ctx, readable)
        self.retain("readable/VeriSlopBridgeGoal.lean", readable.text.encode())
        self.retain("readable/observation.json", build.observation)
        self.assertEqual(build.proposition_hash, self.first.proposition_hash)
        goal = {name: row for name, row in build.decls.items() if row.get("module") == [target.GOAL_MODULE]}
        self.assertEqual(target.statement_mismatches(readable, goal), [])
        descriptor = checker._semantic_descriptor(self.ctx, readable, build.axioms)
        self.retain("readable/certificate-descriptor.json", descriptor)
        key = name_str([target.GOAL_MODULE, "Readable", "RunEquals_entry_0"])
        self.assertIn(key, descriptor["statement_identity"])
        self.assertEqual(goal[key]["name"], [target.GOAL_MODULE, "Readable", "RunEquals_entry_0"])
        self.assertIn(name_str(target.gname("Transfer_N.bump")), descriptor["statement_identity"])

    def test_host_audit_rejects_missing_near_name_dependency_kind_and_statement(self):
        def transfer(response, oid):
            return next(row for row in response["constants"] if row["name"] == target.gname("transfer_" + oid))

        def missing(response):
            response["constants"].remove(transfer(response, "N-bump"))

        def near_name(response):
            transfer(response, "N.bump")["name"] = [target.GOAL_MODULE, "transfer_N", "bump"]

        def dependency(response):
            row = transfer(response, "N-bump")
            row["value_constants"] = [n for n in row["value_constants"] if n != ["NameFixture", "bump-law"]]
            row["value_constants"].append(["NameFixture", "plain_law"])

        def wrong_kind(response):
            transfer(response, "N-bump")["kind"] = "definition"

        def numeric_component(response):
            row = transfer(response, "N:7")
            row["value_constants"] = [["NameFixture", 7] if n == ["NameFixture", "7"] else n for n in row["value_constants"]]

        def namespace_dependency(response):
            row = transfer(response, "N.bump")
            row["value_constants"] = [["NameFixture", "bump", "law"] if n == ["NameFixture", "bump.law"] else n
                                      for n in row["value_constants"]]

        def statement(response):
            row = next(row for row in response["constants"] if row["name"] == target.gname("Transfer_N.bump"))
            row["value"] = const("True")

        cases = (missing, near_name, dependency, wrong_kind, numeric_component, namespace_dependency, statement)
        for mutate in cases:
            with self.subTest(case=mutate.__name__):
                response = copy.deepcopy(self.response)
                mutate(response)
                self.retain(f"host-audit-mutations/{mutate.__name__}.json", response)
                with self.assertRaises(checker.EdgeFailure) as result:
                    self.audit_response(response)
                self.assertEqual(result.exception.diagnostics[0].code, "STATEMENT_MISMATCH")
                self.retain(f"host-audit-mutations/{mutate.__name__}-result.json", [d.to_json() for d in result.exception.diagnostics])

    def test_reexport_preserves_exact_lookup_and_constructor_checks(self):
        goal = {name: row for name, row in self.first.decls.items() if row.get("module") == [target.GOAL_MODULE]}
        self.assertEqual(target.reexport(self.spec, goal), self.first.ir)
        for case in ("missing", "wrong-constructor"):
            with self.subTest(case=case):
                mutated = copy.deepcopy(goal)
                key = name_str(target.gname("rawProgram"))
                if case == "missing":
                    mutated.pop(key)
                else:
                    mutated[key]["value"] = const("True")
                with self.assertRaises(target.BridgeInvalid) as result:
                    target.reexport(self.spec, mutated)
                self.assertEqual(result.exception.code, "IR_REIFICATION_MISMATCH")
                self.retain(f"reexport-negatives/{case}.json", {"message": str(result.exception), "code": result.exception.code})

    def test_real_compiled_goals_reject_near_name_wrong_dependency_kind_and_statement(self):
        # These mutations are compiled and replayed normally. Their statements
        # remain provable in Lean, but differ from the supervisor's exact contract.
        def near_name(spec):
            spec.text = spec.text.replace("«transfer_N.bump»", "transfer_N.bump")

        def dependency(spec):
            spec.text = spec.text.replace("@NameFixture.«bump-law»", "@NameFixture.plain_law")

        def wrong_kind(spec):
            spec.text = spec.text.replace("theorem «transfer_N-bump»", "def «transfer_N-bump»")

        def statement(spec):
            component = "Transfer_N.bump"
            definition = "def " + target.lean_component(component) + " : Prop := "
            start = spec.text.index(definition)
            end = spec.text.index("\n", start)
            spec.text = spec.text[:start] + definition + "True" + spec.text[end:]
            start = spec.text.index("theorem «transfer_N.bump»")
            header_end = spec.text.index("\n", start)
            body_end = spec.text.index("\n\n", header_end)
            spec.text = spec.text[:header_end] + "\n  trivial" + spec.text[body_end:]

        for mutate in (near_name, dependency, wrong_kind, statement):
            with self.subTest(case=mutate.__name__):
                mutant = copy.deepcopy(self.spec)
                mutate(mutant)
                phase = "compiled-negatives/" + mutate.__name__
                self.retain(phase + "/VeriSlopBridgeGoal.lean", mutant.text.encode())
                calls = []
                with patch.object(leanbridge, "run_kernel_tool_modules", self.capture_kernel(phase, calls)):
                    with self.assertRaises(checker.EdgeFailure) as result:
                        checker.run_build(self.tc, self.ctx, mutant)
                self.assertEqual(len(calls), 1, "negative must reach actual kernel replay")
                self.assertTrue(calls[0]["import"]["ok"])
                self.assertTrue(calls[0]["replay"]["ok"])
                self.assertEqual(result.exception.diagnostics[0].code, "STATEMENT_MISMATCH")
                self.retain(phase + "/result.json", [d.to_json() for d in result.exception.diagnostics])
                expression = replay.ground(self.spec, self.ctx.obligations["N-bump"]["formula"], [13])
                probe_calls = []
                with patch.object(leanbridge, "run_kernel_tool_modules", self.capture_kernel(phase + "/review", probe_calls)):
                    with self.assertRaises(replay.Unsupported) as review_result:
                        replay.check(self.tc, self.ctx, self.spec, expression, deadline=time.monotonic() + 30,
                                     goal_parts=self.goal_parts[phase])
                self.assertEqual(len(probe_calls), 1, "review negative must reach actual kernel replay")
                self.assertTrue(probe_calls[0]["import"]["ok"])
                self.assertTrue(probe_calls[0]["replay"]["ok"])
                reason = "source goal differs" if mutate.__name__ == "statement" else "original accepted theorem"
                self.assertIn(reason, str(review_result.exception))
                self.retain(phase + "/review/result.json", {"status": "UNSUPPORTED", "reason": str(review_result.exception)})


if __name__ == "__main__":
    unittest.main()
