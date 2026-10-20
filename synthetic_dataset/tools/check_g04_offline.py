"""Read-only G04 comparison against a frozen VSCore 0.3 bridge source.

This command is not part of the model harness or any acceptance gate. It compares
source results to independent concrete request outputs, never accepted formulas.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synthetic_dataset.tools import g04_oracle as oracle
from verislop import canonical, leanbridge
from verislop.bridges import vscore3_checker as checker
from verislop.bridges.manifest import PackageReader
from verislop.exprjson import app
from verislop.reify import _Denoter
from verislop.targets import vscore3_replay as kernel, vscore3_target as target

AUTHORITY = ("Finite independent semantic diagnostic only; does not grant TESTED, Lean proof, "
             "END_TO_END_VERIFIED, release review or strict Tier 2 qualification.")
INPUT = {"prefix": "String", "assets": [{"path": "String", "bytes": "Nat", "enabled": "Bool"}]}
OUTPUT = {"items": [{"destination": "String", "bytes": "Nat", "destination_length": "Nat"}],
          "total_bytes": "Nat", "item_count": "Nat"}


def check_shape(sort, shape, profile):
    """Match exact named fields, allowing only nominal record IDs/order to vary."""
    if isinstance(shape, str):
        if sort != shape:
            raise ValueError("G04 scalar sort mismatch")
    elif isinstance(shape, list):
        if not isinstance(sort, dict) or set(sort) != {"list"}:
            raise ValueError("G04 list sort mismatch")
        check_shape(sort["list"], shape[0], profile)
    else:
        if not isinstance(sort, dict) or set(sort) != {"record"}:
            raise ValueError("G04 record sort mismatch")
        fields = profile.records[sort["record"]]["fields"]
        if len(fields) != len(shape) or {f["name"] for f in fields} != set(shape):
            raise ValueError("G04 exact field inventory mismatch")
        for field in fields:
            check_shape(field["sort"], shape[field["name"]], profile)


def endpoint(spec):
    matches = [s for s in spec.symbols if s.entry == "solve"]
    if len(matches) != 1 or len(matches[0].arg_sorts) != 1:
        raise ValueError("G04 requires exactly one solve entry taking one record")
    selected = matches[0]
    check_shape(selected.arg_sorts[0], INPUT, spec.profile)
    check_shape(selected.result_sort, OUTPUT, spec.profile)
    return selected


def carrier(value, sort, profile):
    """Encode independently supplied concrete values into native nominal carriers."""
    if isinstance(sort, str):
        return value
    if "list" in sort:
        return tuple(carrier(v, sort["list"], profile) for v in value)
    name = sort["record"]
    return ("record", name, tuple(carrier(value[f["name"]], f["sort"], profile)
                                  for f in profile.records[name]["fields"]))


def equality(spec, selected, data):
    # The only expected algorithm is oracle.expected. No accepted formula/body is consulted.
    actual = app(target.gconst("source_fn_" + selected.symbol),
                 kernel.literal(carrier(data, selected.arg_sorts[0], spec.profile),
                                selected.arg_sorts[0], spec.profile))
    wanted = kernel.literal(carrier(oracle.expected(data), selected.result_sort, spec.profile),
                            selected.result_sort, spec.profile)
    return target.old.eq_expr(_Denoter(spec.profile).sort(selected.result_sort), actual, wanted)


def compare(spec, observe):
    selected = endpoint(spec)
    results = []
    for row in oracle.cases():
        record = {"case_id": row["case_id"], "input": oracle.wire(row["input"]),
                  "expected": oracle.wire(oracle.expected(row["input"]))}
        try:
            expression = equality(spec, selected, row["input"])
            observation = observe(expression)
            # A compiler error, timeout, or missing decision is never a counterexample.
            if type(observation.get("predicate")) is not bool or observation.get("kernel_replay") is not True:
                raise ValueError("missing native kernel decision")
            record.update(status="PASS" if observation["predicate"] else "FAIL", observation=observation)
        except Exception as exc:
            record.update(status="UNRESOLVED", diagnostic=f"{type(exc).__name__}: {exc}")
        results.append(record)
    status = ("FAIL" if any(r["status"] == "FAIL" for r in results) else
              "UNRESOLVED" if any(r["status"] != "PASS" for r in results) else "PASS")
    return {"status": status, "cases": results}


def run(bundle: Path, bridge_id: str, edge_id: str, source_sha256: str, seconds: float) -> dict:
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("seconds per case must be positive and finite")
    # A descriptor-relative reader rejects symlinks, hardlinks and path traversal.
    # Keep a snapshot across load_context and all probes, without writing to bundle.
    reader = PackageReader(bundle)
    try:
        plan, plan_snap = reader.json("plan.json")
        manifest, manifest_snap = reader.json("artifacts.json")
        checker._schema("bridge-plan", plan)
        checker._schema("bridge-artifacts", manifest)
        for artifact in manifest["artifacts"]:
            snap = reader.read(artifact["path"])
            if snap.sha256 != artifact["sha256"] or snap.size != artifact["size"]:
                raise ValueError("frozen artifact binding mismatch")
        ctx = checker.load_context(bundle, bridge_id, edge_id)
        reader.recheck()
        if ctx.plan_hash != plan_snap.sha256 or ctx.artifacts_hash != manifest_snap.sha256:
            raise ValueError("bundle changed while loading")
        source_hash = canonical.digest(ctx.inputs["source"][1])
        if source_sha256 != source_hash:
            raise ValueError("source hash does not match the explicitly selected frozen source")
        spec = checker.derive_goal(ctx)
        endpoint(spec)  # Reject a foreign request signature before native work.
        tc = leanbridge.resolve_toolchain(ctx.acceptance["toolchain"]["pin"])
        result = compare(spec, lambda expr: kernel.check(tc, ctx, spec, expr,
                         deadline=time.monotonic() + seconds))
        reader.recheck()
        result["binding"] = {"bridge_id": bridge_id, "edge_id": edge_id, "source_sha256": source_hash,
                             "plan_sha256": ctx.plan_hash, "artifacts_sha256": ctx.artifacts_hash,
                             "accepted_profile_sha256": ctx.accepted_profile_hash,
                             "toolchain": tc.identity()}
        return result
    finally:
        reader.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", action="store_true", help="print the finite diagnostic suite without native execution")
    parser.add_argument("--bundle", type=Path, help="frozen bridges/<bridge-id> directory (not a live run)")
    parser.add_argument("--bridge-id")
    parser.add_argument("--edge-id")
    parser.add_argument("--source-sha256", help="required sha256:<hex> of the frozen source")
    parser.add_argument("--seconds-per-case", type=float, default=60)
    args = parser.parse_args(argv)
    required = (args.bundle, args.bridge_id, args.edge_id, args.source_sha256)
    if (args.cases and any(required)) or (not args.cases and not all(required)):
        parser.error("use --cases alone, or all of --bundle/--bridge-id/--edge-id/--source-sha256")
    report = {"format": oracle.VERSION, "task": oracle.TASK, "authority": AUTHORITY,
              "request_sha256": oracle.REQUEST_SHA256,
              "suite_sha256": canonical.digest_json(oracle.suite()),
              "checker_sources": {p.name: canonical.digest_file(p) for p in (Path(__file__), Path(oracle.__file__))}}
    try:
        report.update({"status": "NOT_RUN", "cases": oracle.suite()} if args.cases else
                      run(args.bundle, args.bridge_id, args.edge_id, args.source_sha256, args.seconds_per_case))
    except Exception as exc:
        report.update(status="UNRESOLVED", diagnostic=f"{type(exc).__name__}: {exc}")
    print(canonical.dumps(report).decode())
    return {"PASS": 0, "NOT_RUN": 0, "FAIL": 1, "UNRESOLVED": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
