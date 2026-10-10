"""Frozen unrelated host preflight; no actual tool-channel or task invocation."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_once(path, data):
    with path.open("xb") as stream:
        stream.write(data)


def main():
    manifest_raw = (ROOT / "input-freeze.json").read_bytes()
    manifest = json.loads(manifest_raw)
    for path, expected in manifest["files"].items():
        actual = (ROOT / path).read_bytes()
        if digest(actual) != expected:
            raise RuntimeError("INPUT_MUTATION: " + path)
    case = json.loads((ROOT / "case.json").read_bytes())
    carrier = (ROOT / "carrier.json").read_bytes()
    producer = load_module(ROOT / "registered-inputs/producer.py", "registered_producer")
    old = load_module(ROOT / "registered-inputs/original-comparator.py", "registered_old_comparator")
    namespace = {}
    exec(producer.READER_SOURCE, namespace)
    received = namespace["carrier_view"](case["reference"], case["view"])
    write_once(ROOT / "actual-reader.stdout", received)
    record = json.loads(received)
    try:
        expected, _ = old.expected_record(case["comparator_case"], carrier)
        old_outcome = {"status": "PASS", "expected_wire_hash": digest(old.wire(expected))}
    except old.Block as exc:
        old_outcome = {"status": "BLOCK", "code": str(exc)}
    mismatch = record.get("status") == "ok" and record.get("content") == "x" and record.get("field_eof") is True and old_outcome == {"status": "BLOCK", "code": "METADATA_RESERVE_EXCEEDED"}
    result = {"format": "verislop.carrier-channel-comparator-preflight/1",
              "input_freeze_sha256": digest(manifest_raw),
              "input_root_hash": manifest["input_root_hash"],
              "actual_reader_stdout_sha256": digest(received),
              "actual_reader_record": record, "original_comparator_outcome": old_outcome,
              "concrete_mismatch_reproduced": mismatch,
              "qualification_authority": False, "actual_channel_calls": 0,
              "task_inputs": False, "model_calls": 0}
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    write_once(ROOT / "original-comparator-result.json", raw)
    print(json.dumps(result, sort_keys=True))
    return 0 if mismatch else 1


if __name__ == "__main__":
    raise SystemExit(main())
