"""Detached orchestration only; run the unchanged, frozen native bootstrap."""
from pathlib import Path
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
project = root / "synthetic_dataset/bootstrap/stages/tier2-source-facets-013/project"
cohort = project.parent / "run"
gate = Path(__file__).resolve().parent
if Path.cwd() != project:
    raise RuntimeError("The native driver must run in its exact frozen project")
sys.path.insert(0, str(project))
from synthetic_dataset.tools import bootstrap_tier2 as bootstrap
from verislop import canonical

command = [sys.executable, "-m", "synthetic_dataset.tools.bootstrap_tier2", "run", "--cohort", str(cohort)]
bootstrap.write_once(gate / "driver-invocation.json", {
    "format": "verislop.tier2-native-live-driver/0.1",
    "command": command, "cwd": str(project), "cohort": str(cohort),
    "source_root": bootstrap.load(cohort / "protocol.json")["source_root"],
    "driver_script_sha256": canonical.digest_file(Path(__file__)),
    "detached_session": True, "supervisor_pid": os.getpid(),
    "model_generation_deadline": None, "model_identity_attested": False,
})
with (gate / "driver.stdout.log").open("xb") as out, (gate / "driver.stderr.log").open("xb") as err:
    result = subprocess.run(command, cwd=project, stdout=out, stderr=err)
bootstrap.write_once(gate / "driver-result.json", {
    "format": "verislop.tier2-native-live-driver-result/0.1",
    "returncode": result.returncode,
    "stdout_sha256": canonical.digest_file(gate / "driver.stdout.log"),
    "stderr_sha256": canonical.digest_file(gate / "driver.stderr.log"),
})
print(json.dumps({"returncode": result.returncode}), flush=True)
sys.exit(result.returncode)
