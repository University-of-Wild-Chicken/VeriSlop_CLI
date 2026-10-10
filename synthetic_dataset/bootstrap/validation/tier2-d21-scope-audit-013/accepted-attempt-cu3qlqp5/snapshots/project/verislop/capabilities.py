"""Published capabilities (specification §2: a release MUST publish its supported
tier/language/property combinations) and environment diagnostics (`verislop doctor`)."""

from __future__ import annotations

import shutil
import sys
from typing import Any

from . import __version__
from .errors import Diagnostic
from .stage import StageResult

ENDPOINT_TIER = {
    "test_campaign": 0,
    "instrumented_runtime": 1,
    "restricted_source": 2,
    "proof_bearing_source": 3,
    "extracted_language": 3,
    "native_binary": 4,
}
DEFAULT_ENDPOINT = {0: "test_campaign", 1: "instrumented_runtime", 2: "restricted_source", 3: "proof_bearing_source", 4: "native_binary"}

BRIDGES: list[dict[str, Any]] = [
    {
        "tier": 0, "target": "python", "endpoint": "test_campaign", "status": "supported",
        "serialization_profile": "python-v0_1 or python-v0_2, selected from the accepted contract profile",
        "milestones": ["IMPLEMENTED", "LINKED", "TESTED"],
        "properties": "executable contracts over Nat/Int/Bool/Unit/String, finite enumerations, Result, typed Lists and fixed-field records; infinite input domains are sampled, finite sorts enumerated",
        "unsupported": "opaque lean_expr statements (no fabricated oracle); dynamic JSON, recursive records, arbitrary products, state, traces, costs",
        "end_to_end_eligible": False,
        "assurance": "TESTED (finite campaign); never implementation proof",
    },
    {
        "tier": 1, "target": "python", "endpoint": "instrumented_runtime", "status": "supported",
        "serialization_profile": "python-v0_1",
        "milestones": ["IMPLEMENTED", "LINKED", "TESTED (when the release policy runs the campaign)"],
        "properties": "per-call pre/postcondition monitors for obligations whose prefix binds the call's arguments and result",
        "violation_behavior": "detection: the wrapper raises before returning; side effects inside the target are not rolled back",
        "bypass": "callers importing the unwrapped module bypass the monitors",
        "end_to_end_eligible": False,
        "assurance": "runtime detection plus executed tests; never END_TO_END_VERIFIED",
    },
    {
        "tier": 2, "target": "vscore", "endpoint": "restricted_source", "status": "supported",
        "language": "vscore/0.1", "semantics": "vscore-semantics/0.1",
        "relation_templates": {"vscore.reference_refinement/0.1": "verislop.vscore-checker"},
        "available": ("`verislop bridge accept`/`bridge verify`: kernel-checked exact-byte parse and typing equations, "
                      "extensional refinement against the accepted reference functions, input coverage, mechanically "
                      "derived transfer of covered contract-DSL obligations, implementation IR re-export and two "
                      "isolated reproducible builds"),
        "properties": ("functional postconditions, explicit result/error semantics and pure value invariants stated in the "
                       "contract DSL over Nat, Bool, Unit, finite enumerations and Result"),
        "unsupported": ("opaque lean_expr statements, calls inside range-quantifier bounds, obligations that mention no "
                        "implementation symbol, recursion, loops, calls between entries, state, sequences and I/O; "
                        "executing the source with any interpreter or compiler is outside the certificate"),
        "end_to_end_eligible": True,
        "testing": "unsupported",
        "assurance": "END_TO_END_VERIFIED [restricted_source; vscore/0.1] after complete mechanical closure; independent TESTED unavailable",
    },
    {
        "tier": 2, "target": "vscore", "endpoint": "restricted_source", "status": "supported",
        "backend_version": "0.3", "language": "vscore/0.3", "semantics": "vscore-semantics/0.3",
        "relation_templates": {"vscore.reference_refinement/0.3": "verislop.vscore3-checker"},
        "available": "explicit version selection, exact source admission, universal accepted-function refinement, binder-preserving obligation transfer and two isolated reproducible closure builds",
        "properties": "accepted DSL 0.1/0.2 values over unbounded Nat/Int, Unicode String, Bool, Unit, accepted records/enumerations, lists, options and Result; distinct reconstructed source facets via exact typed-entry and observation laws",
        "unsupported": "native Python facets without an explicit new delivery contract, opaque statements, liveness, physical resources, unrestricted recursion, mutable state and I/O",
        "end_to_end_eligible": True, "testing": "unsupported",
        "assurance": "END_TO_END_VERIFIED [restricted_source; vscore/0.3] after complete mechanical closure; independent TESTED unavailable",
    },
    {"tier": 3, "status": "unsupported",
     "reason": "no proof-producing generator or verified extraction route with artifact-specific preservation proofs is integrated"},
    {"tier": 4, "status": "unsupported",
     "reason": "no machine-code semantics or verified compiler-chain certificates for delivered bytes exist"},
]

