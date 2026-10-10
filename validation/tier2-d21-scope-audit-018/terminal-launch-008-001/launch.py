from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
import time
HERE=Path(__file__).absolute().parent
def write(name,obj):
    with (HERE/name).open("x") as h:
        json.dump(obj,h,sort_keys=True,indent=2);h.write("\n")
def stream(path):
    data=path.read_bytes()
    return {"path":str(path),"byte_count":len(data),"sha256":"sha256:"+hashlib.sha256(data).hexdigest()}
def main():
    invocation_path=HERE/"invocation-root-authorized.json"
    raw=invocation_path.read_bytes();request=json.loads(raw)
    if request["process_deadline"] is not None or request["root_authorization"] is not True:
        raise ValueError("Missing exact root authorization or unexpected deadline")
    for name,digest in request["bound_files"].items():
        if "sha256:"+hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise ValueError("Authorized launcher input changed: "+name)
    started=datetime.now(timezone.utc).isoformat();tick=time.monotonic_ns()
    environment=dict(os.environ);environment.update(request["environment_overrides"])
    out=HERE/"stdout.log";err=HERE/"stderr.log"
    with out.open("xb") as oh,err.open("xb") as eh:
        child=subprocess.Popen(request["argv"],cwd=request["cwd"],env=environment,stdin=subprocess.DEVNULL,stdout=oh,stderr=eh)
        write("invocation-actual.json",{"format":"verislop.actual-registered-reader-invocation/1","argv":request["argv"],"cwd":request["cwd"],"environment_overrides":request["environment_overrides"],"stdin":"DEVNULL","launcher_pid":os.getpid(),"pid":child.pid,"started_at_utc":started,"timeout_seconds":None,"authorized_invocation_sha256":"sha256:"+hashlib.sha256(raw).hexdigest()})
        print(json.dumps({"pid":child.pid,"launcher_pid":os.getpid(),"started_at_utc":started}),flush=True)
        returncode=child.wait()
    ended=datetime.now(timezone.utc).isoformat();elapsed=time.monotonic_ns()-tick
    receipt={"format":"verislop.actual-registered-reader-process/1","argv":request["argv"],"cwd":request["cwd"],"environment_overrides":request["environment_overrides"],"launcher_pid":os.getpid(),"pid":child.pid,"started_at_utc":started,"ended_at_utc":ended,"elapsed_nanoseconds":elapsed,"returncode":returncode,"timed_out":False,"timeout_seconds":None,"stdout":stream(out),"stderr":stream(err),"authorized_invocation_sha256":"sha256:"+hashlib.sha256(raw).hexdigest(),"cpu_and_peak_memory":"UNAVAILABLE"}
    write("process-receipt.json",receipt)
    print(json.dumps({"returncode":returncode,"receipt":str(HERE/"process-receipt.json")}),flush=True)
    return returncode
if __name__=="__main__":raise SystemExit(main())
