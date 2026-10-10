"""Retain supplied observable actual call bytes; no tool or verifier execution."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical

UNAVAILABLE = {"hidden_native_outer_http_mcp_envelope": "UNAVAILABLE", "separated_stdout": "UNAVAILABLE",
               "separated_stderr": "UNAVAILABLE", "pid": "UNAVAILABLE"}


def parse(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON member")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def write(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(raw), "byte_count": len(raw)}


def wire(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8", "strict")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", required=True)
    args = parser.parse_args()
    supplied = parse(args.payload)
    relative = Path(supplied["qualification_root"])
    gate = ROOT / relative
    if (relative.is_absolute() or relative.as_posix() != supplied["qualification_root"] or
            relative.parent != Path("validation") or not relative.name.startswith("tier2-support-019-qualification-") or
            gate.resolve() != gate.absolute() or not gate.is_dir() or gate.is_symlink()):
        raise ValueError("Expected canonical registered current root")
    manifest = bootstrap.load(gate / "qualification-inputs.json")
    spec = bootstrap.load(gate / "qualification-specification.json")
    hashes = manifest["source_hashes"]
    def guard():
        for name, expected in hashes.items():
            path = ROOT / name
            if not path.is_file() or path.is_symlink() or path.resolve() != path.absolute() or canonical.digest_file(path) != expected:
                raise ValueError("Frozen input changed")
        if (canonical.digest_json(bootstrap.source_inventory()) != manifest["source_root"] or
                {p.relative_to(ROOT).as_posix(): canonical.digest_file(p) for p in (ROOT / "tests").rglob("*.py")} != spec["test_sources"] or
                hashes.get(Path(__file__).relative_to(ROOT).as_posix()) != canonical.digest_file(Path(__file__))):
            raise ValueError("Source/test/writer identity differs")
    guard()
    ordinal = supplied["ordinal"]
    if type(ordinal) is not int or not 1 <= ordinal <= spec["channel_recorder"]["max_calls"]:
        raise ValueError("Unregistered ordinal")
    kind = supplied["kind"]
    cases = spec["channel_recorder"]["cases"]
    registration = cases[supplied["case_id"]]
    if kind not in registration["kinds"]:
        raise ValueError("Unregistered call role")
    view = supplied["retained_record"]["view"]
    actual = supplied["retained_record"]["result"]
    if (not isinstance(actual, dict) or type(actual.get("exit_code")) is not int or actual["exit_code"] != 0 or
            "session_id" in actual or not isinstance(actual.get("output"), str)):
        raise ValueError("Actual completed nested object unavailable")
    nested, outer = supplied["nested_max_output_tokens"], supplied["outer_max_output_tokens"]
    if [kind, outer, nested, view["output_cap_bytes"], view["metadata_reserve_bytes"]] not in registration["budgets"]:
        raise ValueError("Unregistered call budget")
    fields = {"operation", "output_cap_bytes", "metadata_reserve_bytes"}
    if view["operation"] == "field":
        fields |= {"selector", "start_char"}
        if view["selector"] not in ("/system", "/user") or type(view["start_char"]) is not int or view["start_char"] < 0:
            raise ValueError("Malformed closed field VIEW")
    elif view["operation"] != "inventory":
        raise ValueError("Unregistered operation")
    if set(view) != fields:
        raise ValueError("VIEW is not closed")
    reference_path = ROOT / registration["reference_file"]
    factory_path = ROOT / spec["channel_recorder"]["factory_source"]
    for path in (reference_path, factory_path):
        name = path.relative_to(ROOT).as_posix()
        if (not path.is_file() or path.is_symlink() or path.resolve() != path.absolute() or
                hashes.get(name) != canonical.digest_file(path)):
            raise ValueError("Recipe reference/factory not registered")
    reference = bootstrap.load(reference_path)
    module_spec = importlib.util.spec_from_file_location("support019_observable_recorder_factory", factory_path)
    factory = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(factory)
    if view["operation"] == "inventory":
        recipe = factory.initial_collector_template(reference, supplied["case_id"])
    else:
        recipe = factory.next_collector_template(reference, view, supplied["case_id"],
                                                fault=kind in ("nested-fault", "outer-fault"))
    if kind == "legacy-nested-fault":
        recipe = factory._replace_exact_source_line(
            recipe, factory.NORMAL_ACTUAL_RESULT,
            "const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 100});",
            "ONE_LEGACY_NESTED100_BUDGET_POSITION_REQUIRED")
    if recipe != supplied["submitted_code"]:
        raise ValueError("Actual submitted recipe differs from registered fixed recipe")
    raw = actual["output"].encode("utf-8", "strict")
    parsed = None
    try:
        parsed = parse(raw)
    except (ValueError, UnicodeError):
        pass
    fault = kind in ("nested-fault", "outer-fault", "legacy-nested-fault")
    observed = supplied.get("outer_visible_observation")
    if kind == "outer-fault" and (not isinstance(observed, str) or "truncat" not in observed.lower()):
        raise ValueError("Actual visible outer truncation observation missing")
    accepted = not fault and isinstance(parsed, dict) and parsed.get("status") == "ok"
    start = view.get("start_char")
    after = start
    if accepted and view["operation"] == "field":
        after = parsed.get("next_char")
        if type(after) is not int or after < start:
            raise ValueError("Actual cursor unavailable")
    if not fault and not accepted:
        raise ValueError("Intact view not available; preserve actual failure separately")
    target = gate / "actual-channel/calls" / f"{ordinal:04d}"
    if target.exists() or target.resolve() != target.absolute():
        raise ValueError("Call evidence already exists or is indirect")
    target.mkdir(parents=True)
    retained_ref = write(target / "retained-record.json", wire(supplied["retained_record"]))
    nested_ref = write(target / "nested-result.json", wire(actual))
    output_ref = write(target / "returned-output.bin", raw)
    code_ref = write(target / "submitted-code.js", supplied["submitted_code"].encode("utf-8", "strict"))
    record = {"case_id": supplied["case_id"], "kind": kind, "view": view,
              "submitted_code_ref": code_ref, "retained_record_ref": retained_ref,
              "own_result_key": factory.collector_result_key(reference, supplied["case_id"]),
              "nested_result_ref": nested_ref, "returned_output_ref": output_ref,
              "decision": "ACCEPT" if accepted else "REJECT", "cursor_before": start, "cursor_after": after,
              "outer_max_output_tokens": outer, "nested_max_output_tokens": nested,
              "actual_result_forwards": 1, "recipe_identity_verified": True,
              "unavailable": UNAVAILABLE, "observation_scope": "rendered_items_only",
              "rendered_outer_truncation_observed": kind == "outer-fault"}
    if observed is not None:
        record["rendered_observation_ref"] = write(target / "visible-outer-observation.txt", observed.encode("utf-8", "strict"))
    record_ref = write(target / "call.json", wire(record))
    guard()
    print(json.dumps({"status": "RECORDED_OBSERVATION_ONLY", "call_ref": record_ref,
                      "cursor_before": start, "cursor_after": after,
                      "field_eof": parsed.get("field_eof") if accepted else None}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