FORMAL = {
    "lean_toolchains": ["leanprover/lean4:v4.34.1"],
    "acceptance_policies": {"strict": "accepted-and-proved gate (default)", "exploratory": "typecheck-only; never labelled accepted-and-proved"},
    "contract_dsl": "verislop.contract-dsl/0.1 and /0.2: legacy primitives plus signed Int, floor division, bounded range, total optional indexing, scalar sorting/first-occurrence deduplication, Unicode String ordering, typed Lists, fixed-field records and unambiguous nullable Option values; registered arithmetic, list pipelines, Boolean conditionals and logical formulas",
    "native_facets": {"encoding": "verislop.contract-facets/0.1", "model": "verislop.native-boundary/0.2",
        "scope": "accepted-AST entry layout and closed/pure/frame/runtime requirements, with kernel-checked abstract transfer and admission inhabitation; actual source conformance and finite typed calls remain required",
        "assurance": "Python Tier 0 only; trusted source checker and adapters; ineligible for END_TO_END_VERIFIED"},
    "formalizer_frontend": {"encoding": "verislop.formalizer-ast/0.1", "status": "supported",
        "scope": "untrusted monomorphic typed definitions/formulas compiled to canonical Lean; exact kernel denotation audit, proofs and accepted-AST reconstruction remain required",
        "automatic_selection": "Python Tier 0 TESTED/test_campaign; raw Lean proposals remain supported",
        "downstream_json": "reconstructed from accepted Lean, never promoted from the formalizer proposal"},
    "opaque_statements": "accepted and proved as lean_expr; no executable oracle or monitor",
    "kernel_replay": "Lean.Kernel.Environment.replay in a separate trusted process",
    "module_system": "Lean 4.34.1 module files supported; full private declaration environment replayed from a complete hashed artifact bundle",
    "imports": "pinned toolchain imports only; third-party libraries such as Mathlib remain unsupported",
    "axiom_policy": "baseline allowlist propext, Classical.choice, Quot.sound; sorryAx, native evaluation and unknown axioms rejected",
    "witnesses": "non-vacuity witnesses must be concrete and extractable by bounded kernel head-normalisation",
}

SOURCE_ADMISSION = {
    "language": "vscore/0.2", "profile": "pure-data/0.2", "status": "supported",
    "authoring": "vscore compile: named surface grammar to delivered canonical JSON",
    "kernel_check": "vscore check: exact byte decoding and program admission, accepted-AST reconstruction, two clean kernel builds",
    "features": ["base", "nominalData", "option", "list", "acyclicCalls", "listFold", "natFold"],
    "verifier": "verislop.vscore2-source-checker", "assigns_obligation_milestones": False,
    "accepted_contract_bridge": "unsupported", "end_to_end_eligible": False,
    "testing": "no registered campaign backend",
}

SOURCE_ADMISSION3 = {
    "language": "vscore/0.3", "profile": "data-pipeline/0.3", "status": "supported",
    "authoring": "vscore compile: named surface grammar to delivered canonical JSON",
    "kernel_check": "vscore check: exact byte decoding and program admission, accepted-AST reconstruction, two clean kernel builds",
    "features": SOURCE_ADMISSION["features"] + ["int", "string", "pureList"],
    "verifier": "verislop.vscore3-source-checker", "assigns_obligation_milestones": False,
    "accepted_contract_bridge": "vscore.reference_refinement/0.3; explicit backend version 0.3",
    "end_to_end_eligible": False,
    "testing": "no registered campaign backend",
    "assurance": "source admission alone assigns no contract milestone; complete selected bridge closure is separate",
}


