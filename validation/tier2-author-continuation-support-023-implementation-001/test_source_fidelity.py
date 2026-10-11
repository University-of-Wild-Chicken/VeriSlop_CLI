"""Registered synthetic author-method controls and immutable source projections.

No actual agent, qualification, carrier, Lean, or private task data is used.
"""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
from types import SimpleNamespace
import unittest

from continuation_contract import POLICY
from test_continuation import SEED, GUARDS, build_ledger, complete_value, incomplete_value, wire

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / "preimages/validation/tier2-support-019-qualification-adapters-008"
HELPER = HERE / "continuation_contract.py"
HELPER_REF = {"path": str(HELPER.relative_to(ROOT)), "sha256": "sha256:" + hashlib.sha256(HELPER.read_bytes()).hexdigest()}

def load(name, path):
    definition = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(module)
    return module

def function(tree, class_name, name):
    parent = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == class_name)
    return next(item for item in parent.body if isinstance(item, ast.FunctionDef) and item.name == name)

def normalize_format(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "verislop.support023-single-fresh-author-evidence/1":
            node.value = "verislop.support019-single-fresh-author-evidence/1"

class CandidateSourceFidelityControls(unittest.TestCase):
    def test_13_reader_additional_whole_ast_projection_and_private_equality(self):
        for filename, classname, extension_size in (("predicate_reader.py", "Reader", 10), ("additional_predicates.py", "AdditionalPredicates", 7)):
            with self.subTest(source=filename):
                old = ast.parse((BASE / filename).read_bytes())
                new = ast.parse((HERE / filename).read_bytes())
                selected = function(new, classname, "fresh_author")
                start = next(index for index, node in enumerate(selected.body) if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "contract" for target in node.targets))
                extension = selected.body[start:start+extension_size]
                self.assertTrue(any(isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "turn_result" for target in node.targets) for node in extension))
                del selected.body[start:start+extension_size]
                normalize_format(new)
                self.assertEqual(ast.dump(new, include_attributes=False), ast.dump(old, include_attributes=False))
                # Whole method projection retains the exact private evaluator
                # equality conditions, marker expectations and both true EOFs.
                self.assertEqual(ast.dump(selected, include_attributes=False), ast.dump(function(old, classname, "fresh_author"), include_attributes=False))

    def test_14_assembler_whole_ast_projection_claims_and_counting(self):
        old = ast.parse((BASE / "assemble_ancillary_indexes.py").read_bytes())
        new = ast.parse((HERE / "assemble_ancillary_indexes.py").read_bytes())
        main = next(item for item in new.body if isinstance(item, ast.FunctionDef) and item.name == "main")
        branch = next(node for node in ast.walk(main) if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) and node.test.left.id == "kind")
        start = next(index for index, node in enumerate(branch.orelse) if isinstance(node, ast.Import) and node.names[0].name == "importlib.util")
        self.assertEqual(len(branch.orelse)-start, 11)
        del branch.orelse[start:]
        normalize_format(new)
        self.assertEqual(ast.dump(new, include_attributes=False), ast.dump(old, include_attributes=False))
        original = json.loads((HERE / "preimages/validation/tier2-support-019-qualification-plan-012/claims.json").read_bytes())
        candidate = json.loads((HERE / "candidate-claims.json").read_bytes())
        self.assertEqual(original["original_claims"], candidate["original_claims"])
        for left, right in zip(original["additional_claims"], candidate["additional_claims"]):
            if left["id"] not in ("Q019-07", "Q019-08"):
                self.assertEqual(left, right)
        changed = copy.deepcopy(candidate)
        for number in (6,7):
            changed["additional_claims"][number] = original["additional_claims"][number]
        self.assertEqual(changed, original)

    def author_case(self, class_kind, final_raw):
        index, blobs = build_ledger([final_raw])
        guards = dict(GUARDS, **{HELPER_REF["path"]: HELPER_REF["sha256"]})
        for turn in index["author_turns"]:
            turn["guards_before"] = dict(guards); turn["guards_after"] = dict(guards)
        index["fresh_fixture"] = {"synthetic_source_control": True}
        fixture = {"system": "public system", "user": "marker_expected public user"}
        expected = {"markers": ["marker_expected"], "field_roots": {"/"+key: "sha256:"+hashlib.sha256(fixture[key].encode()).hexdigest() for key in ("system","user")}, "field_eof": {"/system":True,"/user":True}, "field_chars": {"/"+key:len(fixture[key]) for key in ("system","user")}}
        raw = wire(expected)
        expected_ref = {"path":"SYNTHETIC_SOURCE_CONTROL_NO_ACTUAL_AGENT/evaluator.json","sha256":"sha256:"+hashlib.sha256(raw).hexdigest(),"byte_count":len(raw)}
        blobs[expected_ref["path"]] = raw; index["evaluator_expectations_ref"] = expected_ref
        literals = {"marker_pattern": "marker_[a-z]+", "expected_markers": ["marker_expected"], "source":{"path":"SYNTHETIC_source","sha256":"sha256:"+"d"*64}, "author_protocol":{"reconstruction_source":{"path":"SYNTHETIC_protocol","sha256":"sha256:"+"e"*64}}}
        config = {"author_contract":{"continuation_contract_source":dict(HELPER_REF)},"author_turn_policy":dict(POLICY)}
        if class_kind == "reader":
            module = load("support023_synthetic_reader", HERE / "predicate_reader.py")
            instance = module.Reader.__new__(module.Reader)
            instance.adapters = config; instance.hashes = guards
            instance.index = lambda kind:index; instance.bound = lambda doc:None
            instance.fresh_fixture = lambda ref:(fixture,{})
            instance.recipe_literals = lambda:literals; instance.author_message = lambda ref:SEED
            instance.fresh_ref = lambda ref:blobs[ref["path"]]
            instance.ref = lambda ref:HELPER.read_bytes()
            instance.path = lambda path:ROOT/path
        else:
            module = load("support023_synthetic_additional", HERE / "additional_predicates.py")
            instance = module.AdditionalPredicates()
            instance.config = dict(config,predicate_reader_carrier_literals="SYNTHETIC_literals")
            instance.hashes = dict(guards, **{"SYNTHETIC_protocol":"sha256:"+"e"*64})
            for turn in index["author_turns"]:
                turn["guards_before"] = dict(instance.hashes); turn["guards_after"] = dict(instance.hashes)
            instance.additional_index = lambda kind:index
            instance.carrier_fixture = lambda ref:(fixture,{})
            instance.additional_ref = lambda ref:blobs[ref["path"]]
            instance.additional_doc = lambda ref:json.loads(blobs[ref["path"]])
            instance.path = lambda path:path
            instance.registered = lambda path:path
            instance.document = lambda path:literals
            instance.read = lambda path,digest:b"SYNTHETIC" if path=="SYNTHETIC_source" else HELPER.read_bytes()
            protocol = SimpleNamespace(validate_literals=lambda *args:None,author_message=lambda *args:SEED)
            instance.module = lambda name,path:load(name,HELPER) if name=="support023_registered_continuation_contract" else protocol
            instance.canonical = SimpleNamespace(dumps=wire)
        return instance, module, expected

    def test_15_complete_wrong_answer_reaches_unchanged_private_rejection(self):
        wrong = wire(complete_value())
        for kind in ("reader","additional"):
            with self.subTest(reader=kind):
                instance, module, expected = self.author_case(kind, wrong)
                with self.assertRaisesRegex(ValueError, "LITERAL_FINAL_SYNTAX_MARKER_ROOT_TOTALS_EOF_MISMATCH|FRESH_LITERAL_FINAL_MARKERS_ROOTS_COUNTS_EOF_MISMATCH"):
                    instance.fresh_author()
                instance, module, expected = self.author_case(kind, wire(expected))
                result = instance.fresh_author()
                self.assertEqual(result["semantic_consumption"],"UNATTESTED")

    def test_16_active_helper_and_policy_binding_reject_changes(self):
        for kind in ("reader","additional"):
            instance, _, expected = self.author_case(kind,wire(complete_value()))
            config = instance.adapters if kind=="reader" else instance.config
            config["author_contract"]["continuation_contract_source"]["sha256"] = "sha256:"+"f"*64
            with self.assertRaisesRegex(ValueError,"CONTINUATION_HELPER_NOT_FROZEN"):
                instance.fresh_author()
            instance, _, _ = self.author_case(kind,wire(expected))
            config = instance.adapters if kind=="reader" else instance.config
            config["author_turn_policy"]["max_corrective_followups"] = 33
            with self.assertRaisesRegex(ValueError,"CONTINUATION_POLICY_NOT_FROZEN"):
                instance.fresh_author()

if __name__ == "__main__":
    unittest.main()
