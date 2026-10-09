"""Generate the frozen, human-authored synthetic benchmark locally; no model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GENERATORS = ("generate_graph_systems", "generate_text_data", "generate_algorithms")


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode()


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build(out=ROOT):
    import importlib
    tasks = []
    for name in GENERATORS:
        module = importlib.import_module("synthetic_dataset." + name)
        batch = module.build_tasks()
        assert encode(batch) == encode(module.build_tasks()), f"{name}: nondeterministic generation"
        for task in batch:
            assert task["difficulty"] == "hard"
            assert len(task["cases"]) >= 10
            assert sum(c["visibility"] == "public" for c in task["cases"]) == 2
            assert len({c["id"] for c in task["cases"]}) == len(task["cases"])
            assert len({encode(c["input"]) for c in task["cases"]}) == len(task["cases"]), task["id"]
            for case in task["cases"]:
                observed = module.reference(task["id"], json.loads(encode(case["input"])))
                assert encode(observed) == encode(case["expected"]), (task["id"], case["id"])
            tasks.append(task)
    tasks.sort(key=lambda t: t["id"])
    assert len(tasks) == 100 and len({t["id"] for t in tasks}) == 100
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in tasks:
        directory = out / "tasks" / task["id"]
        directory.mkdir(parents=True, exist_ok=True)
        examples = [{"input": c["input"], "output": c["expected"]} for c in task["cases"] if c["visibility"] == "public"]
        prompt = (f"Software engineering task {task['id']}: {task['title']}\n\n{task['prompt'].strip()}\n\n"
                  "Implement a pure deterministic Python 3 function solve(data) in solution.py. "
                  "Use only the standard library, no external I/O. The function receives a JSON value and returns a JSON-serializable value. "
                  "Preserve the specified input/output structure and exact ordering.\n\n"
                  "Public examples (additional held-out cases will be scored):\n" + json.dumps(examples, ensure_ascii=False, sort_keys=True) + "\n")
        (directory / "prompt.txt").write_text(prompt)
        (directory / "cases.json").write_bytes(encode(task["cases"]))
        meta = {k: task[k] for k in ("id", "title", "category", "difficulty")}
        meta.update({"prompt_path": f"tasks/{task['id']}/prompt.txt", "cases_path": f"tasks/{task['id']}/cases.json",
                     "public_cases": 2, "hidden_cases": len(task["cases"]) - 2})
        rows.append(meta)
    (out / "tasks.jsonl").write_bytes(b"".join(encode(row) for row in rows))
    paths = [out / "tasks.jsonl", *(out / "tasks").rglob("*.txt"), *(out / "tasks").rglob("*.json")]
    manifest = {"format": "verislop.synthetic-dataset/0.1", "tasks": len(rows), "seed_policy": "fixed in each generator",
                "generation": "local deterministic human-authored generators; no model-generated tasks",
                "cases": sum(t["public_cases"] + t["hidden_cases"] for t in rows),
                "files": {p.relative_to(out).as_posix(): digest(p.read_bytes()) for p in sorted(paths)}}
    manifest["generator_hashes"] = {name + ".py": digest((ROOT / (name + ".py")).read_bytes()) for name in GENERATORS}
    manifest["dataset_root"] = digest(encode(manifest))
    (out / "manifest.json").write_bytes(encode(manifest))
    return manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=ROOT)
    args = p.parse_args()
    print(json.dumps(build(args.out), indent=2))