def capability(tier: int, target: str, endpoint: str, *, require_tests: bool = False,
               backend_version: str | None = None, obligations: list[dict[str, Any]] | None = None) -> tuple[bool, str]:
    from .backends.registry import select

    descriptor = select(tier, target, endpoint, backend_version)
    if descriptor is None:
        return False, f"no registered backend for Tier {tier}, target {target!r}, endpoint {endpoint!r}, version {backend_version!r}"
    if require_tests and descriptor["testing"] != "supported":
        return False, "no independent VSCore campaign is registered"
    if tier == 2 and obligations is not None:
        if descriptor["backend_version"] == "0.3":
            from .backends.vscore3_admission import unsupported, covered
        else:
            from .backends.admission import unsupported, covered

        bad = unsupported(obligations)
        if bad or not covered(obligations):
            return False, f"no complete admitted guarantee set (unsupported: {', '.join(bad) or 'empty'})"
    for b in BRIDGES:
        if b["tier"] != tier:
            continue
        if tier == 2 and b.get("language") != descriptor["language"]:
            continue
        if b["status"] != "supported":
            return False, f"Tier {tier} is not supported: {b['reason']}"
        if b["target"] != target:
            return False, f"Tier {tier} supports target {b['target']!r}, not {target!r}"
        if b["endpoint"] != endpoint:
            return False, f"Tier {tier} establishes the {b['endpoint']} endpoint, not {endpoint}"
        return True, "supported"
    return False, f"unknown tier {tier}"


def normalize_endpoint(endpoint: str | None, tier: int) -> str:
    if not endpoint:
        return DEFAULT_ENDPOINT[tier]
    return endpoint.replace("-", "_")


def report() -> StageResult:
    from .providers.registry import ADAPTERS

    res = StageResult("capabilities", "PASS", "capability table published")
    res.summary = {
        "verislop_version": __version__,
        "bridges": BRIDGES,
        "formal": FORMAL,
        "source_admission": SOURCE_ADMISSION,
        "source_admissions": [SOURCE_ADMISSION, SOURCE_ADMISSION3],
        "provider_adapters": {k: {"protocol": v["protocol"], "status": v["status"]} for k, v in ADAPTERS.items()},
        "review": "hierarchical adversarial review: user-configured tiers, counts and consensus; a workflow gate, never proof",
    }
    for b in BRIDGES:
        if b["status"] == "supported":
            res.lines.append(f"Tier {b['tier']} {b['target']} -> {b['endpoint']}: {b['assurance']}")
        elif b["status"] == "partial":
            res.lines.append(f"Tier {b['tier']} {b['target']} -> {b['endpoint']}: PARTIAL — {b['available']}; {b['reason']}")
        else:
            res.lines.append(f"Tier {b['tier']}: UNSUPPORTED — {b['reason']}")
    from .backends.registry import DESCRIPTORS

    res.summary["backend_descriptors"] = DESCRIPTORS
    res.lines.append("VSCore 0.2: surface authoring and kernel source admission; accepted-contract bridge unsupported")
    res.lines.append("VSCore 0.3: explicit data-pipeline backend; accepted-contract refinement and complete restricted_source closure; native Python facets unsupported")
    res.lines.append("END_TO_END_VERIFIED: Tier 2 vscore -> restricted_source only; Tiers 0/1 are ineligible and Tiers 3/4 unsupported")
    return res


def doctor() -> StageResult:
    from . import leanbridge, sandbox

    res = StageResult("doctor", "PASS", "toolchain, sandbox and verifier prerequisites available")
    checks: dict[str, Any] = {"python": sys.version.split()[0]}
    if sys.version_info < (3, 10):
        res.diagnostics.append(Diagnostic("VERIFIER_FAILURE", "Python >= 3.10 is required", severity="infrastructure"))
    try:
        tc = leanbridge.resolve_toolchain(leanbridge.DEFAULT_TOOLCHAIN)
        checks["lean"] = tc.identity()
    except Exception as exc:  # noqa: BLE001
        res.diagnostics.append(Diagnostic("VERIFIER_FAILURE", str(exc), severity="infrastructure"))
    checks["network_namespace"] = sandbox.network_isolation_available()
    if not checks["network_namespace"]:
        res.diagnostics.append(Diagnostic(
            "VERIFIER_FAILURE", "unprivileged network namespaces (unshare -rn) are unavailable; the strict policy requires network isolation",
            severity="infrastructure"))
    checks["unshare"] = shutil.which("unshare")
    checks["filesystem_isolation"] = sandbox.filesystem_isolation_available()
    checks["bubblewrap"] = shutil.which("bwrap")
    if not checks["filesystem_isolation"]:
        res.diagnostics.append(Diagnostic(
            "VERIFIER_FAILURE", "bubblewrap filesystem containment is unavailable; candidate execution requires it",
            severity="infrastructure"))
    checks["kernel_tool_sha256"] = leanbridge.kernel_tool_hash()
    res.summary = checks
    res.lines = [f"{k}: {v}" for k, v in checks.items()]
    res.status = "INFRASTRUCTURE_FAILURE" if res.diagnostics else "PASS"
    return res
