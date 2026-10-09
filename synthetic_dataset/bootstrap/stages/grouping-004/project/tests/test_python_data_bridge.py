"""Strict structured data transport and finite campaigns against real isolated Python."""
from __future__ import annotations

import copy
import itertools
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from verislop import canonical, contract, dsl, fsutil, review, review_counterexamples as rc, schemas, testing
from verislop.package import Package
from verislop.targets import python_harness as ph, python_target as pt

ZERO = "sha256:" + "0" * 64


def data_profile():
    records = {
        "Input": {"fields": [{"name": "numbers", "sort": {"list": "Int"}}, {"name": "threshold", "sort": "Int"}, {"name": "label", "sort": "String"}]},
        "Output": {"fields": [{"name": "values", "sort": {"list": "Int"}}, {"name": "total", "sort": "Int"}, {"name": "count", "sort": "Nat"}, {"name": "label", "sort": "String"}]},
        "Nested": {"fields": [{"name": "rows", "sort": {"list": {"list": "Int"}}}, {"name": "input", "sort": {"record": "Input"}}]}}
    for rid, rec in records.items():
        rec.update(lean_decl="Data." + rid, lean_constructor="Data." + rid + ".mk", decl_hash=ZERO, constructor_hash=ZERO)
        for field in rec["fields"]:
            field.update(lean_projection="Data." + rid + "." + field["name"], projection_hash=ZERO)
    return dsl.Profile.from_json({"profile_id": "data.v0_2", "dsl": dsl.ENCODING_V2, "records": records,
        "symbols": {"pipeline": {"lean_decl": "Data.pipeline", "args": [{"record": "Input"}],
                    "result": {"record": "Output"}, "body": pipeline_formula()["body"]["right"]}},
        "enums": {}, "predicates": {}})


def pipeline_formula():
    inp = {"tag": "var", "index": 0}
    field = lambda name, value=inp: {"tag": "field", "sort": "Input", "field": name, "value": value}
    filtered = {"tag": "list_filter", "value": field("numbers"), "function": {"sort": "Int", "body": {
        "tag": "decide", "formula": {"tag": "le", "left": field("threshold", {"tag": "var", "index": 1}),
                                       "right": {"tag": "var", "index": 0}}}}}
    values = {"tag": "list_map", "value": filtered, "function": {"sort": "Int", "body": {
        "tag": "int_mul", "left": {"tag": "var", "index": 0}, "right": {"tag": "int", "value": "2"}}}}
    expected = {"tag": "record", "sort": "Output", "fields": [values, {"tag": "list_sum", "value": values},
                 {"tag": "list_length", "value": values}, field("label")]}
    return {"tag": "forall", "sort": {"record": "Input"}, "body": {"tag": "eq",
        "left": {"tag": "call", "symbol": "pipeline", "args": [inp]}, "right": expected}}


SOURCE = ('def pipeline(data):\n'
          '    values = [x * 2 for x in data["numbers"] if x >= data["threshold"]]\n'
          '    return {"values": values, "total": sum(values), "count": len(values), "label": data["label"]}\n')


class PythonDataBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="verislop-data-bridge-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = data_profile()

    def test_empty_materialization_inventory_has_real_sandbox_working_directory(self):
        impl = self.root / "empty-implementation"
        impl.mkdir()
        output = self.root / "compile"
        result = pt.byte_compile(impl, [], output)
        self.assertTrue(result["ok"], result)
        self.assertEqual({}, result["pyc"])
        self.assertTrue((output / "src").is_dir())

    def test_nested_round_trip_preserves_hashable_values_and_native_shapes(self):
        value = dsl.record_v("Nested", [((-3, 0), (), (2, 2)), dsl.record_v("Input", [(-2, -2, 4), -1, "é🙂\x00"])])
        wire = pt.encode_arg(value, {"record": "Nested"}, self.profile)
        self.assertEqual(value, pt.decode_result(wire, {"record": "Nested"}, self.profile))
        self.assertIsInstance(hash(value), int)
        native = ph.dec(wire)
        self.assertEqual([[-3, 0], [], [2, 2]], native["rows"])
        self.assertEqual([-2, -2, 4], native["input"]["numbers"])
        self.assertEqual(-1, native["input"]["threshold"])
        self.assertEqual(wire, ph.enc(native))

    def test_records_require_exact_keys_and_nested_lists_are_not_result_tuples(self):
        good = pt.encode_arg(dsl.record_v("Input", [(-2, 3), -1, "é"]), {"record": "Input"}, self.profile)
        for mutation in ("missing", "extra", "tuple", "bool"):
            bad = copy.deepcopy(good)
            if mutation == "missing":
                del bad["dict"]["label"]
            elif mutation == "extra":
                bad["dict"]["extra"] = {"int": "1"}
            elif mutation == "tuple":
                bad["dict"]["numbers"] = {"tuple": [{"int": "-2"}, {"int": "3"}]}
            else:
                bad["dict"]["threshold"] = {"bool": True}
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                pt.decode_result(bad, {"record": "Input"}, self.profile)

    def test_primitive_decoding_is_closed_canonical_and_exact(self):
        self.assertEqual(-10, pt.decode_result({"int": "-10"}, "Int", self.profile))
        for bad in ({"int": True}, {"int": "+1"}, {"int": "-0"}, {"int": "01"}, {"int": "1", "bool": False}):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                pt.decode_result(bad, "Int", self.profile)
        for bad, sort in (({"bool": 1}, "Bool"), ({"none": False}, "Unit"), ({"str": "\ud800"}, "String"), ({"int": "-1"}, "Nat")):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                pt.decode_result(bad, sort, self.profile)
        with self.assertRaises(ValueError):
            pt.encode_arg(True, "Int", self.profile)

    def test_budget_exhaustion_is_distinct_from_malformed_profile_values(self):
        for value, sort in (({"list": [{"int": "0"}] * 257}, {"list": "Int"}),
                            ({"str": "a" * 16385}, "String"), ({"int": "1" * 4097}, "Int")):
            with self.subTest(sort=sort), self.assertRaises(pt.WireBudgetExceeded):
                pt.decode_result(value, sort, self.profile)
        with self.assertRaises(pt.WireBudgetExceeded):
            pt.encode_arg(2**20000, "Int", self.profile)
        with self.assertRaises(dsl.BudgetExceeded):
            rc._decode({"encoding_budget": "output too large"}, "String", self.profile)

    def test_generic_signed_nested_wire_is_valid_but_sort_checks_stay_strict(self):
        wire = pt.encode_arg(dsl.record_v("Input", [(-3, 0, 3), -1, "é🙂"]), {"record": "Input"}, self.profile)
        proposal = {"kind": "target_case", "obligation_id": "O1", "assignment": [wire]}
        self.assertEqual([], rc.validate_proposal(proposal))
        self.assertEqual([], schemas.validate("review-counterexample-proposal", proposal))
        self.assertEqual(dsl.record_v("Input", [(-3, 0, 3), -1, "é🙂"]), rc._decode(wire, {"record": "Input"}, self.profile))
        for bad in ({"dict": {"label": {"str": "\ud800"}}}, {"list": [{"int": "-0"}]}, {"list": [{"bool": 1}]},
                    {"list": [{"none": None}] * 257}, {"dict": {str(i): {"int": "0"} for i in range(65)}}):
            with self.subTest(wire=bad):
                self.assertTrue(rc.validate_proposal({**proposal, "assignment": [bad]}))

    def test_legacy_profile_selection_and_new_sorts_are_not_silently_upgraded(self):
        old = dsl.Profile.from_json({"profile_id": "old", "enums": {}, "symbols": {}, "predicates": {}})
        self.assertEqual(pt.PROFILE_ID, pt.profile_id(old))
        self.assertEqual(pt.PROFILE_DOC, pt.profile_doc(old))
        self.assertEqual(pt.PROFILE_ID_V2, pt.profile_id(self.profile))
        for sort, wire in (("Int", {"int": "-1"}), ("String", {"str": "é"}), ({"list": "Nat"}, {"list": []})):
            with self.subTest(sort=sort), self.assertRaises(ValueError):
                pt.decode_result(wire, sort, old)

    def test_real_harness_receives_native_lists_dicts_unicode_and_exact_signed_ints(self):
        impl = self.root / "implementation"
        fsutil.atomic_write(impl / "pipeline.py", SOURCE.encode())
        inv = pt.inventory(impl)
        harness = pt.Harness(impl, inv.files, {"pipeline": ("pipeline.py", "pipeline")})
        self.addCleanup(harness.close)
        oracle = testing.Oracle(harness, self.profile, {"pipeline"})
        arg = dsl.record_v("Input", [(-3, 1, 1, 4), 1, "é🙂"])
        result = oracle.symbols()["pipeline"]([arg])
        self.assertEqual(dsl.record_v("Output", [(2, 2, 8), 12, 3, "é🙂"]), result)
        self.assertEqual(2, harness.calls)
        self.assertEqual(result, oracle.symbols()["pipeline"]([arg]))
        self.assertEqual(2, harness.calls)

    def execute_pipeline(self, source):
        impl = self.root / "implementation"
        fsutil.atomic_write(impl / "pipeline.py", source.encode())
        formula = pipeline_formula()
        package = dsl.make_package(formula, self.profile.profile_id, encoding=dsl.ENCODING_V2)
        dsl.check_package(package, self.profile)
        payload = canonical.dumps(package)
        digest = canonical.digest(payload)
        expressions = self.root / "expressions"
        fsutil.atomic_write(expressions / (digest[7:] + ".json"), payload)
        link = {"bindings": [{"symbol": "pipeline", "implementation_object": {"file": "pipeline.py", "qualname": "pipeline"}}]}
        claims = {"claims": [{"milestone": "TESTED", "obligation": "O1", "applicable": True}]}
        ir = {"obligations": {"O1": {"kind": "postcondition", "formal": {"representation": "contract_dsl", "formula_ref": "artifact:formula@" + digest}}}}
        cfg = testing.campaign_config(17, 32, 5000, self.profile)
        return testing.execute(impl, link, claims, ir, self.profile, cfg, expressions, {})

    def test_finite_data_campaign_passes_actual_correct_pipeline_and_finds_concrete_mutant(self):
        good = self.execute_pipeline(SOURCE)["obligations"]["O1"]
        self.assertEqual("PASS", good["outcome"], good)
        self.assertEqual(32, good["detail"]["counts"]["effective"])
        bad = self.execute_pipeline(SOURCE.replace('"total": sum(values)', '"total": sum(values) + 1'))["obligations"]["O1"]
        self.assertEqual("FAIL", bad["outcome"], bad)
        self.assertEqual(["TEST_FAILURE"], bad["codes"])
        self.assertTrue(bad["detail"]["counterexamples"])

    def test_data_sampler_is_deterministic_bounded_and_covers_requested_edge_families(self):
        cfg = testing.campaign_config(7, 12, 5000, self.profile)
        self.assertEqual(cfg, canonical.loads(canonical.dumps(cfg)))
        self.assertTrue(all(type(n) is str for n in cfg["signed_grid"]))
        oracle = SimpleNamespace(symbols=lambda: {})
        formula = {"tag": "forall", "sort": {"record": "Input"}, "body": {"tag": "true"}}
        first = testing.Campaign(formula, self.profile, oracle, cfg, 7)
        second = testing.Campaign(formula, self.profile, oracle, cfg, 7)
        values = list(first.assignments())
        self.assertEqual(values, list(second.assignments()))
        self.assertLessEqual(len(values), 12 * cfg["max_generated_factor"])
        self.assertIn(-1, first._grid_values("Int"))
        self.assertIn(-(2**63), first._grid_values("Int"))
        self.assertIn("", first._grid_values("String"))
        self.assertIn("🙂", first._grid_values("String"))
        lists = first._grid_values({"list": "Int"})
        self.assertIn((), lists)
        self.assertTrue(any(len(xs) > 1 and len(set(xs)) == 1 for xs in lists))
        nested = first._grid_values({"list": {"list": "Int"}})
        self.assertTrue(any(xs and type(xs[0]) is tuple for xs in nested))

    def test_nested_generation_stops_before_exponential_value_allocation(self):
        cfg = testing.campaign_config(7, 20, 5000, self.profile)
        cfg["data_limits"]["max_value_nodes"] = 32
        sort = "Int"
        for _ in range(7):
            sort = {"list": sort}
        formula = {"tag": "forall", "sort": sort, "body": {"tag": "true"}}
        campaign = testing.Campaign(formula, self.profile, SimpleNamespace(symbols=lambda: {}), cfg, 7)
        with patch.object(campaign.rng, "choice", side_effect=lambda seq: seq[-1]), self.assertRaises(dsl.BudgetExceeded):
            campaign._value(sort, 0, [])
        cfg["data_limits"]["max_value_depth"] = 2
        exhausted = testing.Campaign(formula, self.profile, SimpleNamespace(symbols=lambda: {}), cfg, 7)
        self.assertEqual([], list(exhausted.assignments()))
        self.assertIn("budget", exhausted.generation_problem)

    def test_inner_infinite_domains_stay_unknown_and_reviewer_rejects_them(self):
        for sort in ("Int", "String", {"list": "Int"}, {"record": "Input"}):
            f = {"tag": "forall", "sort": sort, "body": {"tag": "true"}}
            evaluator = dsl.Evaluator(self.profile, {}, lambda *_: [0, 1])
            self.assertEqual(dsl.UNKNOWN, evaluator.formula(f, []))
            with self.subTest(sort=sort), self.assertRaises(rc._ReplayUnsupported):
                rc._decidable(f, self.profile)

    def test_sampled_legacy_antecedent_cannot_make_an_effective_passing_case(self):
        legacy = dsl.Profile.from_json({"profile_id": "old", "symbols": {}, "enums": {}, "predicates": {}})
        formula = {"tag": "implies", "left": {"tag": "forall", "sort": "Nat", "body": {"tag": "true"}},
                   "right": {"tag": "true"}}
        campaign = testing.Campaign(formula, legacy, SimpleNamespace(symbols=lambda: {}), testing.campaign_config(1, 20, 5000), 1)
        self.assertEqual(dsl.Truth(True, False), campaign.ev.formula(formula["left"], []))
        self.assertEqual("indeterminate", campaign.classify([])[0])

    def test_signed_subtraction_keeps_int_semantics_in_bounded_reviewer(self):
        evaluator = rc._BoundedEvaluator(self.profile, {}, lambda *_: [], deadline=time.monotonic() + 1)
        term = {"tag": "int_sub", "left": {"tag": "int", "value": "1"}, "right": {"tag": "int", "value": "3"}}
        self.assertEqual(-2, evaluator.term(term, []))
        natural = {"tag": "sub", "left": {"tag": "nat", "value": "1"}, "right": {"tag": "nat", "value": "3"}}
        self.assertEqual(0, evaluator.term(natural, []))

    def test_reviewer_data_syntax_is_profile_selected_and_still_rejects_unaccounted_calls(self):
        pkg = Package(self.root / "package")
        pkg.ensure("data-review-admission")
        fsutil.atomic_write(pkg.path("implementation") / "pipeline.py", SOURCE.encode())
        inv = pt.inventory(pkg.path("implementation"))
        inputs = SimpleNamespace(bytes=lambda path: path.read_bytes())
        rc._admit_python(pkg, inv, inputs, self.profile)
        with self.assertRaises(rc._ReplayUnsupported):
            rc._admit_python(pkg, inv, inputs)
        loop = ('def pipeline(data):\n    values = []\n    total = 0\n    for x in data["numbers"]:\n'
                '        if x >= data["threshold"]:\n            values.append(x * 2)\n            total += x * 2\n'
                '    return {"values": values, "total": total, "count": len(values), "label": data["label"]}\n')
        fsutil.atomic_write(pkg.path("implementation") / "pipeline.py", loop.encode())
        rc._admit_python(pkg, pt.inventory(pkg.path("implementation")), inputs, self.profile)
        for unsafe in ('def pipeline(data): return open("anything")\n', 'def pipeline(data): return data.keys()\n',
                       'def pipeline(data): return getattr(data, "__class__")\n'):
            fsutil.atomic_write(pkg.path("implementation") / "pipeline.py", unsafe.encode())
            with self.subTest(source=unsafe), self.assertRaises(rc._ReplayUnsupported):
                rc._admit_python(pkg, pt.inventory(pkg.path("implementation")), inputs, self.profile)

    def review_fixture(self, source):
        """Isolate real process replay; kernel provenance is covered separately by integration."""
        pkg = Package(self.root / "review-package")
        pkg.ensure("structured-review")
        fsutil.atomic_write(pkg.path("implementation") / "pipeline.py", source.encode())
        raw = self.profile.raw
        fsutil.write_json(contract.challenge_dir(pkg) / "profile.json", raw)
        package = dsl.make_package(pipeline_formula(), self.profile.profile_id, encoding=dsl.ENCODING_V2)
        payload = canonical.dumps(package)
        digest = canonical.digest(payload)
        fsutil.atomic_write(pkg.path("accepted") / "expressions" / (digest[7:] + ".json"), payload)
        ir = {"acceptance_certificate_ref": "accepted/acceptance.json", "obligations": {"O1": {
            "id": "O1", "revision": 1, "required": True, "role": "guarantee", "kind": "postcondition",
            "formal": {"representation": "contract_dsl", "formula_ref": "artifact:formula@" + digest, "statement_hash": ZERO}}}}
        fsutil.write_json(pkg.path("accepted_ir"), ir)
        fsutil.write_json(pkg.path("accepted") / "acceptance.json", {})
        ir_hash = canonical.digest_json(ir)
        fsutil.write_json(contract.challenge_dir(pkg) / "statements.json", {
            "statements": {"O1": {"semantic_closure": ["Data.pipeline"]}}, "declaration_hashes": {"Data.pipeline": ZERO}})
        binding = {"schema_version": "0.1", "artifact_kind": "implementation_bindings", "target": "python",
            "serialization_profile": pt.PROFILE_ID_V2, "helpers": [], "bindings": [{"binding_id": "B-pipeline", "symbol": "pipeline",
            "object": {"file": "pipeline.py", "qualname": "pipeline"}, "obligations": ["O1"]}]}
        fsutil.write_json(pkg.path("bridges") / "bindings.json", binding)
        claim = {"claim_id": "LINKED:O1@1", "obligation": "O1", "milestone": "LINKED", "applicable": True,
                 "required": True, "verifier": "verislop.python-linker"}
        fsutil.write_json(pkg.path("closure") / "implementation-claims.json", {
            "schema_version": "0.1", "artifact_kind": "implementation_claims", "claims": [claim], "bound_to": {"accepted_ir": ir_hash},
            "parameters": {"tier": 0, "target": "python", "endpoint": "test_campaign"}})
        inv = pt.inventory(pkg.path("implementation"))
        obj = inv.find("pipeline.py", "pipeline")
        spec = raw["symbols"]["pipeline"]
        fsutil.write_json(pkg.path("bridges") / "link.json", {
            "schema_version": "0.1", "artifact_kind": "link_record", "accepted_ir": ir_hash,
            "implementation_root": pkg.implementation_root(), "serialization_profile": pt.profile_doc(self.profile),
            "correspondence": "structural identity and coverage only; semantic correspondence is not established at this tier",
            "bindings": [{"binding_id": "B-pipeline", "symbol": "pipeline", "obligations": ["O1"], "serialization_profile": pt.PROFILE_ID_V2,
                "formal_declaration": {"lean_decl": "Data.pipeline", "decl_hash": ZERO, "args": spec["args"], "result": spec["result"]},
                "implementation_object": {"file": "pipeline.py", "qualname": "pipeline", "source_hash": obj["source_hash"],
                                          "file_hash": inv.files["pipeline.py"], "lineno": obj["lineno"]}}]})
        pkg.evidence.record(claim_id=claim["claim_id"], verifier_id="verislop.python-linker", status="PASS", scope=["isolated replay fixture"],
                            input_root=pkg.link_root(), result={"milestone_outcome": "PASS"}, invocation=["unit"])
        return pkg, ir, ir_hash

    def test_real_nested_reviewer_probe_confirms_only_actual_counterexample(self):
        value = dsl.record_v("Input", [(-3, 1, 1, 4), 1, "é🙂"])
        proposal = {"kind": "target_case", "obligation_id": "O1", "assignment": [pt.encode_arg(value, {"record": "Input"}, self.profile)]}
        for source, status in ((SOURCE, "NOT_REPRODUCED"), (SOURCE.replace('"total": sum(values)', '"total": sum(values) + 1'), "CONFIRMED")):
            pkg, ir, digest = self.review_fixture(source)
            with patch.object(rc, "verified_ir", return_value=(ir, digest, {}, [])), patch.object(contract, "frozen_json", return_value=self.profile.raw):
                result = rc.replay(pkg, "implementation", proposal)
            self.assertEqual(status, result["status"], result)
            self.assertTrue(result["observed"]["guard"])
            self.assertEqual(status == "NOT_REPRODUCED", result["observed"]["predicate"])
            self.assertEqual(proposal["assignment"], result["observed"]["calls"][0]["arguments"])

    def test_reviewer_binder_guidance_uses_exact_record_fields_and_wire_shape(self):
        pkg, ir, digest = self.review_fixture(SOURCE)
        with patch("verislop.export.verified_ir", return_value=(ir, digest, {}, [])), patch.object(contract, "frozen_json", return_value=self.profile.raw):
            guidance = review._target_case_binders(pkg, ["O1"])
        entry = guidance["obligations"]["O1"]
        self.assertEqual("supported", entry["status"])
        self.assertEqual(1, entry["assignment_arity"])
        self.assertEqual([{"record": "Input"}], entry["leading_universal_sorts"])
        wire = entry["assignment_example"][0]
        self.assertEqual({"numbers", "threshold", "label"}, set(wire["dict"]))
        self.assertEqual(dsl.record_v("Input", [(), 0, ""]), rc._decode(wire, {"record": "Input"}, self.profile))
        self.assertEqual([{"name": "numbers", "sort": {"list": "Int"}}, {"name": "threshold", "sort": "Int"}, {"name": "label", "sort": "String"}],
                         guidance["record_fields"]["Input"])


if __name__ == "__main__":
    unittest.main()
