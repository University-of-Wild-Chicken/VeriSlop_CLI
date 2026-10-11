"""Materialize registered unrelated pure JavaScript source controls only."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[1]
HELPER_PATH = ROOT / "validation/tier2-support-019-qualification-adapters-006/author_protocol_reconstruction.py"
REFERENCE = {"path": "/generic-source-control/empty-fields.json", "sha256": "sha256:" + "3" * 64,
             "request_sha256": "sha256:" + "4" * 64}
PURE_CONTROL = r'''
const assert = require("node:assert/strict");
const reference = __REFERENCE__;
function pendingFor(view, chunk) {
  const doc = {format: "verislop.exact-carrier-view/0.1", status: "ok", carrier_path: reference.path,
    carrier_raw_bytes: 42, carrier_sha256: reference.sha256, request_sha256: reference.request_sha256,
    request_id: "generic-empty-pure-control", char_unit: "decoded_unicode_code_points", byte_unit: "decoded_field_utf8",
    output_cap_bytes: view.output_cap_bytes, metadata_reserve_bytes: view.metadata_reserve_bytes, operation: view.operation};
  if(view.operation === "inventory") {
    doc.navigation = "complete_linear_fields_only";
    doc.fields = ["/system", "/user"].map(selector => ({selector, field_chars: 0, field_utf8_bytes: 0, start_char: 0, end_char: 0}));
  } else {
    Object.assign(doc, {selector: view.selector, field_chars: 0, field_utf8_bytes: 0, start_char: 0, end_char: 0,
      start_utf8_byte: 0, end_utf8_byte: 0, content_chars: 0, content_utf8_bytes: 0, content: "", next_char: 0, field_eof: true});
  }
  return {reference, view, result: {chunk_id: chunk, exit_code: 0, wall_time_seconds: 0.001,
    original_token_count: 100, output: checkpointWire(doc) + "\n"}};
}
let state;
const inventory = pendingFor({operation: "inventory", output_cap_bytes: 8192, metadata_reserve_bytes: 2048}, "generic-inventory");
state = checkpointConfirm(state, inventory, {chunk_id: "generic-inventory", outer_output_intact: true}, reference);
for(const selector of ["/system", "/user"]) {
  const pending = pendingFor({operation: "field", selector, start_char: 0, output_cap_bytes: 8192, metadata_reserve_bytes: 2048}, "generic-" + selector);
  const before = checkpointWire(state);
  assert.throws(() => checkpointConfirm(state, pending, {chunk_id: pending.result.chunk_id, outer_output_intact: false}, reference), /OUTER_OUTPUT_NOT_CONFIRMED_INTACT/);
  assert.equal(checkpointWire(state), before, "rejected confirmation changed original checkpoint");
  state = checkpointConfirm(state, pending, {chunk_id: pending.result.chunk_id, outer_output_intact: true}, reference);
}
const summary = checkpointSummary(state);
assert.equal(summary.availability_only, true);
assert.equal(summary.semantic_consumption, "UNATTESTED");
assert.equal(summary.semantic_acceptance_authority, false);
for(const selector of ["/system", "/user"]) {
  assert.equal(summary.fields[selector].field_eof, true);
  assert.equal(summary.fields[selector].next_char, 0);
  assert.equal(summary.fields[selector].next_utf8_byte, 0);
}
console.log(JSON.stringify({scope:"UNRELATED_PURE_SOURCE_ONLY", explicit_empty_eofs:2,
  rejected_confirmation_preserved_state:true, same_pending_allowed_correction:true,
  availability_only:summary.availability_only, semantic_consumption:summary.semantic_consumption,
  semantic_acceptance_authority:summary.semantic_acceptance_authority}));
'''


def ref(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(), "byte_count": len(raw)}


def main():
    spec = importlib.util.spec_from_file_location("source_owner_controls006", HELPER_PATH)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    profile = json.loads((HERE / "independent-carrier-literals.json").read_bytes())
    helper.validate_literals((HERE / "bootstrap_tier2_carrier_view.py").read_bytes(), profile)
    confirm = helper.recipes(profile, REFERENCE)["confirm"]
    original = "semantic_acceptance_authority: false, fields};"
    malformed = 'semantic_acceptance_authority": false, fields};'
    assert confirm.count(original) == 1 and malformed not in confirm
    damaged = confirm.replace(original, malformed, 1)
    restored = damaged.replace(malformed, original, 1)
    assert restored == confirm
    minimal_good = 'const fields = {}; const summary = {semantic_consumption: "UNATTESTED", semantic_acceptance_authority: false, fields};\nconsole.log(JSON.stringify(summary));\n'
    minimal_bad = minimal_good.replace(original, malformed, 1)
    assert minimal_bad != minimal_good
    sources = HERE / "control-sources"
    sources.mkdir()
    values = {"minimal-malformed.js": minimal_bad, "minimal-canonical.js": minimal_good,
              "canonical-confirm.js": confirm, "malformed-confirm-transcription.js": damaged,
              "restored-confirm.js": restored,
              "canonical-pure-validator.js": profile["constants"]["CHECKPOINT_VALIDATOR_SOURCE"] + PURE_CONTROL.replace("__REFERENCE__", json.dumps(REFERENCE, sort_keys=True))}
    for name, value in values.items():
        with (sources / name).open("x", encoding="utf-8") as stream: stream.write(value)
    value = {"format": "verislop.support019-independent-transcription-counterexample/1",
             "scope": "UNRELATED_CONSTRUCTED_SOURCE_ONLY", "historical_attempted_program": "UNAVAILABLE",
             "historical_cause": "UNAVAILABLE", "historical_reproduction_authority": False,
             "qualification_authority": False, "only_synthetic_transcription_change": {"original": original, "malformed": malformed},
             "restoration_exact_original": restored == confirm,
             "programs": {name: ref(sources / name) for name in values}, "producer_message_api_calls": 0}
    with (HERE / "CONSTRUCTED_COUNTEREXAMPLE.json").open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2); stream.write("\n")
    print(json.dumps({"status": "PURE_CONTROL_SOURCES_PREPARED_NOT_EXECUTED", "program_count": len(values)}, sort_keys=True))


if __name__ == "__main__":
    main()
