"""Five preregistered bounded source groups; no workflow or runtime execution."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import os
import shlex

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INT = ROOT / "validation/tier2-carrier-runtime-support-020-integration-001"
GROUPS = []


def need(value, detail):
    if not value:
        raise AssertionError(detail)


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def read(ref):
    return (ROOT / ref).read_bytes()


def doc(path):
    return json.loads(path.read_bytes())


def dump(node):
    return ast.dump(node, include_attributes=False)


def functions(tree):
    result = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            result[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef):
                    result[node.name + "." + child.name] = child
    return result


def group(identifier, observation):
    GROUPS.append({"id": identifier, "status": "PASS", "observation": observation})


def identity(ref):
    raw = read(ref["path"])
    need(sha(raw) == ref["sha256"], "IDENTITY_HASH:" + ref["path"])
    if "byte_count" in ref:
        need(len(raw) == ref["byte_count"], "IDENTITY_LENGTH:" + ref["path"])
    return raw


def authenticate():
    manifest = doc(INT / "source-manifest.json")
    need(sha((INT / "source-manifest.json").read_bytes()) == "sha256:e7d8b84d4f927f3edb896ed3d89a81b93216598ac227762841c519d598aaf127", "PUBLISHED_MANIFEST")
    need((INT / "SOURCE_SEAL.sha256").read_text() == sha((INT / "source-manifest.json").read_bytes()) + "  source-manifest.json\n", "SOURCE_SEAL")
    need(len(manifest["own_files"]) == 38 and len(manifest["inputs"]) == 14, "MANIFEST_COUNTS")
    for name, ref in manifest["own_files"].items():
        identity({**ref, "path": (INT / name).relative_to(ROOT).as_posix()})
    for name, digest in manifest["inputs"].items():
        need(sha(read(name)) == digest, "MANIFEST_INPUT:" + name)
    observations = []
    for directory, count, pid in (("draft-source-process-001", 32, 3539972), ("focused-source-process-001", 41, 3543604)):
        receipt = doc(INT / directory / "receipt.json")
        registration = doc(ROOT / receipt["registration"]["path"])
        identity(receipt["registration"])
        need(receipt["command"] == registration["command"] and receipt["command"][:3] == ["/usr/bin/python3.12", "-I", "-B"], "ACTUAL_ARGV")
        need(type(receipt["pid"]) is int and receipt["pid"] == pid and type(receipt["integer_exit_status"]) is int and receipt["integer_exit_status"] == 0, "ACTUAL_PID_STATUS")
        need(receipt["outer_timeout"] is None and len(receipt["before_guards"]) == count and receipt["before_guards"] == receipt["after_guards"] == registration["guards"], "ACTUAL_GUARDS")
        for name, digest in receipt["after_guards"].items():
            need(sha(read(name)) == digest, "CURRENT_GUARD:" + name)
        identity(receipt["stdout"]); identity(receipt["stderr"])
        actual = doc(INT / directory / "actual-tool-result.json")
        exposed = json.loads(actual["output"])
        need(type(actual["exit_code"]) is int and actual["exit_code"] == 0 and exposed["pid"] == pid and exposed["integer_exit_status"] == 0 and exposed["guard_count"] == count, "ACTUAL_TOOL_RECEIPT")
        observations.append({"directory": directory, "pid": pid, "status": 0, "guards": count})
    group("I020-01", {"files": 38, "inputs": 14, "actual_processes": observations, "live_bootstrap_input": "HISTORICAL_PREINSTALLATION_ONLY; immutable raw preimage is the stable final binding"})


def compare_projection(name, preimage, changed, added=()):
    old = ast.parse((INT / "preimages" / preimage).read_bytes())
    new = ast.parse((INT / name).read_bytes())
    old_functions, new_functions = functions(old), functions(new)
    need(set(new_functions) == set(old_functions) | set(added), "FUNCTION_SET:" + name)
    actual_changed = {key for key in old_functions if dump(old_functions[key]) != dump(new_functions[key])}
    need(actual_changed == set(changed), "CHANGED_FUNCTIONS:" + name + ":" + repr(actual_changed))
    projected = copy.deepcopy(new)
    for index, node in enumerate(projected.body):
        if isinstance(node, ast.FunctionDef) and node.name in changed:
            projected.body[index] = copy.deepcopy(old_functions[node.name])
        elif isinstance(node, ast.ClassDef):
            node.body = [copy.deepcopy(old_functions[node.name + "." + child.name]) if isinstance(child, ast.FunctionDef) and node.name + "." + child.name in changed else child
                         for child in node.body if not (isinstance(child, ast.FunctionDef) and node.name + "." + child.name in added)]
    if name in ("bootstrap_tier2.py", "prepare_unrelated_fixture.py"):
        projected.body = [node for node in projected.body if not (isinstance(node, ast.ImportFrom) and node.module == "synthetic_dataset.tools" and [part.name for part in node.names] == ["bootstrap_tier2_runtime_integration"])]
    if name == "bootstrap_tier2.py":
        old_assignment = next(node for node in old.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TRANSPORT_FILES" for t in node.targets))
        new_assignment = next(node for node in new.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TRANSPORT_FILES" for t in node.targets))
        need(ast.literal_eval(new_assignment.value) == ast.literal_eval(old_assignment.value) + ("synthetic_dataset/tools/bootstrap_tier2_runtime_integration.py",), "TRANSPORT_CONSTANT_DELTA")
        projected.body = [copy.deepcopy(old_assignment) if node is not None and isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TRANSPORT_FILES" for t in node.targets) else node for node in projected.body]
    if name == "prepare_unrelated_fixture.py":
        old.body = [node for node in old.body if not (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CANDIDATE_PATH" for t in node.targets))]
    need(dump(old) == dump(projected), "WHOLE_MODULE_PROJECTION:" + name)
    return {"unchanged_functions": len(old_functions) - len(changed), "changed": sorted(changed), "added": sorted(added)}, old_functions, new_functions


def inventory():
    observation, old, new = compare_projection("bootstrap_tier2.py", "00-bootstrap_tier2.py.raw", {"source_inventory", "prepare", "verify_inputs", "_carrier_binding", "_binding"})
    need(dump(old["snapshot"]) == dump(new["snapshot"]), "SNAPSHOT_CHANGED")
    source = (INT / "bootstrap_tier2.py").read_text()
    need("runtime_integration.source_inventory(repo)" in source and "for name in source:" in source and "execution-source" in source, "INVENTORY_NOT_COPIED")
    bridge = (INT / "runtime_integration.py").read_text()
    need('ROLES = {"generator", "reader", "runtime"}' in bridge and 'for name in (REGISTRATION_PATH, INTEGRATION_PATH):' in bridge and 'verify_interpreters(descriptor)' in bridge and 'result[ref["path"]] = ref["sha256"]' in bridge, "RUNTIME_DEPENDENCY_INVENTORY")
    need('descriptor["source_files"]' in bridge and 'session_files_in_source_inventory' in (INT / "profile_tools.py").read_text(), "SESSION_POLICY_NOT_EXPLICIT")
    group("I020-02", {"bootstrap_projection": observation, "snapshot_AST_exact": True, "frozen_copy_source_loop_preserved": True, "embedded_launcher_bound_by_generator": True, "own_sessions_outside_inventory": True})


def load_helper():
    path = INT / "compact_author_protocol_reconstruction.py"
    definition = importlib.util.spec_from_file_location("independent_review020_source_renderer", path)
    result = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(result)
    return result


def reconstruction():
    old = (INT / "preimages/02-author_protocol_reconstruction.py.raw").read_bytes()
    extension = (INT / "compact_reconstruction_extension.py").read_bytes()
    need((INT / "compact_author_protocol_reconstruction.py").read_bytes() == old + b"\n\n" + extension, "LEGACY_RECONSTRUCTOR_PREFIX")
    tree = ast.parse(extension)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            need(node.func.id not in ("eval", "exec", "compile", "__import__", "open"), "DYNAMIC_RENDERER_CALL")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            need("compact_protocol" not in dump(node) and "importlib" not in dump(node), "PRODUCER_IMPORT")
    helper = load_helper()
    legacy = (INT / "preimages/stable-legacy006.py.raw").read_bytes()
    sources = {role: (INT / "preimages" / name).read_bytes() for role, name in (("generator", "stable-compact_protocol.py.raw"), ("reader", "stable-reader.py.raw"), ("runtime", "stable-carrier_runtime.js.raw"))}
    engine = helper.PureTemplateAST(sources["generator"])
    refs = {role: {"path": "synthetic_dataset/tools/runtime020/" + name, "sha256": sha(sources[role])} for role, name in (("generator", "compact_protocol.py"), ("reader", "reader.py"), ("runtime", "carrier_runtime.js"))}
    descriptor = {"format": "verislop.carrier-runtime-registration/1", "api_revision": "support020-compact-runtime/1", "source_files": refs, "interpreters": {role: {"path": name, "sha256": sha(Path(name).read_bytes())} for role, name in (("node", "/usr/bin/node"), ("python", "/usr/bin/python3.12"))}, "launcher": {"kind": "generator_literal", "name": "LAUNCHER_SOURCE", "sha256": sha(engine.constants["LAUNCHER_SOURCE"].encode())}, "session_policy": "own-carrier-parent/runtime020-own-sessions"}
    wire = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    sources["descriptor"] = wire(descriptor).encode()
    refs = {**refs, "descriptor": {"path": "synthetic_dataset/tools/carrier_runtime020-registration.json", "sha256": sha(sources["descriptor"])}}
    code = {"runtime_path": "/unrelated-review/" + refs["runtime"]["path"], "runtime_sha256": refs["runtime"]["sha256"], "reader_path": "/unrelated-review/" + refs["reader"]["path"], "reader_sha256": refs["reader"]["sha256"], "node_path": "/usr/bin/node", "python_path": "/usr/bin/python3.12", "session_directory": "/unrelated-review/own/runtime020-own-sessions"}
    profile = helper.extract_schema(legacy)
    profile["source"] = {"path": "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py", "sha256": sha(legacy)}
    profile["author_protocol"]["reconstruction_source"] = {"path": (INT / "compact_author_protocol_reconstruction.py").relative_to(ROOT).as_posix(), "sha256": sha((INT / "compact_author_protocol_reconstruction.py").read_bytes())}
    profile["compact_protocol"] = {"format": helper.COMPACT_SCHEMA, "sources": refs, "code": code, "source_schema": engine.schema()}
    helper.validate_literals(legacy, profile, sources)
    reference = {"path": "/unrelated-review/own/é🙂'`$(data); carrier.json", "sha256": "sha256:" + "a" * 64, "request_sha256": "sha256:" + "b" * 64}
    session = code["session_directory"] + "/verislop-runtime020-" + hashlib.sha256(wire(reference).encode()).hexdigest() + ".json"
    pending = "verislop.runtime020-own-pending/0.1:" + wire(reference)
    prefix = shlex.quote("/usr/bin/python3.12") + " -I -B -c " + shlex.quote(engine.constants["LAUNCHER_SOURCE"]) + " "
    def expected(operation, view=None, confirmation=None):
        request = {"format": "verislop.carrier-runtime-request/0.1", "operation": operation, "reference": reference, "code": code, "session_path": session}
        result = engine.constants["EXEC_PRAGMA"] + "const REQUEST = " + wire(request) + ";\nconst PENDING_KEY = " + wire(pending) + ";\n"
        if view is not None: result += "const VIEW = " + wire(view) + ";\nREQUEST.view = VIEW;\n"
        if confirmation is not None: result += "const CONFIRM = " + wire(confirmation) + ";\nREQUEST.pending = load(PENDING_KEY);\nREQUEST.confirmation = CONFIRM;\n"
        result += engine.constants["SHELL_SAFE_JS"] + "const cmd = " + wire(prefix) + " + posixQuote(wire(REQUEST));\nconst ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});\n"
        if view is not None: result += "store(PENDING_KEY, {reference: REQUEST.reference, view: VIEW, result: ACTUAL_RESULT});\n"
        return result + "text(ACTUAL_RESULT);\n"
    inventory_view = {"operation": "inventory", "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
    field_view = {"operation": "field", "selector": "/system", "start_char": 0, "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
    confirmation = {"chunk_id": "COPY_ACTUAL_CHUNK_ID", "outer_output_intact": True}
    recipes = {"runtime_initial_template": expected("view", inventory_view), "runtime_next_template": expected("view", field_view), "runtime_confirm_template": expected("confirm", confirmation=confirmation), "runtime_hash_template": expected("hash")}
    for name, value in recipes.items():
        need(engine.call(name, reference, code) == value, "INDEPENDENT_FIXED_RECIPE:" + name)
    pieces = helper.flatten(helper.return_value(engine.functions["runtime_agent_message"]))
    symbols = {dump(ast.parse('_json(reference)', mode='eval').body): wire(reference), dump(ast.parse('_json(code)', mode='eval').body): wire(code), dump(ast.parse('session_path(reference, code)', mode='eval').body): session}
    symbols.update({dump(ast.parse(name + '(reference, code)', mode='eval').body): value for name, value in recipes.items()})
    expected_message = "".join(node.value if isinstance(node, ast.Constant) and type(node.value) is str else symbols[dump(node)] for node in pieces)
    actual = helper.author_message(profile, reference, sources)
    need(actual == expected_message.encode("utf-8", "strict"), "INDEPENDENT_MESSAGE_FRAGMENTS")
    group("I020-03", {"legacy_helper_prefix_exact": True, "source_roles_authenticated": sorted(sources), "independent_four_recipes_and_message_exact": True, "message_sha256": sha(actual), "producer_generator_imports": 0, "runtime_or_carrier_calls": 0, "descriptor_trust": "Externally frozen registry and immutable authorized templates; caller repinning is not publisher authentication"})


def completion():
    projections = {}
    for name, preimage, changed, added in (("predicate_reader.py", "03-predicate_reader.py.raw", {"Reader.recipe_literals", "Reader.author_message"}, {"Reader.author_protocol_sources"}), ("additional_predicates.py", "04-additional_predicates.py.raw", {"AdditionalPredicates.fresh_author"}, set()), ("prepare_unrelated_fixture.py", "01-prepare_unrelated_fixture.py.raw", {"fixture", "main"}, set())):
        observation, old, new = compare_projection(name, preimage, changed, added)
        projections[name] = observation
        if name == "additional_predicates.py":
            def tail(function):
                start = next(index for index, node in enumerate(function.body) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "request" for t in node.targets))
                return [dump(node) for node in function.body[start:]]
            need(tail(old["AdditionalPredicates.fresh_author"]) == tail(new["AdditionalPredicates.fresh_author"]), "COMPLETION_TAIL_CHANGED")
        if name == "prepare_unrelated_fixture.py":
            def collectors(tree):
                return sorted(dump(node) for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "candidate" and node.func.attr != "agent_message")
            need(collectors(ast.parse((INT / "preimages" / preimage).read_bytes())) == collectors(ast.parse((INT / name).read_bytes())), "LEGACY_COLLECTOR_RECIPES")
    group("I020-04", {"projections": projections, "AdditionalPredicates_completion_tail_exact": True, "Reader_fresh_author_entire_AST_exact": True, "legacy_collector_call_multiset_exact": True, "semantic_predicate_changes": 0, "literal_FINAL_EOF_marker_hash_count_requirements_preserved": True})


def focused_evidence():
    registration = doc(INT / "FOCUSED_SOURCE_CHECKS_REGISTRATION_BEFORE_EXECUTION.json")
    tree = ast.parse((INT / "test_integration_sources.py").read_bytes())
    methods = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    need(set(methods) == set(registration["finite_methods"]) and len(methods) == registration["expected_method_count"] == 18, "REGISTERED_TEST_METHODS")
    stderr = (INT / "focused-source-process-001/stderr.log").read_text()
    need(stderr.count(" ... ok\n") == 18 and "Ran 18 tests" in stderr and stderr.endswith("\nOK\n"), "ACTUAL_18_SOURCE_CONTROLS")
    stdout = json.loads((INT / "focused-source-process-001/stdout.log").read_text())
    need(stdout["source_control_pid"] == 3543604 and all(stdout[key] == 0 for key in ("views", "model_calls", "runtime_calls", "qualification_calls")), "SOURCE_CONTROL_SCOPE")
    forbidden = {"run", "Popen", "system", "check_call", "exec_command"}
    # The synthetic AST rejection string is a Constant, never an executed AST call.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            need(node.func.attr not in forbidden, "FOCUSED_RUNTIME_OR_SHELL_CALL")
    group("I020-05", {"actual_focused_controls": 18, "actual_pid": 3543604, "actual_integer_status": 0, "method_registry_exact": True, "runtime_workflow_model_calls": 0, "existing_controls_not_reexecuted": True, "no_inherited_runtime_PASS": True})


def main():
    print(json.dumps({"pid": os.getpid(), "scope": "FIVE_GROUP_SOURCE_ONLY_REVIEW", "group_count": 5}), flush=True)
    try:
        authenticate(); inventory(); reconstruction(); completion(); focused_evidence()
    except Exception as exc:
        result = {"status": "SOURCE_BLOCKER", "completed_groups": GROUPS, "error_type": type(exc).__name__, "error": str(exc), "qualification_authority": False}
        (HERE / "observations.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        raise
    result = {"status": "SOURCE_REVIEWED_NO_CURRENT_RUNTIME_ADMISSION_BLOCKER_RUNTIME_UNQUALIFIED", "groups": GROUPS, "qualification_authority": False, "activation_authority": False, "runtime_success_authority": False}
    (HERE / "observations.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
