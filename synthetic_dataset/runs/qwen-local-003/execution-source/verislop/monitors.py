"""Tier 1 bridge: runtime assertion wrappers for Python entry points (specification §8.3).

For each bound symbol, obligations whose universal prefix is fully bound by one observed call
(the call `f(x₁..xₙ)` with distinct prefix variables as arguments, and the result equal to a
prefix variable, `ok(v)`/`error(v)` of one, or a closed term) are monitored; the rest are listed
as not monitorable. Violation behaviour: the wrapper raises `ContractViolation` before returning
— detection, because effects inside the target are not rolled back and purity is not
established. Callers importing the unwrapped module bypass the monitors; the report says so.
Tier 1 never assigns END_TO_END_VERIFIED, and monitor installation alone never assigns TESTED.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from . import canonical, dsl, fsutil
from .errors import Diagnostic
from .events import EventSink
from .package import Package
from .targets import python_target as pt

VERIFIER = "verislop.python-tier1-monitor"
RUNTIME = Path(__file__).resolve().parent / "targets" / "monitor_runtime.py"


def _binding_pattern(body: dict[str, Any], k: int, symbol: str) -> tuple[list[int], dict[str, Any] | None] | None:
    """Find eq(call(symbol, vars), R) at the top level of the body (outside inner binders)."""
    def atoms(p: dict[str, Any]):
        if p["tag"] in ("eq",):
            yield p
        elif p["tag"] == "not":
            yield from atoms(p["body"])
        elif p["tag"] in ("and", "or", "implies", "iff"):
            yield from atoms(p["left"])
            yield from atoms(p["right"])

    for a in atoms(body):
        for lhs, rhs in ((a["left"], a["right"]), (a["right"], a["left"])):
            if lhs.get("tag") != "call" or lhs["symbol"] != symbol:
                continue
            if not all(x.get("tag") == "var" and x["index"] < k for x in lhs["args"]):
                continue
            arg_vars = [k - 1 - x["index"] for x in lhs["args"]]
            if len(set(arg_vars)) != len(arg_vars):
                continue
            if rhs.get("tag") == "var" and rhs["index"] < k:
                rb = {"var": k - 1 - rhs["index"], "wrap": None}
            elif rhs.get("tag") in ("ok", "error") and rhs["value"].get("tag") == "var" and rhs["value"]["index"] < k:
                rb = {"var": k - 1 - rhs["value"]["index"], "wrap": rhs["tag"]}
            elif _closed(rhs):
                rb = None
            else:
                continue
            bound = set(arg_vars) | ({rb["var"]} if rb else set())
            if bound == set(range(k)):
                return arg_vars, rb
    return None


def _closed(t: Any) -> bool:
    if isinstance(t, dict):
        if t.get("tag") == "var":
            return False
        return all(_closed(v) for v in t.values())
    if isinstance(t, list):
        return all(_closed(x) for x in t)
    return True


def _inner_quantifiers_finite(p: dict[str, Any]) -> bool:
    if p["tag"] in ("forall", "exists"):
        return dsl.is_finite(p["sort"]) and _inner_quantifiers_finite(p["body"])
    if p["tag"] in ("forall_range", "exists_range", "not"):
        return _inner_quantifiers_finite(p["body"])
    if p["tag"] in ("and", "or", "implies", "iff"):
        return _inner_quantifiers_finite(p["left"]) and _inner_quantifiers_finite(p["right"])
    return True


def generate(pkg: Package, events: EventSink, irj: dict[str, Any], profile: dict[str, Any], statements: dict[str, Any],
             proposal: dict[str, Any]) -> list[Diagnostic]:
    out_dir = pkg.path("bridges") / "tier1"
    if out_dir.exists():
        fsutil.remove_tree(out_dir)
    out_dir.mkdir(parents=True)
    bindings = {b["symbol"]: b for b in proposal["bindings"]}
    spec: dict[str, Any] = {"runtime": "verislop.monitor-runtime/0.1", "profile": pt.PROFILE_ID,
                            "enums": {k: v["constructors"] for k, v in profile["enums"].items()}, "symbols": {}}
    not_monitorable: list[dict[str, str]] = []
    for sym, s in profile["symbols"].items():
        spec["symbols"][sym] = {"args": s["args"], "result": s["result"], "obligations": []}
    for oid, rec in sorted(irj["obligations"].items()):
        if rec["role"] != "guarantee" or rec["kind"] == "non_vacuity":
            continue
        formal = rec["formal"]
        if rec["kind"] in ("liveness_property", "resource_constraint"):
            not_monitorable.append({"obligation": oid, "reason": f"a {rec['kind']} cannot be established by finite per-call monitoring"})
            continue
        if formal["representation"] != "contract_dsl":
            not_monitorable.append({"obligation": oid, "reason": "opaque statement: no executable monitor is fabricated"})
            continue
        h = formal["formula_ref"].rsplit("@", 1)[1].split(":")[1]
        formula = canonical.load_file(pkg.path("accepted") / "expressions" / f"{h}.json")["formula"]
        prefix, body = dsl.prefix(formula)
        placed = False
        for sym in sorted(dsl.calls(formula)):
            pat = _binding_pattern(body, len(prefix), sym)
            if pat and _inner_quantifiers_finite(body) and sym in bindings:
                spec["symbols"][sym]["obligations"].append({"id": oid, "prefix": prefix, "body": body,
                                                            "arg_vars": pat[0], "result_binding": pat[1]})
                placed = True
                break
        if not placed:
            not_monitorable.append({"obligation": oid, "reason": "the prefix is not bound by one observed call, or inner quantifiers range over Nat"})
    impl_rel = "../../" + pkg.rel(pkg.path("implementation"))
    lines = [
        '"""Generated by `verislop generate --tier 1`: monitored entry points (python-v0_1).',
        "",
        "Violation behaviour: ContractViolation is raised before returning (detection; effects inside the",
        "target are not rolled back). Importing the implementation module directly bypasses these monitors.",
        '"""',
        "import json as _json",
        "import os as _os",
        "import sys as _sys",
        "",
        "_HERE = _os.path.dirname(_os.path.abspath(__file__))",
        f"_sys.path.insert(0, _os.path.normpath(_os.path.join(_HERE, {impl_rel!r})))",
        "_sys.path.insert(0, _HERE)",
        "import verislop_monitor_runtime as _rt",
        "",
        f"SPEC = _json.loads({json.dumps(canonical.dumps(spec).decode())})",
        "ContractViolation = _rt.ContractViolation",
        "",
    ]
    imports = []
    impls = []
    for sym, b in sorted(bindings.items()):
        mod = b["object"]["file"][:-3].replace("/", ".")
        alias = f"_impl_{sym.replace('.', '_')}"
        imports.append(f"from {mod} import {b['object']['qualname']} as {alias}")
        impls.append(f"    {sym!r}: {alias},")
    lines += imports + ["", "_IMPLS = {", *impls, "}", ""]
    for sym, b in sorted(bindings.items()):
        alias = f"_impl_{sym.replace('.', '_')}"
        lines += [
            f"def {b['object']['qualname']}(*args):",
            f"    result = {alias}(*args)",
            f"    _rt.check(SPEC, {sym!r}, _IMPLS, list(args), result)",
            "    return result",
            "",
        ]
    fsutil.atomic_write(out_dir / "verislop_monitors.py", "\n".join(lines).encode())
    shutil.copyfile(RUNTIME, out_dir / "verislop_monitor_runtime.py")
    placement = {
        "schema_version": "0.1", "artifact_kind": "tier1_monitor_placement",
        "violation_behavior": "detection: raise before returning; no rollback of target effects",
        "bypassable": True, "bypass_note": "the unwrapped implementation module remains importable",
        "monitored": {sym: [o["id"] for o in s["obligations"]] for sym, s in spec["symbols"].items()},
        "not_monitorable": not_monitorable,
        "entry_points_wrapped": sorted(b["object"]["qualname"] for b in bindings.values()),
        "runtime_sha256": canonical.digest(RUNTIME.read_bytes()),
        "monitors_sha256": canonical.digest((out_dir / "verislop_monitors.py").read_bytes()),
    }
    fsutil.write_json(out_dir / "placement.json", placement, pretty=True)
    events.emit("verifier_decision", "generate", f"Tier 1 monitors: {sum(len(v) for v in placement['monitored'].values())} obligation(s) monitored, "
                f"{len(not_monitorable)} not monitorable")
    diags = [Diagnostic("UNSUPPORTED_SEMANTICS", f"{n['obligation']}: not monitored at runtime ({n['reason']})", obligations=[n["obligation"]], severity="warning")
             for n in not_monitorable]
    return diags
