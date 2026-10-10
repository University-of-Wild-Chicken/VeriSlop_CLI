#!/usr/bin/env python3
"""Source interface preflight only; never execute an evidence verifier or task."""
import argparse
import ast
import hashlib
import json
from pathlib import Path


def identity(path, raw):
    return {"path": str(path), "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "byte_count": len(raw)}


def inspect(spec_path, adapter_dir):
    raw = spec_path.read_bytes()
    spec = json.loads(raw)
    records, failures = [], []
    for filename in ("predicate_reader.py", "current_root_reconcile.py", "additional_predicates.py"):
        path = adapter_dir / filename
        source = path.read_bytes()
        tree = ast.parse(source, filename=str(path))
        checked = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Subscript):
                continue
            value, keys = node, []
            while (isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Constant)
                   and type(value.slice.value) in (str, int)):
                keys.append(value.slice.value)
                value = value.value
            if not (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
                    and value.value.id == "self" and value.attr in ("adapters", "config", "spec")):
                continue
            keys.reverse()
            marker = (node.lineno, value.attr, tuple(keys))
            if marker in checked:
                continue
            checked.add(marker)
            current = spec if value.attr == "spec" else spec["adapters"]
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                elif isinstance(current, list) and type(key) is int and 0 <= key < len(current):
                    current = current[key]
                else:
                    failures.append({"source": str(path), "line": node.lineno,
                                     "configuration_base": value.attr, "path": keys,
                                     "first_missing_component": key})
                    break
        records.append({**identity(path, source), "literal_paths_inspected": len(checked)})
    return {"format": "verislop.source-interface-preflight/1",
            "status": "READY" if not failures else "BLOCKED", "configuration": identity(spec_path, raw),
            "sources": records, "missing_literal_paths": failures,
            "scope": "Static literal configuration paths only; dynamic artifacts and semantic predicates require actual admission.",
            "verifiers_executed": 0, "model_calls": 0, "task_inputs": False,
            "qualification_or_task_lifecycle_authority": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--adapter-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.spec, args.adapter_dir)
    with args.output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
