#!/usr/bin/env python3
"""Frozen finite qualification of shared Unicode Lean literal rendering.

This verifier never imports task fixtures or evaluates source-program behavior.
Denotation evidence is the existing kernel tool's exact exported literal Expr.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from tests.test_unicode_lean_literals_018 import invalid_fixtures, positive_fixtures
from verislop import leanbridge, sandbox
from verislop.errors import InfrastructureError
from verislop.targets import vscore_source, vscore2_source, vscore3_source
from verislop.targets import vscore_target, vscore3_target


VERIFIER_ID = "UL18-V1"
CLAIM_IDS = [f"UL18-C{i}" for i in range(1, 6)]
MODULE_NAMESPACE = "UnicodeLiteral018"
TCB = ["TCB-PINNED-LEAN", "TCB-KERNEL-EXPORTER", "TCB-PYTHON", "TCB-SANDBOX", "TCB-SHA256", "TCB-OS-HARDWARE"]


def json_bytes(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def digest_file(path):
    with path.open("rb") as handle:
        value = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path, value):
    path.write_bytes(json_bytes(value))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def input_paths(tc):
    paths = {Path(__file__).resolve(), leanbridge.KERNEL_TOOL.resolve(), Path(sys.executable).resolve(), tc.lean.resolve()}
    paths.update(PACKAGE / name for name in ("spec.json", "fixtures.json", "negative-plan.json", "verifier-plan.json"))
    paths.update(PACKAGE / "ledger-extension-001" / name for name in
                 ("design.json", "registration.json", "mock_shape_checks.py", "prior/verify.py"))
    paths.add(ROOT / "docs/unicode-lean-literal-support-018.md")
    paths.add(ROOT / "tests/test_unicode_lean_literals_018.py")
    paths.add(ROOT / "pyproject.toml")
    paths.add(ROOT / "verislop/policy.py")
    paths.add(ROOT / "examples/lean/lean-toolchain")
    # All repository Python files actually imported by this finite verifier are
    # frozen. Python standard-library semantics remain explicit trusted runtime.
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename:
            path = Path(filename).resolve()
            if path.is_file() and (path.is_relative_to(ROOT) or ".so" in path.name):
                paths.add(path)
    # Bind installed module parts for both implicit Init and the Lean-importing
    # exporter, rather than discovering unbound toolchain dependencies after a run.
    for path in tc.libdir.rglob("*"):
        if path.is_file() and any(path.name.endswith(s) for s in (".olean", ".olean.server", ".olean.private", ".ir", ".ir.sig")):
            paths.add(path.resolve())
    for path in (tc.prefix / "lib").rglob("*"):
        if path.is_file() and ".so" in path.name:
            paths.add(path.resolve())
    paths.update(tc.prefix / "src/lean" / rel for rel in
                 ("Lean/Parser/Basic.lean", "Init/Meta/Defs.lean", "Init/Data/Char/Basic.lean"))
    return sorted(paths, key=str)


def manifest(paths):
    rows = [{"path": str(path), "sha256": digest_file(path), "bytes": path.stat().st_size} for path in paths]
    return {"schema_version": "1.0", "files": rows}


@contextlib.contextmanager
def record_sandbox(directory, rows):
    original = sandbox.run

    def recorded(argv, cwd, **kwargs):
        requested_options = {key: kwargs[key] for key in
                             ("timeout", "memory_mb", "require_network_isolation", "require_filesystem_isolation")}
        requested_options["read_only_paths"] = [str(Path(path).absolute()) for path in kwargs["read_only_paths"]]
        result = original(argv, cwd, **kwargs)
        index = len(rows)
        stdout_path = directory / f"process-{index:02d}.stdout"
        stderr_path = directory / f"process-{index:02d}.stderr"
        stdout_path.write_bytes(result.stdout)
        stderr_path.write_bytes(result.stderr)
        row = {"argv": [str(v) for v in argv], "cwd": str(cwd), "returncode": result.returncode,
               "timed_out": result.timed_out, "wall_seconds": result.wall_seconds,
               "isolation": result.isolation, "requested_options": requested_options,
               "stdout": {"path": stdout_path.name, "sha256": digest(result.stdout), "bytes": len(result.stdout)},
               "stderr": {"path": stderr_path.name, "sha256": digest(result.stderr), "bytes": len(result.stderr)}}
        rows.append(row)
        if "--run" in row["argv"]:
            # This executes after the actual sandbox invocation, while
            # run_kernel_tool still owns its temporary staging directory.
            # Keep raw files distinct from leanbridge's normalized export.
            def retain(actual_path, name):
                data = actual_path.read_bytes()
                retained = directory / f"process-{index:02d}.{name}"
                retained.write_bytes(data)
                return {"path": retained.name, "sha256": digest(data), "bytes": len(data)}

            actual_cwd = Path(cwd)
            request_path = actual_cwd / row["argv"][-2]
            response_path = actual_cwd / row["argv"][-1]
            tool_path = actual_cwd / row["argv"][row["argv"].index("--run") + 1]
            evidence = {"request": retain(request_path, "request.json"),
                        "response": retain(response_path, "response.json"),
                        "kernel_tool": retain(tool_path, "VeriSlopKernel.lean")}
            request = json.loads(request_path.read_bytes())
            stage = Path(request["search_dir"])
            require(request["module"] == leanbridge.MODULE, "kernel request module differs from the compiled fixture")
            part_directory = directory / f"process-{index:02d}.stage"
            part_directory.mkdir()
            parts = {}
            for name in leanbridge.MODULE_PARTS:
                actual_part = stage / name
                if actual_part.is_file():
                    data = actual_part.read_bytes()
                    (part_directory / name).write_bytes(data)
                    parts[name] = digest(data)
            require(leanbridge.MODULE_PARTS[0] in parts, "actual kernel stage lacks compiled public module")
            evidence["staged_module_parts"] = {"module": request["module"], "parts": parts}
            row["kernel_evidence"] = evidence
        return result

    with patch.object(sandbox, "run", side_effect=recorded):
        yield


def host_checks(positive, invalid):
    rows, rejected, legacy = [], [], []
    for row in positive:
        text = row["text"]
        expr = {"lit": {"str": text}}
        rendered = vscore_target.Printer().term(expr)
        require(vscore3_target.Printer().term(expr) == rendered, f"Printer mismatch: {row['id']}")
        for module in (vscore_source, vscore2_source, vscore3_source):
            require(module.lean_string(text) == rendered, f"alias mismatch: {row['id']}")
        if "expected_lean" in row:
            require(rendered == row["expected_lean"], f"syntax expectation mismatch: {row['id']}")
        if row["id"] == "empty" or row["id"].startswith("legacy_"):
            require(rendered == '"' + text + '"', f"legacy byte mismatch: {row['id']}")
            legacy.append(row["id"])
        encoded = rendered.encode("utf-8", "strict")
        rows.append({"fixture_id": row["id"], "declaration": [MODULE_NAMESPACE, "case_" + row["id"]],
                     "input_scalars": [ord(c) for c in text], "original_expr": expr,
                     "literal_utf8_sha256": digest(encoded), "literal": rendered})
    for row in invalid:
        expr = {"lit": {"str": row["text"]}}
        calls = [lambda module=module: module.lean_string(row["text"])
                 for module in (vscore_source, vscore2_source, vscore3_source)]
        calls.extend(lambda printer=printer: printer().term(expr)
                     for printer in (vscore_target.Printer, vscore3_target.Printer))
        for call in calls:
            try:
                call()
            except vscore_source.SourceError as exc:
                require("surrogate" in str(exc), f"unexpected rejection: {row['id']}: {exc}")
            else:
                raise AssertionError(f"invalid surrogate accepted: {row['id']}")
        rejected.append({"fixture_id": row["id"], "input_codepoints": row["codepoints"], "rejected_paths": len(calls)})
    require(len({row["fixture_id"] for row in rows}) == len(rows), "fixture IDs are not unique")
    return rows, rejected, legacy


def compile_record(result):
    return {"ok": result.ok, "messages": result.messages, "errors": result.errors,
            "sorry_positions": result.sorry_positions, "timed_out": result.timed_out,
            "wall_seconds": result.wall_seconds, "isolation": result.isolation,
            "stderr": result.raw_stderr, "process_evidence": result.process_evidence}


def check_export(response, rows, tc, frozen_paths):
    require(response.get("import", {}).get("ok") is True, "kernel import failed")
    require(response.get("replay", {}).get("ok") is True, "kernel replay failed")
    for module in response["import"]["modules"]:
        if module["name"] == [leanbridge.MODULE]:
            continue
        path = Path(module["olean"]).resolve()
        require(path.is_relative_to(tc.libdir.resolve()), "dependency outside pinned Lean toolchain")
        require(path in frozen_paths, "imported module was not frozen")
    constants = response["constants"]
    index = {}
    for declaration in constants:
        key = tuple(declaration["name"])
        require(key not in index, "duplicate exported declaration")
        index[key] = declaration
        require("export_error" not in declaration, "declaration export error")
        if declaration.get("kind") == "missing_after_replay":
            require(declaration.get("replay_exclusion") == "runtime_auxiliary", "unexplained missing declaration")
    mapped = []
    for row in rows:
        key = tuple(row["declaration"])
        require(key in index, "missing literal definition " + ".".join(key))
        declaration = index[key]
        require(declaration.get("kind") == "definition" and declaration.get("safety") == "safe", "literal is not a safe definition")
        require(declaration.get("type") == {"const": ["String"], "levels": []}, "literal type is not exact String Expr")
        require(declaration.get("value") == row["original_expr"], "kernel literal Expr differs: " + row["fixture_id"])
        require(declaration.get("axioms") == [] and declaration.get("unresolved_constants") == [], "literal has axioms or unresolved constants")
        mapped.append({"fixture_id": row["fixture_id"], "declaration": row["declaration"],
                       "original_expr_sha256": digest(json_bytes(row["original_expr"])),
                       "exported_expr_sha256": digest(json_bytes(declaration["value"])), "status": "PASS"})
    return mapped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="development-1")
    args = parser.parse_args()
    require(args.run_id.replace("-", "").replace("_", "").isalnum(), "run ID must be a safe path component")
    output = PACKAGE / "runs" / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    spec = json.loads((PACKAGE / "spec.json").read_text())
    negatives = json.loads((PACKAGE / "negative-plan.json").read_text())["lean_negative_sources"]
    closure_id = spec["closure_id"] + "/" + args.run_id
    verifier_hash = digest_file(Path(__file__))
    statuses = {claim: "UNRESOLVED" for claim in CLAIM_IDS}
    report = {"schema_version": "1.0", "closure_id": closure_id, "status": "UNSET", "verifier_id": VERIFIER_ID,
              "verifier_hash": verifier_hash, "input_root_hash": None, "blocking_reasons": [], "infrastructure_errors": [],
              "execution_environment": {"python": sys.version, "python_executable": sys.executable, "platform": platform.platform()},
              "dependencies": {"verified": [], "trusted": TCB, "undeclared": []},
              "builds": {"required": 2, "passed": 0}, "determinism": {"required": True, "status": "UNSET"},
              "correspondence": {"required_objects": 0, "mapped_objects": 0, "unmapped_objects": 0, "ambiguous_objects": 0},
              "witnesses": {"required": 0, "valid": 0, "invalid": 0},
              "provenance": {"public_claims": 5, "fully_bound": 0, "orphan_claims": 5},
              "closure_boundary": {"verified_surface": CLAIM_IDS, "trusted_surface": TCB,
                                   "excluded_surface": spec["excluded"], "interpretation":
                                   "Closure covers only this frozen finite literal corpus under the declared TCB; it does not establish universal completeness."}}
    processes = []
    root_hash = None
    try:
        tc = leanbridge.resolve_toolchain()
        report["execution_environment"]["toolchain"] = tc.identity()
        rows, rejected, legacy = host_checks(positive_fixtures(), invalid_fixtures())
        batches = []
        for offset in range(0, len(rows), spec["positive_batch_size"]):
            batch_rows = rows[offset:offset + spec["positive_batch_size"]]
            source = ("namespace " + MODULE_NAMESPACE + "\n" + "\n".join(
                "def " + row["declaration"][1] + " : String := " + row["literal"] for row in batch_rows) +
                "\nend " + MODULE_NAMESPACE + "\n").encode("utf-8", "strict")
            source_path = output / f"positive-{len(batches):02d}.lean"
            source_path.write_bytes(source)
            batches.append((batch_rows, source_path, source))
        write_json(output / "correspondence-input.json", rows)
        for negative in negatives:
            (output / (negative["id"] + ".lean")).write_bytes(negative["source"].encode("utf-8", "strict"))
        paths = sorted([*input_paths(tc), *(source_path for _, source_path, _ in batches), output / "correspondence-input.json",
                        *(output / (negative["id"] + ".lean") for negative in negatives)], key=str)
        frozen = manifest(paths)
        root_hash = digest(json_bytes(frozen))
        report["input_root_hash"] = root_hash
        write_json(output / "manifest.json", frozen)
        write_json(output / "verifier-registry.json", {"verifier_id": VERIFIER_ID, "implementation_sha256": verifier_hash,
                   "closure_id": closure_id, "input_root_hash": root_hash, "argv": sys.argv, "exit_codes": {"0": "VERIFIED", "1": "BLOCKED", "2": "INFRASTRUCTURE_FAILURE"}})
        write_json(output / "tcb.json", {"trusted_components": [{"id": item, "classification": "TRUSTED"} for item in TCB],
                   "toolchain": tc.identity(), "runtime": report["execution_environment"], "scope": spec["excluded"]})
        write_json(output / "host-checks.json", {"invalid": rejected, "legacy_ids": legacy, "positive_count": len(rows)})
        report["correspondence"]["required_objects"] = len(rows)
        report["witnesses"]["required"] = len(rows)
        statuses["UL18-C2"] = "PASS"
        statuses["UL18-C3"] = "PASS"
        unit_argv = [sys.executable, "-m", "unittest", "tests.test_unicode_lean_literals_018", "-v"]
        unit = subprocess.run(unit_argv, cwd=ROOT, capture_output=True, timeout=30)
        (output / "unit.stdout").write_bytes(unit.stdout)
        (output / "unit.stderr").write_bytes(unit.stderr)
        write_json(output / "unit.json", {"argv": unit_argv, "returncode": unit.returncode,
                   "stdout_sha256": digest(unit.stdout), "stderr_sha256": digest(unit.stderr)})
        require(unit.returncode == 0, "Unicode regression unit tests failed")
        builds, inventories, correspondences = [], [], []
        budget = spec["budget"]
        with record_sandbox(output, processes):
            for build_id in ("A", "B"):
                round_artifacts, round_inventory, round_mapped = {}, [], []
                for batch_id, (batch_rows, _, source) in enumerate(batches):
                    label = f"{build_id}-{batch_id:02d}"
                    with tempfile.TemporaryDirectory(prefix="verislop-unicode-018-clean-") as work:
                        result = leanbridge.compile_module(tc, source, Path(work), timeout=budget["compile_timeout_seconds"], memory_mb=budget["memory_mb"])
                        compiler_process_index = len(processes) - 1
                        write_json(output / f"build-{label}.json", compile_record(result))
                        require(result.ok and not result.errors and not result.sorry_positions and
                                not any(message.get("severity") == "warning" for message in result.messages), "positive clean build failed: " + label)
                        require(result.process_evidence["returncode"] == 0, "positive compiler actual return code not zero")
                        artifact_paths = sorted(Path(work).glob("VeriSlopContract.olean*"))
                        artifacts = {path.name: digest_file(path) for path in artifact_paths}
                        require("VeriSlopContract.olean" in artifacts, "no compiled module")
                        for path in artifact_paths:
                            (output / f"build-{label}-{path.name}").write_bytes(path.read_bytes())
                        response = leanbridge.run_kernel_tool(tc, result.olean, {"export": True, "axioms": True},
                                                             timeout=budget["kernel_timeout_seconds"], memory_mb=budget["memory_mb"])
                        require(len(processes) == compiler_process_index + 2 and
                                "--run" in processes[-1]["argv"], "actual kernel row must immediately follow its positive compiler row")
                        require(processes[-1]["returncode"] == 0 and processes[-1]["timed_out"] is False,
                                "actual kernel process did not complete successfully")
                        require(processes[-1]["kernel_evidence"]["staged_module_parts"]["parts"] == artifacts,
                                "actual kernel staged module parts differ from retained compiler artifacts")
                        write_json(output / f"kernel-{label}.json", response)
                        mapped = check_export(response, batch_rows, tc, set(paths))
                        write_json(output / f"correspondence-{label}.json", mapped)
                        inventory = {"replay": response["replay"], "constants": response["constants"]}
                        round_artifacts[str(batch_id)] = {"source_sha256": digest(source), "artifacts": artifacts}
                        round_inventory.append(inventory)
                        round_mapped.extend(mapped)
                builds.append({"id": build_id, "artifacts": round_artifacts,
                               "inventory_sha256": digest(json_bytes(round_inventory)), "correspondence_sha256": digest(json_bytes(round_mapped))})
                inventories.append(round_inventory)
                correspondences.append(round_mapped)
                report["builds"]["passed"] += 1
            negative_results = []
            for negative in negatives:
                negative_source = negative["source"].encode("utf-8", "strict")
                with tempfile.TemporaryDirectory(prefix="verislop-unicode-018-negative-") as work:
                    result = leanbridge.compile_module(tc, negative_source, Path(work), timeout=budget["compile_timeout_seconds"], memory_mb=budget["memory_mb"])
                write_json(output / (negative["id"] + ".json"), compile_record(result))
                require(not result.ok and result.olean is None and not result.timed_out and result.errors and not result.sorry_positions,
                        "Lean negative did not fail with a genuine error: " + negative["id"])
                require(result.process_evidence["returncode"] != 0, "negative actual compiler return code is zero")
                require(any(negative["expected_error_fragment"] in error for error in result.errors), "negative diagnostic differs: " + negative["id"])
                negative_results.append({"id": negative["id"], "source_sha256": digest(negative_source),
                                         "returncode": result.process_evidence["returncode"], "errors": result.errors, "status": "PASS"})
        statuses["UL18-C1"] = "PASS"
        statuses["UL18-C4"] = "PASS"
        require(builds[0]["artifacts"] == builds[1]["artifacts"], "clean module artifacts differ")
        require(inventories[0] == inventories[1] and correspondences[0] == correspondences[1], "clean replay metadata differs")
        require(manifest(paths) == frozen, "frozen qualification input mutation")
        statuses["UL18-C5"] = "PASS"
        report["determinism"]["status"] = "PASS"
        report["correspondence"]["mapped_objects"] = len(rows)
        report["witnesses"]["valid"] = len(rows)
        write_json(output / "builds.json", builds)
        write_json(output / "negative-summary.json", negative_results)
        report["fixture_counts"] = {"positive": len(rows), "legacy": len(legacy), "invalid_surrogate": len(rejected), "lean_negative": len(negative_results)}
        report["status"] = "VERIFIED"
    except AssertionError as exc:
        report["status"] = "BLOCKED"
        report["blocking_reasons"].append({"code": "INPUT_MUTATION" if "input mutation" in str(exc) else "VERIFIER_FAILURE", "message": str(exc)})
        (output / "exception.txt").write_text(traceback.format_exc())
    except Exception as exc:
        report["status"] = "INFRASTRUCTURE_FAILURE"
        report["infrastructure_errors"].append({"code": "INFRASTRUCTURE_ERROR", "message": str(exc)})
        (output / "exception.txt").write_text(traceback.format_exc())
    write_json(output / "processes.json", processes)
    evidence = []
    for claim in spec["claims"]:
        claim_id = claim["id"]
        status = statuses[claim_id]
        row = {"schema_version": "1.0", "closure_id": closure_id, "claim_id": claim_id, "input_root_hash": root_hash,
               "verifier_id": VERIFIER_ID, "verifier_hash": verifier_hash, "execution_environment": report["execution_environment"],
               "raw_result": {"registered_statement": claim["statement"], "report_status": report["status"],
                              "artifacts": [{"path": path.name, "sha256": digest_file(path)} for path in sorted(output.iterdir())
                                            if path.is_file() and path.suffix in (".json", ".stdout", ".stderr") and not path.name.startswith("UL18-C")]},
               "exit_code": 0 if status == "PASS" else (2 if report["status"] == "INFRASTRUCTURE_FAILURE" else 1), "status": status}
        write_json(output / (claim_id + ".json"), row)
        evidence.append({"public_claim": claim["statement"], "claim_id": claim_id, "evidence": claim_id + ".json",
                         "verifier": VERIFIER_ID, "input_root_hash": root_hash, "trusted_dependencies": TCB})
    write_json(output / "provenance.json", evidence)
    report["claims"] = {"total": len(statuses), "passed": sum(v == "PASS" for v in statuses.values()),
                        "blocked": sum(v == "BLOCK" for v in statuses.values()), "unresolved": sum(v == "UNRESOLVED" for v in statuses.values()), "statuses": statuses}
    report["provenance"] = {"public_claims": len(evidence), "fully_bound": len(evidence) if root_hash else 0, "orphan_claims": 0 if root_hash else len(evidence)}
    report["decision"] = {"valid_states": ["VERIFIED", "BLOCKED", "INFRASTRUCTURE_FAILURE"], "manual_override_allowed": False}
    write_json(output / "report.json", report)
    print(json.dumps({"status": report["status"], "closure_id": closure_id, "input_root_hash": root_hash,
                      "claims": report["claims"], "report": str(output / "report.json")}))
    return {"VERIFIED": 0, "BLOCKED": 1, "INFRASTRUCTURE_FAILURE": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
