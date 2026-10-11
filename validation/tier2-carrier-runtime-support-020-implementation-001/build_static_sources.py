"""Source-only deterministic construction; no runtime, tests or model call."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
HEADER = ('"use strict";\nconst fs = require("node:fs");\n'
          'const path = require("node:path");\nconst crypto = require("node:crypto");\n'
          'const childProcess = require("node:child_process");\n\n')


def main():
    reader = (HERE / "READER_SOURCE.py.literal").read_bytes()
    validator = (HERE / "CHECKPOINT_VALIDATOR_SOURCE.js.literal").read_bytes()
    sha = (HERE / "OWN_SHA256_SOURCE.js.literal").read_bytes()
    (HERE / "reader.py").write_bytes(reader + (HERE / "reader_cli.py.fragment").read_bytes())
    (HERE / "carrier_runtime.js").write_bytes(HEADER.encode() + validator + b"\n" + sha + b"\n"
                                             + (HERE / "runtime_tail.js.fragment").read_bytes())
    print(json.dumps({name: {"sha256": "sha256:" + hashlib.sha256((HERE/name).read_bytes()).hexdigest(),
                            "byte_count": (HERE/name).stat().st_size}
                      for name in ("reader.py", "carrier_runtime.js")}))


if __name__ == "__main__":
    main()
