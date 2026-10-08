"""Implementation parameters and Tier 2 admission (milestone §1, §8).

The decision functions mirror `formal/ClosureModel/Admission.lean` one to one (`resolve_tests`,
`resolve_state`, `resolve_params`, `covered`, `transfer_supported`, `unsupported`, `admit`);
`tests/test_closure_model.py` checks them against the Lean definitions with the kernel.
`features` reduces each accepted record to the facts the model decides on, read from the
accepted IR, accepted profile and accepted formula packages only.
"""

from __future__ import annotations

from typing import Any

from .. import canonical
from ..dsl import DSLError, Profile, type_formula
from ..errors import Diagnostic
from ..lifecycle import applicability
from . import registry

TEST_FLAGS = ("omitted", "require_tests", "no_tests")
UNSUPPORTED_KINDS = ("liveness_property", "resource_constraint")


# ------------------------------------------------------------------------------------------
# parameters (model: resolveState, resolveTests, resolveParams)
# ------------------------------------------------------------------------------------------

def resolve_state(tier: int, state: str | None) -> str | None:
    if state is None:
        return "END_TO_END_VERIFIED" if tier == 2 else None
    return state


def resolve_tests(tier: int, state: str | None, flag: str) -> tuple[str | None, bool]:
    """(error code or None, require_tests). Tier 0 tests are mandatory; Tier 1 keeps its default."""
    if flag not in TEST_FLAGS:
        raise ValueError(flag)
    if state == "TESTED" and flag == "no_tests":
        return "CONFIGURATION_INVALID", False
    if flag == "require_tests":
        return None, True
    if flag == "no_tests":
        return None, tier == 0
    if state == "TESTED":
        return None, True
    return None, tier < 2


def resolve_params(tier: int, target: str, endpoint: str, version: str | None, state: str | None,
                   flag: str) -> tuple[str | None, dict[str, Any] | None]:
    """(error code, (descriptor, resolved state, require_tests)) without any downgrade."""
    err, tests = resolve_tests(tier, state, flag)
    if err:
        return err, None
    d = registry.select(tier, target, endpoint, version)
    if d is None:
        return "UNSUPPORTED_CAPABILITY", None
    s = resolve_state(tier, state)
    if s == "END_TO_END_VERIFIED" and not d["end_to_end_eligible"]:
        return "UNSUPPORTED_CAPABILITY", None
    if tests and d["testing"] != "supported":
        return "UNSUPPORTED_CAPABILITY", None
    return None, {"descriptor": d, "state": s, "require_tests": tests}


# ------------------------------------------------------------------------------------------
# obligations (model: Obligation, coveredSet, unsupportedSet, admit)
# ------------------------------------------------------------------------------------------

def is_covered(f: dict[str, Any]) -> bool:
    return bool(f["required"] and f["role"] == "guarantee" and f["e2e_applicable"])


def transfer_supported(f: dict[str, Any]) -> bool:
    return bool(f["contract_dsl"] and f["mentions_symbol"] and not f["call_in_range_bound"]
                and f["representable_sorts"] and f["kind"] not in UNSUPPORTED_KINDS)


def is_interface_declaration(f: dict[str, Any]) -> bool:
    return bool(f["required"] and f["role"] == "declaration")


def covered(fs: list[dict[str, Any]]) -> list[str]:
    return [f["id"] for f in fs if is_covered(f)]


def unsupported(fs: list[dict[str, Any]]) -> list[str]:
    return [f["id"] for f in fs
            if (is_covered(f) and not transfer_supported(f))
            or (is_interface_declaration(f) and not f["decl_representable"])]


def admit(tier: int, state: str | None, flag: str, fs: list[dict[str, Any]]) -> tuple[str, str | None, list[str]]:
    """("admitted", None, covered) or ("rejected", code, obligations)."""
    err, _ = resolve_params(tier, "vscore", "restricted_source", "0.1", state, flag)
    if err:
        return "rejected", err, []
    bad = unsupported(fs)
    if bad:
        return "rejected", "UNSUPPORTED_CAPABILITY", bad
    cov = covered(fs)
    if not cov:
        return "rejected", "ORPHAN_CLAIM", []
    return "admitted", None, cov


# ------------------------------------------------------------------------------------------
# features of accepted records
# ------------------------------------------------------------------------------------------

def _range_bound_calls(formula: Any) -> bool:
    from ..targets.vscore_target import _calls_postorder

    stack = [formula]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if x.get("tag") in ("forall_range", "exists_range"):
                found: list = []
                _calls_postorder(x.get("lower"), found)
                _calls_postorder(x.get("upper"), found)
                if found:
                    return True
            stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
    return False


def _representable(sort: Any) -> bool:
    from ..targets.vscore_target import BridgeUnsupported, sort_ty

    try:
        sort_ty(sort)
        return True
    except (BridgeUnsupported, KeyError, TypeError):
        return False


def symbol_representable(spec: dict[str, Any]) -> bool:
    return not spec.get("level_params") and all(_representable(s) for s in [*spec["args"], spec["result"]])


