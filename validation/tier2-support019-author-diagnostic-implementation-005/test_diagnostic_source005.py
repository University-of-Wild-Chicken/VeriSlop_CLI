"""Unrelated pure source controls; no producer message, VIEW or runtime calls."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OLD = REPO / "validation/tier2-carrier-context-support-019-implementation-004"
ADAPTER = REPO / "validation/tier2-support-019-qualification-adapters-006"
HELPER_SHA = "bd71acc4808d3524e3c793e0a3b899d3c264f2192ff82e75f3bb060c3422a897"


def module(path, name, required_sha=None):
    if required_sha is not None:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == required_sha
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


PARSER = module(HERE / "diagnostic_failure_parser.py", "diagnostic005")
HELPER = module(ADAPTER / "author_protocol_reconstruction.py", "independent005", HELPER_SHA)


def report():
    return {
        "markers": [], "field_roots": {},
        "field_eof": {"/system": False, "/user": False},
        "field_chars": {"/system": 0, "/user": 0},
        "failure": {
            "format": "verislop.author-observed-failure/0.1", "trust": "UNATTESTED",
            "stage": "NEXT_USER", "operation": {"chunk_id": "own-generic-chunk", "selector": "/user",
                "start_char": 0, "output_cap_bytes": 4096, "metadata_reserve_bytes": 2048},
            "observation": {"kind": "literal", "source": "PURE_EXCEPTION_RESPONSE",
                            "text": "GENERIC_EXPOSED_ERROR", "scope": "visible_fragment"},
            "reproduction": {"template": "NEXT", "view": {"operation": "field", "selector": "/user",
                "start_char": 0, "output_cap_bytes": 4096, "metadata_reserve_bytes": 2048},
                "confirmation": None, "own_input_literal": None,
                "expected_observed_error_literal": "GENERIC_EXPOSED_ERROR", "availability": "PROVIDED"},
            "self_critique": {"violated_check": "GENERIC_EXPOSED_CHECK", "own_attempted_retry": None,
                "observed_retry_error_literal": None, "recovery": "FIXED_SOURCE_BLOCKED"}
        }
    }


def unknown_report():
    value = report()
    failure = value["failure"]
    failure.update(stage="UNKNOWN", operation=None, observation={"kind": "unavailable", "reason": "NOT_EXPOSED"})
    failure["reproduction"] = {"template": "UNAVAILABLE", "view": None, "confirmation": None,
        "own_input_literal": None, "expected_observed_error_literal": None, "availability": "UNAVAILABLE"}
    failure["self_critique"] = {"violated_check": None, "own_attempted_retry": None,
        "observed_retry_error_literal": None, "recovery": "UNAVAILABLE"}
    return value


def raw(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class FailureSyntax(unittest.TestCase):
    def accept(self, value, **kwargs):
        return PARSER.parse_failure(raw(value), fixture_failure_allowed=True, **kwargs)

    def reject(self, value, code, **kwargs):
        with self.assertRaises(PARSER.DiagnosticSchemaError) as caught:
            self.accept(value, **kwargs)
        self.assertEqual(str(caught.exception), code)

    def reject_raw(self, value, code):
        with self.assertRaises(PARSER.DiagnosticSchemaError) as caught:
            PARSER.parse_failure(value, fixture_failure_allowed=True)
        self.assertEqual(str(caught.exception), code)

    def test_01_literal_failure_keeps_exact_hash_and_no_authority(self):
        value = report()
        data = b" \n" + raw(value) + b"\n"
        evidence = PARSER.parse_failure(data, fixture_failure_allowed=True)
        self.assertEqual(evidence["report"], value)
        self.assertEqual(evidence["literal_final_sha256"], "sha256:" + hashlib.sha256(data).hexdigest())
        self.assertIs(evidence["success"], False)
        self.assertEqual(evidence["trust"], "UNATTESTED")
        self.assertEqual(evidence["qualification_claims_discharged"], [])
        self.assertEqual(evidence["historical_cause"], "UNAVAILABLE")

    def test_02_complete_looking_failure_never_becomes_success(self):
        value = report()
        value.update(markers=["GENERIC_START", "GENERIC_END"],
            field_roots={"/system": "sha256:" + "a" * 64, "/user": "sha256:" + "b" * 64},
            field_eof={"/system": True, "/user": True}, field_chars={"/system": 8, "/user": 400001})
        value["failure"]["observation"]["scope"] = "complete"
        evidence = self.accept(value)
        self.assertIs(evidence["success"], False)
        self.assertEqual(evidence["trust"], "UNATTESTED")
        self.assertEqual(evidence["qualification_claims_discharged"], [])

    def test_03_native_success_and_unauthorized_failure_rejected(self):
        value = report()
        del value["failure"]
        self.reject(value, "NOT_CLOSED_DIAGNOSTIC_FAILURE_BRANCH")
        with self.assertRaisesRegex(PARSER.DiagnosticSchemaError, "^FIXTURE_FAILURE_BRANCH_NOT_AUTHORIZED$"):
            PARSER.parse_failure(raw(report()))
        with self.assertRaisesRegex(PARSER.DiagnosticSchemaError, "^INVALID_FIXTURE_PERMISSION_TYPE$"):
            PARSER.parse_failure(raw(report()), fixture_failure_allowed=1)

    def test_04_unknown_is_honest_unavailable_evidence(self):
        value = unknown_report()
        evidence = self.accept(value)
        self.assertEqual(evidence["report"], value)
        self.assertEqual(evidence["historical_cause"], "UNAVAILABLE")
        value["failure"]["reproduction"]["own_input_literal"] = "Actually retained incomplete own data"
        self.assertIs(self.accept(value)["success"], False)

    def test_05_unknown_cannot_invent_stage_cursor_or_check(self):
        for field, replacement in [("stage", "HASH"), ("operation", report()["failure"]["operation"]),
                                   ("self_critique", report()["failure"]["self_critique"])]:
            with self.subTest(field=field):
                value = unknown_report()
                value["failure"][field] = replacement
                self.reject(value, "UNKNOWN_FAILURE_INVENTED_DETAILS")
        value = report()
        value["failure"]["stage"] = "UNKNOWN"
        self.reject(value, "UNKNOWN_FAILURE_INVENTED_DETAILS")

    def test_06_closed_keys_and_authority_overclaim(self):
        value = report(); value["failure"]["trust"] = "PROVED"
        self.reject(value, "FAILURE_AUTHORITY_OVERCLAIM")
        value = report(); value["extra"] = 0
        self.reject(value, "NOT_CLOSED_DIAGNOSTIC_FAILURE_BRANCH")
        value = report(); value["failure"]["trace"] = "invented"
        self.reject(value, "INVALID_FAILURE_OBJECT")
        value = report(); del value["failure"]["observation"]["scope"]
        self.reject(value, "INVALID_OBSERVATION")
        value = report(); value["failure"]["operation"] = {"chunk_id,selector,start_char,output_cap_bytes,metadata_reserve_bytes": None}
        self.reject(value, "INVALID_OWN_OPERATION")

    def test_07_observation_enum_and_scope_closed(self):
        for key, replacement, code in [("source", "HIDDEN_MODEL_TRACE", "INVALID_OBSERVATION_SOURCE"),
                                      ("scope", "attested", "INVALID_OBSERVATION_SCOPE"),
                                      ("kind", "inferred", "INVALID_OBSERVATION_KIND")]:
            with self.subTest(key=key):
                value = report(); value["failure"]["observation"][key] = replacement
                self.reject(value, code)

    def test_08_reference_exact_exposed_membership(self):
        ref = {"path": "own-exposed/generic.json", "sha256": "sha256:" + "c" * 64, "byte_count": 12}
        value = report(); value["failure"]["observation"] = {"kind": "reference", "source": "OUTER_ACTUAL_RESPONSE",
            "reference": ref, "scope": "visible_fragment"}
        self.assertIs(self.accept(value, exposed_references=[ref])["success"], False)
        self.reject(value, "REFERENCE_NOT_EXPOSED_ALLOWLIST_MEMBER")
        for key, replacement in [("path", "future/unexposed.json"), ("sha256", "sha256:" + "d" * 64), ("byte_count", 13)]:
            with self.subTest(key=key):
                changed = copy.deepcopy(value); changed["failure"]["observation"]["reference"][key] = replacement
                self.reject(changed, "REFERENCE_NOT_EXPOSED_ALLOWLIST_MEMBER", exposed_references=[ref])
        self.reject(value, "DUPLICATE_REFERENCE_ALLOWLIST", exposed_references=[ref, ref])
        changed = copy.deepcopy(value); changed["failure"]["observation"]["reference"]["byte_count"] = True
        self.reject(changed, "INVALID_EXPOSED_REFERENCE", exposed_references=[ref])

    def test_09_partial_results_exact_types(self):
        for mutate, code in [
            (lambda v: v["field_chars"].update({"/user": True}), "INVALID_PARTIAL_TOTAL"),
            (lambda v: v["field_eof"].update({"/user": 1}), "INVALID_PARTIAL_EOF_FLAG"),
            (lambda v: v["field_roots"].update({"/other": "sha256:" + "a" * 64}), "INVALID_PARTIAL_ROOTS"),
            (lambda v: v["field_roots"].update({"/user": "sha256:" + "A" * 64}), "INVALID_PARTIAL_ROOT"),
            (lambda v: v["markers"].append(""), "INVALID_PARTIAL_MARKER")]:
            with self.subTest(code=code):
                value = report(); mutate(value); self.reject(value, code)

    def test_10_operation_bounds_and_nullable_fields(self):
        value = report()
        value["failure"]["operation"] = dict.fromkeys(value["failure"]["operation"])
        self.assertIs(self.accept(value)["success"], False)
        for key, replacement, code in [("start_char", True, "INVALID_OWN_CURSOR"), ("start_char", -1, "INVALID_OWN_CURSOR"),
            ("selector", "/unknown", "INVALID_OWN_SELECTOR"), ("output_cap_bytes", 255, "INVALID_OWN_CAP"),
            ("metadata_reserve_bytes", 4096, "INVALID_OWN_RESERVE")]:
            with self.subTest(key=key, replacement=replacement):
                value = report(); value["failure"]["operation"][key] = replacement; self.reject(value, code)

    def test_11_closed_view_rejects_extra_bool_and_bad_reserve(self):
        for key, replacement, code in [("extra", 0, "INVALID_CLOSED_VIEW"), ("start_char", True, "INVALID_VIEW_CURSOR"),
            ("output_cap_bytes", True, "INVALID_VIEW_CAP"), ("metadata_reserve_bytes", 4096, "INVALID_VIEW_RESERVE")]:
            with self.subTest(key=key):
                value = report(); value["failure"]["reproduction"]["view"][key] = replacement; self.reject(value, code)

    def test_12_closed_confirmation_requires_real_boolean(self):
        value = report(); reproduction = value["failure"]["reproduction"]
        reproduction.update(template="CONFIRM", view=None, confirmation={"chunk_id": "own-chunk", "outer_output_intact": False}, own_input_literal="retained own pending data")
        self.assertIs(self.accept(value)["success"], False)
        reproduction["confirmation"]["outer_output_intact"] = 0
        self.reject(value, "INVALID_CONFIRMATION_FLAG")
        reproduction["confirmation"]["outer_output_intact"] = True
        reproduction["confirmation"]["extra"] = 0
        self.reject(value, "INVALID_CLOSED_CONFIRMATION")

    def test_13_provided_null_and_template_view_mismatch_counterexamples(self):
        value = report(); value["failure"]["reproduction"] = unknown_report()["failure"]["reproduction"]
        value["failure"]["reproduction"]["availability"] = "PROVIDED"
        self.reject(value, "PROVIDED_TEMPLATE_UNAVAILABLE")
        value = report(); value["failure"]["reproduction"]["template"] = "FIRST"
        self.reject(value, "PROVIDED_VIEW_TEMPLATE_MISMATCH")
        value = report(); value["failure"]["reproduction"]["view"] = {"operation": "inventory", "output_cap_bytes": 4096, "metadata_reserve_bytes": 2048}
        self.reject(value, "PROVIDED_VIEW_TEMPLATE_MISMATCH")
        value = report(); value["failure"]["reproduction"]["view"] = None
        self.reject(value, "PROVIDED_VIEW_TEMPLATE_MISMATCH")

    def test_14_provided_requires_error_and_needed_own_input(self):
        for error in (None, ""):
            value = report(); value["failure"]["reproduction"]["expected_observed_error_literal"] = error
            self.reject(value, "PROVIDED_ERROR_UNAVAILABLE")
        for template in ("HASH", "FINAL_SCHEMA", "CONFIRM"):
            value = report(); reproduction = value["failure"]["reproduction"]
            reproduction.update(template=template, view=None)
            self.reject(value, "PROVIDED_OWN_INPUT_UNAVAILABLE")
        value = report(); reproduction = value["failure"]["reproduction"]
        reproduction.update(template="CONFIRM", view=None, own_input_literal="own pending")
        self.reject(value, "PROVIDED_CONFIRMATION_UNAVAILABLE")

    def test_15_provided_template_specific_positive_and_irrelevant_fields(self):
        for template in ("FIRST", "HASH", "FINAL_SCHEMA"):
            value = report(); reproduction = value["failure"]["reproduction"]
            reproduction["template"] = template
            if template == "FIRST":
                reproduction["view"] = {"operation": "inventory", "output_cap_bytes": 4096, "metadata_reserve_bytes": 2048}
            else:
                reproduction.update(view=None, own_input_literal="own accepted complete data")
            self.assertIs(self.accept(value)["success"], False)
        value = report(); value["failure"]["reproduction"]["confirmation"] = {"chunk_id": "own", "outer_output_intact": True}
        self.reject(value, "PROVIDED_IRRELEVANT_CONFIRMATION")
        value = report(); value["failure"]["reproduction"].update(template="HASH", own_input_literal="own data")
        self.reject(value, "PROVIDED_IRRELEVANT_VIEW")

    def test_16_retry_is_closed_data_not_arbitrary_source(self):
        value = report(); value["failure"]["self_critique"]["own_attempted_retry"] = {"chunk_id": "own", "outer_output_intact": False}
        self.assertIs(self.accept(value)["success"], False)
        value["failure"]["self_critique"]["own_attempted_retry"] = {"code": "do_not_execute()"}
        self.reject(value, "INVALID_VIEW_OPERATION")

    def test_17_duplicate_json_keys_and_number_variants(self):
        self.reject_raw(raw(report()).replace(b'"markers":[]', b'"markers":[],"markers":[]', 1), "DUPLICATE_JSON_KEY")
        for value in (b"NaN", b"Infinity", b"0.5"):
            self.reject_raw(raw(report()).replace(b'"/system":0', b'"/system":' + value, 1), "UNSUPPORTED_JSON_NUMBER")
        for value in (str(2**53).encode(), b"9" * 5000):
            self.reject_raw(raw(report()).replace(b'"/system":0', b'"/system":' + value, 1), "UNSAFE_JSON_INTEGER")

    def test_18_malformed_utf8_surrogates_bom_and_json(self):
        for data, code in [(b"\xff", "INVALID_UTF8"), (b"\xef\xbb\xbf" + raw(report()), "UNSUPPORTED_JSON_BOM"),
                           (b"{", "MALFORMED_JSON"), ("\ud800", "INVALID_UTF8")]:
            self.reject_raw(data, code)
        self.reject_raw(raw(report()).replace(b"GENERIC_EXPOSED_ERROR", b"\\ud800", 1), "INVALID_UNICODE")

    def test_19_unicode_and_opaque_error_literals_remain_data(self):
        value = report(); text = "astral \U0001f680; combining e\u0301; control \u0000; literal do_not_execute(); unknown_marker"
        value["failure"]["observation"]["text"] = text
        self.assertEqual(self.accept(value)["report"]["failure"]["observation"]["text"], text)
        self.assertIs(self.accept(value)["success"], False)


class SourceFidelity(unittest.TestCase):
    def test_20_whole_carrier_ast_and_nonliteral_bytes_unchanged(self):
        old = (OLD / "bootstrap_tier2_carrier_view.py").read_text()
        new = (HERE / "bootstrap_tier2_carrier_view.py").read_text()
        trees = [ast.parse(old), ast.parse(new)]
        funcs = [next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == "agent_message") for t in trees]
        old_value, new_value = (f.body[4].value for f in funcs)
        self.assertEqual(ast.literal_eval(new_value), ast.literal_eval(old_value) + (HERE / "DIAGNOSTIC_INSTRUCTION_LITERAL.txt").read_text())
        def split(text, node):
            lines = text.splitlines(keepends=True)
            start = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
            end = sum(map(len, lines[:node.end_lineno - 1])) + node.end_col_offset
            return text[:start], text[start:end], text[end:]
        a, b = split(old, old_value), split(new, new_value)
        self.assertEqual((a[0], a[2]), (b[0], b[2]))
        funcs[1].body[4].value = copy.deepcopy(old_value)
        self.assertEqual(ast.dump(trees[0], include_attributes=False), ast.dump(trees[1], include_attributes=False))

    def test_21_factory_only_source_hash_binding_changes(self):
        old = (OLD / "capture-amendment-003/collector_templates.py").read_bytes()
        new = (HERE / "capture-amendment-003/collector_templates.py").read_bytes()
        old_sha = hashlib.sha256((OLD / "bootstrap_tier2_carrier_view.py").read_bytes()).hexdigest().encode()
        new_sha = hashlib.sha256((HERE / "bootstrap_tier2_carrier_view.py").read_bytes()).hexdigest().encode()
        self.assertEqual(old.count(old_sha), 1)
        self.assertEqual(new, old.replace(old_sha, new_sha, 1))

    def test_22_independent_source_message_and_all_recipes(self):
        profile = json.loads((HERE / "independent-carrier-literals.json").read_text())
        old_profile = json.loads((ADAPTER / "predicate-reader-carrier-literals.json").read_text())
        HELPER.validate_literals((HERE / "bootstrap_tier2_carrier_view.py").read_bytes(), profile)
        HELPER.validate_literals((OLD / "bootstrap_tier2_carrier_view.py").read_bytes(), old_profile)
        ref = {"path": "unrelated/generic ' quoted \U0001f680.json", "sha256": "sha256:" + "1" * 64, "request_sha256": "sha256:" + "2" * 64}
        self.assertEqual(HELPER.recipes(profile, ref), HELPER.recipes(old_profile, ref))
        old_message = HELPER.author_message(old_profile, ref)
        old_instruction = old_profile["author_protocol"]["instruction"].encode()
        new_instruction = profile["author_protocol"]["instruction"].encode()
        anchor = old_instruction + b"\nCARRIER:\n"
        self.assertEqual(old_message.count(anchor), 1)
        self.assertEqual(HELPER.author_message(profile, ref), old_message.replace(anchor, new_instruction + b"\nCARRIER:\n", 1))

    def test_23_independent_reconstruction_rejects_tampering(self):
        source = (HERE / "bootstrap_tier2_carrier_view.py").read_bytes()
        profile = json.loads((HERE / "independent-carrier-literals.json").read_text())
        changed = copy.deepcopy(profile); changed["author_protocol"]["instruction"] += "unregistered policy"
        with self.assertRaisesRegex(ValueError, "^AUTHOR_PROTOCOL_SCHEMA_NOT_SOURCE_DERIVED$"):
            HELPER.validate_literals(source, changed)
        with self.assertRaisesRegex(ValueError, "^AUTHOR_SOURCE_HASH_MISMATCH$"):
            HELPER.validate_literals(source + b"\n", profile)
        changed = copy.deepcopy(profile); changed["constants"]["READER_SOURCE"] += "\n"
        with self.assertRaisesRegex(ValueError, "^AUTHOR_LITERAL_OR_AST_MISMATCH:constants$"):
            HELPER.validate_literals(source, changed)

    def test_24_fixed_collector_recipes_remain_byte_exact(self):
        old = module(OLD / "capture-amendment-003/collector_templates.py", "old_fixed_factory005")
        new = module(HERE / "capture-amendment-003/collector_templates.py", "new_fixed_factory005")
        ref = {"path": "unrelated/generic.json", "sha256": "sha256:" + "1" * 64, "request_sha256": "sha256:" + "2" * 64}
        self.assertEqual(old.initial_collector_template(ref), new.initial_collector_template(ref))
        self.assertEqual(old.next_collector_template(ref), new.next_collector_template(ref))
        for case in ("AC002-002", "AC002-003"):
            self.assertEqual(old.next_collector_template(ref, old.FAULT_VIEW, case, fault=True),
                             new.next_collector_template(ref, new.FAULT_VIEW, case, fault=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
