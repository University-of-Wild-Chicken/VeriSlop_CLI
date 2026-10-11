"""Finite unrelated string/schema source controls; no qualification/model/view.

The producer module is used only as a source-only comparison oracle for generic
recipe strings in development. Runtime reconstruction never imports its APIs.
No evaluator expected reply, actual task fixture or proof candidate is read.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


protocol = module(HERE / "author_protocol_reconstruction.py", "source_controls_reconstruction006")
SOURCE_PATH = ROOT / "validation/tier2-carrier-context-support-019-implementation-004/bootstrap_tier2_carrier_view.py"
SOURCE = SOURCE_PATH.read_bytes()
producer = module(SOURCE_PATH, "source_controls_producer004")
LITERALS = json.loads((HERE / "predicate-reader-carrier-literals.json").read_text())
REFERENCE = {"path": "/synthetic/unrelated-own.json", "sha256": "sha256:" + "a" * 64,
             "request_sha256": "sha256:" + "b" * 64}


class AuthorReconstructionSourceControls(unittest.TestCase):
    def test_accepted_source_literal_schema_and_all18_function_asts(self):
        protocol.validate_literals(SOURCE, LITERALS)
        self.assertEqual(len(LITERALS["function_ast_hashes"]), 18)
        self.assertEqual(len(LITERALS["constants"]), 6)
        self.assertEqual(LITERALS["author_protocol"]["reconstruction_source"]["sha256"], protocol.sha((HERE / "author_protocol_reconstruction.py").read_bytes()))

    def test_exact_four_author_and_two_legacy_recipes_and_message(self):
        protocol.validate_literals(SOURCE, LITERALS)
        actual = protocol.recipes(LITERALS, REFERENCE)
        expected = {"legacy_first": producer.initial_session_template(REFERENCE), "legacy_next": producer.next_session_template(REFERENCE),
                    "author_first": producer.author_initial_session_template(REFERENCE), "author_next": producer.author_next_session_template(REFERENCE),
                    "confirm": producer.confirm_session_template(REFERENCE), "hash": producer.hash_session_template(REFERENCE)}
        self.assertEqual(actual, expected)
        self.assertEqual(protocol.author_message(LITERALS, REFERENCE), producer.agent_message(REFERENCE).encode())

    def test_exact_unicode_quotes_newlines_and_code_text_in_own_reference(self):
        paths = ["/synthetic/é😀𝄞\u2028'\"\\\n/own.json",
                 "/synthetic/text(await tools.exec_command({cmd, max_output_tokens: 16384}));/own.json",
                 "/synthetic/observable-carrier-collector-result/own.json"]
        for path in paths:
            with self.subTest(path=path):
                ref = {**REFERENCE, "path": path}
                self.assertEqual(protocol.author_message(LITERALS, ref), producer.agent_message(ref).encode())
                self.assertEqual(protocol.recipes(LITERALS, ref)["author_first"], producer.author_initial_session_template(ref))

    def test_explicit_next_cursor_and_same_cursor_smaller_retry_byte_exact(self):
        for start, cap in ((0, 8192), (17, 8192), (17, 4096)):
            view = {"operation": "field", "selector": "/user", "start_char": start,
                    "output_cap_bytes": cap, "metadata_reserve_bytes": 2048}
            self.assertEqual(protocol.recipes(LITERALS, REFERENCE, view=view)["author_next"], producer.author_next_session_template(REFERENCE, view))

    def test_explicit_confirmation_bytes_and_closed_schema(self):
        for intact in (True, False):
            closed = {"chunk_id": "generic-own-chunk", "outer_output_intact": intact}
            self.assertEqual(protocol.recipes(LITERALS, REFERENCE, confirmation=closed)["confirm"], producer.confirm_session_template(REFERENCE, closed))
        for closed in ({"chunk_id": "generic-own-chunk", "outer_output_intact": 1},
                       {"chunk_id": "", "outer_output_intact": True},
                       {"chunk_id": "generic-own-chunk", "outer_output_intact": True, "advance": 1}):
            with self.subTest(closed=closed), self.assertRaises(ValueError):
                protocol.recipes(LITERALS, REFERENCE, confirmation=closed)

    def test_unsafe_or_extra_view_schema_rejected(self):
        ordinary = {"operation": "field", "selector": "/user", "start_char": 0, "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
        for name, value in (("start_char", True), ("start_char", 2**53), ("selector", "/other"),
                            ("output_cap_bytes", 9000), ("unexpected", "quoted code")):
            with self.subTest(name=name), self.assertRaises(ValueError):
                protocol.recipes(LITERALS, REFERENCE, view={**ordinary, name: value})

    def test_tampered_source_constant_function_hash_instruction_or_transform_rejected(self):
        changes = [(["constants", "CHECKPOINT_VALIDATOR_SOURCE"], "modified"),
                   (["function_ast_hashes", "agent_message"], "sha256:" + "0" * 64),
                   (["author_protocol", "instruction"], "modified"),
                   (["author_protocol", "message_transforms"], []),
                   (["author_protocol", "hash"], [{"literal": "wrong"}])]
        for path, value in changes:
            with self.subTest(path=path):
                changed = copy.deepcopy(LITERALS); item = changed
                for key in path[:-1]: item = item[key]
                item[path[-1]] = value
                with self.assertRaises(ValueError): protocol.validate_literals(SOURCE, changed)

    def test_missing_or_extra_literal_function_or_protocol_schema_rejected(self):
        for component, key in (("constants", "OWN_SHA256_SOURCE"), ("function_ast_hashes", "confirm_session_template"),
                               ("author_protocol", "message_append")):
            with self.subTest(component=component):
                changed = copy.deepcopy(LITERALS); del changed[component][key]
                with self.assertRaises(ValueError): protocol.validate_literals(SOURCE, changed)
        changed = copy.deepcopy(LITERALS); changed["author_protocol"]["unexpected"] = False
        with self.assertRaises(ValueError): protocol.validate_literals(SOURCE, changed)

    def test_tampered_static_collector_observer_rejected_but_own_pending_present(self):
        changed = copy.deepcopy(LITERALS)
        changed["author_protocol"]["observer_new"] += '\nstore("verislop.observable-carrier-collector-result/0.1:fake", ACTUAL_RESULT);'
        with self.assertRaises(ValueError): protocol.validate_literals(SOURCE, changed)
        with self.assertRaises(ValueError): protocol.author_message(changed, REFERENCE)
        ordinary = protocol.author_message(LITERALS, REFERENCE).decode()
        self.assertIn("store(PENDING_KEY, {reference: OWN_REFERENCE, view: VIEW, result: ACTUAL_RESULT});", ordinary)
        self.assertNotIn("verislop.observable-carrier-collector-result/0.1:", ordinary)

    def test_no_producer_import_or_execution_in_runtime_reconstruction(self):
        tree = ast.parse((HERE / "author_protocol_reconstruction.py").read_text())
        imports = {node.names[0].name for node in tree.body if isinstance(node, ast.Import)}
        self.assertEqual(imports, {"ast", "hashlib", "json"})
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"exec", "eval", "compile", "open", "__import__"})
        text = (HERE / "author_protocol_reconstruction.py").read_text()
        self.assertNotIn("tools.exec_command", text)
        self.assertNotIn("spec_from_file_location", text)

    def test_all27_claim_objects_and_legacy_recipe_unchanged(self):
        old = ROOT / "validation/tier2-support-019-qualification-adapters-005"
        for name in ("predicate-reader-specification.json", "reconciliation-specification.json", "additional-witness-contract.json"):
            self.assertEqual((HERE / name).read_bytes(), (old / name).read_bytes())
        def method(path, class_name, name):
            root = ast.parse(path.read_text()); cls = next(node for node in root.body if isinstance(node, ast.ClassDef) and node.name == class_name)
            return ast.dump(next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name), include_attributes=False)
        self.assertEqual(method(HERE / "predicate_reader.py", "Reader", "recipe"), method(old / "predicate_reader.py", "Reader", "recipe"))
        self.assertEqual((HERE / "assemble_ancillary_indexes.py").read_bytes(), (old / "assemble_ancillary_indexes.py").read_bytes())

    def test_current_marker_version_preserves_exact_declared_scope(self):
        old = json.loads((ROOT / "validation/tier2-support-019-qualification-adapters-005/predicate-reader-carrier-literals.json").read_text())
        self.assertEqual(LITERALS["marker_pattern"], old["marker_pattern"].replace("UNRELATED_019_002_", "UNRELATED_019_003_"))
        self.assertEqual(LITERALS["expected_markers"], [value.replace("UNRELATED_019_002_", "UNRELATED_019_003_", 1) for value in old["expected_markers"]])

    def test_current_installed_hash_binding_preserves_all_old30_pure_semantics(self):
        def function(path):
            tree = ast.parse(path.read_text())
            cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AdditionalPredicates")
            return next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "carrier_pure")
        old = function(ROOT / "validation/tier2-support-019-qualification-adapters-005/additional_predicates.py")
        current = function(HERE / "additional_predicates.py")
        self.assertEqual(ast.dump(old.body[0], include_attributes=False), ast.dump(current.body[0], include_attributes=False))
        self.assertEqual(ast.dump(old.body[1], include_attributes=False), ast.dump(current.body[1], include_attributes=False))
        self.assertEqual(current.body[2].targets[0].id, "installed_hash")
        self.assertIn("synthetic_dataset/tools/bootstrap_tier2_carrier_view.py", ast.unparse(current.body[2]))
        self.assertIn("PURE_INSTALLED_SOURCE_NOT_CURRENT_FROZEN_INPUT", ast.unparse(current.body[3]))
        class CurrentHash(ast.NodeTransformer):
            def visit_Constant(self, node):
                if node.value == "sha256:9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366":
                    return ast.Name(id="installed_hash", ctx=ast.Load())
                return node
        changed = CurrentHash().visit(copy.deepcopy(old.body[2]))
        self.assertEqual(ast.dump(changed, include_attributes=False), ast.dump(current.body[4], include_attributes=False))
        self.assertEqual([ast.dump(node, include_attributes=False) for node in old.body[3:]],
                         [ast.dump(node, include_attributes=False) for node in current.body[5:]])

    def test_complete_source_delta_admits_only_registered_methods_and_import(self):
        old_root = ROOT / "validation/tier2-support-019-qualification-adapters-005"
        allowed = {"predicate_reader.py": {"Reader.recipe_literals", "Reader.fresh_author", "Reader.author_protocol_module", "Reader.author_message"},
                   "additional_predicates.py": {"AdditionalPredicates.carrier_pure", "AdditionalPredicates.fresh_author"}}
        for filename in ("predicate_reader.py", "additional_predicates.py", "assemble_ancillary_indexes.py", "current_root_reconcile.py", "materialize_adapter_configuration.py"):
            before = ast.parse((old_root / filename).read_text()); after = ast.parse((HERE / filename).read_text())
            def projection(tree):
                tree = copy.deepcopy(tree)
                for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
                    cls.body = [node for node in cls.body if not (isinstance(node, ast.FunctionDef) and cls.name + "." + node.name in allowed.get(filename, set()))]
                return tree
            before = projection(before); after = projection(after)
            if filename == "predicate_reader.py":
                matching = [node for node in after.body if isinstance(node, ast.Import) and ast.dump(node, include_attributes=False) == ast.dump(ast.parse("import importlib.util").body[0], include_attributes=False)]
                self.assertEqual(len(matching), 1); after.body.remove(matching[0])
            self.assertEqual(ast.dump(before, include_attributes=False), ast.dump(after, include_attributes=False), filename)

    def test_fresh_author_count_identity_final_roots_eof_and_failure_guards_preserved(self):
        old_root = ROOT / "validation/tier2-support-019-qualification-adapters-005"
        def method(root, filename, classname):
            tree = ast.parse((root / filename).read_text())
            cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == classname)
            return next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "fresh_author")
        before = method(old_root, "predicate_reader.py", "Reader"); after = method(HERE, "predicate_reader.py", "Reader")
        self.assertEqual([ast.dump(node, include_attributes=False) for node in before.body[:5]], [ast.dump(node, include_attributes=False) for node in after.body[:5]])
        self.assertEqual([ast.dump(node, include_attributes=False) for node in before.body[6:]], [ast.dump(node, include_attributes=False) for node in after.body[6:]])
        before = method(old_root, "additional_predicates.py", "AdditionalPredicates"); after = method(HERE, "additional_predicates.py", "AdditionalPredicates")
        self.assertEqual([ast.dump(node, include_attributes=False) for node in before.body[:3]], [ast.dump(node, include_attributes=False) for node in after.body[:3]])
        class CurrentPattern(ast.NodeTransformer):
            def visit_Constant(self, node):
                if node.value == "UNRELATED_019_002_[A-Za-z0-9_]+":
                    return ast.Subscript(value=ast.Name(id="literals", ctx=ast.Load()), slice=ast.Constant(value="marker_pattern"), ctx=ast.Load())
                return node
        expected = [ast.dump(CurrentPattern().visit(copy.deepcopy(node)), include_attributes=False) for node in before.body[6:]]
        self.assertEqual(expected, [ast.dump(node, include_attributes=False) for node in after.body[11:]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
