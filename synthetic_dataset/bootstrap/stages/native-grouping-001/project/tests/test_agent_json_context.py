"""Authored malformed-response and lossless accepted-context regressions; no PoC scoring."""
import copy
import json
import unittest
from verislop import agents, canonical


class ResponseObjectTests(unittest.TestCase):
    def test_escaped_quotes_backslashes_and_braces_remain_in_the_outer_object(self):
        obj = {"lean_source": 'def text := "{"\n-- "quoted }" \\ tail\n',
               "formalization": {"bindings": [], "message": "é🙂"}}
        encoded = json.dumps(obj)
        for text in (encoded, "Explanation\n" + encoded + "\nDone.", "```json\n" + encoded + "\n```"):
            self.assertEqual(obj, agents.extract_json(text))

    def test_duplicate_outer_key_reports_exact_error_without_selecting_records(self):
        text = '{"records":{"Input":{"fields":[]}},"right":1,"right":2}'
        with self.assertRaisesRegex(ValueError, "duplicate object key: 'right'"):
            agents.extract_json(text)

    def test_malformed_outer_and_unterminated_response_never_promote_a_valid_child(self):
        for text in ('{"records":{"Input":{}},"broken":}', '{"records":{"Input":{}}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                agents.extract_json(text)

    def test_noncanonical_numbers_are_not_hidden_by_nested_valid_data(self):
        for value in ('9007199254740992', 'NaN', '1.5'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                agents.extract_json('{"records":{},"value":' + value + '}')


class AcceptedContextTests(unittest.TestCase):
    def test_shared_formula_packages_round_trip_every_obligation_and_dependency(self):
        shared = {"encoding": "fixture", "formula": {"tag": "true"}}
        rows = {"G1": {"formula_package": shared, "role": "guarantee", "dependencies": ["A1"], "revision": 1},
                "G2": {"formula_package": copy.deepcopy(shared), "role": "guarantee", "dependencies": [], "revision": 2},
                "G3": {"formula_package": {"encoding": "fixture", "formula": {"tag": "false"}},
                       "role": "guarantee", "dependencies": ["G1"], "revision": 1}}
        original = copy.deepcopy(rows)
        packed = canonical.loads(canonical.dumps(agents._python_prompt_formulas(rows)))
        self.assertEqual(original, rows)
        self.assertEqual(set(rows), set(packed["obligations"]))
        self.assertEqual(2, len(packed["formula_packages"]))
        for oid, row in packed["obligations"].items():
            reference = row["formula_package_ref"]
            package = packed["formula_packages"][reference]
            self.assertEqual(reference, canonical.digest_json(package))
            restored = {k: v for k, v in row.items() if k != "formula_package_ref"}
            restored["formula_package"] = package
            self.assertEqual(rows[oid], restored)


if __name__ == "__main__":
    unittest.main()
