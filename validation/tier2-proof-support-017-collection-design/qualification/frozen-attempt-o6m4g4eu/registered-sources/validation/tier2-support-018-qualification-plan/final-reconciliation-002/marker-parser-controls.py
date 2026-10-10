"""Development-only exact marker parser controls; never open capture paths."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = json.loads((HERE / "marker-parser-control-inputs.json").read_text())
    for name, expected in frozen["files"].items():
        if digest(ROOT / name) != expected:
            raise ValueError("Development parser input changed: " + name)
    source = ast.parse((HERE / "reconcile.py").read_text())
    names = {"Block", "need", "collection_marker_paths"}
    nodes = [node for node in source.body if
             (isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names) or
             (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
              {"COLLECTION_ID", "CAPTURE_MARKERS"} for t in node.targets))]
    # Only the registered parser definitions execute, not the reconciler or any
    # producer/test/package/build function. Printed witness paths are never opened.
    environment = {"Path": Path, "re": re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "registered-marker-parser", "exec"), environment)
    parser, block = environment["collection_marker_paths"], environment["Block"]
    rows = []
    controls = json.loads((HERE / "marker-controls.json").read_text())["controls"]
    for control in controls:
        try:
            paths = list(parser(control["stdout"]))
            actual, reason = "ADMITTED", None
        except block as exc:
            paths, actual, reason = None, "BLOCKED", str(exc)
        expected = control["expected"]
        matches = actual == expected and (actual != "ADMITTED" or paths == control["paths"])
        rows.append({"id": control["id"], "expected": expected, "actual": actual,
                     "matches_registered_control": matches, "reason": reason})
    witness = ROOT / "validation/tier2-support-018-qualification/capture-stream-witness-001.stdout"
    witness_paths = parser(witness.read_text())
    report = {"format": "verislop.support018-marker-development-controls/1",
              "scope": "Development reader compatibility controls only; no qualification evidence or path/package reuse",
              "qualification": False, "controls": rows, "actual_stream_representation_admitted": len(witness_paths) == 2,
              "source_sha256": digest(HERE / "reconcile.py"), "input_freeze_sha256": digest(HERE / "marker-parser-control-inputs.json"),
              "paths_opened": ["registered parser/spec/control bytes and designated raw stream witness only"],
              "packages_opened": 0, "tests_executed": 0, "builds": 0, "models": 0, "channel_calls": 0}
    if not all(row["matches_registered_control"] for row in rows):
        raise ValueError("Development marker control disposition differs")
    target = HERE / "marker-parser-development-result.json"
    with target.open("x") as handle:
        json.dump(report, handle, sort_keys=True, indent=2)
        handle.write("\n")
    print(json.dumps({"scope": "DEVELOPMENT_ONLY_NONQUALIFICATION", "registered_controls": len(rows),
                      "matched_controls": sum(row["matches_registered_control"] for row in rows),
                      "actual_stream_representation_admitted": len(witness_paths) == 2,
                      "packages_opened": 0, "tests_executed": 0, "builds": 0, "models": 0, "channel_calls": 0}))


if __name__ == "__main__":
    main()
