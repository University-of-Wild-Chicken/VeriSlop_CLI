"""Prepare only the specified source candidate; never run a model or VIEW."""
import ast
import copy
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[1]
OLD = ROOT / "validation/tier2-support019-author-diagnostic-implementation-005"
HELPER_PATH = ROOT / "validation/tier2-support-019-qualification-adapters-006/author_protocol_reconstruction.py"
RECOVERY = """\nCANONICAL FIXED-TEMPLATE RESTORATION:\nA syntax exception from your own copied FIRST/NEXT/CONFIRM/HASH program does not alone show a defect in the fixed source. Criticize the exact program you actually attempted against the corresponding canonical template supplied in this message. If transcription changed any fixed byte, restore the exact canonical template; do not patch, simplify or rewrite its validator or other fixed code. Restoration to the supplied original is expressly permitted and is distinct from editing the fixed protocol. Retain only the already allowed closed VIEW/CONFIRM substitutions. Reattempt within this same actor against the same own pending observation and unchanged explicit selector/cursor; a parse failure must not advance accepted state. Preserve the unchanged operations, complete forwarding, bounds, checks, EOF/HASH prerequisites and success schema. No helper/file/network/history/other-agent access, callable storage, dynamic wrapper, automatic VIEW loop, extra actor, new retry budget or inference/retrieval/review deadline is introduced.\nKeep the exact attempted program and actual visible error in your authorized own notes when available. A failed diagnostic's existing reproduction.own_input_literal must retain the exact attempted program and necessary own input when retained, as data; provide the smallest available concrete reproducer and its exact observed error. If complete program or necessary input was not retained, explicitly state that unavailability and keep reproduction.availability UNAVAILABLE rather than claiming executable sufficiency. Do not label a copied program's syntax failure FIXED_SOURCE_BLOCKED without an exact canonical-template attempt and its concrete observed failure. Unknown causes remain unknown; even a reproduced generic source error does not establish a historical or universal cause. Never infer success, inspection or acceptance from syntax repair. Failure stays UNATTESTED and unsuccessful; the exact SYSTEM-defined response protocol remains authoritative.\n"""


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def ref(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(raw), "byte_count": len(raw)}


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write("\n")


def main():
    assert (HERE / "SPECIFICATION_BEFORE_SOURCE.md").is_file()
    assert (HERE / "CONTROL_SPECIFICATION_BEFORE_TEST_SOURCE.md").is_file()
    raw = (OLD / "bootstrap_tier2_carrier_view.py").read_bytes()
    assert sha(raw) == "sha256:a56590eb051ebac28312031b157195caab0d747aa20ebc4557d70ff5b1b2921f"
    text = raw.decode("utf-8", "strict")
    tree = ast.parse(text)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "agent_message")
    assert len(function.body) == 7
    node = function.body[4].value
    old_instruction = ast.literal_eval(node)
    lines = text.splitlines(keepends=True)
    start = sum(len(line.encode("utf-8")) for line in lines[:node.lineno - 1]) + node.col_offset
    end = sum(len(line.encode("utf-8")) for line in lines[:node.end_lineno - 1]) + node.end_col_offset
    candidate = raw[:start] + repr(old_instruction + RECOVERY).encode("utf-8") + raw[end:]
    (HERE / "bootstrap_tier2_carrier_view.py").write_bytes(candidate)
    (HERE / "RECOVERY_INSTRUCTION_LITERAL.txt").write_text(RECOVERY, encoding="utf-8")
    (HERE / "diagnostic_failure_parser.py").write_bytes((OLD / "diagnostic_failure_parser.py").read_bytes())
    factory_old = (OLD / "capture-amendment-003/collector_templates.py").read_bytes()
    old_digest = hashlib.sha256(raw).hexdigest().encode()
    assert factory_old.count(old_digest) == 1
    factory = factory_old.replace(old_digest, hashlib.sha256(candidate).hexdigest().encode(), 1)
    (HERE / "capture-amendment-003").mkdir()
    (HERE / "capture-amendment-003/collector_templates.py").write_bytes(factory)
    spec = importlib.util.spec_from_file_location("closed_source_owner006", HELPER_PATH)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    profile = json.loads((OLD / "independent-carrier-literals.json").read_bytes())
    profile.update(helper.extract_schema(candidate))
    profile["source"] = ref(HERE / "bootstrap_tier2_carrier_view.py")
    profile["author_protocol"]["reconstruction_source"] = {k: v for k, v in ref(HELPER_PATH).items() if k != "byte_count"}
    helper.validate_literals(candidate, profile)
    write(HERE / "independent-carrier-literals.json", profile)
    preimages = HERE / "preimages"
    preimages.mkdir()
    for name in ("bootstrap_tier2_carrier_view.py", "diagnostic_failure_parser.py", "independent-carrier-literals.json"):
        (preimages / (name + ".raw")).write_bytes((OLD / name).read_bytes())
    (preimages / "collector_templates.py.raw").write_bytes(factory_old)
    restored = ast.parse(candidate.decode("utf-8"))
    restored_function = next(n for n in restored.body if isinstance(n, ast.FunctionDef) and n.name == "agent_message")
    restored_function.body[4].value = copy.deepcopy(node)
    assert ast.dump(restored, include_attributes=False) == ast.dump(tree, include_attributes=False)
    write(HERE / "SOURCE_PREPARATION.json", {
        "format": "verislop.support019-canonical-restoration-source-preparation/1",
        "status": "SOURCE_PREPARED_UNSEALED_RUNTIME_UNQUALIFIED",
        "candidate": ref(HERE / "bootstrap_tier2_carrier_view.py"),
        "factory": ref(HERE / "capture-amendment-003/collector_templates.py"),
        "parser": ref(HERE / "diagnostic_failure_parser.py"),
        "profile": ref(HERE / "independent-carrier-literals.json"),
        "source_owner_extraction": ref(HELPER_PATH),
        "only_carrier_ast_change": "agent_message.body[4].value",
        "producer_message_api_calls": 0, "model_calls": 0, "VIEW_calls": 0,
        "qualification_authority": False, "historical_actor_failure_cause": "UNAVAILABLE"
    })
    patch = "".join(difflib.unified_diff(text.splitlines(keepends=True), candidate.decode().splitlines(keepends=True),
                                       fromfile=str((OLD / "bootstrap_tier2_carrier_view.py").relative_to(ROOT)),
                                       tofile=str((HERE / "bootstrap_tier2_carrier_view.py").relative_to(ROOT))))
    (HERE / "exact-source.diff").write_text(patch, encoding="utf-8")
    print(json.dumps({"status": "SOURCE_PREPARED_UNSEALED_RUNTIME_UNQUALIFIED", "candidate": ref(HERE / "bootstrap_tier2_carrier_view.py")}, sort_keys=True))


if __name__ == "__main__":
    main()
