"""Registered verifier inventory.

A verifier's hash covers the exact source bytes of the modules it executes (plus the shared
core and relevant schemas). Changing any of them changes the hash, so evidence produced by an
older verifier no longer binds to the current registry and is reported STALE.
"""

from __future__ import annotations

import platform
import sys
from functools import lru_cache
from pathlib import Path

from . import __version__, canonical
from .schemas import schema_dir

PKG = Path(__file__).resolve().parent

CORE = [
    "__init__.py", "package.py", "stage.py", "events.py",
    "canonical.py", "jsonschema_lite.py", "fsutil.py", "evidence.py", "errors.py",
    "lifecycle.py", "verifiers.py", "schemas.py", "claimcheck.py",
]

KERNEL = ["lean/VeriSlopKernel.lean", "leanbridge.py", "sandbox.py", "exprjson.py"]
BRIDGE_IMPORT = [
    "bridges/import_contract.py", "bridges/manifest.py", "export.py", "accept.py",
    "contract.py", "dsl.py", "reify.py", "policy.py", "view.py", "closure.py",
    "capabilities.py", "targets/python_target.py", *KERNEL,
]
BRIDGE_IMPORT_SCHEMAS = [
    "acceptance-certificate.schema.json", "accepted-ir.schema.json", "obligation.schema.json",
    "claims.schema.json", "evidence.schema.json", "formalization-candidate.schema.json",
    "interpretation.schema.json",
]
BRIDGE_PREPARATION = [
    "bridges/__init__.py", "bridges/prepare.py", "bridges/publish.py",
    "bridges/check.py", "bridges/registry.py", *BRIDGE_IMPORT,
]
BRIDGE_PREPARATION_SCHEMAS = [
    "bridge-proposal.schema.json", "bridge-preparation-certificate.schema.json",
    "bridge-plan.schema.json", "bridge-artifacts.schema.json", "semantic-edge-certificate.schema.json",
    *BRIDGE_IMPORT_SCHEMAS,
]

VSCORE_LIBRARY = ["lean/VSCore.lean", "lean/VSCore/Syntax.lean", "lean/VSCore/Decode.lean", "lean/VSCore/Typing.lean",
                  "lean/VSCore/Semantics.lean", "lean/VSCore/Transport.lean"]
VSCORE_CHECKER = ["bridges/vscore_checker.py", "targets/vscore_target.py", "targets/vscore_source.py",
                  *VSCORE_LIBRARY, *BRIDGE_PREPARATION]
VSCORE_SCHEMAS = ["vscore-source.schema.json", "vscore-relation.schema.json", "vscore-model.schema.json",
                  "vscore-profile.schema.json", "vscore-implementation-ir.schema.json",
                  "vscore-edge-certificate.schema.json", *BRIDGE_PREPARATION_SCHEMAS]
VSCORE_BACKEND = ["backends/__init__.py", "backends/registry.py", "backends/admission.py", "backends/vscore.py",
                  "backends/vscore_closure.py", "backends/vscore_release.py", "review_projection.py",
                  "generate.py", "link.py", "testing.py", "run.py", "cli.py", "agents.py", "review.py", "report.py", "inspection.py",
                  *VSCORE_CHECKER]
VSCORE_BACKEND_SCHEMAS = ["implementation-claims-v2.schema.json", "implementation-bindings-v2.schema.json",
                        "link-record-v2.schema.json", "implementation-selection-v2.schema.json",
                        "vscore-materialization.schema.json", "closure-plan.schema.json", "closure-manifest.schema.json",
                        "mechanical-result.schema.json", "run-report-v2.schema.json", *VSCORE_SCHEMAS]

# One vocabulary for declared trust, so reports list each trusted component once.
TRUST = {
    "lean": "Lean 4 kernel and elaborator of the pinned toolchain, with its toolchain .olean files",
    "kernel_tool": "VeriSlop kernel tool (replay driver, exporter, axiom walker, witness extractor)",
    "reifier": "VeriSlop reifier, DSL denotation builder and canonical serializer (round trip checked per value)",
    "sandbox": "VeriSlop launcher, bubblewrap and Linux namespace confinement; explicitly mounted runtime roots remain readable",
    "axioms": "logical axioms permitted by the acceptance policy (actual use listed per theorem)",
    "nl": "natural-language interpretation of the request (a recorded semantic assumption, not proved)",
    "segmenter": "mechanical clause segmentation verislop.segment/0.1",
    "router": "lexical routing heuristics (advisory; never evidence)",
    "cpython": "CPython interpreter and byte compiler of the supervisor host",
    "adapters": "python-v0_1 serialization adapters (fixed, not proved)",
    "oracle": "DSL executable oracle and monitor translation (trusted, not proved equivalent to the Lean predicate)",
    "bypass": "Tier 1 monitors can be bypassed by importing the unwrapped module",
    "orchestration": "closure orchestration, manifest canonicalisation and hashing",
    "consensus": "review consensus checks only the configured voting rule, never technical truth",
    "os": "operating system and hardware",
    "vscore": "VSCore 0.1 semantic library (verifier-owned Lean definitions of parsing, typing, evaluation and adapters; "
              "its soundness lemmas and every bridge equation are kernel-checked)",
    "vscore_goal": "VSCore goal generator (statement derivation from the accepted IR; elaborated statements are "
                   "compared with the derived kernel expressions)",
}