def formula_package(pkg, rec: dict[str, Any]) -> dict[str, Any] | None:
    digest = rec["formal"]["formula_ref"].rsplit("@", 1)[-1]
    p = pkg.path("accepted") / "expressions" / (digest.split(":", 1)[1] + ".json")
    if not p.is_file() or canonical.digest(p.read_bytes()) != digest:
        return None
    return canonical.load_file(p)


def features(pkg, irj: dict[str, Any], profile_json: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Model features of every accepted record, plus a reason per unsupported record."""
    profile = Profile.from_json(profile_json)
    by_decl = {s["lean_decl"]: (sid, s) for sid, s in profile_json["symbols"].items()}
    enum_decls = {n for e in profile_json.get("enums", {}).values() for n in [e["lean_decl"], *e.get("lean_constructors", [])]}
    out: list[dict[str, Any]] = []
    reasons: dict[str, str] = {}
    for oid, rec in sorted(irj["obligations"].items()):
        e2e, _ = applicability(rec)["END_TO_END_VERIFIED"]
        f = {"id": oid, "role": rec["role"], "kind": rec["kind"], "required": bool(rec["required"]),
             "e2e_applicable": bool(e2e), "contract_dsl": rec["formal"]["representation"] == "contract_dsl",
             "mentions_symbol": False, "call_in_range_bound": False, "representable_sorts": True,
             "decl_representable": True}
        package = formula_package(pkg, rec)
        if f["contract_dsl"] and package is not None:
            formula = package["formula"]
            if package.get("encoding") != "verislop.contract-dsl/0.1":
                f["contract_dsl"] = False
            try:
                type_formula(formula, [], profile)
                from ..dsl import calls

                syms = sorted(calls(formula))
            except DSLError:
                syms = []
                f["contract_dsl"] = False
            f["mentions_symbol"] = bool(syms)
            f["call_in_range_bound"] = _range_bound_calls(formula)
            f["representable_sorts"] = all(s in profile_json["symbols"] and symbol_representable(profile_json["symbols"][s])
                                           for s in syms)
        elif f["contract_dsl"]:
            f["contract_dsl"] = False
        if rec["role"] == "declaration":
            bound = (package or {}).get("bindings", {})
            ok = isinstance(bound, dict) and bool(bound)
            for decl in bound if isinstance(bound, dict) else []:
                if decl in enum_decls:
                    continue
                if decl in by_decl and symbol_representable(by_decl[decl][1]):
                    continue
                ok = False
            f["decl_representable"] = ok
        out.append(f)
        if is_covered(f) and not transfer_supported(f):
            reasons[oid] = _reason(f)
        elif is_interface_declaration(f) and not f["decl_representable"]:
            reasons[oid] = ("a required declaration lies outside the representable VSCore profile "
                            "(Nat, Bool, Unit, accepted finite enumerations, nested Result and their functions)")
    return out, reasons


def _reason(f: dict[str, Any]) -> str:
    if not f["contract_dsl"]:
        return "an opaque or non-contract-DSL statement has no transfer rule"
    if f["kind"] == "liveness_property":
        return "a reactive liveness property has no restricted_source transfer rule"
    if f["kind"] == "resource_constraint":
        return ("a resource constraint is a physical claim; an arithmetic reading of the accepted statement would not "
                "establish it for the delivered source")
    if not f["mentions_symbol"]:
        return "the accepted statement mentions no implementation symbol; no transfer rule applies"
    if f["call_in_range_bound"]:
        return "calls inside range-quantifier bounds have no transfer rule"
    return "a called symbol has a sort outside the representable VSCore profile"


def admission_diagnostics(decision: tuple[str, str | None, list[str]], reasons: dict[str, str]) -> list[Diagnostic]:
    status, code, obls = decision
    if status == "admitted":
        return []
    if code == "CONFIGURATION_INVALID":
        return [Diagnostic("CONFIGURATION_INVALID",
                           "--no-tests contradicts --require-state TESTED; a requested campaign cannot be dropped")]
    if code == "ORPHAN_CLAIM":
        return [Diagnostic("ORPHAN_CLAIM", "the accepted contract has no required guarantee with applicable "
                                           "implementation milestones; there is nothing to verify end to end")]
    if not obls:
        return [Diagnostic("UNSUPPORTED_CAPABILITY",
                           "no registered VSCore campaign backend exists: a Tier 2 request that requires tests is "
                           "rejected before generation (use --no-tests; TESTED then stays PENDING)")]
    diags = [Diagnostic("UNSUPPORTED_CAPABILITY",
                        f"admission rejected: required obligation(s) {', '.join(obls)} have no supported "
                        f"{registry.VSCORE_ID} translation; they remain required and UNSUPPORTED (never NOT_APPLICABLE)",
                        obligations=list(obls))]
    diags += [Diagnostic("UNSUPPORTED_SEMANTICS", f"{oid}: {reasons.get(oid, 'unsupported')}", obligations=[oid])
              for oid in obls]
    return diags
