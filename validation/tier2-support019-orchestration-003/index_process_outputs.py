"""Bind actual fresh registered receipt/output files, without deciding claims."""
import argparse
from pathlib import Path
from execute_phases import ROOT, bootstrap, canonical, gate_path, guard, identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", required=True)
    args = parser.parse_args()
    gate = gate_path(args.qualification_root)
    spec = bootstrap.load(gate / "qualification-specification.json")
    manifest = bootstrap.load(gate / "qualification-inputs.json")
    frozen = bootstrap.load(gate / "source-freeze.json")
    external = {p.relative_to(ROOT).as_posix(): canonical.digest_file(p)
                for p in (gate / "qualification-inputs.json", gate / "preregistration.json")}
    guard(manifest["source_hashes"], external, frozen, spec)
    own_path = Path(__file__).relative_to(ROOT).as_posix()
    if manifest["source_hashes"].get(own_path) != canonical.digest_file(Path(__file__)):
        raise ValueError("Index producer is not frozen")
    result = {"format": "verislop.support019-process-output-index/1", "closure_id": spec["closure_id"],
              "source_root": spec["source_root"], "input_root": manifest["input_root"],
              "producer_path": own_path, "producer_sha256": canonical.digest_file(Path(__file__)),
              "processes": {}}
    for phase in spec["execution_phases"] + spec["additional_processes"]:
        result["processes"][phase["id"]] = {
            "receipt": identity(gate / (phase["id"] + "-actual-process-receipt.json")),
            "outputs": {key: identity(ROOT / name) for key, name in phase["outputs"].items()}}
    guard(manifest["source_hashes"], external, frozen, spec)
    output = ROOT / spec["actual_process_output_index_path"]
    if output.parent != gate:
        raise ValueError("Index output is not at the frozen new root")
    bootstrap.write_once(output, result)
    print(output.relative_to(ROOT).as_posix(), canonical.digest_file(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
