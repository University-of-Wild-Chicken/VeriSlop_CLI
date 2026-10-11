"""Observe only registered source guards and this unrelated probe's own session."""
from pathlib import Path
import hashlib
import json
import os
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
registration = json.loads((HERE / "CONTROL_REGISTRATION_BEFORE_EXECUTION.json").read_bytes())
binding = json.loads((HERE / "OWN_REFERENCE_AND_CODE.json").read_bytes())
phase = sys.argv[1]
if phase not in ("BEFORE_SEQUENCE", "BEFORE_INVALID", "AFTER_INVALID", "AFTER_VALID_VIEW", "AFTER_CONFIRM"):
    raise ValueError("UNREGISTERED_PROBE_PHASE")
observed = {name: "sha256:" + hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in registration["guards"]}
if not observed or observed != registration["guards"]:
    raise ValueError("ACTUAL_REGISTERED_GUARD_MISMATCH")
state = Path(binding["session_path"])
record = {"phase": phase, "actual_observer_pid": os.getpid(), "guards": observed,
          "all_registered_guards_match": True, "accepted_state_exists": state.exists()}
if state.exists():
    raw = state.read_bytes()
    (HERE / (phase + "-accepted-state.raw")).write_bytes(raw)
    record["accepted_state_sha256"] = "sha256:" + hashlib.sha256(raw).hexdigest()
    record["accepted_state_bytes"] = len(raw)
(HERE / (phase + "-observation.json")).write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({key: value for key, value in record.items() if key != "guards"}), flush=True)
