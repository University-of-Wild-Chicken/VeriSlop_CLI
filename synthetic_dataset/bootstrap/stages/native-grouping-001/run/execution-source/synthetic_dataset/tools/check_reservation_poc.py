"""Finite independent request oracle for the reservation proof of concept.

Executes generated Python through the isolated target Harness. The expected result
comes directly from request.txt, never the Lean reference. This supplementary result
does not assign milestones or change package evidence, even for a negative candidate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from verislop import canonical, contract, fsutil
from verislop.export import verified_ir
from verislop.errors import VeriSlopError
from verislop.package import Package
from verislop.targets import python_target as pt

REPO = Path(__file__).resolve().parents[2]
REQUEST = REPO / "examples/proof-of-concept/reservation/request.txt"
VALUES = (*range(16), 2**64 - 1, 2**64, 2**64 + 1, 2**128)


class CheckFailure(ValueError):
    pass


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise CheckFailure(detail)


def exact(left: Any, right: Any) -> bool:
    return canonical.dumps(left) == canonical.dumps(right)


def expected_wire(balance: int, amount: int) -> dict[str, Any]:
    """Request oracle: exact Nat arithmetic and the specified tuple serialization."""
    if amount <= balance:
        return {"tuple": [{"str": "ok"}, {"int": str(balance - amount)}]}
    return {"tuple": [{"str": "error"}, {"str": "insufficient"}]}


def confined(pkg: Package, path: Path) -> Path:
    lexical = Path(path).absolute()
    resolved = lexical.resolve()
    require(resolved.is_relative_to(pkg.root), "Package artifact path escapes its package")
    current = lexical
    while current != pkg.root:
        require(not current.is_symlink(), "Package artifact path contains a symlink")
        current = current.parent
    return resolved


def external_inputs() -> dict[str, str]:
    paths = {Path(__file__).resolve(), REQUEST,
             REPO / "examples/proof-of-concept/reservation/qwen-config.json",
             REPO / "examples/proof-of-concept/reservation/endpoint-profiles.json"}
    paths.update((REPO / "verislop").rglob("*.py"))
    paths.update((REPO / "verislop/lean").rglob("*.lean"))
    paths.update((REPO / "schemas").glob("*.json"))
    return {p.relative_to(REPO).as_posix(): canonical.digest_file(p) for p in sorted(paths) if p.is_file()}


def select_reserve(pkg: Package, ir_hash: str):
    implementation = confined(pkg, pkg.path("implementation"))
    manifest = fsutil.manifest_tree(implementation, "implementation")
    inventory = pt.inventory(implementation)
    require(not inventory.errors, "Generated implementation has invalid Python syntax")
    link_path = confined(pkg, pkg.path("bridges") / "link.json")
    link = canonical.load_file(link_path)
    require(link.get("artifact_kind") == "link_record" and link.get("accepted_ir") == ir_hash,
            "Link does not bind the verified accepted IR")
    require(link.get("implementation_root") == fsutil.manifest_root(manifest), "Implementation bytes differ from the linked manifest")
    require(exact(link.get("serialization_profile"), pt.PROFILE_DOC), "Link has a different serialization profile")
    profile = contract.frozen_json(pkg, "profile.json")
    statements = contract.frozen_json(pkg, "statements.json")
    claims = canonical.load_file(confined(pkg, pkg.path("closure") / "implementation-claims.json"))
    require(claims.get("bound_to", {}).get("accepted_ir") == ir_hash and claims.get("parameters", {}).get("target") == "python",
            "Implementation claims have a different IR or target")
    bindings = link.get("bindings")
    require(isinstance(bindings, list), "Missing structural link bindings")
    reserve, symbols, objects, ids = [], set(), set(), set()
    for binding in bindings:
        symbol = binding.get("symbol")
        obj = binding.get("implementation_object", {})
        key = (obj.get("file"), obj.get("qualname"))
        binding_id = binding.get("binding_id")
        require(isinstance(symbol, str) and symbol and symbol not in symbols and key not in objects and
                isinstance(binding_id, str) and binding_id and binding_id not in ids,
                "Missing or ambiguous structural binding identity")
        symbols.add(symbol)
        objects.add(key)
        ids.add(binding_id)
        actual = inventory.find(*key)
        spec = profile.get("symbols", {}).get(symbol)
        require(actual is not None and actual["kind"] == "function" and not actual["decorated"] and
                not actual["varargs"] and not actual["kwonly_required"] and isinstance(spec, dict),
                "Binding is not an exact top-level accepted function")
        require(actual["positional"] - actual["defaults"] <= len(spec["args"]) <= actual["positional"], "Bound signature differs from its accepted arity")
        expected_object = {"file": actual["file"], "qualname": actual["qualname"], "source_hash": actual["source_hash"],
                           "file_hash": inventory.files[actual["file"]], "lineno": actual["lineno"]}
        expected_formal = {"lean_decl": spec["lean_decl"], "decl_hash": statements["declaration_hashes"].get(spec["lean_decl"]),
                           "args": spec["args"], "result": spec["result"]}
        require(exact(obj, expected_object) and exact(binding.get("formal_declaration"), expected_formal) and
                binding.get("serialization_profile") == pt.PROFILE_ID, "Link metadata differs from exact source or accepted declaration")
        if actual["qualname"] == "reserve":
            require(spec["args"] == ["Nat", "Nat"], "reserve does not accept two natural-number arguments")
            result = spec.get("result", {}).get("result", {}) if isinstance(spec.get("result"), dict) else {}
            error = result.get("error", {})
            enum = profile.get("enums", {}).get(error.get("enum"), {}) if isinstance(error, dict) else {}
            require(set(result) == {"ok", "error"} and result["ok"] == "Nat" and
                    "insufficient" in enum.get("constructors", []), "reserve does not return the specified Result enum/Nat")
            reserve.append(binding)
    require(len(reserve) == 1, "Missing or ambiguous reserve implementation entry")
    return implementation, inventory.files, reserve[0], manifest, link_path


def run_check(package: Path, repeats: int = 2) -> dict[str, Any]:
    require(type(repeats) is int and 1 <= repeats <= 3, "Repeat count must be between one and three")
    lexical = package.absolute()
    require(not any(p.is_symlink() for p in (lexical, *lexical.parents)), "Package path contains a symlink")
    pkg = Package(lexical)
    require(pkg.exists(), "Not a run package")
    before = fsutil.manifest_tree(pkg.root)
    inputs = external_inputs()
    result: dict[str, Any] = {"format": "verislop.reservation-request-oracle/0.1", "status": "INPUT_INVALID",
                              "checked_at_utc": datetime.now(timezone.utc).isoformat(), "package": str(pkg.root),
                              "oracle": "Python natural arithmetic from reservation/request.txt; no Lean reference calls",
                              "scope": "Finite supplementary evidence only; no package milestone or end-to-end verification claim",
                              "case_values": [str(v) for v in VALUES], "distinct_cases": len(VALUES)**2, "repeats": repeats,
                              "package_manifest": before, "package_root_hash": fsutil.manifest_root(before),
                              "checker_inputs": inputs, "runtime": pt.python_identity(), "cases": [], "diagnostics": []}
    try:
        for kind in ("prompt", "accepted_ir", "accepted", "contract", "claims", "bridges", "implementation", "closure", "report"):
            confined(pkg, pkg.path(kind))
        require(pkg.path("prompt").read_bytes() == REQUEST.read_bytes(), "Package request differs from this fixed reservation oracle")
        require(pkg.path("report").is_file(), "Package report is missing; no report hash can be bound")
        ir, ir_hash, certificate, diagnostics = verified_ir(pkg)
        require(not diagnostics and ir is not None and ir_hash is not None and certificate is not None,
                "verified_ir rejected accepted source linkage: " + "; ".join(d.code + ": " + d.message for d in diagnostics))
        implementation, files, binding, manifest, link_path = select_reserve(pkg, ir_hash)
        result.update(accepted_ir_hash=ir_hash, binding=binding, implementation_manifest=manifest,
                      implementation_manifest_root=fsutil.manifest_root(manifest), link_hash=canonical.digest_file(link_path),
                      request_hash=canonical.digest_file(pkg.path("prompt")), report_hash=canonical.digest_file(pkg.path("report")))
        cases = [{"balance": str(balance), "amount": str(amount), "expected": expected_wire(balance, amount), "observations": []}
                 for balance in VALUES for amount in VALUES]
        result["cases"] = cases
        isolation = []
        symbol = binding["symbol"]
        target = binding["implementation_object"]
        for _ in range(repeats):
            harness = pt.Harness(implementation, files, {symbol: (target["file"], target["qualname"])},
                                 per_call_timeout=1.0, memory_mb=512,
                                 require_network_isolation=True, require_filesystem_isolation=True)
            try:
                isolation.append(harness.isolation)
                for case in cases:
                    response = harness.call(symbol, [{"int": case["balance"]}, {"int": case["amount"]}])
                    require(response.get("id") == harness.calls and response.get("op") in ("result", "exception"), "Uncorrelated target response")
                    ok = set(response) == {"op", "id", "value"} and response["op"] == "result" and exact(response["value"], case["expected"])
                    case["observations"].append({"response": response, "passed": ok})
            finally:
                harness.close()
        for case in cases:
            case["passed"] = len(case["observations"]) == repeats and all(o["passed"] for o in case["observations"])
        passed = sum(case["passed"] for case in cases)
        result.update(status="PASS" if passed == len(cases) else "FAIL", passed_cases=passed,
                      failed_cases=len(cases) - passed, completed_observations=sum(len(c["observations"]) for c in cases), isolation=isolation)
    except CheckFailure as exc:
        result["diagnostics"].append(str(exc))
    except pt.HarnessError as exc:
        result.update(status="INFRASTRUCTURE_FAILURE")
        result["diagnostics"].append({"kind": exc.kind, "message": str(exc)})
    except (OSError, ValueError, KeyError, TypeError, AttributeError, VeriSlopError) as exc:
        result["diagnostics"].append(str(exc))
    try:
        unchanged = exact(before, fsutil.manifest_tree(pkg.root)) and inputs == external_inputs()
    except (OSError, ValueError, VeriSlopError):
        unchanged = False
    if not unchanged:
        result.update(status="INPUT_MUTATION", input_bytes_unchanged=False)
        result["diagnostics"].append("Package or checker/config/runtime inputs changed during observation")
    else:
        result["input_bytes_unchanged"] = True
    result["observations_hash"] = canonical.digest_json(result["cases"])
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Write-once JSON result outside the package")
    parser.add_argument("--repeats", type=int, default=2, choices=(1, 2, 3))
    args = parser.parse_args(argv)
    try:
        package, out = args.package.absolute(), args.out.absolute()
        require(not out.resolve().is_relative_to(package.resolve()), "Supplementary output must be outside the package")
        require(not out.exists() and not out.is_symlink(), "Write-once result already exists")
        result = run_check(package, args.repeats)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("xb") as stream:
            stream.write(canonical.dumps(result))
        print(canonical.dumps({"status": result["status"], "distinct_cases": result["distinct_cases"],
                               "passed_cases": result.get("passed_cases"), "out": str(out),
                               "result_hash": canonical.digest_file(out)}).decode().strip())
        return 0 if result["status"] == "PASS" else 2
    except (CheckFailure, OSError, ValueError, VeriSlopError) as exc:
        print(canonical.dumps({"status": "INPUT_INVALID", "error": str(exc)}).decode().strip())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
