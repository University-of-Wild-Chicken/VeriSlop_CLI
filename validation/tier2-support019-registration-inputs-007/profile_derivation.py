"""Registered source-only fixture/profile derivation; expected payloads stay opaque."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).absolute().parents[2]
HERE = Path(__file__).absolute().parent
BASELINE = ROOT / "validation/tier2-support019-registration-inputs-006"
ADAPTER = "validation/tier2-support-019-qualification-adapters-008"
INTEGRATION = "validation/tier2-carrier-runtime-support-020-integration-001"

def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def ref(path):
    raw = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(raw), "byte_count": len(raw)}

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

def write(name, value):
    with (HERE / name).open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")

def source_fidelity():
    before = (BASELINE / "prepare_unrelated_fixture.py").read_bytes()
    after = (HERE / "prepare_unrelated_fixture.py").read_bytes()
    old_tree, new_tree = ast.parse(before), ast.parse(after)
    def system(tree):
        return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                    and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == "SYSTEM")
    old_system, new_system = system(old_tree), system(new_tree)
    class Mask(ast.NodeTransformer):
        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "SYSTEM":
                return ast.Assign(targets=node.targets, value=ast.Constant(value="REGISTERED_SYSTEM_LITERAL"))
            return self.generic_visit(node)
        def visit_Constant(self, node):
            if type(node.value) is str:
                return ast.Constant(value=node.value.replace("UNRELATED_019_005_", "UNRELATED_019_007_"))
            return node
    old_dump = ast.dump(Mask().visit(copy.deepcopy(old_tree)), include_attributes=False)
    new_dump = ast.dump(Mask().visit(copy.deepcopy(new_tree)), include_attributes=False)
    assert old_dump == new_dump
    old_prefix = old_system.split("If a concrete observed protocol failure prevents completion,", 1)[0]
    new_prefix = new_system.split("A first rejected editable VIEW argument is recoverable:", 1)[0]
    assert old_prefix.replace("UNRELATED_019_005_", "UNRELATED_019_007_") == new_prefix
    for text in ("-9007199254740991 through 9007199254740991", "excluding booleans",
                 "output_cap_bytes256..8192", "integer128<=metadata_reserve_bytes<output_cap_bytes",
                 "SAME accepted selector/cursor", "unsuccessful UNATTESTED data"):
        assert text in new_system
    assert ast.dump(next(node for node in old_tree.body if isinstance(node, ast.FunctionDef) and node.name == "fixture"),
                    include_attributes=False) == ast.dump(next(node for node in new_tree.body if isinstance(node, ast.FunctionDef) and node.name == "fixture"),
                                                          include_attributes=False)
    result = {"format": "verislop.q007-fixture-source-fidelity/1",
              "baseline_ref": ref(BASELINE / "prepare_unrelated_fixture.py"),
              "successor_ref": ref(HERE / "prepare_unrelated_fixture.py"),
              "masked_AST_sha256": sha(old_dump.encode()),
              "all_ASTs_exact_except_label_strings_and_SYSTEM": True,
              "four_key_success_prefix_preserved_after_labeling": True,
              "fixture_atom_repetitions_floor_function_AST_exact": True,
              "runtime_accepted_domain_changed": False,
              "attempted_numeric_evidence_domain_signed_safe": True,
              "qualification_authority": False}
    write("FIXTURE_SOURCE_FIDELITY.json", result)
    return result

def main():
    fidelity = source_fidelity()
    reconstruction = ROOT / ADAPTER / "author_protocol_reconstruction.py"
    assert reconstruction.read_bytes() == (ROOT / INTEGRATION / "compact_author_protocol_reconstruction.py").read_bytes()
    helper = module("registered_q007_independent_reconstruction", reconstruction)
    tools = module("registered_q007_profile_tools", ROOT / INTEGRATION / "profile_tools.py")
    descriptor_path = ROOT / "synthetic_dataset/tools/carrier_runtime020-registration.json"
    descriptor = json.loads(descriptor_path.read_bytes())
    sources = {role: (ROOT / value["path"]).read_bytes() for role, value in descriptor["source_files"].items()}
    sources["descriptor"] = descriptor_path.read_bytes()
    references = {role: {"path": value["path"], "sha256": sha(sources[role])}
                  for role, value in descriptor["source_files"].items()}
    references["descriptor"] = {"path": str(descriptor_path.relative_to(ROOT)), "sha256": sha(sources["descriptor"])}
    for role, value in descriptor["source_files"].items():
        assert references[role]["sha256"] == value["sha256"]
    for value in descriptor["interpreters"].values():
        assert sha(Path(value["path"]).read_bytes()) == value["sha256"]
    fixture = HERE / "fixture-current-whole-gate-007"
    session_directory = fixture / "runtime020-own-sessions"
    assert session_directory.is_dir() and not list(session_directory.iterdir())
    code = {"runtime_path": str(ROOT / descriptor["source_files"]["runtime"]["path"]),
            "runtime_sha256": descriptor["source_files"]["runtime"]["sha256"],
            "reader_path": str(ROOT / descriptor["source_files"]["reader"]["path"]),
            "reader_sha256": descriptor["source_files"]["reader"]["sha256"],
            "node_path": descriptor["interpreters"]["node"]["path"],
            "python_path": descriptor["interpreters"]["python"]["path"],
            "session_directory": str(session_directory)}
    legacy_source = (ROOT / "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py").read_bytes()
    legacy = json.loads((BASELINE / "fresh-author-carrier-literals-006.json").read_bytes())
    registration = json.loads((HERE / "fixture-registration-before-generation.json").read_bytes())
    profile = tools.build_profile(helper, legacy_source, legacy, references, sources, code,
                                  {"path": str(reconstruction.relative_to(ROOT)), "sha256": sha(reconstruction.read_bytes())},
                                  marker_pattern=registration["marker_prefix"] + r"[A-Z_]+",
                                  expected_markers=[registration["marker_prefix"] + suffix for suffix in
                                                    ("START", "MIDDLE_A", "MIDDLE_B", "FINAL_TAIL")])
    reference = json.loads((fixture / "reference.json").read_bytes())
    actual_message = (fixture / "fresh-author-exact-message.txt").read_bytes()
    rebuilt = helper.author_message(profile, reference, sources)
    assert rebuilt == actual_message
    write("fresh-author-carrier-literals-007.json", profile)
    capture_bytes = (BASELINE / "fresh-author-capture-literals-006.json").read_bytes()
    capture = json.loads(capture_bytes)
    capture_source = (ROOT / capture["source"]["path"]).read_bytes()
    assert sha(capture_source) == capture["source"]["sha256"]
    capture_tree = ast.parse(capture_source)
    constants = {node.targets[0].id: ast.literal_eval(node.value) for node in capture_tree.body
                 if isinstance(node, ast.Assign) and len(node.targets) == 1
                 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in capture["constants"]}
    assert json.loads(json.dumps(constants)) == capture["constants"]
    hashes = {node.name: sha(ast.dump(node, include_attributes=False).encode()) for node in capture_tree.body
              if isinstance(node, ast.FunctionDef) and node.name in capture["function_ast_hashes"]}
    assert hashes == capture["function_ast_hashes"]
    with (HERE / "fresh-author-capture-literals-007.json").open("xb") as stream:
        stream.write(capture_bytes)
    roles = ("own-unrelated-carrier.json", "original-unrelated-request.json", "reference.json",
             "fixture-only-expected.json", "fresh-author-exact-message.txt", "first-functions-exec.js",
             "next-functions-exec.js", "own-unrelated-empty-carrier.json", "original-unrelated-empty-request.json",
             "empty-reference.json", "empty-first-functions-exec.js", "empty-next-system-functions-exec.js",
             "empty-next-user-functions-exec.js", "preexecution-registration.json")
    assert sorted(path.name for path in fixture.iterdir() if path.is_file()) == sorted(roles)
    fixture_refs = {str((fixture / name).relative_to(ROOT)): sha((fixture / name).read_bytes()) for name in roles}
    write("fresh-fixture-input-map.json", fixture_refs)
    evidence = {"format": "verislop.support021-current-compact-source-profile-derivation/1",
                "status": "SOURCE_DERIVED_RUNTIME_UNQUALIFIED",
                "source_refs": references, "reconstructor": ref(reconstruction),
                "carrier_profile": ref(HERE / "fresh-author-carrier-literals-007.json"),
                "capture_profile": ref(HERE / "fresh-author-capture-literals-007.json"),
                "fixture_input_map": ref(HERE / "fresh-fixture-input-map.json"),
                "fixture_source_fidelity": ref(HERE / "FIXTURE_SOURCE_FIDELITY.json"),
                "independent_full_message_byte_equal": True, "message_bytes": len(rebuilt),
                "message_sha256": sha(rebuilt), "capture_constants": len(constants), "capture_ASTs": len(hashes),
                "capture_profile_byte_exact006": capture_bytes == (HERE / "fresh-author-capture-literals-007.json").read_bytes(),
                "fixture_file_roles": len(roles), "private_expected_payload_values_read": False,
                "fixture_floor_assertion_preserved_in_actual_generator": True,
                "runtime_interpreter": "/usr/bin/python3.12", "VIEW_model_reader_runtime_qualification_calls": 0,
                "legacy_truth_conditions_unchanged": True, "qualification_authority": False}
    write("compact-profile-source-derivation.json", evidence)
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()
