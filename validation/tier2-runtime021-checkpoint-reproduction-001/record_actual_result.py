from pathlib import Path
import json
import os
import re
import sys

HERE = Path(__file__).resolve().parent
record = json.loads(sys.argv[1])
label = record["label"]
if not re.fullmatch(r"P0[1-9]|PREPARATION|(?:BEFORE_SEQUENCE|BEFORE_CHECKPOINT|AFTER_CHECKPOINT|AFTER_RECOVERY_VIEW|AFTER_RECOVERY_CONFIRM)-OBSERVER", label):
    raise ValueError("UNREGISTERED_RESULT_LABEL")
if set(record) - {"label", "request", "submitted_command", "result"}:
    raise ValueError("INVALID_RESULT_RECORD")
for key in ("request", "submitted_command", "result"):
    if key in record:
        (HERE / (label + "-actual-" + key + ".json")).write_text(json.dumps(record[key], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
if "result" in record:
    (HERE / (label + "-actual-combined-output.raw")).write_text(record["result"]["output"], encoding="utf-8")
print(json.dumps({"actual_recorder_pid": os.getpid(), "label": label}), flush=True)
