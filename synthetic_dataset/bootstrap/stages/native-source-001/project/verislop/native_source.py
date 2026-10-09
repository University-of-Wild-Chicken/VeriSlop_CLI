"""Source-bound conformance to accepted native facets and the V2 source profile.

Callers first validate accepted IR/certificate authority. This module checks
package hashes, native model/endpoint anchors and actual source bytes afresh;
candidate bindings are identity proposals, never observations or PASS receipts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import canonical, native_contract, python_boundary
from .errors import Diagnostic
from .targets import python_target as pt

FORMAT = "verislop.native-source-receipt/0.1"
NATIVE_FIELDS = {"requirement_id", "definition", "definition_hash", "symbol", "lean_decl", "decl_hash",
                 "requirements", "model_version", "model_source_hash"}


def source_files(root: Path) -> dict[str, bytes]:
    """Read the exact complete staged artifact inventory without modifying it."""
    from . import fsutil
    return {file: (root / file).read_bytes() for file in fsutil.list_files(root)}


def accepted_packages(ir: dict, expressions_dir: Path) -> dict[str, dict]:
    """Load each exact referenced accepted package, rejecting stale bytes."""
    result = {}
    for oid, record in ir["obligations"].items():
        formal = record["formal"]
        if formal["representation"] not in {"contract_dsl", "contract_facets"}:
            continue
        digest = formal["formula_ref"].rsplit("@", 1)[1]
        if len(digest) != 71 or not digest.startswith("sha256:") or any(c not in "0123456789abcdef" for c in digest[7:]):
            raise ValueError("accepted package reference is not an exact SHA256 digest")
        data = (expressions_dir / (digest[7:] + ".json")).read_bytes()
        if canonical.digest(data) != digest:
            raise ValueError("accepted package bytes changed: " + oid)
        package = canonical.loads(data)
        if canonical.digest_json(package) != digest:
            raise ValueError("accepted package bytes are not their canonical payload: " + oid)
        result[oid] = package
    return result


def _diagnostic(code, message, *, file="", ast_path="/", symbol=None, oid=None):
    out = {"code": code, "message": message, "file": file, "ast_path": ast_path,
           "line": None, "column": None}
    if symbol is not None:
        out["symbol"] = symbol
    if oid is not None:
        out["obligation_id"] = oid
    return out


def normalize_bindings(bindings: dict | None) -> tuple[list[dict], list[dict]]:
    """Proposal and link forms have the same authoritative identity projection."""
    rows, diagnostics = [], []
    if not isinstance(bindings, dict) or not isinstance(bindings.get("bindings"), list):
        return [], [_diagnostic("BINDING_SHAPE", "source conformance requires a binding identity proposal")]
    seen_symbols, seen_objects = set(), set()
    for row in bindings["bindings"]:
        obj = row.get("object", row.get("implementation_object")) if isinstance(row, dict) else None
        if (not isinstance(row, dict) or not isinstance(row.get("symbol"), str) or
                not isinstance(obj, dict) or not isinstance(obj.get("file"), str) or not isinstance(obj.get("qualname"), str)):
            diagnostics.append(_diagnostic("BINDING_SHAPE", "binding does not identify a file/function/symbol"))
            continue
        symbol, identity = row["symbol"], (obj["file"], obj["qualname"])
        if symbol in seen_symbols or identity in seen_objects:
            diagnostics.append(_diagnostic("DUPLICATE_BINDING", "source binding identity is not unique", file=identity[0], symbol=symbol))
        seen_symbols.add(symbol); seen_objects.add(identity)
        rows.append({"symbol": symbol, "file": identity[0], "qualname": identity[1]})
    return sorted(rows, key=lambda row: (row["symbol"], row["file"], row["qualname"])), diagnostics


def check_sources(files: dict[str, bytes], ir: dict, profile: dict, *, bindings: dict,
                  packages: dict[str, dict] | None = None, statements: dict | None = None) -> dict:
    """Compute generic and per-obligation receipts; no submitted facts are used.

    ``packages`` contains exact accepted packages. ``statements`` is an alternate
    accepted reconstruction carrying ``formula_package`` per obligation. Native
    facets cannot be omitted; their package hash must match ``ir`` in either form.
    Bindings normalize identically whether provided as proposal or link records.
    """
    packages = {} if packages is None else dict(packages)
    if statements is not None:
        for oid, row in statements.items():
            if isinstance(row, dict) and "formula_package" in row:
                packages.setdefault(oid, row["formula_package"])
    native_records = {oid for oid, rec in ir["obligations"].items()
                      if rec["formal"]["representation"] == "contract_facets"}
    enabled = pt.profile_id(profile) == pt.PROFILE_ID_V2 or bool(native_records)
    if not enabled:
        return {"format": FORMAT, "enabled": False, "accepted": True, "obligations": {}, "diagnostics": []}
    normalized, binding_diagnostics = normalize_bindings(bindings)
    by_symbol = {row["symbol"]: row for row in normalized}
    typed = {}
    for row in normalized:
        symbol = profile.get("symbols", {}).get(row["symbol"])
        if symbol is not None:
            typed[row["file"] + ":" + row["qualname"]] = symbol["args"]
    generic = python_boundary.check_sources(files, typed_args=typed, profile=profile)
    diagnostics = list(binding_diagnostics) + list(generic["diagnostics"])
    package_hashes, obligations = {}, {}
    inventory = {(row["file"], row["name"]): row for row in generic["functions"]}
    for oid, rec in sorted(ir["obligations"].items()):
        if rec.get("role", "guarantee") != "guarantee" or rec.get("kind") == "non_vacuity":
            continue
        row_diagnostics = list(binding_diagnostics) + list(generic["diagnostics"])
        facets = []
        if oid in native_records:
            package = packages.get(oid)
            try:
                if not isinstance(package, dict) or package.get("encoding") != native_contract.ENCODING:
                    raise ValueError("required native accepted package is missing")
                digest = canonical.digest_json(package)
                if rec["formal"]["formula_ref"].rsplit("@", 1)[1] != digest:
                    raise ValueError("native package differs from its accepted formula reference")
                package_hashes[oid] = digest
                native = native_contract.native_facets(package)
                if not isinstance(native, list) or not 1 <= len(native) <= native_contract.MAX_NATIVE_FACETS:
                    raise ValueError("native package has no bounded required facet list")
                for facet in native:
                    facet_diagnostics = []
                    if not isinstance(facet, dict) or set(facet) != NATIVE_FIELDS:
                        raise ValueError("native facet has unknown/missing fields")
                    symbol = profile.get("symbols", {}).get(facet["symbol"])
                    if (symbol is None or facet["lean_decl"] != symbol["lean_decl"] or
                            facet["decl_hash"] != symbol["decl_hash"] or
                            facet["model_version"] != native_contract.MODEL_VERSION or
                            facet["model_source_hash"] != native_contract.model_source_hash()):
                        raise ValueError("native facet endpoint/model anchor changed")
                    requirements = native_contract.validate_requirements(facet["requirements"], arity=len(symbol["args"]))
                    binding = by_symbol.get(facet["symbol"])
                    actual = inventory.get((binding["file"], binding["qualname"])) if binding else None
                    if actual is None or actual["arity"] != len(symbol["args"]):
                        facet_diagnostics.append(_diagnostic("NATIVE_TARGET_BINDING", "native endpoint lacks its exact delivered definition/signature",
                            file=binding["file"] if binding else "", symbol=facet["symbol"], oid=oid))
                    for requirement in requirements:
                        if requirement["tag"] == "entry" and (binding is None or actual is None or
                                (binding["file"], binding["qualname"], actual["arity"]) !=
                                (requirement["file"], requirement["qualname"], requirement["arity"])):
                            facet_diagnostics.append(_diagnostic("ENTRY_MISMATCH", "bound endpoint differs from the accepted entry file/function/arity",
                                file=requirement["file"], ast_path=actual["ast_path"] if actual else "/",
                                symbol=facet["symbol"], oid=oid))
                    facts = generic["facts"]
                    model_facts = {"entries": [{"file": actual["file"], "qualname": actual["name"], "arity": actual["arity"]}] if actual else [],
                        "uniqueFunctions": facts["unique_global_names"],
                        "closedNames": facts["closed_top_level"] and facts["closed_calls"],
                        "acyclicCalls": facts["acyclic_calls"], "pureJson": facts["pure_json"],
                        "standardRuntimeOnly": facts["standard_runtime_only"],
                        "noExternalIO": facts["no_target_external_io"],
                        "inputPreserved": facts["input_frame_preserved"],
                        "deterministic": facts["deterministic_local_evaluation"]}
                    facets.append({**facet, "requirements_hash": canonical.digest_json(requirements),
                        "model_facts": model_facts, "model_facts_hash": canonical.digest_json(model_facts),
                        "accepted": generic["accepted"] and not binding_diagnostics and not facet_diagnostics,
                        "diagnostics": list(generic["diagnostics"]) + list(binding_diagnostics) + facet_diagnostics})
                    row_diagnostics.extend(facet_diagnostics)
            except (KeyError, TypeError, ValueError, canonical.CanonicalJSONError) as exc:
                row_diagnostics.append(_diagnostic("NATIVE_REQUIREMENT_BINDING", "native facet conformance is incomplete: " + str(exc), oid=oid))
        obligations[oid] = {"required": bool(rec.get("required", True)), "accepted": generic["accepted"] and not row_diagnostics,
                            "facets": facets, "diagnostics": row_diagnostics}
        diagnostics.extend(item for item in row_diagnostics if item not in diagnostics)
    receipt = {"format": FORMAT, "enabled": True, "accepted": generic["accepted"] and not diagnostics,
        "checker": {"id": "verislop.native-source/0.1", "source_hash": canonical.digest_file(Path(__file__))},
        "accepted_ir_hash": canonical.digest_json(ir), "profile_hash": canonical.digest_json(profile),
        "bindings_hash": canonical.digest_json(normalized), "bindings": normalized,
        "package_hashes": package_hashes, "source_check": generic, "obligations": obligations,
        "diagnostics": diagnostics}
    receipt["receipt_hash"] = canonical.digest_json(receipt)
    return receipt


def for_package(pkg, ir: dict, profile: dict, *, bindings: dict, statements: dict | None = None) -> dict:
    """Convenience for stages operating on a certificate-validated package."""
    packages = accepted_packages(ir, pkg.path("accepted") / "expressions") if statements is None else None
    return check_sources(source_files(pkg.path("implementation")), ir, profile,
                         bindings=bindings, packages=packages, statements=statements)


def diagnostics(receipt: dict) -> list[Diagnostic]:
    if not receipt["enabled"]:
        return []
    result = []
    for item in receipt["diagnostics"]:
        scopes = [oid for oid, row in receipt["obligations"].items() if item in row["diagnostics"] and row["required"]]
        result.append(Diagnostic("INVALID_CANDIDATE",
            f"native source boundary {item['code']} at {item['file']}:{item['ast_path']}: {item['message']}",
            obligations=scopes, details={"native_source": item, "receipt_hash": receipt["receipt_hash"]}))
    return result
