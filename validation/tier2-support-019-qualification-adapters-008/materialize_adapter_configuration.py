#!/usr/bin/env python3
"""Resolve registered adapter paths/contracts before freeze; run no verifier."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_source(name):
    path = ROOT / name
    if not path.is_file() or path.is_symlink() or path.resolve() != path.absolute():
        raise ValueError("Missing canonical registered source: " + name)
    return path


def expand(value, replacements):
    if isinstance(value, str):
        for old, new in replacements.items(): value = value.replace("{" + old + "}", new)
        return value
    if isinstance(value, list): return [expand(item, replacements) for item in value]
    if isinstance(value, dict): return {key: expand(item, replacements) for key, item in value.items()}
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", required=True)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--equality-producer-source", required=True)
    parser.add_argument("--pure-producer-source", required=True)
    parser.add_argument("--pure-contracts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(args.qualification_root)
    if root.is_absolute() or root.parent.as_posix() != "validation" or not root.name.startswith("tier2-support-019-qualification-"):
        raise ValueError("Expected literal new qualification root relative to repository")
    bindings = load(args.bindings)
    equality = canonical_source(args.equality_producer_source)
    pure = canonical_source(args.pure_producer_source)
    replacements = {"qualification_root": root.as_posix(), "repository_root": str(ROOT), "python": sys.executable}
    config = expand(bindings, replacements)
    contracts = expand(load(HERE / "finite-equality-contracts-template.json"), replacements)
    config["qualification_root"] = root.as_posix()
    config["equality_producer_path"] = equality.relative_to(ROOT).as_posix()
    config["equality_guard_mutant_source"] = (equality.parent/"fixture_only_analysis_guard_mutant.py").relative_to(ROOT).as_posix()
    config["equality_case_contracts"] = contracts["cases"]
    config["equality_processes"], config["equality_child_processes"] = {}, {}
    for name, source, env in (("original-main", "test_candidate_019.py", "EQUALITY019_RUN"),
                              ("original-additional", "test_additional_controls_019.py", "EQUALITY019_ADD_RUN"),
                              ("private-binding", "test_revision002_private_and_binding.py", "EQUALITY019_PRIVATE_RUN")):
        child = equality.parent / source
        canonical_source(child.relative_to(ROOT).as_posix())
        directory = root.as_posix() + "/equality/" + name
        argv = [sys.executable, str(child)]
        config["equality_processes"][name] = {"argv": argv, "output_directory": directory}
        config["equality_child_processes"][name] = {"argv": argv, "accepted_exit_code": 0,
            "environment": {env: str(ROOT / directory), "PYTHONDONTWRITEBYTECODE": "1"},
            "output_directory": directory, "removed_environment_keys": ["EQUALITY019_CASES", "EQUALITY019_CONTROL"]}
    config["additional_evidence_paths"] = {"equality": root.as_posix()+"/equality/equality-result.json",
        "pure": root.as_posix()+"/carrier-pure-result.json", "carrier": root.as_posix()+"/actual-channel/capture-index.json",
        "author": root.as_posix()+"/fresh-author/author-index.json"}
    pure_contract = expand(load(args.pure_contracts), replacements)
    if args.pure_contracts.absolute() != pure.parent/"WITNESS_SCHEMA.json":
        raise ValueError("Pure contracts must be the exact producer-local registered schema")
    config["pure_witness_contracts"] = pure_contract.get("pure_witness_contracts", pure_contract)
    pure_ids = ([case["case_id"] for case in pure_contract["case_contracts"]] if "case_contracts" in pure_contract
                else list(config["pure_witness_contracts"]["cases"]))
    if set(pure_ids) != set(config["exact_pure_test_ids"]) or len(config["exact_pure_test_ids"]) != 30:
        raise ValueError("Exact30 pure semantic contract mismatch")
    config["pure_evidence"] = {"producer_path": pure.relative_to(ROOT).as_posix(),
        "schema_path": args.pure_contracts.absolute().relative_to(ROOT).as_posix(),
        "semantic_witnesses_path":root.as_posix()+"/semantic-witnesses.json",
        "actual_process_receipt_path": root.as_posix()+"/carrier-pure-controls-actual-process-receipt.json",
        "process_contract": {"argv": [sys.executable, str(pure), "--qualification-root", str(ROOT/root)],
                             "accepted_exit_code": 0, "environment": bindings["pure_environment"]}}
    prefixes = config["fresh_evidence_prefixes"]
    if type(prefixes) is not list or root.as_posix() not in prefixes or len(prefixes) != len(set(prefixes)):
        raise ValueError("Exact explicitly registered fresh prefixes must include new qualification root")
    for prefix in prefixes:
        path = Path(prefix)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != prefix or not prefix.startswith("validation/"):
            raise ValueError("Noncanonical registered fresh prefix")
    required = set(load(HERE/"runtime-contract.json")["adapters_required_keys"]) | set(
        load(HERE/"runtime-contract-amendment-001.json")["additional_required_runtime_keys"])
    required |= set(load(HERE/"independent-reader-interface-amendment-001.json")["additional_required_keys"])
    required -= {"additional_processes", "pure_process", "pure_witness_ids"}
    missing = [key for key in sorted(required) if key not in config or config[key] is None]
    def unresolved(value):
        if value is None: return True
        if isinstance(value,str): return any("{"+name+"}" in value for name in replacements) or value.startswith("MATERIALIZE ")
        if isinstance(value,(list,dict)):
            return any(unresolved(item) for item in (value.values() if isinstance(value,dict) else value))
        return False
    if missing or any(unresolved(config[key]) for key in required):
        raise ValueError("Final adapter registration unresolved: " + ",".join(missing))
    output = {"format":"verislop.support019-resolved-adapter-configuration/1", "execution_authority":False,
              "qualification_root":root.as_posix(), "adapters":config,
              "qualification_specification_additions":{
                  "actual_equality_evidence_path":config["additional_evidence_paths"]["equality"],
                  "actual_pure_evidence_path":config["additional_evidence_paths"]["pure"],
                  "actual_channel_evidence_path":config["additional_evidence_paths"]["carrier"],
                  "actual_author_evidence_path":config["additional_evidence_paths"]["author"],
                  "fresh_evidence_prefixes":config["fresh_evidence_prefixes"]}}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(output,stream,sort_keys=True,indent=2,allow_nan=False); stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
