"""Registered finite generic source controls, with no protocol execution."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "validation/tier2-carrier-context-support-019-implementation-004"
NEW = ROOT / "validation/tier2-support019-author-diagnostic-implementation-005"
ADAPTER_OLD = ROOT / "validation/tier2-support-019-qualification-adapters-006"
ADAPTER_NEW = ROOT / "validation/tier2-support-019-qualification-adapters-007"
PURE_OLD = ROOT / "validation/tier2-support019-core-drivers-003"
PURE_NEW = ROOT / "validation/tier2-support019-core-drivers-004"
PLAN_OLD = ROOT / "validation/tier2-support-019-qualification-plan-008"
PLAN_NEW = ROOT / "validation/tier2-support-019-qualification-plan-009"
HASH = "sha256:a56590eb051ebac28312031b157195caab0d747aa20ebc4557d70ff5b1b2921f"
OLD_HASH = "sha256:774081ab079b0bb9086479782d065c9e4b91c372ecce765c248b533c1c2b666a"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dump(node):
    return ast.dump(node, include_attributes=False)


def function(tree, name):
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def instruction_node(tree):
    return next(node.value for node in function(tree, "agent_message").body
                if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "instruction")


def without_literal(raw, node):
    lines = raw.splitlines(keepends=True)
    start = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
    end = sum(map(len, lines[:node.end_lineno - 1])) + node.end_col_offset
    return raw[:start] + b"<EXACT_ALLOWED_INSTRUCTION_LITERAL>" + raw[end:]


def wire(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def known_failure():
    return {"markers": [], "field_roots": {},
            "field_eof": {"/system": False, "/user": False},
            "field_chars": {"/system": 0, "/user": 0},
            "failure": {"format": "verislop.author-observed-failure/0.1", "trust": "UNATTESTED",
                        "stage": "HASH", "operation": None,
                        "observation": {"kind": "literal", "source": "PURE_EXCEPTION_RESPONSE",
                                        "scope": "visible_fragment", "text": "GENERIC_OWN_ERROR"},
                        "reproduction": {"template": "UNAVAILABLE", "view": None, "confirmation": None,
                                         "own_input_literal": None, "expected_observed_error_literal": None,
                                         "availability": "UNAVAILABLE"},
                        "self_critique": {"violated_check": "GENERIC_OWN_CHECK", "own_attempted_retry": None,
                                          "observed_retry_error_literal": None, "recovery": "FIXED_SOURCE_BLOCKED"}}}


def unknown_failure():
    value = known_failure()
    value["failure"].update(stage="UNKNOWN", observation={"kind": "unavailable", "reason": "NOT_EXPOSED"})
    value["failure"]["self_critique"] = {"violated_check": None, "own_attempted_retry": None,
                                           "observed_retry_error_literal": None, "recovery": "UNAVAILABLE"}
    return value


class IndependentControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_raw = (OLD / "bootstrap_tier2_carrier_view.py").read_bytes()
        cls.new_raw = (NEW / "bootstrap_tier2_carrier_view.py").read_bytes()
        cls.old = load_module("source_review_immutable004", OLD / "bootstrap_tier2_carrier_view.py")
        cls.new = load_module("source_review_immutable005", NEW / "bootstrap_tier2_carrier_view.py")
        cls.parser = load_module("source_review_closed_parser005", NEW / "diagnostic_failure_parser.py")
        cls.helper = load_module("source_review_unchanged006_reconstruction", ADAPTER_OLD / "author_protocol_reconstruction.py")
        cls.old_factory = load_module("source_review_factory004", OLD / "capture-amendment-003/collector_templates.py")
        cls.new_factory = load_module("source_review_factory005", NEW / "capture-amendment-003/collector_templates.py")
        cls.refs = [{"path": "/unrelated/source-only/ASCII", "sha256": "sha256:" + "1" * 64, "request_sha256": "sha256:" + "2" * 64},
                    {"path": "/unrelated/source-only/é🙂e\u0301", "sha256": "sha256:" + "3" * 64, "request_sha256": "sha256:" + "4" * 64},
                    {"path": '/unrelated/source-only/comma,quote"backslash\\', "sha256": "sha256:" + "5" * 64, "request_sha256": "sha256:" + "6" * 64}]

    def accepted(self, value, *, exposed_references=()):
        raw = wire(value)
        result = self.parser.parse_failure(raw, fixture_failure_allowed=True, exposed_references=exposed_references)
        self.assertEqual(result["report"], value)
        self.assertIs(result["success"], False)
        self.assertEqual(result["trust"], "UNATTESTED")
        self.assertEqual(result["qualification_claims_discharged"], [])
        self.assertEqual(result["historical_cause"], "UNAVAILABLE")
        self.assertEqual(result["literal_final_sha256"], "sha256:" + hashlib.sha256(raw).hexdigest())
        return result

    def rejected(self, value, code, **kwargs):
        raw = value if isinstance(value, (bytes, str)) else wire(value)
        with self.assertRaises(self.parser.DiagnosticSchemaError) as error:
            self.parser.parse_failure(raw, fixture_failure_allowed=True, **kwargs)
        self.assertEqual(str(error.exception), code)

    def test_IC005_01_carrier_exact_single_instruction_delta(self):
        a, b = ast.parse(self.old_raw), ast.parse(self.new_raw)
        old_literal, new_literal = instruction_node(a), instruction_node(b)
        self.assertTrue(new_literal.value.startswith(old_literal.value))
        self.assertEqual(new_literal.value[len(old_literal.value):], (NEW / "DIAGNOSTIC_INSTRUCTION_LITERAL.txt").read_text())
        self.assertEqual(without_literal(self.old_raw, old_literal), without_literal(self.new_raw, new_literal))
        new_literal.value = old_literal.value
        self.assertEqual(dump(a), dump(b))

    def test_IC005_02_factory_exact_hash_binding_delta(self):
        a = (OLD / "capture-amendment-003/collector_templates.py").read_bytes()
        b = (NEW / "capture-amendment-003/collector_templates.py").read_bytes()
        self.assertEqual(a.count(OLD_HASH.encode()), 1)
        self.assertEqual(a.replace(OLD_HASH.encode(), HASH.encode()), b)
        self.assertEqual(self.new_factory.CANDIDATE_SHA256, HASH)
        self.assertEqual(self.new_factory.CANDIDATE_PATH, NEW / "bootstrap_tier2_carrier_view.py")

    def test_IC005_03_pure_exact_two_binding_delta(self):
        a = (PURE_OLD / "verify_carrier_controls.py").read_bytes()
        b = (PURE_NEW / "verify_carrier_controls.py").read_bytes()
        old_path = "validation/tier2-carrier-context-support-019-implementation-004/bootstrap_tier2_carrier_view.py"
        new_path = "validation/tier2-support019-author-diagnostic-implementation-005/bootstrap_tier2_carrier_view.py"
        self.assertEqual(a.count(OLD_HASH.encode()), 1)
        self.assertEqual(a.count(old_path.encode()), 1)
        self.assertEqual(a.replace(OLD_HASH.encode(), HASH.encode()).replace(old_path.encode(), new_path.encode()), b)
        self.assertEqual(a, (PURE_NEW / "PREIMAGE_VERIFY_CARRIER_CONTROLS.py.txt").read_bytes())
        self.assertEqual((PURE_OLD / "WITNESS_SCHEMA.json").read_bytes(), (PURE_NEW / "WITNESS_SCHEMA.json").read_bytes())

    def test_IC005_04_materializer_exact_two_binding_delta(self):
        a = (PLAN_OLD / "materialize_registration.py").read_bytes()
        b = (PLAN_NEW / "materialize_registration.py").read_bytes()
        operand = b'adapters["adapter_revision"] == "006"'
        self.assertEqual(a.count(operand), 1)
        self.assertEqual(a.count(OLD_HASH.encode()), 1)
        self.assertEqual(a.replace(OLD_HASH.encode(), HASH.encode()).replace(operand, b'adapters["adapter_revision"] == "007"'), b)
        self.assertEqual(a, (PLAN_NEW / "preimages/tier2-support-019-qualification-plan-008/materialize_registration.py").read_bytes())

    def test_IC005_05_independent_message_and_unchanged_adapters(self):
        self.assertEqual((ADAPTER_OLD / "author_protocol_reconstruction.py").read_bytes(),
                         (ADAPTER_NEW / "author_protocol_reconstruction.py").read_bytes())
        extracted = self.helper.extract_schema(self.new_raw)
        current = json.loads((ADAPTER_NEW / "predicate-reader-carrier-literals.json").read_bytes())
        self.helper.validate_literals(self.new_raw, current)
        for reference in self.refs:
            expected = self.helper.author_message(extracted, reference)
            self.assertEqual(expected, self.new.agent_message(reference).encode("utf-8"))
            self.assertNotIn(b"observable-carrier-collector-result", expected)
        manifest = json.loads((ADAPTER_OLD / "hash-manifest.json").read_bytes())
        checked = 0
        for name in manifest["files"]:
            relative = Path(name).relative_to(ADAPTER_OLD.relative_to(ROOT)) if name.startswith("validation/") else Path(name)
            if relative.suffix == ".py" and len(relative.parts) == 1:
                self.assertEqual((ADAPTER_OLD / relative).read_bytes(), (ADAPTER_NEW / relative).read_bytes(), str(relative))
                checked += 1
        self.assertGreater(checked, 0)
        for name in ("predicate-reader-specification.json", "reconciliation-specification.json", "additional-witness-contract.json"):
            self.assertEqual((ADAPTER_OLD / name).read_bytes(), (ADAPTER_NEW / name).read_bytes(), name)

    def test_IC005_06_all_fixed_recipes_equal004(self):
        view = {"operation": "field", "selector": "/user", "start_char": 0, "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
        confirmation = {"chunk_id": "unrelated-own-chunk", "outer_output_intact": True}
        for reference in self.refs:
            for name, extra in (("initial_session_template", ()), ("next_session_template", (view,)),
                                ("author_initial_session_template", ()), ("author_next_session_template", (view,)),
                                ("confirm_session_template", (confirmation,)), ("hash_session_template", ())):
                self.assertEqual(getattr(self.old, name)(reference, *extra), getattr(self.new, name)(reference, *extra), name)
            for case in self.new_factory.CASE_IDS:
                self.assertEqual(self.old_factory.initial_collector_template(reference, case), self.new_factory.initial_collector_template(reference, case))
                self.assertEqual(self.old_factory.next_collector_template(reference, view, case), self.new_factory.next_collector_template(reference, view, case))
                if case in ("AC002-002", "AC002-003"):
                    self.assertEqual(self.old_factory.next_collector_template(reference, view, case, fault=True), self.new_factory.next_collector_template(reference, view, case, fault=True))

    def provided(self, template):
        value = known_failure()
        reproduction = value["failure"]["reproduction"]
        reproduction.update(template=template, availability="PROVIDED", expected_observed_error_literal="GENERIC_OWN_ERROR")
        if template == "FIRST":
            reproduction["view"] = {"operation": "inventory", "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
        elif template == "NEXT":
            reproduction["view"] = {"operation": "field", "selector": "/user", "start_char": 0,
                                    "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
        else:
            reproduction["own_input_literal"] = "Generic own literal é🙂e\u0301"
            if template == "CONFIRM":
                reproduction["confirmation"] = {"chunk_id": "generic-own-chunk", "outer_output_intact": False}
        return value

    def test_IC005_07_closed_provided_reproductions_remain_failure(self):
        for template in ("FIRST", "NEXT", "CONFIRM", "HASH", "FINAL_SCHEMA"):
            self.accepted(self.provided(template))

    def test_IC005_08_exact_reproduction_counterexamples(self):
        value = known_failure()
        value["failure"]["reproduction"]["availability"] = "PROVIDED"
        self.rejected(value, "PROVIDED_TEMPLATE_UNAVAILABLE")
        for template in ("FIRST", "NEXT"):
            value = self.provided(template)
            value["failure"]["reproduction"]["view"] = self.provided("NEXT" if template == "FIRST" else "FIRST")["failure"]["reproduction"]["view"]
            self.rejected(value, "PROVIDED_VIEW_TEMPLATE_MISMATCH")
        for template in ("FIRST", "NEXT", "CONFIRM", "HASH", "FINAL_SCHEMA"):
            value = self.provided(template)
            value["failure"]["reproduction"]["expected_observed_error_literal"] = None
            self.rejected(value, "PROVIDED_ERROR_UNAVAILABLE")
        for template in ("CONFIRM", "HASH", "FINAL_SCHEMA"):
            value = self.provided(template)
            value["failure"]["reproduction"]["own_input_literal"] = None
            self.rejected(value, "PROVIDED_OWN_INPUT_UNAVAILABLE")
        value = self.provided("CONFIRM")
        value["failure"]["reproduction"]["confirmation"] = None
        self.rejected(value, "PROVIDED_CONFIRMATION_UNAVAILABLE")
        value = self.provided("HASH")
        value["failure"]["reproduction"]["view"] = self.provided("NEXT")["failure"]["reproduction"]["view"]
        self.rejected(value, "PROVIDED_IRRELEVANT_VIEW")
        value = self.provided("NEXT")
        value["failure"]["reproduction"]["confirmation"] = {"chunk_id": "generic-own-chunk", "outer_output_intact": False}
        self.rejected(value, "PROVIDED_IRRELEVANT_CONFIRMATION")

    def test_IC005_09_honest_unknown_and_invented_details(self):
        self.accepted(unknown_failure())
        for field, invented in (("stage", "NEXT_USER"), ("operation", {"chunk_id": None, "selector": "/user", "start_char": 9,
                                                                      "output_cap_bytes": None, "metadata_reserve_bytes": None})):
            value = unknown_failure()
            value["failure"][field] = invented
            self.rejected(value, "UNKNOWN_FAILURE_INVENTED_DETAILS")
        value = unknown_failure()
        value["failure"]["self_critique"]["violated_check"] = "invented-check"
        self.rejected(value, "UNKNOWN_FAILURE_INVENTED_DETAILS")
        value = unknown_failure()
        value["failure"]["reproduction"] = self.provided("NEXT")["failure"]["reproduction"]
        self.rejected(value, "UNKNOWN_FAILURE_INVENTED_DETAILS")

    def test_IC005_10_closed_authority_json_and_type_counterexamples(self):
        value = known_failure()
        value.update(markers=["generic-marker"], field_roots={"/system": "sha256:" + "a" * 64, "/user": "sha256:" + "b" * 64},
                     field_eof={"/system": True, "/user": True}, field_chars={"/system": 12, "/user": 34})
        self.accepted(value)
        native = {key: item for key, item in value.items() if key != "failure"}
        self.rejected(native, "NOT_CLOSED_DIAGNOSTIC_FAILURE_BRANCH")
        with self.assertRaises(self.parser.DiagnosticSchemaError) as error:
            self.parser.parse_failure(wire(value))
        self.assertEqual(str(error.exception), "FIXTURE_FAILURE_BRANCH_NOT_AUTHORIZED")
        cases = []
        item = known_failure(); item["unexpected"] = True; cases.append((item, "NOT_CLOSED_DIAGNOSTIC_FAILURE_BRANCH"))
        item = known_failure(); item["failure"]["trust"] = "ATTESTED"; cases.append((item, "FAILURE_AUTHORITY_OVERCLAIM"))
        item = known_failure(); item["field_chars"]["/user"] = True; cases.append((item, "INVALID_PARTIAL_TOTAL"))
        item = self.provided("NEXT"); item["failure"]["reproduction"]["view"]["start_char"] = True; cases.append((item, "INVALID_VIEW_CURSOR"))
        for item, code in cases:
            self.rejected(item, code)
        self.rejected(b'{"failure":null,"failure":null}', "DUPLICATE_JSON_KEY")
        self.rejected(b'{"number":9007199254740992}', "UNSAFE_JSON_INTEGER")
        self.rejected(b'{"number":1.0}', "UNSUPPORTED_JSON_NUMBER")
        self.rejected(b'{"string":"\\ud800"}', "INVALID_UNICODE")
        self.rejected(b'\xef\xbb\xbf{}', "UNSUPPORTED_JSON_BOM")
        self.rejected(b'\xff', "INVALID_UTF8")
        ref = {"path": "/unrelated/already-exposed", "sha256": "sha256:" + "c" * 64, "byte_count": 4}
        item = known_failure()
        item["failure"]["observation"] = {"kind": "reference", "source": "OUTER_ACTUAL_RESPONSE", "scope": "visible_fragment", "reference": ref}
        self.accepted(item, exposed_references=[ref])
        self.rejected(item, "REFERENCE_NOT_EXPOSED_ALLOWLIST_MEMBER")
        self.rejected(item, "DUPLICATE_REFERENCE_ALLOWLIST", exposed_references=[ref, ref])


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
