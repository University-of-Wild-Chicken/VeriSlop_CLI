"""Authenticate source bytes and prepare the root's static ready handoff only."""
from pathlib import Path
import ast
import hashlib
import json

ROOT = Path(__file__).absolute().parents[2]
REG = "validation/tier2-support019-registration-inputs-006"
BASE = "validation/tier2-support019-final-configuration-006"
PLAN = "validation/tier2-support-019-qualification-plan-011"
ADAPTER = "validation/tier2-support-019-qualification-adapters-008"
Q = "validation/tier2-support-019-qualification-006"


def data(name):
    p = ROOT / name
    assert p.is_file() and not p.is_symlink() and p.resolve() == p.absolute(), name
    assert not name.startswith(("validation/tier2-support-019-qualification-001/",
                                "validation/tier2-support-019-qualification-002/",
                                "validation/tier2-support-019-qualification-003/",
                                "validation/tier2-support-019-qualification-004/", "validation/tier2-support-019-qualification-005/")), name
    return p.read_bytes()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def ref(name):
    raw = data(name)
    return {"path": name, "sha256": digest(raw), "byte_count": len(raw)}


def load(name):
    return json.loads(data(name))


def main():
    assert not (ROOT / Q).exists(), "No qualification execution in source preparation"
    paths = set()
    packages = []
    declarations = [
        (PLAN, "hash-manifest.json", ["files"]),
        (ADAPTER, "hash-manifest.json", ["files"]),
        ("validation/tier2-support019-core-drivers-005", "manifest.json", ["files"]),
        ("validation/tier2-support019-author-recovery-implementation-006", "hash-manifest.json", ["files"]),
        # The old production reference in this preinstallation review is historical.
        ("validation/tier2-carrier006-source-review-001", "manifest.json", ["files", "inputs"]),
        ("validation/tier2-carrier-runtime-support-020-implementation-001", "hash-manifest.json", ["files"]),
        ("validation/tier2-carrier-runtime-support-020-integration-001", "source-manifest.json", ["own_files"]),
        ("validation/tier2-carrier-runtime-support-020-integration-source-review-001", "hash-manifest.json", ["files", "inputs"]),
        ("validation/tier2-carrier-runtime-support-020-review-001", "hash-manifest.json", ["files"]),
    ]
    for folder, manifest_name, maps in declarations:
        manifest_path = folder + "/" + manifest_name
        seal_path = folder + ("/SOURCE_SEAL.sha256" if manifest_name == "source-manifest.json" else "/SEAL.sha256")
        manifest = load(manifest_path)
        tokens = data(seal_path).decode("ascii").strip().split()
        assert len(tokens) in (1, 2) and tokens[0].removeprefix("sha256:") == ref(manifest_path)["sha256"][7:]
        if len(tokens) == 2:
            assert tokens[1] == manifest_name
        paths.update((manifest_path, seal_path))
        for key in maps:
            entries = manifest[key]
            assert isinstance(entries, dict) and entries
            for name, expected in entries.items():
                relative = name if name.startswith(("/", "validation/", "synthetic_dataset/", "tests/", "verislop/", "docs/", "formal/", "grammar/", "policies/", "schemas/")) else folder + "/" + name
                actual = ref(relative)
                expected_hash = expected if isinstance(expected, str) else expected["sha256"]
                assert actual["sha256"] == expected_hash, relative
                if isinstance(expected, dict):
                    for count in ("byte_count", "bytes", "size"):
                        if count in expected:
                            assert type(expected[count]) is int and actual["byte_count"] == expected[count], relative
                paths.add(relative)
        packages.append({"manifest": ref(manifest_path), "seal": ref(seal_path), "entry_maps": maps})
    review = "validation/tier2-carrier006-source-review-001/REVIEW.json"
    assert load(review)["status"] == "SOURCE_REVIEWED_NO_CURRENT_RUNTIME_ADMISSION_BLOCKER_RUNTIME_UNQUALIFIED"
    adaptation = load(PLAN + "/predicate-reader-adaptation-specification.json")
    assert adaptation["binding_status"] == "ROOT_SOURCE_REVIEWED_FROZEN"
    assert adaptation["adapter_revision"] == "008"
    carrier = "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py"
    assert ref(carrier)["sha256"] == "sha256:f855de49fa8522cfc91053fe3f1f0db1ebd3c199260acbb97618d0f998c5eb4a"
    assert data(carrier) == data("validation/tier2-support019-author-recovery-implementation-006/bootstrap_tier2_carrier_view.py")
    paths.add(carrier)
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/"validation/tier2-carrier-runtime-support-020-installation-001").iterdir() if p.is_file())
    paths.update({'validation/tier2-carrier006-installation-001/SPECIFICATION_BEFORE_INSTALLATION.json','validation/tier2-carrier006-installation-001/production005-preinstallation.raw','validation/tier2-carrier006-installation-001/ROOT_REVIEW_AUTHENTICATION.json','validation/tier2-carrier006-installation-001/SOURCE_INSTALLATION_OBSERVATION.json'})
    for entry in adaptation["source_templates"]:
        assert ref(entry["path"])["sha256"] == entry["sha256"]
        paths.add(entry["path"])
    # Exact current preflight maps are static inventories, not execution results.
    preflight = REG + "/preflight-006/stdout.log"
    inventory = load(preflight)
    assert inventory["tests_executed"] == inventory["model_calls"] == 0 and inventory["task_inputs"] is False
    assert len(inventory["test_ids"]) == inventory["test_count"] == 208
    assert len(inventory["test_modules"]) == 18
    for key in ("source_files", "test_sources"):
        for name, expected in inventory[key].items():
            assert ref(name)["sha256"] == expected, name
            paths.add(name)
    fixture_map = REG + "/fresh-fixture-input-map.json"
    for name, expected in load(fixture_map).items():
        assert ref(name)["sha256"] == expected
        paths.add(name)
    ids = load(REG + "/checkpoint-control-identities.json")["ids"]
    tree = ast.parse(data(PLAN + "/materialize_registration.py"))
    bound = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
             if isinstance(node, ast.Assign) and len(node.targets) == 1
             and isinstance(node.targets[0], ast.Name)
             and node.targets[0].id in ("EXPECTED_CARRIER", "EXPECTED_CHECKPOINT_IDS")}
    assert bound["EXPECTED_CARRIER"] == ref(carrier)["sha256"]
    assert bound["EXPECTED_CHECKPOINT_IDS"] == tuple(ids) and len(ids) == 17
    for folder in (REG, BASE):
        for p in (ROOT / folder).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                paths.add(p.relative_to(ROOT).as_posix())
    paths.add("validation/tier2-support019-final-configuration-002/final-config.json")
    reviews = [review, "validation/tier2-carrier-runtime-support-020-integration-source-review-001/REVIEW.json",
               PLAN + "/FINAL_SUPPORT020_Q006_BINDINGS_SOURCE_FIDELITY.json"]
    paths.update(reviews)
    ready_path = BASE + "/generation-inputs-ready.json"
    assert not (ROOT / ready_path).exists()
    before = {name: ref(name) for name in sorted(paths)}
    ready = {"format": "verislop.support019-current-source-generation-ready/1",
             "status": "ROOT_SOURCE_REVIEWED_READY_FOR_CONFIGURATION_GENERATION",
             "actual_execution": 0, "qualification_authority": False, "activation_authority": False,
             "qualification_root": Q, "closure_id": "support019-final-current-root-006", "input_root": None,
             "source_dependencies": before, "sealed_packages": packages,
             "independent_source_reviews": [ref(name) for name in reviews],
             "additional_static_inputs": sorted(paths), "preflight": ref(preflight),
             "fixture_map": ref(fixture_map), "capture_registration": ref(REG + "/capture003-registration.json"),
             "checkpoint_control_ids": ids,
             "historical_preinstallation_review_inputs": "Carrier006 review own files authenticate historical preinstallation observations; installed current source binds separately through actual installation and preflight005. No old production input asserted current.",
             "prior_runtime_outcome_reuse": False}
    assert before == {name: ref(name) for name in sorted(paths)}
    with (ROOT / ready_path).open("x") as output:
        json.dump(ready, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({"status": ready["status"], "source_dependencies": len(before),
                      "sealed_packages": len(packages), "ready": ref(ready_path), "targets_executed": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