VERIFIERS: dict[str, dict] = {
    "verislop.bridge-contract-importer": {
        "milestones": [],
        "sources": BRIDGE_IMPORT,
        "schemas": BRIDGE_IMPORT_SCHEMAS,
        "trusted": [TRUST[k] for k in ("lean", "kernel_tool", "reifier", "sandbox", "axioms", "orchestration", "os")],
    },
    "verislop.bridge-preparation": {
        "milestones": [],
        "sources": BRIDGE_PREPARATION,
        "schemas": BRIDGE_PREPARATION_SCHEMAS,
        "trusted": [TRUST[k] for k in ("lean", "kernel_tool", "reifier", "sandbox", "axioms", "orchestration", "os")],
    },
    "verislop.vscore-checker": {
        "milestones": [],
        "sources": VSCORE_CHECKER,
        "schemas": VSCORE_SCHEMAS,
        "trusted": [TRUST[k] for k in ("lean", "kernel_tool", "vscore", "vscore_goal", "reifier", "sandbox",
                                       "axioms", "orchestration", "os")],
    },
    "verislop.vscore-materializer": {
        "milestones": ["IMPLEMENTED"], "sources": VSCORE_BACKEND, "schemas": VSCORE_BACKEND_SCHEMAS,
        "trusted": [TRUST[k] for k in ("lean", "kernel_tool", "vscore", "vscore_goal", "sandbox", "orchestration", "os")],
    },
    "verislop.vscore-linker": {
        "milestones": ["LINKED"], "sources": VSCORE_BACKEND, "schemas": VSCORE_BACKEND_SCHEMAS,
        "trusted": [TRUST[k] for k in ("lean", "kernel_tool", "vscore", "vscore_goal", "orchestration", "os")],
    },
    "verislop.vscore-campaign-unavailable": {
        "milestones": [], "sources": ["backends/registry.py", "testing.py"], "schemas": [],
        "trusted": [TRUST["orchestration"]],
    },
    "verislop.bridge-semantic-unavailable": {
        "milestones": [],
        "sources": ["bridges/registry.py"],
        "schemas": [],
        "trusted": [TRUST["orchestration"]],
    },
    "verislop.bridge-envelope-checker": {
        "milestones": [],
        "sources": ["bridges/__init__.py", "bridges/manifest.py", "bridges/check.py", "bridges/registry.py", "stage.py"],
        "schemas": ["bridge-plan.schema.json", "bridge-artifacts.schema.json", "semantic-edge-certificate.schema.json",
                    "accepted-ir.schema.json", "obligation.schema.json", "acceptance-certificate.schema.json", "evidence.schema.json"],
        "trusted": [TRUST["orchestration"]],
    },
    "verislop.routing-classifier": {
        "milestones": [],
        "sources": ["classify.py", "segment.py"],
        "schemas": ["routing.schema.json"],
        "trusted": [TRUST["router"]],
    },
    "verislop.interpretation-recorder": {
        "milestones": ["INTERPRETED"],
        "sources": ["draft.py", "interpret.py", "segment.py"],
        "schemas": ["draft.schema.json", "obligation.schema.json", "interpretation.schema.json"],
        "trusted": [TRUST["nl"], TRUST["segmenter"]],
    },
    "verislop.formal-statement-checker": {
        "milestones": ["FORMALIZED", "INTERPRETED (derived obligations only)"],
        "sources": ["formalize.py", "dsl.py", "reify.py", "contract.py", *KERNEL],
        "schemas": ["formalization-candidate.schema.json", "claims.schema.json"],
        "trusted": [TRUST["lean"], TRUST["kernel_tool"], TRUST["reifier"], TRUST["sandbox"]],
    },
    "verislop.lean-acceptance": {
        "milestones": ["TYPECHECKED", "PROVED"],
        "sources": ["accept.py", "dsl.py", "reify.py", "contract.py", "policy.py", *KERNEL],
        "schemas": ["acceptance-certificate.schema.json", "evidence.schema.json"],
        "trusted": [TRUST["lean"], TRUST["kernel_tool"], TRUST["sandbox"], TRUST["axioms"]],
    },
    "verislop.reifier": {
        "milestones": [],
        "sources": ["export.py", "accept.py", "dsl.py", "reify.py", "contract.py", "policy.py", "view.py",
                    "closure.py", "capabilities.py", "targets/python_target.py", *KERNEL],
        "schemas": ["accepted-ir.schema.json", "obligation.schema.json", "acceptance-certificate.schema.json",
                    "claims.schema.json", "evidence.schema.json"],
        "trusted": [TRUST["reifier"], TRUST["lean"], TRUST["kernel_tool"]],
    },
    "verislop.python-materializer": {
        "milestones": ["IMPLEMENTED"],
        "sources": ["materialize.py", "targets/python_target.py", "sandbox.py"],
        "schemas": [],
        "trusted": [TRUST["cpython"], TRUST["sandbox"]],
    },
    "verislop.python-linker": {
        "milestones": ["LINKED"],
        "sources": ["link.py", "targets/python_target.py", "dsl.py"],
        "schemas": ["implementation-bindings.schema.json"],
        "trusted": [TRUST["adapters"]],
    },
    "verislop.python-tier0-campaign": {
        "milestones": ["TESTED"],
        "sources": ["testing.py", "dsl.py", "targets/python_target.py", "targets/python_harness.py", "sandbox.py"],
        "schemas": [],
        "trusted": [TRUST["oracle"], TRUST["adapters"], TRUST["cpython"], TRUST["sandbox"]],
    },
    "verislop.python-tier1-monitor": {
        "milestones": ["IMPLEMENTED"],
        "sources": ["monitors.py", "dsl.py", "targets/python_target.py", "targets/monitor_runtime.py"],
        "schemas": [],
        "trusted": [TRUST["oracle"], TRUST["adapters"], TRUST["bypass"]],
    },
    "verislop.closure": {
        "milestones": ["END_TO_END_VERIFIED"],
        "sources": ["closure.py", "report.py", "materialize.py", "testing.py", "capabilities.py",
                    "targets/python_target.py", "targets/python_harness.py", "review.py",
                    "providers/config.py", "providers/registry.py", *BRIDGE_PREPARATION, *VSCORE_BACKEND],
        "schemas": ["report.schema.json", "claims.schema.json", "review-config.schema.json",
                    "review-ballot.schema.json", "consensus-certificate.schema.json",
                    "endpoint-profiles.schema.json", *BRIDGE_PREPARATION_SCHEMAS, *VSCORE_BACKEND_SCHEMAS],
        "trusted": [TRUST["orchestration"], TRUST["os"]],
    },
    "verislop.review-consensus": {
        "milestones": [],
        "sources": ["review.py", "review_projection.py", "backends/registry.py", "backends/vscore_release.py"],
        "schemas": ["review-ballot.schema.json", "review-config.schema.json", "consensus-certificate.schema.json"],
        "trusted": [TRUST["consensus"]],
    },
}


@lru_cache(maxsize=None)
def verifier_hash(verifier_id: str) -> str:
    spec = VERIFIERS[verifier_id]
    rows = []
    for rel in sorted(set(CORE + spec["sources"])):
        path = PKG / rel
        data = path.read_bytes() if path.is_file() else b"<missing>"
        rows.append({"path": f"verislop/{rel}", "sha256": canonical.digest(data)})
    for name in sorted(spec["schemas"]):
        path = schema_dir() / name
        data = path.read_bytes() if path.is_file() else b"<missing>"
        rows.append({"path": f"schemas/{name}", "sha256": canonical.digest(data)})
    return canonical.digest_json({"verifier": verifier_id, "version": __version__, "files": rows})


def registry_snapshot() -> dict:
    return {
        vid: {
            "hash": verifier_hash(vid),
            "milestones": spec["milestones"],
            "trusted_dependencies": spec["trusted"],
        }
        for vid, spec in sorted(VERIFIERS.items())
    }


def trusted_dependencies(verifier_id: str) -> list[str]:
    return list(VERIFIERS[verifier_id]["trusted"])


@lru_cache(maxsize=1)
def host_environment() -> dict[str, str]:
    return {
        "verislop": __version__,
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
    }
