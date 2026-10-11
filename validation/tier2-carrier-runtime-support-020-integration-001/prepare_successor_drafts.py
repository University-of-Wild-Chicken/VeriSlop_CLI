"""One finite registered source transform; no production or qualification writes."""
from pathlib import Path
import ast
import hashlib
import json
import os

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def transform(text, old, new):
    assert text.count(old) == 1, "SOURCE_TRANSFORM_ANCHOR_NOT_SINGLE: " + old[:100]
    return text.replace(old, new, 1)


def write_new(name, raw):
    path = HERE / name
    assert not path.exists()
    path.write_bytes(raw)


def main():
    inputs = json.loads((HERE / "SOURCE_INPUTS_BEFORE_DRAFT.json").read_text())["inputs"]
    def baseline(name):
        ref = inputs[name]
        raw = (ROOT / ref["preimage"]).read_bytes()
        assert sha(raw) == ref["sha256"] and len(raw) == ref["byte_count"]
        assert (ROOT / name).read_bytes() == raw, "BASELINE_SOURCE_CHANGED"
        return raw.decode("utf-8", "strict")
    boot = baseline("synthetic_dataset/tools/bootstrap_tier2.py")
    boot = transform(boot, "from synthetic_dataset.tools import bootstrap_tier2_carrier_view as carrier_view\n",
                     "from synthetic_dataset.tools import bootstrap_tier2_carrier_view as carrier_view\nfrom synthetic_dataset.tools import bootstrap_tier2_runtime_integration as runtime_integration\n")
    boot = transform(boot, '    "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py")',
                     '    "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py",\n    "synthetic_dataset/tools/bootstrap_tier2_runtime_integration.py")')
    boot = transform(boot, '    return {path.relative_to(repo).as_posix(): canonical.digest(_regular(path)) for path in sorted(paths)}',
                     '    inventory = {path.relative_to(repo).as_posix(): canonical.digest(_regular(path)) for path in sorted(paths)}\n    runtime_sources = runtime_integration.source_inventory(repo)\n    for name, digest in runtime_sources.items():\n        if name in inventory and inventory[name] != digest:\n            raise ValueError("INPUT_MUTATION: registered runtime source identity differs")\n        inventory[name] = digest\n    return dict(sorted(inventory.items()))')
    boot = transform(boot, '        "relay_mode": "file", "carrier_format": CARRIER_FORMAT, "fork_turns": "none", "fresh_agent_per_request": True,',
                     '        "relay_mode": "file", "carrier_format": CARRIER_FORMAT, "fork_turns": "none", "fresh_agent_per_request": True,\n        "carrier_runtime_registration": runtime_integration.delivery_registration(REPO),')
    boot = transform(boot, '    frozen = {name: canonical.digest(_regular(cohort / "execution-source" / name)) for name in protocol["source_files"]}',
                     '    if protocol.get("carrier_runtime_registration") != runtime_integration.delivery_registration(REPO):\n        raise ValueError("INPUT_MUTATION: carrier runtime selection differs from frozen source")\n    frozen = {name: canonical.digest(_regular(cohort / "execution-source" / name)) for name in protocol["source_files"]}')
    boot = transform(boot, 'def _carrier_binding(cohort: Path, task: str, request_path: Path, request: dict, *, create: bool) -> dict:',
                     'def _carrier_binding(cohort: Path, task: str, request_path: Path, request: dict, *, create: bool, runtime_registration: dict | None = None) -> dict:')
    boot = transform(boot, '    message = carrier_view.agent_message(reference)',
                     '    runtime_binding = None\n    if runtime_registration is None:\n        message = carrier_view.agent_message(reference)\n    else:\n        if runtime_registration != runtime_integration.delivery_registration(REPO):\n            raise ValueError("INPUT_MUTATION: native compact runtime registration differs")\n        message, runtime_binding = runtime_integration.native_message(REPO, reference, create=create)')
    boot = transform(boot, '    if path.is_symlink() or receipt_path.is_symlink():',
                     '    if runtime_binding is not None:\n        receipt["format"] = "verislop.collaboration-carrier-binding/0.2"\n        receipt["carrier_runtime"] = runtime_binding\n    if path.is_symlink() or receipt_path.is_symlink():')
    boot = transform(boot, '**_carrier_binding(cohort, task, request_path, request, create=create),',
                     '**_carrier_binding(cohort, task, request_path, request, create=create,\n                               runtime_registration=protocol.get("carrier_runtime_registration")),')
    write_new("bootstrap_tier2.py", boot.encode())

    pred = baseline("validation/tier2-support-019-qualification-adapters-007/predicate_reader.py")
    pred = transform(pred, '        protocol.validate_literals(source,literals)\n        return literals',
                     '        if "compact_protocol" in literals:\n            protocol.validate_literals(source,literals,self.author_protocol_sources(literals))\n        else:\n            protocol.validate_literals(source,literals)\n        return literals')
    pred = transform(pred, '    def author_message(self, reference):\n        literals=self.recipe_literals()\n        return self.author_protocol_module(literals).author_message(literals,reference)',
                     '    def author_protocol_sources(self, literals):\n        if "compact_protocol" not in literals:\n            return {}\n        identities=literals["compact_protocol"]["sources"]\n        need(type(identities) is dict and set(identities)=={"generator","reader","runtime","descriptor"}, "COMPACT_SOURCE_ROLES_NOT_CLOSED")\n        sources={}\n        for role, identity in identities.items():\n            need(type(identity) is dict and set(identity)=={"path","sha256"} and self.hashes.get(identity["path"])==identity["sha256"], "COMPACT_SOURCE_NOT_FROZEN:"+role)\n            sources[role]=self.read(identity["path"],identity["sha256"])\n        return sources\n\n    def author_message(self, reference):\n        literals=self.recipe_literals()\n        protocol=self.author_protocol_module(literals)\n        if "compact_protocol" in literals:\n            return protocol.author_message(literals,reference,self.author_protocol_sources(literals))\n        return protocol.author_message(literals,reference)')
    write_new("predicate_reader.py", pred.encode())

    extra = baseline("validation/tier2-support-019-qualification-adapters-007/additional_predicates.py")
    extra = transform(extra, '        protocol.validate_literals(source, literals)\n        message = self.additional_ref(index["submitted_message_ref"])',
                      '        if "compact_protocol" in literals:\n            identities = literals["compact_protocol"]["sources"]\n            require(type(identities) is dict and set(identities) == {"generator", "reader", "runtime", "descriptor"}, "COMPACT_SOURCE_ROLES_NOT_CLOSED")\n            sources = {}\n            for role, identity in identities.items():\n                require(type(identity) is dict and set(identity) == {"path", "sha256"} and self.hashes.get(identity["path"]) == identity["sha256"], "COMPACT_SOURCE_NOT_FROZEN:" + role)\n                sources[role] = self.read(self.registered(self.path(identity["path"])), identity["sha256"])\n            protocol.validate_literals(source, literals, sources)\n            expected_message = protocol.author_message(literals, reference, sources)\n        else:\n            protocol.validate_literals(source, literals)\n            expected_message = protocol.author_message(literals, reference)\n        message = self.additional_ref(index["submitted_message_ref"])')
    extra = transform(extra, '                protocol.author_message(literals, reference), "ORIGINAL_PLAIN_AUTHOR_MESSAGE_NOT_EXACT")',
                      '                expected_message, "ORIGINAL_PLAIN_AUTHOR_MESSAGE_NOT_EXACT")')
    write_new("additional_predicates.py", extra.encode())

    fixture = baseline("validation/tier2-support019-registration-inputs-005/prepare_unrelated_fixture.py")
    fixture = transform(fixture, 'from pathlib import Path\n', 'from pathlib import Path\nfrom synthetic_dataset.tools import bootstrap_tier2_runtime_integration as runtime_integration\n')
    fixture = transform(fixture, 'CANDIDATE_PATH = HERE.parents[1] / "validation/tier2-support019-author-recovery-implementation-006/bootstrap_tier2_carrier_view.py"',
                        '# Legacy carrier source and the compact deployment are explicit registered CLI inputs.')
    fixture = transform(fixture, 'def fixture():', 'def fixture(markers=MARKERS, system=SYSTEM):')
    fixture = transform(fixture, '    user = (MARKERS[0] + "\\n" + ATOM * 11000\n            + "\\n" + MARKERS[1] + "\\n" + ATOM * 11000\n            + "\\n" + MARKERS[2] + "\\n" + ATOM * 11000\n            + "\\n" + MARKERS[3] + "🙂\\t ")',
                        '    user = (markers[0] + "\\n" + ATOM * 11000\n            + "\\n" + markers[1] + "\\n" + ATOM * 11000\n            + "\\n" + markers[2] + "\\n" + ATOM * 11000\n            + "\\n" + markers[3] + "🙂\\t ")')
    fixture = transform(fixture, '    return SYSTEM, user', '    return system, user')
    fixture = transform(fixture, '    args = parser.parse_args()',
                        '    parser.add_argument("--legacy-carrier-file", type=Path, required=True)\n    parser.add_argument("--runtime-deployment-root", type=Path, required=True)\n    parser.add_argument("--fixture-registration", type=Path, required=True)\n    args = parser.parse_args()')
    fixture = transform(fixture, '    candidate_path = CANDIDATE_PATH',
                        '    candidate_path = args.legacy_carrier_file.absolute()\n    registration = json.loads(args.fixture_registration.read_text())\n    if set(registration) != {"legacy_revision", "fixture_revision", "marker_prefix", "request_id", "empty_request_id"} or not all(type(v) is str and v for v in registration.values()):\n        raise ValueError("EXACT_FRESH_FIXTURE_REGISTRATION_REQUIRED")\n    if not registration["marker_prefix"].endswith("_") or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in registration["marker_prefix"]):\n        raise ValueError("FRESH_MARKER_PREFIX_INVALID")\n    markers = tuple(registration["marker_prefix"] + suffix for suffix in ("START", "MIDDLE_A", "MIDDLE_B", "FINAL_TAIL"))\n    system_text = SYSTEM.replace("UNRELATED_019_005_", registration["marker_prefix"])\n    deployment = args.runtime_deployment_root.absolute()\n    runtime_registration = runtime_integration.delivery_registration(deployment)\n    if runtime_registration is None or frozen.get("runtime_registration") != runtime_registration:\n        raise ValueError("ROOT_REVIEWED_RUNTIME_REGISTRATION_REQUIRED")\n    runtime_descriptor = runtime_integration.load_registration(deployment)')
    fixture = transform(fixture, 'frozen.get("revision") != "006"', 'frozen.get("revision") != registration["legacy_revision"]')
    fixture = transform(fixture, '    system, user = fixture()', '    system, user = fixture(markers, system_text)')
    fixture = transform(fixture, '"request_id": "unrelated-carrier-context019-005-001"', '"request_id": registration["request_id"]')
    fixture = transform(fixture, '    expected = {"markers": list(MARKERS),', '    expected = {"markers": list(markers),')
    fixture = transform(fixture, '(output / "fresh-author-exact-message.txt").write_text(candidate.agent_message(reference))',
                        'session_directory = output / "runtime020-own-sessions"\n    session_directory.mkdir(mode=0o700)\n    (output / "fresh-author-exact-message.txt").write_text(runtime_integration.compact_message(\n        deployment, runtime_descriptor, reference, str(session_directory)))')
    fixture = transform(fixture, '"request_id": "unrelated-carrier-context019-005-empty"', '"request_id": registration["empty_request_id"]')
    fixture = transform(fixture, '        "revision": "006",', '        "revision": registration["fixture_revision"],\n        "runtime_registration": runtime_registration,\n        "runtime_source_files": runtime_descriptor["source_files"],\n        "fixture_registration_sha256": digest(args.fixture_registration.read_bytes()),')
    fixture = transform(fixture, '        "markers": list(MARKERS),', '        "markers": list(markers),')
    write_new("prepare_unrelated_fixture.py", fixture.encode())

    legacy = baseline("validation/tier2-support-019-qualification-adapters-007/author_protocol_reconstruction.py")
    extension = (HERE / "compact_reconstruction_extension.py").read_text()
    write_new("compact_author_protocol_reconstruction.py", (legacy + "\n\n" + extension).encode())
    for name in ("bootstrap_tier2.py", "predicate_reader.py", "additional_predicates.py", "prepare_unrelated_fixture.py", "compact_author_protocol_reconstruction.py"):
        ast.parse((HERE / name).read_bytes())
    print(json.dumps({"pid": os.getpid(), "candidate_sources_prepared": 5, "production_writes": 0, "qualification_calls": 0}))


if __name__ == "__main__":
    main()
