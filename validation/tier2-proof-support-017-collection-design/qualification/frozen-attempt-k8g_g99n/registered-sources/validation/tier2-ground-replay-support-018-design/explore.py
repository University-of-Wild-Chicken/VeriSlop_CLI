"""Frozen unrelated exploration; compiler/kernel outputs are retained, not inferred."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

from verislop import canonical, dsl, leanbridge, policy
from verislop.targets import vscore3_replay as replay, vscore3_target as target

ROOT = Path(__file__).resolve().parent


def fixture(name):
    arg = {"list": "Int"} if name == "listhelper" else "Int"
    profile = {"profile_id": "ground018-unrelated", "dsl": dsl.ENCODING_V2,
        "symbols": {"transform": {"lean_decl": "VeriSlopContract.reference", "args": [arg], "result": "Int"}}}
    var = lambda i: {"tag": "var", "index": i}
    ilit = lambda n: {"tag": "int", "value": str(n)}
    body = var(0)
    helpers = []
    source_arg = {"list": "int"} if name == "listhelper" else "int"
    reference = "def reference (x : Int) : Int := x"
    right = var(0)
    assignments = [-2, 7]
    if name == "mutant":
        body = {"tag": "add", "left": var(0), "right": ilit(1)}
    if name == "listhelper":
        helpers = [{"id": "bump", "params": ["int"], "result": "int",
            "body": {"tag": "add", "left": var(0), "right": ilit(1)}}]
        mapped = {"tag": "list_map", "value": var(0), "body": {"tag": "call", "helper": "bump", "args": [var(0)]}}
        body = {"tag": "list_fold", "source": mapped, "initial": ilit(0),
            "step": {"tag": "add", "left": var(1), "right": var(0)}}
        right = {"tag": "list_sum", "value": {"tag": "list_map", "value": var(0),
            "function": {"sort": "Int", "body": {"tag": "int_add", "left": var(0), "right": ilit(1)}}}}
        reference = "def reference (xs : List Int) : Int := (xs.map (fun x => x + 1)).sum"
        assignments = [[], [-4, 2, 9]]
    program = {"language": "vscore/0.3", "profile": "data-pipeline/0.3", "declarations": [],
        "helpers": helpers, "entries": [{"id": "transform", "params": [source_arg], "result": "int", "body": body}]}
    residual = {"tag": "eq", "left": {"tag": "call", "symbol": "transform", "args": [var(0)]}, "right": right}
    if name == "bounded":
        residual = {"tag": "and", "left": residual, "right": {"tag": "forall_range",
            "lower": {"tag": "nat", "value": "0"}, "upper": {"tag": "nat", "value": "3"},
            "body": {"tag": "eq", "left": var(0), "right": var(0)}}}
    formula = {"tag": "forall", "sort": arg, "body": residual}
    p = dsl.Profile.from_json(profile)
    from verislop.reify import _Denoter
    exact = target.Printer().term(_Denoter(p).formula(formula, []))
    proof = "by intro x; rfl" if name != "bounded" else "by intro x; constructor; rfl; intro n hlo hhi; rfl"
    contract = "import VSCore3\nnamespace VeriSlopContract\n" + reference + "\ntheorem guarantee : " + exact + " := " + proof + "\nend VeriSlopContract\n"
    obligations = {"GENERIC": {"formula": formula, "source_facets": [], "lean_symbol": "VeriSlopContract.guarantee",
        "statement_hash": canonical.digest_json(formula)}}
    relation = {"bindings": [{"symbol": "transform", "entry": "transform"}]}
    spec = target.build_goal(canonical.dumps(program), relation, profile, obligations)
    return spec, contract, assignments


def main():
    global replay
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--materialize-only", action="store_true")
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    if args.baseline:
        baseline = ROOT / "baseline-vscore3_replay.py"
        if canonical.digest_file(baseline) != "sha256:7a2f5fc86b55b8c2975c46868c03195d46c0a582494c57c09b6e1cbe0c7ea0dc":
            raise ValueError("preserved baseline source identity changed")
        module_spec = importlib.util.spec_from_file_location("verislop.targets._ground018_baseline", baseline)
        replay = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(replay)
    out = Path(os.environ.get("GROUND018_OUTPUT_ROOT", str(ROOT / "exploration"))) / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    names = ["identity", "mutant", "bounded", "listhelper"]
    all_fixtures = {}
    for name in names:
        spec, contract, assignments = fixture(name)
        folder = out / name
        folder.mkdir()
        (folder / "source.json").write_bytes(spec.source_bytes)
        (folder / "Contract.lean").write_text(contract)
        (folder / "Goal.lean").write_text(spec.text)
        (folder / "assignments.json").write_bytes(canonical.dumps(assignments))
        all_fixtures[name] = (spec, contract, assignments)
    manifest = {str(p.relative_to(out)): canonical.digest_file(p) for p in sorted(out.rglob("*")) if p.is_file()}
    for document in ("specification.json", "qualification-plan.json", "evidence-contract.json", "activation-001.json",
                     "recipe-001.json", "export-frontier-005-freeze.json", "frontier-evidence-006-freeze.json",
                     "negative-controls-007-freeze.json", "clean-builds-008-freeze.json"):
        manifest[document] = canonical.digest_file(ROOT / document)
    manifest["explore.py"] = canonical.digest_file(Path(__file__))
    manifest["vscore3_replay.py"] = canonical.digest_file(Path(replay.__file__))
    from verislop.targets import vscore3_source, vscore3_target, vscore_target, vscore_source
    from verislop import exprjson, reify, fsutil
    for module in (vscore3_source, vscore3_target, vscore_target, vscore_source, leanbridge, dsl, policy, exprjson, reify, fsutil, canonical):
        manifest[str(Path(module.__file__).relative_to(Path.cwd()))] = canonical.digest_file(Path(module.__file__))
    manifest.update({"library:" + module: canonical.digest(source) for module, source in target.library_sources().items()})
    for path in (Path("verislop/lean/VeriSlopKernel.lean"), Path("tests/test_vscore3_ground_support_018.py")):
        manifest[str(path)] = canonical.digest_file(path)
    tc, pol = leanbridge.resolve_toolchain(), policy.get("strict")
    manifest["toolchain"] = tc.identity()
    manifest["policy"] = policy.policy_hash(pol)
    manifest["kernel_tool"] = leanbridge.kernel_tool_hash()
    (out / "frozen-inputs.json").write_bytes(canonical.dumps(manifest))
    if args.materialize_only:
        return
    original_compile, original_kernel = leanbridge.compile_named_module, leanbridge.run_kernel_tool_modules
    current = {"folder": out / "library", "serial": 0}
    current["folder"].mkdir()

    def capture_compile(*a, **kw):
        result, parts = original_compile(*a, **kw)
        serial = current["serial"]
        current["serial"] += 1
        prefix = current["folder"] / ("compile-%03d" % serial)
        prefix.with_suffix(".lean").write_bytes(a[3])
        record = {"module": a[2], "ok": result.ok, "errors": result.errors, "messages": result.messages,
            "sorry_positions": result.sorry_positions, "timed_out": result.timed_out, "process": result.process_evidence,
            "timeout_seconds": str(kw["timeout"]), "memory_mb": kw["memory_mb"]}
        prefix.with_suffix(".json").write_bytes(canonical.dumps(record))
        for suffix, data in parts.items():
            (Path(str(prefix) + suffix)).write_bytes(data)
        return result, parts

    def capture_kernel(*a, **kw):
        response = original_kernel(*a, **kw)
        (current["folder"] / "kernel-response.json").write_bytes(canonical.dumps(response))
        (current["folder"] / "kernel-request.json").write_bytes(canonical.dumps(a[3]))
        (current["folder"] / "kernel-options.json").write_bytes(canonical.dumps({
            "timeout_seconds": str(kw["timeout"]), "memory_mb": kw["memory_mb"]}))
        return response

    leanbridge.compile_named_module = capture_compile
    leanbridge.run_kernel_tool_modules = capture_kernel
    replay._library_parts(tc, pol, time.monotonic() + pol["build_timeout_seconds"], target.library_sources())
    outcomes = []
    for name, (spec, contract, assignments) in all_fixtures.items():
        current["folder"], current["serial"] = out / name, 0
        cr, _ = leanbridge.compile_named_module(tc, out / name / "contract-build", target.CONTRACT_MODULE,
            contract.encode(), {m: leanbridge.write_module_parts(out / "library-imports", m, parts)
            for m, parts in replay._LIBRARIES[next(iter(replay._LIBRARIES))].items()}, read_only=[out / "library-imports"],
            timeout=pol["build_timeout_seconds"], memory_mb=pol["memory_mb"])
        if not cr.ok:
            outcomes.append({"fixture": name, "phase": "contract", "status": "BLOCKED", "errors": cr.errors})
            continue
        ctx = SimpleNamespace(policy=pol, contract_module=cr.olean.read_bytes())
        for i, value in enumerate(assignments):
            folder = out / name / ("assignment-%d" % i)
            folder.mkdir()
            current["folder"], current["serial"] = folder, 0
            expression = replay.ground(spec, spec.obligations[0].formula, [value])
            (folder / "expression.json").write_bytes(canonical.dumps(expression))
            started = time.monotonic()
            try:
                observed = replay.check(tc, ctx, spec, expression, deadline=started + 30)
                result = {"fixture": name, "assignment": i, "status": "NOT_REPRODUCED" if observed["predicate"] else "CONFIRMED", "observed": observed}
            except (replay.Unsupported, dsl.BudgetExceeded) as exc:
                result = {"fixture": name, "assignment": i, "status": "UNSUPPORTED", "observed": None, "diagnostic": str(exc)}
            result["elapsed_seconds"] = str(time.monotonic() - started)
            (folder / "outcome.json").write_bytes(canonical.dumps(result))
            outcomes.append(result)
            print(json.dumps({"fixture": name, "assignment": i, "status": result["status"], "diagnostic": result.get("diagnostic")}), flush=True)
    (out / "outcomes.json").write_bytes(canonical.dumps(outcomes))


if __name__ == "__main__":
    main()
