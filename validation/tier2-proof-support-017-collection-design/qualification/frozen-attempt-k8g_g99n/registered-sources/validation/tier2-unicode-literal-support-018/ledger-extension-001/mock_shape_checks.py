#!/usr/bin/env python3
"""MOCK_ONLY: recording/file-copy checks without Lean or corpus execution."""
from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_record_sandbox(fake_run):
    source_path = PACKAGE / "verify.py"
    tree = ast.parse(source_path.read_bytes(), filename=str(source_path))
    names = {"digest", "digest_file", "record_sandbox", "require"}
    selected = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
    assert {node.name for node in selected.body} == names
    context = {"contextlib": contextlib, "hashlib": hashlib, "json": json, "Path": Path,
               "patch": patch, "sandbox": SimpleNamespace(run=fake_run),
               "leanbridge": SimpleNamespace(MODULE="VeriSlopContract", MODULE_PARTS=("VeriSlopContract.olean", "VeriSlopContract.olean.server", "VeriSlopContract.olean.private"))}
    exec(compile(selected, str(source_path), "exec"), context)
    return context["record_sandbox"]


def main():
    actual_invocations = []
    actual_shape_results = []
    kernel_bytes = b"MOCK_ONLY kernel tool bytes\n"
    raw_response = b'{"MOCK_ONLY":"raw bytes retain whitespace", "import": {"modules": []}}\n'
    staged_bytes = {"VeriSlopContract.olean": b"MOCK_ONLY public", "VeriSlopContract.olean.server": b"MOCK_ONLY server", "VeriSlopContract.olean.private": b"MOCK_ONLY private"}

    def fake_run(argv, cwd, **kwargs):
        actual_invocations.append((list(argv), str(cwd), kwargs))
        if "--run" in argv:
            assert not (Path(cwd) / "response.json").exists(), "response must be created by the mocked invocation, not beforehand"
            (Path(cwd) / "response.json").write_bytes(raw_response)
        return SimpleNamespace(returncode=0, timed_out=False, wall_seconds=0.125,
                               isolation={"MOCK_ONLY": True}, stdout=b"MOCK_ONLY stdout\x00", stderr=b"MOCK_ONLY stderr\xff")

    record_sandbox = load_record_sandbox(fake_run)
    with tempfile.TemporaryDirectory(prefix="unicode018-MOCK_ONLY-") as tmp:
        tmp_path = Path(tmp)
        cwd, output = tmp_path / "cwd", tmp_path / "output"
        cwd.mkdir()
        output.mkdir()
        stage = cwd / "stage"
        stage.mkdir()
        for name, data in staged_bytes.items():
            (stage / name).write_bytes(data)
        tool = cwd / "VeriSlopKernel.lean"
        tool.write_bytes(kernel_bytes)
        request = {"MOCK_ONLY": True, "module": "VeriSlopContract", "sysroot": str(tmp_path / "pin"), "search_dir": str(stage)}
        request_bytes = json.dumps(request, indent=2).encode() + b"\n"
        (cwd / "request.json").write_bytes(request_bytes)
        options = {"timeout": 30, "memory_mb": 24576, "require_network_isolation": True,
                   "require_filesystem_isolation": True, "read_only_paths": [tmp_path / "pin"]}
        rows = []
        with record_sandbox(output, rows):
            # The context manager patches only the fake sandbox object extracted
            # from the producer AST; no repository runner or Lean executable runs.
            sandbox_object = record_sandbox.__wrapped__.__globals__["sandbox"]
            sandbox_object.run(["MOCK_ONLY_lean", "-j4", "--json", "-M8192", "-o", "VeriSlopContract.olean", "VeriSlopContract.lean"], cwd, **options)
            sandbox_object.run(["MOCK_ONLY_lean", "-j4", "-M8192", "--run", str(tool), "request.json", "response.json"], cwd, **options)
        assert len(rows) == 2 and len(actual_invocations) == 2
        assert "kernel_evidence" not in rows[0]
        row = rows[1]
        assert row["argv"] == actual_invocations[1][0] and row["cwd"] == str(cwd)
        assert row["returncode"] == 0 and row["timed_out"] is False and row["wall_seconds"] == 0.125
        assert row["isolation"] == {"MOCK_ONLY": True}
        assert row["requested_options"] == {**options, "read_only_paths": [str(tmp_path / "pin")]}
        evidence = row["kernel_evidence"]
        originals = {"request": request_bytes, "response": raw_response, "kernel_tool": kernel_bytes}
        for kind, data in originals.items():
            field = evidence[kind]
            assert not Path(field["path"]).is_absolute()
            assert (output / field["path"]).read_bytes() == data
            assert field["sha256"] == sha(data) and field["bytes"] == len(data)
        assert evidence["staged_module_parts"] == {"module": "VeriSlopContract", "parts": {name: sha(data) for name, data in staged_bytes.items()}}
        for name, data in staged_bytes.items():
            assert (output / "process-01.stage" / name).read_bytes() == data
        for name, data in (("stdout", b"MOCK_ONLY stdout\x00"), ("stderr", b"MOCK_ONLY stderr\xff")):
            assert (output / row[name]["path"]).read_bytes() == data
            assert row[name]["sha256"] == sha(data) and row[name]["bytes"] == len(data)
        actual_shape_results.append("compiler/kernel order and actual-shaped raw file copies retained after fake run")

    receipt = {"format": "verislop.unicode018-ledger-MOCK_ONLY-shape-receipt/1", "status": "MOCK_ONLY_PASS",
               "actual_lean_builds": 0, "actual_lean_tests": 0, "model_calls": 0,
               "verifier_sha256": sha((PACKAGE / "verify.py").read_bytes()),
               "mock_checker_sha256": sha(Path(__file__).read_bytes()), "checks": actual_shape_results,
               "semantic_evidence": False}
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
