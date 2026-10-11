"""Actual finite source-control launcher; no agent, viewer, or qualification."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def hashes(registration):
    return {name:sha((ROOT/name).read_bytes()) for name in registration["guards"]}

def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

registration = json.loads((HERE/"CONTROL_REGISTRATION_BEFORE_EXECUTION.json").read_bytes())
output = HERE / sys.argv[1]
if output.exists() or output.parent != HERE or not output.name.startswith("source-controls-"):
    raise ValueError("CONTROL_OUTPUT_MUST_BE_NEW")
before = hashes(registration)
if not before or before != registration["guards"]:
    raise ValueError("CONTROL_REGISTERED_GUARD_MISMATCH")
output.mkdir()
argv = registration["argv"]
started = stamp()
process = subprocess.Popen(argv,cwd=ROOT,env=registration["environment"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
stdout,stderr = process.communicate()
completed = stamp()
(output/"stdout.log").write_bytes(stdout); (output/"stderr.log").write_bytes(stderr)
after = hashes(registration)
receipt = {"format":"verislop.support023-actual-source-control-receipt/1","actual_launcher_pid":os.getpid(),"pid":process.pid,"argv":argv,"cwd":str(ROOT),"environment":registration["environment"],"started_utc":started,"completed_utc":completed,"returncode":process.returncode,"timed_out":False,"guards_before":before,"guards_after":after,"all_guards_unchanged":before==after==registration["guards"],"guard_count":len(before),"stdout":{"path":str((output/"stdout.log").relative_to(ROOT)),"sha256":sha(stdout),"byte_count":len(stdout)},"stderr":{"path":str((output/"stderr.log").relative_to(ROOT)),"sha256":sha(stderr),"byte_count":len(stderr)},"synthetic_observations":"SYNTHETIC_SOURCE_CONTROL_NO_ACTUAL_AGENT","qualification_authority":False}
(output/"actual-process-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({"actual_launcher_pid":os.getpid(),"actual_child_pid":process.pid,"returncode":process.returncode,"registered_tests":len(registration["test_ids"]),"guard_count":len(before),"all_guards_unchanged":receipt["all_guards_unchanged"],"receipt":str((output/"actual-process-receipt.json").relative_to(ROOT))}),flush=True)
if before != after or after != registration["guards"]:
    raise SystemExit(3)
raise SystemExit(process.returncode)
