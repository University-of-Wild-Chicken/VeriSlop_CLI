"""Acceptance policies (specification §6).

`strict` is the default prove-before-generation profile. `exploratory` may typecheck abstract
interfaces without witnesses; its certificates are never labelled accepted-and-proved and
`generate` refuses them.
"""

from __future__ import annotations

from typing import Any

from . import canonical
from .errors import UsageError

BASELINE_AXIOMS = ["Classical.choice", "Quot.sound", "propext"]
NATIVE_AXIOM_MARKERS = ("Lean.ofReduceBool", "Lean.trustCompiler", "._native.", "native_decide")

POLICIES: dict[str, dict[str, Any]] = {
    "strict": {
        "id": "verislop.policy.strict/0.1",
        "gate": "accepted_and_proved",
        "allowed_axioms": BASELINE_AXIOMS,
        "allowed_import_roots": ["Init", "Std", "Lean"],
        "forbid_module_axioms": True,
        "require_kernel_replay": True,
        "require_network_isolation": True,
        "require_filesystem_isolation": True,
        "require_witnesses": True,
        "build_timeout_seconds": 300,
        "kernel_timeout_seconds": 300,
        "memory_mb": 8192,
    },
    "exploratory": {
        "id": "verislop.policy.exploratory/0.1",
        "gate": "typechecked_exploratory",
        "allowed_axioms": BASELINE_AXIOMS,
        "allowed_import_roots": ["Init", "Std", "Lean"],
        "forbid_module_axioms": True,
        "require_kernel_replay": True,
        "require_network_isolation": True,
        "require_filesystem_isolation": True,
        "require_witnesses": False,
        "build_timeout_seconds": 300,
        "kernel_timeout_seconds": 300,
        "memory_mb": 8192,
    },
}


def get(name: str) -> dict[str, Any]:
    if name not in POLICIES:
        raise UsageError(f"unknown acceptance policy {name!r}; available: {', '.join(POLICIES)}")
    return dict(POLICIES[name])


def policy_hash(p: dict[str, Any]) -> str:
    return canonical.digest_json(p)


def classify_axiom(name: str, policy: dict[str, Any]) -> str:
    """allowed | sorry | native | unauthorized"""
    if name == "sorryAx":
        return "sorry"
    if any(m in name for m in NATIVE_AXIOM_MARKERS):
        return "native"
    if name in policy["allowed_axioms"]:
        return "allowed"
    return "unauthorized"
