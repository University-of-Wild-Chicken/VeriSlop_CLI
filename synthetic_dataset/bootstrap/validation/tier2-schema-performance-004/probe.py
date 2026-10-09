"""Read-only finite schema performance probe; never used as registered evidence.

These unrelated inputs exercise only structural JSON-schema validation. No model,
task package, proof, source admission or lifecycle claim is consulted or changed.
"""
from __future__ import annotations

from collections import Counter
import copy
import cProfile
import io
import json
from pathlib import Path
import pstats
import time
import traceback

from verislop import canonical
from verislop.jsonschema_lite import Registry

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
SID = "urn:verislop:schema:vscore-source:0.3"
SOURCE = REPO / "schemas/vscore-source-v3.schema.json"
CALL_LIMIT = 3_000_000
CPU_LIMIT_NS = 30_000_000_000


def program(depth):
    value = {"tag": "var", "index": 0}
    for _ in range(depth):
        value = {"tag": "list_map", "value": value, "body": {
            "tag": "add", "left": {"tag": "var", "index": 0},
            "right": {"tag": "int", "value": "-7"}}}
    return {"declarations": [], "entries": [{"body": value, "id": "map_chain",
        "params": [{"list": "int"}], "result": {"list": "int"}}], "helpers": [],
        "language": "vscore/0.3", "profile": "data-pipeline/0.3"}


def node_count(value):
    if isinstance(value, dict):
        return 1 + sum(node_count(v) for v in value.values())
    if isinstance(value, list):
        return 1 + sum(node_count(v) for v in value)
    return 1


def normalized(issues):
    return [{"path": issue.path, "message": issue.message} for issue in issues]


def register(kind=Registry):
    reg = kind()
    reg.add(canonical.load_file(SOURCE))
    return reg


class EngineeringLimit(Exception):
    pass


class CountedRegistry(Registry):
    def validate(self, instance, schema_id):
        self.calls = 0
        self.paths = Counter()
        self.schemas = Counter()
        self.start_cpu = time.process_time_ns()
        self.stack = None
        return super().validate(instance, schema_id)

    def _validate(self, inst, schema, base, path, out):
        self.calls += 1
        self.paths[path] += 1
        label = schema.get("properties", {}).get("tag", {}).get("const") if isinstance(schema, dict) else None
        self.schemas[label or ("$ref" if isinstance(schema, dict) and "$ref" in schema else "other")] += 1
        if self.calls == 20_000:
            self.stack = traceback.format_stack(limit=18)
        if self.calls > CALL_LIMIT or (self.calls % 4096 == 0 and time.process_time_ns() - self.start_cpu > CPU_LIMIT_NS):
            raise EngineeringLimit("finite engineering probe limit; no model/task deadline")
        return super()._validate(inst, schema, base, path, out)


class MemoRegistry(Registry):
    """Local proposal: cache exact issues per invocation, including their paths.

    All oneOf branches still contribute to the exact match count. Only repeated
    visits to the same instance/schema/base/path reuse completed results. This
    prototype is intentionally outside production and current frozen sources.
    """
    def validate(self, instance, schema_id):
        self.memo = {}
        self.calls = self.misses = self.hits = 0
        try:
            return super().validate(instance, schema_id)
        finally:
            self.memo = None

    def _validate(self, inst, schema, base, path, out):
        self.calls += 1
        key = (id(inst), id(schema), base, path)
        cached = self.memo.get(key)
        if cached is not None:
            self.hits += 1
            out.extend(cached)
            return
        self.misses += 1
        fresh = []
        super()._validate(inst, schema, base, path, fresh)
        self.memo[key] = tuple(fresh)
        out.extend(fresh)


def measured(reg, value):
    start_wall, start_cpu = time.perf_counter_ns(), time.process_time_ns()
    status, issues = "COMPLETE", None
    try:
        issues = normalized(reg.validate(value, SID))
    except EngineeringLimit as exc:
        status = "ENGINEERING_PROBE_LIMIT"
        error = str(exc)
    result = {"status": status, "wall_ns": time.perf_counter_ns() - start_wall,
              "cpu_ns": time.process_time_ns() - start_cpu, "issues": issues}
    if status != "COMPLETE":
        result["error"] = error
    for field in ("calls", "misses", "hits"):
        if hasattr(reg, field):
            result[field] = getattr(reg, field)
    if hasattr(reg, "paths"):
        result["most_visited_paths"] = reg.paths.most_common(8)
        result["schema_visits"] = dict(reg.schemas)
        result["sample_stack"] = reg.stack
    return result


