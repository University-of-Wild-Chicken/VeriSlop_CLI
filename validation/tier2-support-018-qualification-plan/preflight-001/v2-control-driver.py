"""Host-only EOF and synthetic truncation-schema controls, never channel evidence."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main():
    freeze_raw = (ROOT / "v2-input-freeze-002.json").read_bytes()
    freeze = json.loads(freeze_raw)
    for relative, expected in freeze["files"].items():
        if digest((ROOT / relative).read_bytes()) != expected:
            raise RuntimeError("INPUT_MUTATION: " + relative)
    path = ROOT / "registered-inputs/comparator-v2.py"
    spec = importlib.util.spec_from_file_location("registered_comparator_v2", path)
    comparator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(comparator)
    case = json.loads((ROOT / "case.json").read_bytes())
    expected, _ = comparator.expected_record(case["comparator_case"], (ROOT / "carrier.json").read_bytes())
    eof_equal = comparator.wire(expected) == (ROOT / "actual-reader.stdout").read_bytes()
    controls = json.loads((ROOT / "v2-controls.json").read_bytes())
    results = [{"id": "EOF-FINAL-ENDPOINT", "status": "PASS" if eof_equal else "BLOCK"}]
    for control in controls:
        args = SimpleNamespace(capture_root=ROOT / control["capture_directory"], index=control["index"],
            index_sha256=control["index_sha256"], frozen_case_plan="case-plan.json",
            frozen_case_plan_sha256=control["case_plan_sha256"], closure_id="preflight-synthetic-only",
            input_root_hash="sha256:" + "2" * 64, source_root_hash="sha256:" + "3" * 64,
            producer_hash="sha256:" + "4" * 64, orchestrator_hash="sha256:" + "5" * 64)
        try:
            comparator.evaluate(args)
            actual = "PASS"
        except comparator.Block as exc:
            actual = "BLOCK:" + str(exc)
        results.append({"id": control["id"], "actual": actual,
                        "expected": control["expected"], "status": "PASS" if actual == control["expected"] else "BLOCK"})
    result = {"format": "verislop.comparator-v2-host-preflight/1", "input_root_hash": freeze["input_root_hash"],
        "input_freeze_sha256": digest(freeze_raw), "results": results,
        "status": "PASS" if all(row["status"] == "PASS" for row in results) else "BLOCK",
        "actual_channel_calls": 0, "fabricated_tool_json_is_only_encoder_control": True,
        "qualification_authority": False, "task_inputs": False, "model_calls": 0}
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    with (ROOT / "v2-control-result.json").open("xb") as stream:
        stream.write(raw)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
