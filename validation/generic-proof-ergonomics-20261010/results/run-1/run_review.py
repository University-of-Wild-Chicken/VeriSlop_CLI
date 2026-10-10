"""Standalone, task-unrelated ergonomics probe. Never mutates frozen inputs."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MODULES = [
    "VSCore.Syntax", "VSCore.Decode", "VSCore3.Syntax", "VSCore3.Equality",
    "VSCore3.Decode", "VSCore3.Typed", "VSCore3.Typing", "VSCore3.Semantics",
    "VSCore3.Proofs", "VSCore3.Transport", "VSCore3.SourceFacts", "VSCore3",
]
FROZEN = [ROOT / "verislop/lean" / (m.replace(".", "/") + ".lean") for m in MODULES]
FROZEN += [ROOT / "verislop/targets/vscore3_target.py", ROOT / "verislop/targets/vscore3_readable.py",
           ROOT / "docs/bootstrap-tier2-readable-denotation.md"]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    modules = HERE / "inputs/modules"
    modules.mkdir(parents=True, exist_ok=True)
    previous = HERE / "results"
    previous.mkdir(exist_ok=True)
    results = previous / ("run-" + str(len(list(previous.glob("run-*")))))
    results.mkdir()
    for path in HERE.glob("*.lean"):
        shutil.copyfile(path, results / path.name)
    inventory = {str(p.relative_to(ROOT)): digest(p) for p in FROZEN}
    for path in FROZEN:
        target = HERE / "inputs/frozen" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for module in MODULES:
        rel = Path(module.replace(".", "/") + ".lean")
        target = modules / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "verislop/lean" / rel, target)
    env = dict(os.environ, LEAN_PATH=str(modules), PYTHONDONTWRITEBYTECODE="1")
    records = []
    def run(label, command):
        started = time.monotonic()
        proc = subprocess.run(command, cwd=HERE, env=env, text=True, capture_output=True, timeout=90)
        (results / (label + ".stdout.txt")).write_text(proc.stdout)
        (results / (label + ".stderr.txt")).write_text(proc.stderr)
        record = {"label": label, "command": command, "returncode": proc.returncode,
                  "elapsed_seconds": time.monotonic() - started}
        records.append(record)
        print(label, proc.returncode, flush=True)
        (results / "commands.json").write_text(json.dumps(records, indent=2) + "\n")
        return proc.returncode
    run("toolchain", ["lean", "--version"])
    for module in MODULES:
        rel = Path(module.replace(".", "/") + ".lean")
        if run("module_" + module, ["lean", "-o", str(modules / rel.with_suffix(".olean")), str(modules / rel)]):
            raise RuntimeError("generic current library compilation failed")
    probe_outcomes = {}
    for fixture in ["Fixture", "MapCatalog", "FilterCatalog", "FoldCatalog", "DecisionCatalog", "PositiveControls"]:
        code = run(fixture, ["lean", "-o", str(modules / (fixture + ".olean")), str(HERE / (fixture + ".lean"))])
        if fixture.endswith("Catalog"):
            probe_outcomes[fixture] = code != 0 and "error: unsolved goals" in (results / (fixture + ".stdout.txt")).read_text()
        else:
            probe_outcomes[fixture] = code == 0
    unchanged = {str(p.relative_to(ROOT)): digest(p) for p in FROZEN} == inventory
    (results / "inventory.json").write_text(json.dumps({"scope": "generic proof ergonomics only",
        "frozen_inputs_unchanged": unchanged, "frozen_inputs": inventory,
        "fixture_inputs": {p.name: digest(p) for p in sorted(HERE.glob("*.lean"))}}, indent=2) + "\n")
    if not unchanged:
        raise RuntimeError("frozen input bytes changed during probe")
    (results / "summary.json").write_text(json.dumps({
        "scope": "generic authoring-catalog limitation; no task assurance or current qualification change",
        "checked_normalization": "explicit adapter unfolding and inverse laws plus the six published ProofSupport lemmas",
        "expected_probe_outcomes": probe_outcomes,
        "all_expected_outcomes_observed": all(probe_outcomes.values()),
        "positive_controls_kernel_elaborated": probe_outcomes["PositiveControls"],
        "frozen_inputs_unchanged": unchanged,
        "limitation": "This is not an automatic normalizer supplied by the product and is not a test of the optional correspondence recipe.",
    }, indent=2) + "\n")
    if not all(probe_outcomes.values()):
        raise RuntimeError("probe not substantiated: expected outcomes missing")

if __name__ == "__main__":
    main()
