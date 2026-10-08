"""Read-only, independently frozen natural-language request checks for data-pipeline PoCs.

The generated candidate is invoked in fresh isolated Python harnesses. No Lean reference
calculates expected outputs. This checker cannot award or alter CLI milestones.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from verislop import canonical, contract, fsutil
from verislop.errors import VeriSlopError
from verislop.export import verified_ir
from verislop.package import Package
from verislop.targets import python_target as pt
from synthetic_dataset.tools.check_reservation_poc import CheckFailure, confined, exact, require
from synthetic_dataset.tools.data_pipeline_oracle import TASKS

REPO = Path(__file__).resolve().parents[2]
PROTOCOL = REPO / "examples/proof-of-concept/data-pipelines"


def check_preregistration() -> dict[str, Any]:
    receipt = canonical.load_file(PROTOCOL / "PREREGISTRATION.json")
    actual = {path: canonical.digest_file(REPO / path) for path in receipt["inputs"]}
    require(actual == receipt["inputs"] and canonical.digest_json(actual) == receipt["root"],
            "Preregistered requests, oracle, cases or rules changed")
    return receipt


def record_fields(sort: Any, profile: dict[str, Any]) -> dict[str, Any]:
    require(type(sort) is dict and set(sort) == {"record"}, "The solve boundary must carry an actual fixed record")
    return {field["name"]: field["sort"] for field in profile["records"][sort["record"]]["fields"]}


def check_interface(task: str, spec: dict[str, Any], profile: dict[str, Any]) -> None:
    require(len(spec["args"]) == 1, "solve must take exactly one record argument")
    source, target = record_fields(spec["args"][0], profile), record_fields(spec["result"], profile)
    if task == TASKS[0]:
        require(source == {"values": {"list": "Int"}, "minimum": "Int", "factor": "Int"}, "Numeric input schema changed")
        require(set(target) == {"values", "total", "count"} and target["values"] == {"list": "Int"}
                and target["total"] == "Int" and target["count"] in ("Nat", "Int"), "Numeric output schema changed")
    elif task == TASKS[1]:
        require(set(source) == {"rows", "minimum"} and source["minimum"] == "Int"
                and type(source["rows"]) is dict and set(source["rows"]) == {"list"}, "Row input schema changed")
        require(record_fields(source["rows"]["list"], profile) == {"tag": "String", "amount": "Int", "enabled": "Bool"},
                "Input row fields or sorts changed")
        require(set(target) == {"rows", "total", "count"} and target["total"] == "Int" and target["count"] in ("Nat", "Int")
                and type(target["rows"]) is dict and set(target["rows"]) == {"list"}, "Row output schema changed")
        require(record_fields(target["rows"]["list"], profile) == {"tag": "String", "amount": "Int"}, "Projected row schema changed")
    else:
        require(source == {"labels": {"list": "String"}, "prefix": "String"}, "Label input schema changed")
        require(set(target) == {"labels", "count"} and target["labels"] == {"list": "String"}
                and target["count"] in ("Nat", "Int"), "Label output schema changed")


def select_solve(pkg: Package, task: str, ir_hash: str):
    implementation = confined(pkg, pkg.path("implementation"))
    manifest = fsutil.manifest_tree(implementation, "implementation")
    inventory = pt.inventory(implementation)
    require(not inventory.errors, "Invalid Python implementation syntax")
    link_path = confined(pkg, pkg.path("bridges") / "link.json")
    link = canonical.load_file(link_path)
    profile = contract.frozen_json(pkg, "profile.json")
    statements = contract.frozen_json(pkg, "statements.json")
    require(profile.get("dsl") == "verislop.contract-dsl/0.2", "Structured contract did not use the extended accepted profile")
    require(link.get("artifact_kind") == "link_record" and link.get("accepted_ir") == ir_hash
            and link.get("implementation_root") == fsutil.manifest_root(manifest), "Link has stale IR or implementation bytes")
    require(exact(link.get("serialization_profile"), pt.profile_doc(profile)), "Link serialization semantics differ")
    claims = canonical.load_file(confined(pkg, pkg.path("closure") / "implementation-claims.json"))
    parameters = claims.get("parameters", {})
    require(claims.get("bound_to", {}).get("accepted_ir") == ir_hash and parameters.get("target") == "python"
            and parameters.get("tier") == 0 and parameters.get("serialization_profile") == pt.profile_id(profile), "Frozen bridge parameters differ")
    bindings = link.get("bindings")
    require(isinstance(bindings, list), "Missing link bindings")
    entry, ids, symbols, objects = [], set(), set(), set()
    for binding in bindings:
        symbol, identity = binding.get("symbol"), binding.get("binding_id")
        obj = binding.get("implementation_object", {})
        key = obj.get("file"), obj.get("qualname")
        require(isinstance(symbol, str) and symbol not in symbols and isinstance(identity, str) and identity not in ids
                and key not in objects, "Missing or ambiguous binding identity")
        symbols.add(symbol); ids.add(identity); objects.add(key)
        actual, spec = inventory.find(*key), profile.get("symbols", {}).get(symbol)
        require(actual is not None and actual["kind"] == "function" and isinstance(spec, dict)
                and not actual["decorated"] and not actual["varargs"] and not actual["defaults"]
                and not actual["kwonly_required"] and actual["positional"] == len(spec["args"]), "Incorrect bound function signature")
        expected_object = {"file": actual["file"], "qualname": actual["qualname"], "source_hash": actual["source_hash"],
                           "file_hash": inventory.files[actual["file"]], "lineno": actual["lineno"]}
        expected_formal = {"lean_decl": spec["lean_decl"], "decl_hash": statements["declaration_hashes"].get(spec["lean_decl"]),
                           "args": spec["args"], "result": spec["result"]}
        require(exact(obj, expected_object) and exact(binding.get("formal_declaration"), expected_formal)
                and binding.get("serialization_profile") == pt.profile_id(profile), "Link metadata differs from exact accepted/source bytes")
        if actual["qualname"] == "solve":
            check_interface(task, spec, profile)
            entry.append(binding)
    require(len(entry) == 1, "Missing or ambiguous solve binding")
    return implementation, inventory.files, entry[0], manifest, link_path


def run_check(package: Path, task: str) -> dict[str, Any]:
    require(task in TASKS, "Task was not preregistered")
    preregistration = check_preregistration()
    pkg = Package(package.absolute())
    require(pkg.exists(), "Not a run package")
    before = fsutil.manifest_tree(pkg.root)
    result: dict[str, Any] = {"format": "verislop.data-pipeline-request-oracle/0.1", "status": "BLOCKED",
                             "task": task, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                             "preregistration_root": preregistration["root"], "package": str(pkg.root),
                             "package_root": fsutil.manifest_root(before), "checker_hash": canonical.digest_file(Path(__file__)),
                             "runtime": pt.python_identity(), "diagnostics": [], "cases": [],
                             "scope": "Independent finite request observations; no CLI milestone promotion or universal refinement claim"}
    try:
        require(pkg.path("prompt").read_bytes() == (PROTOCOL / f"{task}.txt").read_bytes(), "Request differs from preregistered prompt")
        ir, ir_hash, cert, diagnostics = verified_ir(pkg)
        require(not diagnostics and ir is not None and ir_hash is not None and cert is not None,
                "verified_ir rejected accepted artifacts: " + "; ".join(d.code + ": " + d.message for d in diagnostics))
        implementation, files, binding, manifest, link_path = select_solve(pkg, task, ir_hash)
        cases = canonical.load_file(PROTOCOL / "withheld" / f"{task}.json")["cases"]
        result.update(accepted_ir_hash=ir_hash, binding=binding, implementation_manifest=manifest,
                      report_hash=canonical.digest_file(pkg.path("report")), link_hash=canonical.digest_file(link_path),
                      distinct_cases=len(cases), repeats=2, cases=[{**row, "observations": []} for row in cases])
        isolation = []
        obj, symbol = binding["implementation_object"], binding["symbol"]
        for _ in range(2):
            harness = pt.Harness(implementation, files, {symbol: (obj["file"], obj["qualname"])},
                                 per_call_timeout=1.0, memory_mb=512, require_network_isolation=True, require_filesystem_isolation=True)
            try:
                isolation.append(harness.isolation)
                for case in result["cases"]:
                    response = harness.call(symbol, [case["input_wire"]])
                    require(response.get("id") == harness.calls and response.get("op") in ("result", "exception"), "Uncorrelated execution response")
                    passed = set(response) == {"op", "id", "value"} and response["op"] == "result" and exact(response["value"], case["expected_wire"])
                    case["observations"].append({"response": response, "passed": passed})
            finally:
                harness.close()
        for case in result["cases"]:
            case["passed"] = len(case["observations"]) == 2 and all(row["passed"] for row in case["observations"])
        passed = sum(row["passed"] for row in result["cases"])
        report = canonical.load_file(pkg.path("report"))
        native_gate = (report.get("terminal_status") == "VERIFIED" and report.get("tier") == 0
                       and len(report.get("builds", [])) == 2 and all(row.get("ok") for row in report["builds"])
                       and report.get("determinism", {}).get("mismatches") == []
                       and report.get("review", {}).get("checkpoints") == {"formal_contract": "REVIEW_ACCEPTED", "release": "REVIEW_ACCEPTED"})
        tested = [row for row in report.get("obligations", {}).values() if row.get("required") and "TESTED" in row.get("required_milestones", [])]
        native_gate = native_gate and bool(tested) and all(row["outcomes"].get("TESTED") == "PASS" for row in tested)
        result.update(status="VERIFIED" if native_gate and passed == len(cases) else "BLOCKED", native_gate_passed=native_gate,
                      passed_cases=passed, failed_cases=len(cases)-passed, observations=2*len(cases), isolation=isolation)
    except pt.HarnessError as exc:
        result.update(status="INFRASTRUCTURE_FAILURE")
        result["diagnostics"].append({"kind": exc.kind, "message": str(exc)})
    except (CheckFailure, VeriSlopError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result["diagnostics"].append(str(exc))
    if not exact(before, fsutil.manifest_tree(pkg.root)):
        result.update(status="BLOCKED", input_bytes_unchanged=False)
        result["diagnostics"].append("INPUT_MUTATION: generated package changed during read-only observation")
    else:
        result["input_bytes_unchanged"] = True
    check_preregistration()
    result["observations_hash"] = canonical.digest_json(result["cases"])
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--task", required=True, choices=TASKS)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    require(not args.out.exists() and not args.out.is_symlink(), "Receipt is write-once")
    require(not args.out.resolve().is_relative_to(args.package.resolve()), "Receipt must be outside the package")
    result = run_check(args.package, args.task)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("xb") as stream:
        stream.write(canonical.dumps(result))
    print(canonical.dumps({key: result.get(key) for key in ("status", "task", "distinct_cases", "passed_cases", "observations", "diagnostics")}).decode())
    return 0 if result["status"] == "VERIFIED" else 3 if result["status"] == "INFRASTRUCTURE_FAILURE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
