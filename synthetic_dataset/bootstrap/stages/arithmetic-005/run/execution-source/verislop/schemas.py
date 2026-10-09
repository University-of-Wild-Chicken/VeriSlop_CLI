"""Schema registry: loads the repository's Draft 2020-12 schemas and validates artifacts.

Schema validity establishes structure only. Every artifact that carries claims is additionally
checked by a registered semantic validator.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from . import canonical
from .errors import Diagnostic, UsageError
from .jsonschema_lite import Registry, ValidationIssue

PACKAGE_DIR = Path(__file__).resolve().parent


def schema_dir() -> Path:
    for candidate in (PACKAGE_DIR / "schemas", PACKAGE_DIR.parent / "schemas"):
        if (candidate / "draft.schema.json").is_file():
            return candidate
    raise UsageError("VeriSlop schemas directory not found next to the package")


IDS = {
    "draft": "urn:verislop:schema:draft:0.1",
    "obligation": "urn:verislop:schema:obligation:0.1",
    "accepted-ir": "urn:verislop:schema:accepted-ir:0.1",
    "evidence": "urn:verislop:schema:evidence:0.1",
    "review-config": "urn:verislop:schema:review-config:0.1",
    "review-ballot": "urn:verislop:schema:review-ballot:0.1",
    "review-ballot-v2": "urn:verislop:schema:review-ballot:0.2",
    "review-counterexample-proposal": "urn:verislop:schema:review-counterexample-proposal:0.2",
    "review-counterexample-receipt": "urn:verislop:schema:review-counterexample-receipt:0.2",
    "interpretation": "urn:verislop:schema:interpretation:0.1",
    "routing": "urn:verislop:schema:routing:0.1",
    "formalization-candidate": "urn:verislop:schema:formalization-candidate:0.1",
    "formalizer-ast": "urn:verislop:schema:formalizer-ast:0.1",
    "implementation-bindings": "urn:verislop:schema:implementation-bindings:0.1",
    "acceptance-certificate": "urn:verislop:schema:acceptance-certificate:0.1",
    "report": "urn:verislop:schema:report:0.1",
    "event": "urn:verislop:schema:event:0.1",
    "claims": "urn:verislop:schema:claims:0.1",
    "consensus-certificate": "urn:verislop:schema:consensus-certificate:0.1",
    "endpoint-profiles": "urn:verislop:schema:endpoint-profiles:0.1",
    "bridge-plan": "urn:verislop:schema:bridge-plan:0.1",
    "bridge-artifacts": "urn:verislop:schema:bridge-artifacts:0.1",
    "semantic-edge-certificate": "urn:verislop:schema:semantic-edge-certificate:0.1",
    "bridge-proposal": "urn:verislop:schema:bridge-proposal:0.1",
    "bridge-preparation-certificate": "urn:verislop:schema:bridge-preparation-certificate:0.1",
    "vscore-source": "urn:verislop:schema:vscore-source:0.1",
    "vscore-source-v2": "urn:verislop:schema:vscore-source:0.2",
    "vscore-relation": "urn:verislop:schema:vscore-relation:0.1",
    "vscore-model": "urn:verislop:schema:vscore-model:0.1",
    "vscore-profile": "urn:verislop:schema:vscore-profile:0.1",
    "vscore-implementation-ir": "urn:verislop:schema:vscore-implementation-ir:0.1",
    "vscore-edge-certificate": "urn:verislop:schema:vscore-edge-certificate:0.1",
    "implementation-claims-v2": "urn:verislop:schema:implementation-claims:0.2",
    "implementation-bindings-v2": "urn:verislop:schema:implementation-bindings:0.2",
    "link-record-v2": "urn:verislop:schema:link-record:0.2",
    "implementation-selection-v2": "urn:verislop:schema:implementation-selection:0.2",
    "vscore-materialization": "urn:verislop:schema:vscore-materialization:0.1",
    "closure-plan": "urn:verislop:schema:closure-plan:0.2",
    "closure-manifest": "urn:verislop:schema:closure-manifest:0.2",
    "mechanical-result": "urn:verislop:schema:mechanical-result:0.2",
    "run-report-v2": "urn:verislop:schema:run-report:0.2",
}


@lru_cache(maxsize=1)
def registry() -> Registry:
    reg = Registry()
    for path in sorted(schema_dir().glob("*.schema.json")):
        reg.add(canonical.load_file(path))
    return reg


@lru_cache(maxsize=None)
def schema_hash(name: str) -> str:
    sid = IDS[name]
    for path in sorted(schema_dir().glob("*.schema.json")):
        data = path.read_bytes()
        if canonical.loads(data).get("$id") == sid:
            return canonical.digest(data)
    raise UsageError(f"schema {name} not found")


def all_schema_hashes() -> dict[str, str]:
    return {path.name: canonical.digest(path.read_bytes()) for path in sorted(schema_dir().glob("*.schema.json"))}


def validate(name: str, instance: Any) -> list[ValidationIssue]:
    return registry().validate(instance, IDS[name])


def require_valid(name: str, instance: Any, what: str, code: str = "INVALID_CANDIDATE") -> list[Diagnostic]:
    issues = validate(name, instance)
    return [Diagnostic(code, f"{what}: {issue}") for issue in issues[:50]]
