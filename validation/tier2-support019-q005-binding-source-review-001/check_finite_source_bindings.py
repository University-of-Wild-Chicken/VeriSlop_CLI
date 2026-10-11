"""Finite registered source-binding checks; no workflow or builder invocation."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REG = "validation/tier2-support019-registration-inputs-005"
BASE = "validation/tier2-support019-final-configuration-005"
PLAN = "validation/tier2-support-019-qualification-plan-010"
OLD_PLAN = "validation/tier2-support-019-qualification-plan-009"
ADAPTER = "validation/tier2-support-019-qualification-adapters-007"
CANDIDATE = "validation/tier2-support019-author-recovery-implementation-006"
PURE = "validation/tier2-support019-core-drivers-005"
EXPECTED = "sha256:f855de49fa8522cfc91053fe3f1f0db1ebd3c199260acbb97618d0f998c5eb4a"
OLD_EXPECTED = "sha256:a56590eb051ebac28312031b157195caab0d747aa20ebc4557d70ff5b1b2921f"
OLD_RUNTIME = tuple("validation/tier2-support-019-qualification-%03d/" % n for n in range(1, 5))
READS = {}


def raw(name):
    path = ROOT / name
    value = path.read_bytes()
    READS[name] = {"sha256": "sha256:" + hashlib.sha256(value).hexdigest(), "byte_count": len(value)}
    return value


def doc(name):
    assert "fixture-only-expected" not in name and "/qualification-00" not in name, name
    return json.loads(raw(name))


def authenticate(identity, name=None):
    name = identity.get("path", name)
    assert name and not name.startswith(OLD_RUNTIME), name
    raw(name)
    assert READS[name]["sha256"] == identity["sha256"], name
    for key in ("byte_count", "size_bytes", "bytes", "size"):
        if key in identity:
            assert type(identity[key]) is int and READS[name]["byte_count"] == identity[key], name


def module(name, path):
    definition = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(value)
    return value


def source_projection(entry, replacements):
    """Closed declared byte projection, without importing/running the preparer."""
    before = entry["preimage"]["path"]
    text = raw(entry["retained_preimage"]).decode("utf-8")
    assert text.encode() == raw(before)
    for old, new in replacements.items():
        text = text.replace(old, new)
    for old, new in (("preflight-004", "preflight-005"), ("configuration004", "configuration005"),
                     ("registration-inputs004", "registration-inputs005"), ("plan009", "plan010"),
                     ("pure004", "pure005"), ("carrier005", "carrier006"), ("candidate005", "candidate006"),
                     ("qualification004", "qualification005"), ("Q004", "Q005"),
                     ("FINAL_CURRENT005_BINDINGS_SOURCE_FIDELITY.json", "FINAL_CURRENT006_BINDINGS_SOURCE_FIDELITY.json"),
                     ("fresh-author-carrier-literals-004.json", "fresh-author-carrier-literals-005.json"),
                     (OLD_EXPECTED, EXPECTED)):
        text = text.replace(old, new)
    if before.endswith("prepare_configuration.py"):
        for old, new in (("'qualification-019-004'", "'qualification-019-005'"),
                         ("CURRENT004_NOT_BYTE_EXACT_INSTALLED", "CURRENT006_NOT_BYTE_EXACT_INSTALLED"),
                         ("PLAN008_CURRENT_CARRIER", "PLAN010_CURRENT_CARRIER"),
                         ("PLAN008_ADAPTER006", "PLAN010_ADAPTER007"),
                         ("ADAPTERS+'/predicate-reader-capture-literals.json'", "REG+'/fresh-author-capture-literals-005.json'"),
                         ("ADAPTERS+'/author_protocol_reconstruction.py',REG+'/fresh-author-carrier-literals-005.json',",
                          "ADAPTERS+'/author_protocol_reconstruction.py',REG+'/fresh-author-carrier-literals-005.json',REG+'/fresh-author-capture-literals-005.json',"),
                         ("'validation/tier2-support-019-qualification-003/'))",
                          "'validation/tier2-support-019-qualification-003/','validation/tier2-support-019-qualification-004/'))")):
            text = text.replace(old, new)
    elif before.endswith("assemble_current_source_handoff.py"):
        text = text.replace('"validation/tier2-support-019-qualification-003/")),',
                            '"validation/tier2-support-019-qualification-003/",\n                                "validation/tier2-support-019-qualification-004/")),')
        text = text.replace("Carrier004 review own files", "Carrier006 review own files").replace("preflight004", "preflight005")
        installation = "validation/tier2-carrier006-installation-001"
        additions = [installation + "/" + name for name in ("SPECIFICATION_BEFORE_INSTALLATION.json", "production005-preinstallation.raw", "ROOT_REVIEW_AUTHENTICATION.json", "SOURCE_INSTALLATION_OBSERVATION.json")]
        text = text.replace("    paths.add(carrier)\n", "    paths.add(carrier)\n    paths.update({" + ",".join(map(repr, additions)) + "})\n")
    elif before.endswith("prepare_unrelated_fixture.py"):
        text = text.replace("UNRELATED_019_004_", "UNRELATED_019_005_").replace("unrelated-carrier-context019-004-", "unrelated-carrier-context019-005-").replace('"005"', '"006"')
    elif before.endswith("run_nonexecuting_preflight_004.py"):
        anchor = "reg=json.loads((p/'registration-before-execution.json').read_text())\n"
        extra = "def guard():\n return {name:{'path':name,'sha256':'sha256:'+hashlib.sha256((root/name).read_bytes()).hexdigest(),'byte_count':(root/name).stat().st_size} for name in reg['source_guards']}\nbefore=guard();assert before==reg['source_guards'] and before\n"
        text = text.replace(anchor, anchor + extra)
        text = text.replace("receipt={'format':", "after=guard();assert before==after\nreceipt={'before':before,'after':after,'frozen_inputs_unchanged':before==after,'format':", 1)
    labels = doc(REG + "/CURRENT_VERSION_LABEL_AMENDMENT_BEFORE_METADATA_002.json")
    for preimage in labels["preimages"]:
        if entry["path"] == preimage["path"]:
            assert "sha256:" + hashlib.sha256(text.encode()).hexdigest() == preimage["sha256"]
            assert len(text.encode()) == preimage["byte_count"]
            for old, new in labels["replacements"].items():
                text = text.replace(old, new)
    assert text.encode() == raw(entry["path"]), entry["path"]


def main():
    assert sys.executable == "/usr/bin/python3.12" and sys.version_info[:2] == (3, 12)
    handoff = doc(REG + "/CURRENT006_BINDING_SOURCE_HANDOFF.json")
    assert handoff["Q005_exists"] is False and not (ROOT / "validation/tier2-support-019-qualification-005").exists()
    assert handoff["current27_verifier_executions"] == handoff["model_calls"] == handoff["actual_VIEW_calls"] == handoff["Lean_calls"] == handoff["native_task_calls"] == 0
    for value in handoff.values():
        if isinstance(value, dict) and {"path", "sha256"}.issubset(value):
            authenticate(value)
    config = doc(handoff["configuration"]["path"])
    assert config["qualification_root"] == "validation/tier2-support-019-qualification-005"
    assert config["prior_pass_inheritance"] is config["execution_authority"] is config["qualification_authority"] is config["activation_authority"] is False
    processes = []
    for row in handoff["actual_processes"]:
        authenticate(row["receipt"])
        receipt = doc(row["receipt"]["path"])
        assert receipt["pid"] == row["actual_pid"] and type(receipt["returncode"]) is int and receipt["returncode"] == row["returncode"] == 0
        assert receipt["before"] and receipt["before"] == receipt["after"] and len(receipt["before"]) == row["guard_count"]
        registration = receipt.get("registration", {"path": REG + "/preflight-005/registration-before-execution.json"})
        if "sha256" in registration:
            authenticate(registration)
        registered = doc(registration["path"])
        assert registered["argv"] == receipt["argv"] and registered["cwd"] == receipt["cwd"] == str(ROOT)
        assert registered["source_guards"] == receipt["before"]
        assert registered["environment"] == receipt["registered_environment"]
        assert registered["timeout_seconds"] is receipt["timeout_seconds"] is None
        for name, identity in receipt["after"].items():
            authenticate(identity, name)
        authenticate(receipt["stdout"]); authenticate(receipt["stderr"])
        processes.append({"pid": receipt["pid"], "returncode": 0, "guards": len(receipt["before"]), "receipt": row["receipt"]})
    assert len(processes) == 7
    metadata_role = handoff["final_before_builder_metadata_role"]
    builder = next(doc(row["receipt"]["path"]) for row in handoff["actual_processes"] if row["actual_pid"] == 3491905)
    assert builder["before"][metadata_role["path"]]["sha256"] == metadata_role["sha256"]
    metadata = doc(REG + "/source-preparation-metadata.json")
    assert len(metadata["sources"]) == 10
    for entry in metadata["sources"]:
        source_projection(entry, metadata["declared_path_replacements"])
    previous_materializer = raw(PLAN + "/preimages/tier2-support-019-qualification-plan-009/materialize_registration.py")
    assert previous_materializer == raw(OLD_PLAN + "/materialize_registration.py")
    assert previous_materializer.count(OLD_EXPECTED.encode()) == 1
    assert previous_materializer.replace(OLD_EXPECTED.encode(), EXPECTED.encode()) == raw(PLAN + "/materialize_registration.py")
    old_pure = raw("validation/tier2-support019-core-drivers-004/verify_carrier_controls.py")
    old_path = "validation/tier2-support019-author-diagnostic-implementation-005/bootstrap_tier2_carrier_view.py"
    assert old_pure.count(OLD_EXPECTED.encode()) == old_pure.count(old_path.encode()) == 1
    assert old_pure.replace(OLD_EXPECTED.encode(), EXPECTED.encode()).replace(old_path.encode(), (CANDIDATE + "/bootstrap_tier2_carrier_view.py").encode()) == raw(PURE + "/verify_carrier_controls.py")
    assert raw(PURE + "/WITNESS_SCHEMA.json") == raw("validation/tier2-support019-core-drivers-004/WITNESS_SCHEMA.json")
    for name in ("claims.json", "control-registration.json", "mandatory-floor.json", "producer-contracts.json", "audit_actual.py", "test_admission_controls.py"):
        assert raw(PLAN + "/" + name) == raw(OLD_PLAN + "/" + name), name
    claims = doc(PLAN + "/claims.json"); controls = doc(PLAN + "/control-registration.json")
    assert claims["total_count"] == 27 and len(controls["equality_original44"]) == 44 and len(controls["equality_new11"]) == 11
    assert len(config["adapters"]["exact_pure_test_ids"]) == len(doc(PURE + "/WITNESS_SCHEMA.json")["case_contracts"]) == 30
    assert len(config["capture003_checkpoint_control_ids"]) == 17
    assert config["capture003_checkpoint_control_ids"] == doc(REG + "/checkpoint-control-identities.json")["ids"]
    adaptation = doc(PLAN + "/predicate-reader-adaptation-specification.json")
    previous = doc(OLD_PLAN + "/predicate-reader-adaptation-specification.json")
    adaptation_without = dict(adaptation)
    previous_without = dict(previous)
    for name in ("binding_status", "source_binding_resolution", "source_templates", "status"):
        adaptation_without.pop(name); previous_without.pop(name)
    assert adaptation_without == previous_without and adaptation["adapter_revision"] == "007"
    assert len(adaptation["source_templates"]) == 637
    for identity in adaptation["source_templates"]:
        authenticate(identity)
    profile = doc(handoff["active_carrier_profile"]["path"])
    assert config["adapters"]["predicate_reader_carrier_literals"] == handoff["active_carrier_profile"]["path"]
    assert config["adapters"]["predicate_reader_capture_literals"] == handoff["active_capture_profile"]["path"]
    source = raw(CANDIDATE + "/bootstrap_tier2_carrier_view.py")
    assert "sha256:" + hashlib.sha256(source).hexdigest() == EXPECTED
    helper_path = ADAPTER + "/author_protocol_reconstruction.py"; raw(helper_path)
    helper = module("q005_independent_literal_reconstruction", helper_path)
    helper.validate_literals(source, profile)
    assert profile["marker_pattern"] == "UNRELATED_019_005_[A-Z_]+"
    assert all(label.startswith("UNRELATED_019_005_") for label in profile["expected_markers"])
    reference = {"path": "/unrelated/binding-review005/é🙂quote\"slash\\", "sha256": "sha256:" + "c" * 64, "request_sha256": "sha256:" + "d" * 64}
    message = helper.author_message(profile, reference)
    assert message == helper.author_message(helper.extract_schema(source), reference)
    capture = doc(handoff["active_capture_profile"]["path"])
    authenticate(capture["source"])
    tree = ast.parse(raw(capture["source"]["path"]))
    original_capture = doc(ADAPTER + "/predicate-reader-capture-literals.json")
    assert set(capture["function_ast_hashes"]) == set(original_capture["function_ast_hashes"])
    functions = {n.name: "sha256:" + hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest() for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in capture["function_ast_hashes"]}
    assert functions == capture["function_ast_hashes"] and len(functions) == 6
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id in capture["constants"]}
    assert json.loads(json.dumps(constants)) == capture["constants"] and len(constants) == 7
    assert next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "CANDIDATE_SHA256") == EXPECTED
    preflight = doc(REG + "/preflight-005/stdout.log")
    assert preflight["tests_executed"] == preflight["model_calls"] == 0 and preflight["task_inputs"] is False
    assert preflight["test_count"] == len(preflight["test_ids"]) == 208 and len(preflight["test_modules"]) == 18
    assert len(preflight["source_files"]) == 246 and len(preflight["test_sources"]) == 133
    assert preflight["source_root"] == config["source_root"] == handoff["source_root"]
    # The registered data generator owns fixture truth. Only raw byte hashes
    # were authenticated above; no expected-answer or carrier payload is parsed.
    assert len(config["source_preservation_only_inputs"]) == 6 and config["prior_pass_inheritance"] is False
    registered = json.loads((HERE / "registration-before-source-check.json").read_bytes())
    raw(Path(__file__).relative_to(ROOT).as_posix())
    assert set(READS).issubset(registered["source_guards"])
    for name, identity in READS.items():
        assert identity == registered["source_guards"][name], name
    after = {name: {"sha256": "sha256:" + hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), "byte_count": (ROOT / name).stat().st_size} for name in READS}
    assert READS and READS == after
    record = {"format": "verislop.q005-independent-finite-source-check/1", "status": "SOURCE_READINESS_CHECKED_RUNTIME_UNQUALIFIED", "pid": os.getpid(), "integer_exit_status": 0, "registered_interpreter": sys.executable, "finite_groups": 6, "actual_processes_authenticated": processes, "exact_helper_outputs": 10, "source_templates": 637, "claims": 27, "equality_controls": 55, "pure_contracts": 30, "checkpoint_ids": 17, "test_ids": 208, "test_modules": 18, "active_message_sha256": "sha256:" + hashlib.sha256(message).hexdigest(), "active_message_bytes": len(message), "before": READS, "after": after, "qualified_runtime_calls": 0, "model_calls": 0, "VIEW_calls": 0, "qualification_authority": False, "activation_authority": False}
    (HERE / "FINITE_SOURCE_CHECK_ACTUAL_RESULT.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("status", "pid", "integer_exit_status", "finite_groups", "source_templates", "claims", "equality_controls", "pure_contracts", "checkpoint_ids", "test_ids", "test_modules")}))


if __name__ == "__main__":
    main()
