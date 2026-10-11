"""Focused candidate source controls; no VIEW/runtime/model/native/task calls."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def dump(node):
    return ast.dump(node, include_attributes=False)


def functions(raw):
    result = {}
    for node in ast.parse(raw).body:
        if isinstance(node, ast.FunctionDef): result[node.name] = node
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef): result[node.name + "." + child.name] = child
    return result


class IntegrationSourceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helper = module("independent_compact_candidate", HERE / "compact_author_protocol_reconstruction.py")
        cls.bridge = module("candidate_runtime_integration", HERE / "runtime_integration.py")
        cls.profiles = module("candidate_profile_tools", HERE / "profile_tools.py")
        cls.reader = module("candidate_binding_reader_only", HERE / "predicate_reader.py")
        cls.publication = json.loads((HERE / "STABLE_RUNTIME_INPUTS_BEFORE_RECONSTRUCTION.json").read_bytes())["inputs"]
        cls.raw = {name: (ROOT / ref["preimage"]).read_bytes()
                   for name, ref in cls.publication.items() if "preimage" in ref}
        cls.generator = module("actual_registered_generator_pure_only", ROOT / cls.publication["compact_protocol.py"]["path"])
        cls.output = HERE / "focused-source-unrelated-files-001"
        cls.output.mkdir()
        cls.binary_refs = {role: {"path": path, "sha256": sha(Path(path).read_bytes())}
                           for role, path in (("node", "/usr/bin/node"), ("python", "/usr/bin/python3.12"))}

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=self.output)
        self.repo = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.refs = {role: {"path": "synthetic_dataset/tools/runtime020/" + name, "sha256": sha(self.raw[name])}
                     for role, name in (("generator", "compact_protocol.py"), ("reader", "reader.py"), ("runtime", "carrier_runtime.js"))}
        self.descriptor = {"format": self.bridge.FORMAT, "api_revision": self.bridge.REVISION,
            "source_files": copy.deepcopy(self.refs), "interpreters": copy.deepcopy(self.binary_refs),
            "launcher": {"kind": "generator_literal", "name": "LAUNCHER_SOURCE",
                         "sha256": sha(self.generator.LAUNCHER_SOURCE.encode())},
            "session_policy": "own-carrier-parent/runtime020-own-sessions"}
        for role, ref in self.refs.items():
            path = self.repo / ref["path"]; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.raw[{"generator":"compact_protocol.py", "reader":"reader.py", "runtime":"carrier_runtime.js"}[role]])
        (self.repo / self.bridge.INTEGRATION_PATH).write_bytes((HERE / "runtime_integration.py").read_bytes())
        self.descriptor_raw = json.dumps(self.descriptor, sort_keys=True, separators=(",", ":")).encode()
        (self.repo / self.bridge.REGISTRATION_PATH).write_bytes(self.descriptor_raw)
        self.session = self.repo / "own-unrelated" / "runtime020-own-sessions"
        self.session.mkdir(parents=True)
        self.reference = {"path": str(self.session.parent / "carrier.json"),
                          "sha256": "sha256:" + "a" * 64, "request_sha256": "sha256:" + "b" * 64}
        self.code = self.bridge.code_bindings(self.repo, self.descriptor, str(self.session))
        self.sources = {role: self.raw[name] for role, name in
                        (("generator", "compact_protocol.py"), ("reader", "reader.py"), ("runtime", "carrier_runtime.js"))}
        self.sources["descriptor"] = self.descriptor_raw
        references = {**self.refs, "descriptor": {"path": self.bridge.REGISTRATION_PATH, "sha256": sha(self.descriptor_raw)}}
        legacy = self.helper.extract_schema(self.raw["legacy006.py"])
        legacy["source"] = {"path": "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py", "sha256": sha(self.raw["legacy006.py"])}
        legacy["author_protocol"]["reconstruction_source"] = {"path": "unrelated/old-helper.py", "sha256": "sha256:" + "c" * 64}
        self.profile = self.profiles.build_profile(self.helper, self.raw["legacy006.py"], legacy, references,
            self.sources, self.code, {"path": (HERE / "compact_author_protocol_reconstruction.py").relative_to(ROOT).as_posix(),
            "sha256": sha((HERE / "compact_author_protocol_reconstruction.py").read_bytes())},
            marker_pattern="UNRELATED_SOURCE_CONTROL_[A-Z_]+", expected_markers=["START", "A", "B", "TAIL"])

    def test_all_compact_templates_and_message_match_independent_ast(self):
        engine = self.helper.PureTemplateAST(self.sources["generator"])
        for name in ("runtime_initial_template", "runtime_next_template", "runtime_confirm_template", "runtime_hash_template", "runtime_agent_message"):
            self.assertEqual(engine.call(name, self.reference, self.code), getattr(self.generator, name)(self.reference, self.code))
        self.assertEqual(self.helper.author_message(self.profile, self.reference, self.sources),
                         self.generator.runtime_agent_message(self.reference, self.code).encode())

    def test_unicode_apostrophe_shell_metacharacters_remain_data(self):
        reference = {**self.reference, "path": str(self.session.parent / "é🙂'`$(unrelated); carrier.json")}
        engine = self.helper.PureTemplateAST(self.sources["generator"])
        self.assertEqual(engine.call("runtime_agent_message", reference, self.code), self.generator.runtime_agent_message(reference, self.code))
        self.assertEqual(engine.call("runtime_command", {"reference": reference, "code": self.code}),
                         self.generator.runtime_command({"reference": reference, "code": self.code}))

    def test_explicit_cursor_retry_and_confirmation_match(self):
        engine = self.helper.PureTemplateAST(self.sources["generator"])
        view = {"operation":"field", "selector":"/user", "start_char":4097, "output_cap_bytes":4096, "metadata_reserve_bytes":2048}
        confirm = {"chunk_id":"actual-unrelated-control", "outer_output_intact":False}
        self.assertEqual(engine.call("runtime_next_template", self.reference, self.code, view), self.generator.runtime_next_template(self.reference, self.code, view))
        self.assertEqual(engine.call("runtime_confirm_template", self.reference, self.code, confirm), self.generator.runtime_confirm_template(self.reference, self.code, confirm))

    def test_pending_object_retained_before_full_forwarding(self):
        first = self.helper.PureTemplateAST(self.sources["generator"]).call("runtime_initial_template", self.reference, self.code)
        self.assertLess(first.index("store(PENDING_KEY,"), first.index("text(ACTUAL_RESULT);"))
        self.assertEqual(first.count("await tools.exec_command("), 1)
        self.assertEqual(first.count("text(ACTUAL_RESULT);"), 1)

    def test_source_tampering_rejected(self):
        sources = {**self.sources, "reader": self.sources["reader"] + b"\n# mutation"}
        with self.assertRaisesRegex(ValueError, "NOT_AUTHENTICATED"):
            self.helper.validate_literals(self.raw["legacy006.py"], self.profile, sources)

    def test_retained_profile_literal_cannot_replace_source(self):
        profile = copy.deepcopy(self.profile)
        profile["compact_protocol"]["source_schema"]["constants"]["SHELL_SAFE_JS"] += "MUTATED"
        with self.assertRaisesRegex(ValueError, "NOT_SOURCE_DERIVED"):
            self.helper.author_message(profile, self.reference, self.sources)

    def test_descriptor_binding_mismatch_rejected(self):
        descriptor = copy.deepcopy(self.descriptor); descriptor["source_files"]["reader"]["sha256"] = "sha256:" + "d" * 64
        raw = json.dumps(descriptor).encode(); sources = {**self.sources, "descriptor": raw}
        profile = copy.deepcopy(self.profile); profile["compact_protocol"]["sources"]["descriptor"]["sha256"] = sha(raw)
        with self.assertRaisesRegex(ValueError, "SOURCE_DIFFERS"):
            self.helper.validate_literals(self.raw["legacy006.py"], profile, sources)

    def test_duplicate_descriptor_keys_rejected(self):
        raw = b'{"format":1,"format":2}'; sources = {**self.sources, "descriptor": raw}
        profile = copy.deepcopy(self.profile); profile["compact_protocol"]["sources"]["descriptor"]["sha256"] = sha(raw)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_KEY"):
            self.helper.validate_literals(self.raw["legacy006.py"], profile, sources)

    def test_boolean_cursor_and_extra_fields_rejected(self):
        engine = self.helper.PureTemplateAST(self.sources["generator"])
        view = {"operation":"field", "selector":"/system", "start_char":True, "output_cap_bytes":8192, "metadata_reserve_bytes":2048}
        with self.assertRaises(ValueError): engine.call("runtime_next_template", self.reference, self.code, view)
        with self.assertRaises(ValueError): engine.call("runtime_hash_template", {**self.reference,"extra":True}, self.code)

    def test_arbitrary_ast_calls_never_execute(self):
        tree = ast.parse(self.sources["generator"])
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "runtime_agent_message")
        function.body = [ast.Return(ast.parse('__import__("os").system("UNAUTHORIZED")', mode="eval").body)]
        changed = ast.unparse(ast.fix_missing_locations(tree)).encode()
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED"):
            self.helper.PureTemplateAST(changed).call("runtime_agent_message", self.reference, self.code)

    def test_complete_inventory_can_be_copied_and_reverified(self):
        inventory = self.bridge.source_inventory(self.repo)
        self.assertEqual(set(inventory), {self.bridge.INTEGRATION_PATH, self.bridge.REGISTRATION_PATH} | {ref["path"] for ref in self.refs.values()})
        self.assertTrue(any(name.endswith(".js") for name in inventory))
        destination = self.repo / "snapshot"
        for name in inventory:
            path = destination / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes((self.repo / name).read_bytes())
        self.assertEqual(self.bridge.source_inventory(destination), inventory)
        base = json.loads((HERE / "preimages/05-source-inventory-registration.json.raw").read_bytes())
        registration = self.profiles.inventory_registration(base, self.descriptor, self.bridge.REGISTRATION_PATH, self.bridge.INTEGRATION_PATH)
        self.assertTrue(set(inventory).issubset(registration["transport_files"]))
        self.assertFalse(registration["runtime_dependency_registration"]["session_files_in_source_inventory"])

    def test_inventory_mutation_and_symlink_escape_rejected(self):
        runtime = self.repo / self.refs["runtime"]["path"]
        runtime.write_bytes(runtime.read_bytes() + b"MUTATED")
        with self.assertRaisesRegex(ValueError, "HASH_MISMATCH"): self.bridge.source_inventory(self.repo)
        runtime.unlink(); runtime.symlink_to(HERE / "runtime_integration.py")
        with self.assertRaisesRegex(ValueError, "NOT_REGULAR"): self.bridge.source_inventory(self.repo)

    def test_interpreter_hash_mismatch_rejected(self):
        descriptor = copy.deepcopy(self.descriptor); descriptor["interpreters"]["node"]["sha256"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "INTERPRETER_HASH_MISMATCH"):
            self.bridge.code_bindings(self.repo, descriptor, str(self.session))

    def test_multisource_adapter_requires_every_frozen_identity(self):
        reader = self.reader.Reader.__new__(self.reader.Reader)
        identities = self.profile["compact_protocol"]["sources"]
        reader.hashes = {ref["path"]:ref["sha256"] for ref in identities.values()}
        observed = []
        def read(path, digest):
            observed.append((path,digest)); role = next(role for role, ref in identities.items() if ref["path"] == path)
            return self.sources[role]
        reader.read = read
        self.assertEqual(reader.author_protocol_sources(self.profile), self.sources)
        self.assertEqual(len(observed), 4)
        del reader.hashes[identities["runtime"]["path"]]
        with self.assertRaisesRegex(ValueError, "NOT_FROZEN"): reader.author_protocol_sources(self.profile)

    def test_compact_selection_constructs_only_the_bound_message(self):
        message, binding = self.bridge.native_message(self.repo, self.reference, create=False)
        self.assertEqual(message, self.generator.runtime_agent_message(self.reference, self.code))
        self.assertEqual(binding["message_sha256"], sha(message.encode()))
        self.assertEqual(binding["runtime_source_files"], self.descriptor["source_files"])
        self.assertFalse(Path(self.reference["path"]).exists())
        (self.repo / self.bridge.REGISTRATION_PATH).unlink()
        with self.assertRaises(ValueError): self.bridge.native_message(self.repo, self.reference, create=False)

    def test_legacy_helper_prefix_and_unchanged_bootstrap_functions(self):
        original = (HERE / "preimages/02-author_protocol_reconstruction.py.raw").read_bytes()
        self.assertTrue((HERE / "compact_author_protocol_reconstruction.py").read_bytes().startswith(original + b"\n\n"))
        base = functions((HERE / "preimages/00-bootstrap_tier2.py.raw").read_bytes())
        draft = functions((HERE / "bootstrap_tier2.py").read_bytes())
        changed = {"source_inventory","prepare","verify_inputs","_carrier_binding","_binding"}
        for name, node in base.items():
            if name not in changed: self.assertEqual(dump(node), dump(draft[name]), name)
        self.assertEqual(dump(base["snapshot"]), dump(draft["snapshot"]))

    def test_author_completion_predicate_tails_unchanged(self):
        base = functions((HERE / "preimages/03-predicate_reader.py.raw").read_bytes())
        draft = functions((HERE / "predicate_reader.py").read_bytes())
        changed = {"Reader.recipe_literals","Reader.author_message"}
        for name, node in base.items():
            if name not in changed: self.assertEqual(dump(node), dump(draft[name]), name)
        base = functions((HERE / "preimages/04-additional_predicates.py.raw").read_bytes())
        draft = functions((HERE / "additional_predicates.py").read_bytes())
        for name, node in base.items():
            if name != "AdditionalPredicates.fresh_author": self.assertEqual(dump(node), dump(draft[name]), name)
        def completion_tail(node):
            start = next(index for index, part in enumerate(node.body) if isinstance(part, ast.Assign)
                         and any(isinstance(target, ast.Name) and target.id == "request" for target in part.targets))
            return [dump(part) for part in node.body[start:]]
        self.assertEqual(completion_tail(base["AdditionalPredicates.fresh_author"]),
                         completion_tail(draft["AdditionalPredicates.fresh_author"]))

    def test_fixture_legacy_collector_recipes_remain_and_author_selection_changes(self):
        base = ast.parse((HERE / "preimages/01-prepare_unrelated_fixture.py.raw").read_bytes())
        draft = ast.parse((HERE / "prepare_unrelated_fixture.py").read_bytes())
        def collector_calls(tree):
            return sorted(dump(node) for node in ast.walk(tree) if isinstance(node, ast.Call) and
                          isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and
                          node.func.value.id == "candidate" and node.func.attr != "agent_message")
        self.assertEqual(collector_calls(base), collector_calls(draft))
        self.assertNotIn("candidate.agent_message(reference)", (HERE / "prepare_unrelated_fixture.py").read_text())
        self.assertIn("runtime_integration.compact_message(", (HERE / "prepare_unrelated_fixture.py").read_text())


if __name__ == "__main__":
    print(json.dumps({"source_control_pid": os.getpid(), "scope":"SOURCE_ONLY_CANDIDATE", "views":0, "model_calls":0, "runtime_calls":0, "qualification_calls":0}))
    unittest.main(verbosity=2)
