"""Specification-bound single-instance bootstrap; never a full-corpus result.

Reuses the exact strict CLI, origin auditor and two isolated graders. Source
snapshots isolate successive increments without editing historical experiments.
Only model transport is substituted; no positive candidates are supplied.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import signal

from synthetic_dataset import benchmark as bench
from synthetic_dataset.build_dataset import digest, encode
from synthetic_dataset.tools import sol_full_corpus as full

FORMAT = "verislop.coverage-bootstrap/0.1"


def snapshot(base: Path, project: Path, overlays: list[Path]) -> dict:
    if project.exists():
        raise ValueError("Bootstrap project snapshots are write-once")
    original = bench.load(base / "protocol.json")
    project.mkdir(parents=True)
    inventory = {}
    for rel, expected in original["source_hashes"].items():
        src = base / "execution-source" / rel
        if src.is_symlink() or digest(src.read_bytes()) != expected:
            raise ValueError("Historical frozen source changed: " + rel)
        dst = project / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    for rel, expected in original["dataset_files"].items():
        src = base / "frozen-corpus" / rel
        if src.is_symlink() or digest(src.read_bytes()) != expected:
            raise ValueError("Historical frozen corpus changed: " + rel)
        dst = project / "synthetic_dataset" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    manifest = full.ROOT / "manifest.json"
    if digest(manifest.read_bytes()) != original["dataset_manifest_sha256"]:
        raise ValueError("Original corpus manifest changed")
    (project / "synthetic_dataset/manifest.json").write_bytes(manifest.read_bytes())
    for overlay in overlays:
        changed = {}
        for src in sorted(overlay.rglob("*")):
            if src.is_symlink():
                raise ValueError("Overlay symlinks are not supported")
            if not src.is_file() or src.name == "OVERLAY-MANIFEST.json":
                continue
            rel = src.relative_to(overlay).as_posix()
            if not rel.startswith(("verislop/", "schemas/", "formal/", "synthetic_dataset/tools/", "docs/", "tests/")):
                raise ValueError("Overlay path outside source surface: " + rel)
            dst = project / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            changed[rel] = digest(src.read_bytes())
        inventory[str(overlay)] = changed
    # The runner and umbrella specification are new generic measurement inputs.
    for rel in ("synthetic_dataset/tools/bootstrap_coverage.py", "docs/coverage-bootstrap.md"):
        dst = project / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((full.REPO / rel).read_bytes())
    provenance = {"format": FORMAT, "base_protocol_sha256": digest((base / "protocol.json").read_bytes()),
        "project": str(project), "overlays": inventory,
        "spec_sha256": digest((project / "docs/coverage-bootstrap.md").read_bytes())}
    full.write_once(project.parent / "SNAPSHOT-PROVENANCE.json", provenance)
    return provenance


def selection(task: str) -> dict:
    return next(row for row in full.pair_order() if row["task"] == task and row["arm"] == "verislop")


def prepare(cohort: Path, task: str, stage: str) -> dict:
    selected = selection(task)  # Reject unknown tasks before publishing inputs.
    full.prepare(cohort)
    specifications = {p.relative_to(full.REPO).as_posix(): digest(p.read_bytes())
                      for p in sorted((full.REPO / "docs").glob("*bootstrap*.md"))}
    record = {"format": FORMAT, "stage": stage, "selection": selected,
        "scope": "one original corpus instance; not a full-corpus experiment",
        "specifications": specifications, "protocol_sha256": digest((cohort / "protocol.json").read_bytes()),
        "model_context": "Original prompt/public examples and native CLI context only; no hidden cases/oracle/old model answers",
        "success_predicate": "Native strict PASS/TESTED finite VERIFIED closure, exact origin, two clean builds and all corpus cases in both independent graders",
        "excluded_claims": ["END_TO_END_VERIFIED", "universal Python correctness", "unbiased full-corpus or equal-compute comparison"]}
    full.write_once(cohort / "BOOTSTRAP.json", record)
    for rel in specifications:
        dst = cohort / "specifications" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((full.REPO / rel).read_bytes())
    return record


def verify_selection(cohort: Path) -> dict:
    full.verify_inputs(cohort)
    record = bench.load(cohort / "BOOTSTRAP.json")
    if (record.get("format") != FORMAT or record.get("selection") != selection(record["selection"]["task"])
            or record["protocol_sha256"] != digest((cohort / "protocol.json").read_bytes())):
        raise ValueError("Bootstrap selection changed")
    for rel, expected in record["specifications"].items():
        if (digest((full.REPO / rel).read_bytes()) != expected
                or digest((cohort / "specifications" / rel).read_bytes()) != expected):
            raise ValueError("Bootstrap specification changed: " + rel)
    return record


def run(cohort: Path) -> dict:
    record = verify_selection(cohort)
    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("Explicit interruption")))
    try:
        row = full.run_arm(cohort, record["selection"])
    except KeyboardInterrupt:
        full.transport.atomic_json(cohort / "active-arm.json", {"phase": "stopped"})
        full.update_progress(cohort, status="INTERRUPTED")
        raise
    finally:
        signal.signal(signal.SIGTERM, previous)
    full.transport.atomic_json(cohort / "active-arm.json", {"phase": "bootstrap_complete"})
    full.update_progress(cohort, status="BOOTSTRAP_TERMINATED")
    audit = full.verify(cohort)
    result = {"format": FORMAT, "stage": record["stage"], "task": row["task"],
        "status": "VERIFIED" if row["successful_task"] else row["workflow_status"],
        "native_tested": row["native_tested"], "strict_cli_success": row["strict_cli_success"],
        "source_root": row["source_root"], "dataset_root": row["dataset_root"],
        "specifications": record["specifications"], "score": row, "retained_score_audit": audit}
    full.write_once(cohort / "BOOTSTRAP-RESULT.json", result)
    files = full.evidence_files(cohort)
    full.write_once(cohort / "BOOTSTRAP-EVIDENCE-MANIFEST.json", {"format": FORMAT,
        "files": files, "files_root": full.canonical.digest_json(files)})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "prepare", "run", "pending", "submit"))
    parser.add_argument("--cohort", type=Path)
    parser.add_argument("--task", default="D21")
    parser.add_argument("--stage")
    parser.add_argument("--base", type=Path)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--overlay", type=Path, action="append", default=[])
    parser.add_argument("--file", type=Path)
    args = parser.parse_args(argv)
    if args.action == "snapshot":
        value = snapshot(args.base.resolve(), args.project.resolve(), [p.resolve() for p in args.overlay])
    else:
        cohort = args.cohort.resolve()
        if args.action == "prepare":
            value = prepare(cohort, args.task, args.stage)
        elif args.action == "run":
            value = run(cohort)
        elif args.action == "pending":
            verify_selection(cohort)
            value = full.pending_request(cohort)
            if args.file:
                full.transport.atomic_json(args.file, value)
                value = {k: value[k] for k in ("agent_message", "model_override", "fork_turns", "task", "arm") } if value else None
        else:
            verify_selection(cohort)
            value = full.submit_response(cohort, bench.load(args.file))
    if args.action == "run":
        value = {k: value[k] for k in ("stage", "task", "status", "native_tested", "source_root")}
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
