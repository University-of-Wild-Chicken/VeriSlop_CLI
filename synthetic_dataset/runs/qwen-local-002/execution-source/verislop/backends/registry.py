"""Backend descriptors and selection (milestone §2; model: formal/ClosureModel/Admission.lean).

`select` mirrors `ClosureModel.select`: exactly one registered descriptor matches the frozen
tuple, otherwise nothing is selected. `capabilities` publishes these same descriptors. The
descriptor hash covers the descriptor and the current hashes of its registered producers, so a
package cannot keep an older implementation hash to preserve a pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import canonical
from ..errors import Diagnostic

PYTHON_ID = "verislop.backend.python/0.1"
VSCORE_ID = "verislop.backend.vscore/0.1"

VSCORE_PRODUCERS = {
    "IMPLEMENTED": "verislop.vscore-materializer",
    "LINKED": "verislop.vscore-linker",
    "TESTED": "verislop.vscore-campaign-unavailable",
    "semantic_edge": "verislop.vscore-checker",
    "structural": "verislop.bridge-preparation",
    "END_TO_END_VERIFIED": "verislop.closure",
    "closure": "verislop.closure",
}

VSCORE_EXCLUDED = [
    "any host interpreter, ordinary Lean code generation, VM, compiler, linker, loader, operating-system service "
    "or native executable that might later execute the source",
    "general state, sequences, loops, entry-to-entry calls, I/O, concurrency and fairness",
    "constant-time claims and physical time, memory or other resources",
    "machine-width integers (Nat is unbounded; no width conversion exists)",
    "natural-language-to-contract fidelity (a declared interpretation boundary)",
]

DESCRIPTORS: list[dict[str, Any]] = [
    {"id": PYTHON_ID, "tier": 0, "target": "python", "endpoint": "test_campaign", "backend_version": "0.1",
     "language": "python", "serialization_profile": "python-v0_1", "end_to_end_eligible": False,
     "testing": "supported", "claims_format": "0.1"},
    {"id": PYTHON_ID, "tier": 1, "target": "python", "endpoint": "instrumented_runtime", "backend_version": "0.1",
     "language": "python", "serialization_profile": "python-v0_1", "end_to_end_eligible": False,
     "testing": "supported", "claims_format": "0.1"},
    {"id": VSCORE_ID, "tier": 2, "target": "vscore", "endpoint": "restricted_source", "backend_version": "0.1",
     "language": "vscore/0.1", "semantics": "vscore-semantics/0.1",
     "relation_template": "vscore.reference_refinement/0.1", "end_to_end_eligible": True,
     "testing": "unsupported", "claims_format": "0.2", "producers": VSCORE_PRODUCERS,
     "property_fragment": ("functional postconditions, pure value invariants, pure safety properties and explicit "
                           "error semantics in verislop.contract-dsl/0.1 over Nat, Bool, Unit, accepted finite "
                           "enumerations and nested Result, read through the existing transfer rule"),
     "limitations": ["one delivered source file, one selected prepared bridge, one restricted_source node and one "
                     "direct semantic edge from the imported accepted_contract node",
                     "every program entry binds one-to-one to an accepted function symbol",
                     "no guarantee-subset selection, competing bridges or edge composition",
                     "opaque lean_expr statements, formulas without an implementation symbol, calls inside range "
                     "bounds, liveness and physical-resource claims are unsupported"],
     "excluded_surfaces": VSCORE_EXCLUDED},
]


def select(tier: Any, target: Any, endpoint: Any, version: Any = None) -> dict[str, Any] | None:
    """The unique descriptor for the tuple, or None (unknown versions fail closed).

    `version=None` selects the single current version of a tuple; an explicit version must match.
    """
    if type(tier) is not int or not isinstance(target, str) or not isinstance(endpoint, str):
        return None
    hits = [d for d in DESCRIPTORS
            if d["tier"] == tier and d["target"] == target and d["endpoint"] == endpoint
            and (version is None or d["backend_version"] == version)]
    return canonical.loads(canonical.dumps(hits[0])) if len(hits) == 1 else None


def by_id(backend_id: str, tier: Any) -> dict[str, Any] | None:
    hits = [d for d in DESCRIPTORS if d["id"] == backend_id and d["tier"] == tier]
    return hits[0] if len(hits) == 1 else None


def descriptor_hash(descriptor: dict[str, Any]) -> str:
    from ..verifiers import VERIFIERS, verifier_hash

    producers = sorted(set((descriptor.get("producers") or {}).values()))
    return canonical.digest_json({
        "format": "verislop.backend-descriptor/0.1",
        "descriptor": descriptor,
        "producers": {vid: verifier_hash(vid) if vid in VERIFIERS else None for vid in producers},
    })


# ------------------------------------------------------------------------------------------
# dispatch by frozen claim-inventory format
# ------------------------------------------------------------------------------------------

def frozen_claims(pkg) -> dict[str, Any] | None:
    p = Path(pkg.path("closure")) / "implementation-claims.json"
    return canonical.load_file(p) if p.is_file() else None


def claims_format(claims: dict[str, Any] | None) -> str | None:
    """Explicit format dispatch; unknown versions never select the legacy reader."""
    if claims is None:
        return None
    if not isinstance(claims, dict):
        return "unsupported"
    if claims.get("schema_version") == "0.2" and claims.get("format") == "verislop.implementation-claims/0.2":
        return "0.2"
    if claims.get("schema_version") == "0.1" and "format" not in claims:
        return "0.1"
    return "unsupported"


def frozen_backend(pkg) -> tuple[dict[str, Any] | None, list[Diagnostic]]:
    """Descriptor of the package's frozen implementation phase (Python legacy for 0.1 claims)."""
    try:
        claims = frozen_claims(pkg)
    except (OSError, ValueError) as exc:
        return None, [Diagnostic("INVALID_CANDIDATE", f"unreadable frozen implementation claims: {exc}")]
    fmt = claims_format(claims)
    if fmt is None:
        if (Path(pkg.path("closure")) / "selection.json").exists():
            return None, [Diagnostic("VERIFIER_NOT_RUN", "selected implementation has no frozen implementation-claim inventory")]
        return None, []
    if fmt == "unsupported":
        return None, [Diagnostic("UNSUPPORTED_CAPABILITY", "unknown frozen implementation-claim format/version")]
    params = claims.get("parameters", {})
    if not isinstance(params, dict):
        return None, [Diagnostic("INVALID_CANDIDATE", "frozen implementation parameters must be an object")]
    if fmt == "0.1":
        d = select(params.get("tier", 0), "python", params.get("endpoint"))
        if d is None or d["claims_format"] != "0.1" or params.get("target") != "python":
            return None, [Diagnostic("UNSUPPORTED_CAPABILITY", "legacy implementation claims name no registered Python backend")]
        return d, []
    d = select(params.get("tier"), params.get("target"), params.get("endpoint"))
    if d is None or d["id"] != params.get("backend") or d["claims_format"] != "0.2":
        return None, [Diagnostic("UNSUPPORTED_CAPABILITY",
                                 f"frozen backend {params.get('backend')!r} for the tuple "
                                 f"({params.get('tier')}, {params.get('target')}, {params.get('endpoint')}) is not registered")]
    return d, []


def is_vscore(pkg) -> bool:
    d, _ = frozen_backend(pkg)
    return d is not None and d["id"] == VSCORE_ID
