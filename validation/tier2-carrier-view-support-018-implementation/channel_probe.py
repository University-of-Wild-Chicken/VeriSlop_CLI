"""Materialize unrelated channel input/commands; never a fresh author's helper.

Root preparation may read this adapter. The actual tested author command is the
returned complete inline command, which opens only its exact synthetic carrier.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from synthetic_dataset.tools import bootstrap_tier2_carrier_view as viewer
from verislop import canonical


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=False)
    corpus = ''.join(chr(i) for i in range(32)) + '/\\"é🙂e\u0301'
    carrier = {"format": "verislop.collaboration-carrier/0.1", "request_id": "unrelated-channel-fixture",
               "request_sha256": "sha256:" + "a" * 64,
               "system": "Read this unrelated synthetic fixture only.",
               "user": "HEAD" + corpus * 1000 + "TAIL🙂\t "}
    path = (directory / "own-carrier.json").absolute()
    path.write_bytes(canonical.dumps(carrier))
    reference = {"path": str(path), "sha256": canonical.digest_file(path),
                 "request_sha256": carrier["request_sha256"]}
    commands = {}
    for label, cap, reserve, budget in (("intact", 8192, 2048, 16384), ("truncated", 8192, 2048, 100), ("retry", 4096, 2048, 16384)):
        view = {"operation": "field", "selector": "/user", "start_char": 0,
                "output_cap_bytes": cap, "metadata_reserve_bytes": reserve}
        commands[label] = {"cmd": viewer.inline_command(reference, view), "max_output_tokens": budget,
                           "reference": reference, "view": view,
                           "produced_stdout_path": str((directory / (label + ".produced-stdout")).absolute())}
    (directory / "commands.json").write_text(json.dumps(commands, sort_keys=True, indent=2) + '\n')
    return {"commands_path": str((directory / "commands.json").absolute()), "carrier_sha256": reference["sha256"],
            "fixture_source": "public deterministic controls/scalars; no live task input"}


def command(directory, label):
    return json.loads((directory / "commands.json").read_text())[label]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "command"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--label", choices=("intact", "truncated", "retry"), default="intact")
    arguments = parser.parse_args()
    result = prepare(arguments.directory) if arguments.action == "prepare" else command(arguments.directory, arguments.label)
    print(json.dumps(result, sort_keys=True))