def save(name, value):
    (ROOT / name).write_bytes(canonical.dumps(value))


def main():
    observations = []
    for depth in range(5):
        value = program(depth)
        data = canonical.dumps(value)
        (ROOT / f"nested-map-depth-{depth}.json").write_bytes(data)
        row = {"depth": depth, "input": f"nested-map-depth-{depth}.json",
               "input_sha256": canonical.digest(data), "input_bytes": len(data),
               "json_nodes": node_count(value), "instrumented_original": measured(register(CountedRegistry), value),
               "local_memo_proposal": measured(register(MemoRegistry), value)}
        if depth <= 3:
            row["uninstrumented_original"] = measured(register(), value)
        observations.append(row)
        save("observations-in-progress.json", observations)
        print(json.dumps({"depth": depth, "calls": row["instrumented_original"]["calls"],
            "original_cpu_ns": row["instrumented_original"]["cpu_ns"],
            "original_status": row["instrumented_original"]["status"],
            "memo_calls": row["local_memo_proposal"]["calls"],
            "memo_cpu_ns": row["local_memo_proposal"]["cpu_ns"]}), flush=True)

    cases = {"valid_nested_map": program(2)}
    cases["unknown_tag"] = copy.deepcopy(program(2))
    cases["unknown_tag"]["entries"][0]["body"]["tag"] = "absent_constructor"
    cases["missing_body"] = copy.deepcopy(program(2))
    del cases["missing_body"]["entries"][0]["body"]["body"]
    cases["extra_property"] = copy.deepcopy(program(2))
    cases["extra_property"]["entries"][0]["body"]["unexpected"] = 7
    cases["wrong_child_type"] = copy.deepcopy(program(2))
    cases["wrong_child_type"]["entries"][0]["body"]["body"] = True
    cases["noncanonical_signed_int"] = copy.deepcopy(program(2))
    cases["noncanonical_signed_int"]["entries"][0]["body"]["body"]["right"]["value"] = "-0"
    comparisons = []
    for name, value in cases.items():
        save(f"case-{name}.json", value)
        old, new = measured(register(), value), measured(register(MemoRegistry), value)
        comparisons.append({"case": name, "original": old, "local_memo_proposal": new,
            "exact_issue_output_equal": old["issues"] == new["issues"]})

    overlap_sid = "urn:verislop:engineering:overlap-schema"
    overlap_schema = {"$id": overlap_sid, "oneOf": [{"type": "integer"}, {"type": "number"}]}
    save("overlap-schema.json", overlap_schema)
    for value in (3, True, "text"):
        old, new = Registry(), MemoRegistry()
        old.add(overlap_schema)
        new.add(overlap_schema)
        before, after = normalized(old.validate(value, overlap_sid)), normalized(new.validate(value, overlap_sid))
        comparisons.append({"case": "overlapping_oneOf", "input": value, "original_issues": before,
            "proposal_issues": after, "exact_issue_output_equal": before == after})
    # Mutating between separate invocations must not reuse stale successes.
    reused = register(MemoRegistry()) if False else register(MemoRegistry)
    changing = program(1)
    first = normalized(reused.validate(changing, SID))
    changing["entries"][0]["body"]["tag"] = "absent_constructor"
    second = normalized(reused.validate(changing, SID))
    comparisons.append({"case": "invocation_cache_reset", "first_issues": first,
        "second_issues": second, "matches_original_after_mutation": second == normalized(register().validate(changing, SID))})

    profile = cProfile.Profile()
    profile.enable()
    register().validate(program(2), SID)
    profile.disable()
    profile.dump_stats(str(ROOT / "original-depth-2.prof"))
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(25)
    (ROOT / "original-depth-2-profile.txt").write_text(stream.getvalue())
    save("comparisons.json", comparisons)
    report = {"format": "verislop.unrelated-schema-performance-probe/0.1",
        "scope": "Read-only structural validator diagnosis only; no task, model, source admission or milestone authority.",
        "schema_sha256": canonical.digest_file(SOURCE),
        "original_validator_sha256": canonical.digest_file(REPO / "verislop/jsonschema_lite.py"),
        "probe_sha256": canonical.digest_file(Path(__file__)),
        "finite_engineering_limits": {"instrumented_calls_per_input": CALL_LIMIT,
            "instrumented_cpu_ns_per_input": CPU_LIMIT_NS, "uninstrumented_max_depth": 3},
        "observations": observations, "comparisons": comparisons}
    save("report.json", report)
    print("REPORT", ROOT / "report.json", flush=True)


if __name__ == "__main__":
    main()
