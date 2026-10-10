"""Finite AST-extracted path controls; DEVELOPMENT_ONLY_NONQUALIFICATION."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "validation/tier2-support-018-qualification-002/prepare-inputs.py"


def main():
    inputs = json.loads((HERE / "path-normalization-control-inputs.json").read_text())
    digest = lambda data: "sha256:" + hashlib.sha256(data).hexdigest()
    if digest(SOURCE.read_bytes()) != inputs["prepare_sha256"]:
        raise ValueError("Control source changed after registration")
    if digest(Path(__file__).read_bytes()) != inputs["control_sha256"]:
        raise ValueError("Control implementation changed after registration")
    module = ast.parse(SOURCE.read_text())
    helper = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "authenticated_amendment"]
    if len(helper) != 1:
        raise ValueError("Exact helper not found")
    namespace = {"ROOT": ROOT}
    exec(compile(ast.Module(body=helper, type_ignores=[]), str(SOURCE), "exec"), namespace)
    function = namespace["authenticated_amendment"]
    target = HERE / "path-normalization-amendment-001.json"
    wanted = target.relative_to(ROOT).as_posix()
    cases = []
    with tempfile.TemporaryDirectory(prefix="path-control-only-", dir=HERE) as temporary:
        fixture = Path(temporary)
        leaf = fixture / "leaf.json"
        leaf.symlink_to(target)
        directory = fixture / "linked-directory"
        directory.symlink_to(HERE, target_is_directory=True)
        definitions = [
            ("P001", target.relative_to(Path.cwd()), True),
            ("P002", target, True),
            ("P003", HERE / "." / target.name, True),
            ("P004", HERE / ".." / HERE.name / target.name, True),
            ("P005", ROOT.parent / "outside-unopened.json", False),
            ("P006", Path("../outside-unopened.json"), False),
            ("P007", fixture / "missing.json", False),
            ("P008", HERE, False),
            ("P009", leaf, False),
            ("P010", directory / target.name, False),
        ]
        for identifier, argument, expected in definitions:
            try:
                authenticated, relative = function(argument)
                accepted = authenticated == target and relative == wanted and not Path(relative).is_absolute()
                outcome = "accepted" if accepted else "wrong identity"
            except ValueError:
                accepted, outcome = False, "rejected"
            cases.append({"id": identifier, "expected_accepted": expected,
                          "observed": outcome, "matched": accepted is expected})
    output = HERE / "path-normalization-development-result.json"
    if output.exists():
        raise ValueError("Development result already exists")
    result = {"format": "verislop.support018-root002-path-controls/1", "status": "DEVELOPMENT_ONLY_NONQUALIFICATION",
              "prepare_sha256": digest(SOURCE.read_bytes()), "control_sha256": digest(Path(__file__).read_bytes()),
              "controls": cases, "all_expected_dispositions_matched": all(row["matched"] for row in cases),
              "prepare_invoked": False, "actual_tests_executed": 0, "builds": 0, "models": 0,
              "channel_calls": 0, "qualification_runs": 0, "outside_file_contents_read": 0}
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "matched": sum(row["matched"] for row in cases), "controls": len(cases)}))
    return 0 if result["all_expected_dispositions_matched"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
