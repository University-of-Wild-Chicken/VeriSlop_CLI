"""Frozen request constraints for actual reconstructed source constructors.

This policy never supplies an accepted statement, implementation, proof or case.
Only kernel-reconstructed source facets can satisfy its per-obligation rows.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import canonical, dsl, fsutil, schemas, source_contract
from .errors import Diagnostic, UsageError

FORMAT = "verislop.required-source-facets/0.1"
PATH = "request/source-policy.json"
ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")
MAX_BYTES = 1024 * 1024
CODE = "SOURCE_FACETS_REQUIRED"


def validate(policy: Any) -> list[Diagnostic]:
    problems = schemas.require_valid("required-source-facets", policy, "required source-facet policy")
    if problems:
        return problems
    for oid, row in policy["obligations"].items():
        if not ID.fullmatch(oid):
            problems.append(Diagnostic("INVALID_CANDIDATE", "source policy requires bounded ordinary obligation IDs"))
        try:
            source_contract.validate_requirements([
                {"tag": "entry", **{k: row[k] for k in ("file", "entry", "arity")}},
                *({"tag": tag} for tag in row["properties"])])
        except source_contract.SourceError as exc:
            problems.append(Diagnostic("INVALID_CANDIDATE", f"source policy {oid}: {exc}", obligations=[oid]))
    return problems


def stage(pkg, path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise UsageError("source policy must be a bounded regular JSON file")
    data = path.read_bytes()
    try:
        policy = canonical.loads(data)
    except ValueError as exc:
        raise UsageError(f"source policy is invalid JSON: {exc}") from None
    problems = validate(policy)
    if problems:
        raise UsageError("required source-facet policy is invalid", problems)
    target = pkg.root / PATH
    reference = pkg.meta().get("source_policy")
    if reference is not None or target.exists():
        previous, problems = load(pkg)
        if problems or target.read_bytes() != data:
            raise UsageError("source policy is already frozen; a change requires a fresh run",
                problems or [Diagnostic("INPUT_MUTATION", "required source policy bytes differ from the frozen request")])
        return previous
    if pkg.path("interpretation").exists() or (pkg.path("contract") / "challenge/challenge.json").exists():
        raise UsageError("provide --source-policy before recording interpretation in a fresh run",
                         [Diagnostic("CLAIM_MUTATION", "source policy cannot change a recorded request")])
    fsutil.write_once(target, data)
    pkg.set_meta("source_policy", {"format": FORMAT, "path": PATH, "sha256": canonical.digest(data)})
    return policy


def load(pkg) -> tuple[dict | None, list[Diagnostic]]:
    reference = pkg.meta().get("source_policy")
    target = pkg.root / PATH
    if reference is None and not target.exists():
        return None, []
    expected = {"format", "path", "sha256"}
    if (not isinstance(reference, dict) or set(reference) != expected
            or reference.get("format") != FORMAT or reference.get("path") != PATH):
        return None, [Diagnostic("INPUT_MUTATION", "frozen source policy reference is missing or malformed")]
    try:
        if target.is_symlink() or not target.is_file() or target.stat().st_size > MAX_BYTES:
            raise ValueError("policy is missing, indirect or oversized")
        data = target.read_bytes()
        if canonical.digest(data) != reference["sha256"]:
            raise ValueError("policy bytes changed after request freeze")
        policy = canonical.loads(data)
        problems = validate(policy)
        if problems:
            raise ValueError("policy no longer has the frozen closed schema")
    except (OSError, ValueError) as exc:
        return None, [Diagnostic("INPUT_MUTATION", f"frozen source policy: {exc}")]
    return policy, []


def context(pkg) -> dict | None:
    policy, problems = load(pkg)
    if problems:
        raise UsageError("frozen source policy changed", problems)
    return policy


def check(policy: dict | None, statements: dict, records: list[dict]) -> list[Diagnostic]:
    """Check only statement packages reconstructed by contract.analyze."""
    if policy is None:
        return []
    by_id = {r["id"]: r for r in records}
    problems = []
    for oid, required in policy["obligations"].items():
        record = by_id.get(oid)
        statement = statements.get(oid, {})
        missing = []
        matched = []
        if not record or record.get("role") != "guarantee" or not record.get("required") or record.get("blocked_by"):
            missing.append("the same required active guarantee ID")
        if statement.get("representation") == "source_facets":
            package = statement.get("formula_package", {})
            for facet in source_contract.source_facets(package):
                requirements = facet.get("requirements", [])
                entry = {"tag": "entry", **{k: required[k] for k in ("file", "entry", "arity")}}
                if entry in requirements:
                    tags = {row.get("tag") for row in requirements}
                    if set(required["properties"]) <= tags:
                        matched.append(facet)
            if not matched:
                missing.append("a bound SourceBoundary Contract with the exact entry/file/arity and all closed properties")
            if required["value_required"]:
                value = source_contract.value_package(package)
                if value is None:
                    missing.append("the complete functional value conjunct and its checked projection")
                elif not {facet["symbol"] for facet in matched} & dsl.calls(value["formula"]):
                    missing.append("a functional value formula using the endpoint constrained by the exact named source entry")
        else:
            missing.append("actual reconstructed VeriSlop.Source.Contract constructors, not mathematical equality or existence proxies")
        if missing:
            problems.append(Diagnostic(CODE, f"{oid}: required source facets are missing or mismatched: " + "; ".join(missing),
                obligations=[oid], details={"repairable": True, "required_source_policy": required,
                    "reconstructed_representation": statement.get("representation"),
                    "missing": missing, "authority": "request constraint only; accepted statements come from Lean"}))
    return problems


def check_package(pkg, statements: dict, records: list[dict]) -> list[Diagnostic]:
    policy, problems = load(pkg)
    return problems or check(policy, statements, records)


def check_ir(pkg, ir: dict, records: list[dict]) -> list[Diagnostic]:
    """Recheck hash-bound accepted expression files after IR evidence validation."""
    policy, problems = load(pkg)
    if problems or policy is None:
        return problems
    statements = {}
    for oid in policy["obligations"]:
        formal = ir["obligations"].get(oid, {}).get("formal", {})
        statement = dict(formal)
        if formal.get("representation") == "source_facets":
            digest = formal.get("formula_ref", "").rsplit("@", 1)[-1]
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                return [Diagnostic("INPUT_MUTATION", f"{oid}: accepted source expression reference is malformed", obligations=[oid])]
            path = pkg.path("accepted") / "expressions" / (digest.split(":")[1] + ".json")
            try:
                if path.is_symlink() or not path.is_file() or canonical.digest_file(path) != digest:
                    raise ValueError("missing or changed accepted expression")
                statement["formula_package"] = canonical.load_file(path)
            except (OSError, ValueError) as exc:
                return [Diagnostic("INPUT_MUTATION", f"{oid}: {exc}", obligations=[oid])]
        statements[oid] = statement
    return check(policy, statements, records)


def inherit(parent, child) -> None:
    policy = context(parent)
    if policy is not None:
        stage(child, parent.root / PATH)
