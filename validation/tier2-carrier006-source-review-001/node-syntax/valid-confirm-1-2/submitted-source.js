// @exec: {"max_output_tokens": 20000}
const OWN_REFERENCE = {"path": "/unrelated/reviewer006/empty-token-tab\tcomma,end\ud83d\ude42", "request_sha256": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "sha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"};
const CHECKPOINT_KEY = "verislop.own-view-checkpoint/0.1:{\"path\":\"/unrelated/reviewer006/empty-token-tab\\tcomma,end\\ud83d\\ude42\",\"sha256\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}";
const PENDING_KEY = "verislop.own-view-pending/0.1:{\"path\":\"/unrelated/reviewer006/empty-token-tab\\tcomma,end\\ud83d\\ude42\",\"sha256\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}";
const CONFIRM = {"chunk_id": "reviewer006\\slash", "outer_output_intact": true};
// Fixed pure own-session validator. No tools, file/network reads or cursor selection.
function checkpointNeed(condition, code) {
  if (!condition) throw new Error(code);
}
function checkpointKeys(value, keys, code) {
  checkpointNeed(value !== null && typeof value === "object" && !Array.isArray(value), code);
  const actual = Object.keys(value).sort(), expected = keys.slice().sort();
  checkpointNeed(actual.length === expected.length && actual.every((key, index) => key === expected[index]), code);
}
function checkpointWire(value) {
  if (Array.isArray(value)) return "[" + value.map(checkpointWire).join(",") + "]";
  if (value !== null && typeof value === "object") {
    return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + checkpointWire(value[key])).join(",") + "}";
  }
  checkpointNeed(value === null || typeof value === "string" || typeof value === "boolean"
    || (typeof value === "number" && Number.isFinite(value)), "INVALID_OWN_TRANSPORT_VALUE");
  return JSON.stringify(value);
}
function checkpointText(value) {
  checkpointNeed(typeof value === "string", "NONSTRING_OWN_FIELD");
  let chars = 0, bytes = 0;
  for (const char of value) {
    const point = char.codePointAt(0);
    checkpointNeed(!(point >= 0xd800 && point <= 0xdfff), "NONSCALAR_OWN_FIELD");
    chars += 1;
    bytes += point < 0x80 ? 1 : point < 0x800 ? 2 : point < 0x10000 ? 3 : 4;
  }
  return {chars, bytes};
}
function checkpointInteger(value, code) {
  checkpointNeed(Number.isSafeInteger(value) && value >= 0, code);
}
function checkpointReference(reference) {
  checkpointKeys(reference, ["path", "sha256", "request_sha256"], "INVALID_OWN_REFERENCE");
  checkpointNeed(typeof reference.path === "string" && reference.path.startsWith("/")
    && /^sha256:[0-9a-f]{64}$/.test(reference.sha256)
    && /^sha256:[0-9a-f]{64}$/.test(reference.request_sha256), "INVALID_OWN_REFERENCE");
}
function checkpointAdvance(before, pending, confirmation, ownReference) {
  checkpointReference(ownReference);
  checkpointKeys(pending, ["reference", "view", "result"], "INVALID_OWN_PENDING");
  checkpointNeed(checkpointWire(pending.reference) === checkpointWire(ownReference), "UNMATCHED_OWN_PENDING");
  checkpointKeys(confirmation, ["chunk_id", "outer_output_intact"], "INVALID_OUTER_CONFIRMATION");
  checkpointNeed(typeof confirmation.chunk_id === "string" && confirmation.chunk_id.length > 0
    && confirmation.outer_output_intact === true, "OUTER_OUTPUT_NOT_CONFIRMED_INTACT");
  const result = pending.result, view = pending.view;
  checkpointNeed(result !== null && typeof result === "object" && !Array.isArray(result)
    && typeof result.chunk_id === "string" && result.chunk_id === confirmation.chunk_id
    && Number.isInteger(result.exit_code) && result.exit_code === 0
    && !("session_id" in result) && typeof result.output === "string", "ACTUAL_RESULT_NOT_COMPLETE_OR_UNMATCHED");
  checkpointWire(result);
  if ("original_token_count" in result) {
    checkpointInteger(result.original_token_count, "INVALID_ACTUAL_TOKEN_COUNT");
    checkpointNeed(result.original_token_count <= 16384, "NESTED_OUTPUT_TRUNCATION");
  }
  const viewFields = view && view.operation === "inventory"
    ? ["operation", "output_cap_bytes", "metadata_reserve_bytes"]
    : ["operation", "output_cap_bytes", "metadata_reserve_bytes", "selector", "start_char"];
  checkpointKeys(view, viewFields, "INVALID_CLOSED_OWN_VIEW");
  checkpointNeed(Number.isSafeInteger(view.output_cap_bytes) && view.output_cap_bytes >= 256 && view.output_cap_bytes <= 8192
    && Number.isSafeInteger(view.metadata_reserve_bytes) && view.metadata_reserve_bytes >= 128
    && view.metadata_reserve_bytes < view.output_cap_bytes, "INVALID_CLOSED_OWN_VIEW_BOUNDS");
  let doc;
  try { doc = JSON.parse(result.output); } catch (_) { throw new Error("MALFORMED_OR_TRUNCATED_ACTUAL_OUTPUT"); }
  checkpointNeed(checkpointWire(doc) + "\n" === result.output, "NONCANONICAL_OR_DUPLICATE_ACTUAL_OUTPUT");
  const baseKeys = ["format", "status", "carrier_path", "carrier_raw_bytes", "carrier_sha256", "request_sha256", "request_id",
    "char_unit", "byte_unit", "output_cap_bytes", "metadata_reserve_bytes", "operation"];
  const extraKeys = view.operation === "inventory" ? ["fields", "navigation"]
    : ["selector", "field_chars", "field_utf8_bytes", "start_char", "end_char", "start_utf8_byte", "end_utf8_byte",
      "content_chars", "content_utf8_bytes", "content", "next_char", "field_eof"];
  checkpointKeys(doc, baseKeys.concat(extraKeys), "INVALID_ACTUAL_VIEW_FIELDS");
  checkpointNeed(doc.format === "verislop.exact-carrier-view/0.1" && doc.status === "ok"
    && doc.carrier_path === ownReference.path && doc.carrier_sha256 === ownReference.sha256
    && doc.request_sha256 === ownReference.request_sha256 && typeof doc.request_id === "string"
    && doc.char_unit === "decoded_unicode_code_points" && doc.byte_unit === "decoded_field_utf8"
    && doc.operation === view.operation && doc.output_cap_bytes === view.output_cap_bytes
    && doc.metadata_reserve_bytes === view.metadata_reserve_bytes, "ACTUAL_VIEW_IDENTITY_MISMATCH");
  checkpointInteger(doc.carrier_raw_bytes, "INVALID_CARRIER_TOTAL");
  checkpointNeed(checkpointText(result.output).bytes <= view.output_cap_bytes, "ACTUAL_OUTPUT_OVER_CAP");
  if (view.operation === "inventory") {
    checkpointNeed(doc.navigation === "complete_linear_fields_only" && Array.isArray(doc.fields) && doc.fields.length === 2
      && checkpointText(result.output).bytes <= view.metadata_reserve_bytes, "INVALID_ACTUAL_INVENTORY");
    const fields = {};
    for (let index = 0; index < 2; index += 1) {
      const item = doc.fields[index], selector = index === 0 ? "/system" : "/user";
      checkpointKeys(item, ["selector", "field_chars", "field_utf8_bytes", "start_char", "end_char"], "INVALID_INVENTORY_FIELD");
      checkpointInteger(item.field_chars, "INVALID_FIELD_TOTAL");
      checkpointInteger(item.field_utf8_bytes, "INVALID_FIELD_TOTAL");
      checkpointNeed(item.selector === selector && item.start_char === 0 && item.end_char === item.field_chars,
        "INVALID_INVENTORY_FIELD_RANGE");
      fields[selector] = {content: "", next_char: 0, next_utf8_byte: 0, field_chars: item.field_chars,
        field_utf8_bytes: item.field_utf8_bytes, field_eof: false};
    }
    const inventory = {request_id: doc.request_id, carrier_raw_bytes: doc.carrier_raw_bytes, fields: doc.fields};
    if (before !== null) {
      checkpointNeed(checkpointWire(before.inventory) === checkpointWire(inventory), "INVENTORY_REPLAY_MISMATCH");
      return before;
    }
    return {inventory, fields};
  }
  checkpointNeed(view.operation === "field" && (view.selector === "/system" || view.selector === "/user"), "INVALID_OWN_SELECTOR");
  checkpointInteger(view.start_char, "INVALID_CLOSED_OWN_CURSOR");
  checkpointNeed(before !== null, "OWN_INVENTORY_NOT_CONFIRMED");
  checkpointNeed(doc.request_id === before.inventory.request_id && doc.carrier_raw_bytes === before.inventory.carrier_raw_bytes,
    "ACTUAL_REQUEST_IDENTITY_CHANGED");
  checkpointNeed(view.selector !== "/user" || before.fields["/system"].field_eof, "SYSTEM_EOF_REQUIRED_BEFORE_USER");
  const field = before.fields[view.selector];
  for (const name of ["field_chars", "field_utf8_bytes", "start_char", "end_char", "start_utf8_byte", "end_utf8_byte",
    "content_chars", "content_utf8_bytes", "next_char"]) checkpointInteger(doc[name], "INVALID_ACTUAL_CURSOR_OR_TOTAL");
  const size = checkpointText(doc.content);
  checkpointNeed(doc.selector === view.selector && doc.start_char === view.start_char
    && doc.field_chars === field.field_chars && doc.field_utf8_bytes === field.field_utf8_bytes
    && doc.start_char <= doc.end_char && doc.end_char <= field.field_chars && doc.next_char === doc.end_char
    && size.chars === doc.content_chars && size.chars === doc.end_char - doc.start_char
    && size.bytes === doc.content_utf8_bytes && doc.end_utf8_byte === doc.start_utf8_byte + size.bytes
    && doc.end_utf8_byte <= field.field_utf8_bytes && typeof doc.field_eof === "boolean"
    && doc.field_eof === (doc.end_char === field.field_chars), "ACTUAL_CURSOR_LENGTH_OR_EOF_MISMATCH");
  checkpointNeed(checkpointText(checkpointWire(doc.content)).bytes <= view.output_cap_bytes - view.metadata_reserve_bytes
    && checkpointText(result.output).bytes - checkpointText(checkpointWire(doc.content)).bytes + 2 <= view.metadata_reserve_bytes,
    "ACTUAL_CONTENT_OR_METADATA_BOUNDS_MISMATCH");
  checkpointNeed(doc.end_char > doc.start_char || doc.field_eof, "NO_CONTENT_ADVANCEMENT");
  if (doc.start_char < field.next_char) {
    const accepted = Array.from(field.content);
    checkpointNeed(doc.end_char <= field.next_char && accepted.slice(doc.start_char, doc.end_char).join("") === doc.content
      && checkpointText(accepted.slice(0, doc.start_char).join("")).bytes === doc.start_utf8_byte, "REPLAY_OR_OVERLAP_MISMATCH");
    return before;
  }
  checkpointNeed(doc.start_char === field.next_char && doc.start_utf8_byte === field.next_utf8_byte, "OWN_CURSOR_GAP_OR_BYTE_MISMATCH");
  const next = {inventory: before.inventory, fields: {...before.fields}};
  next.fields[view.selector] = {...field, content: field.content + doc.content, next_char: doc.next_char,
    next_utf8_byte: doc.end_utf8_byte, field_eof: doc.field_eof};
  if (doc.field_eof) checkpointNeed(doc.end_utf8_byte === field.field_utf8_bytes, "EOF_BYTE_TOTAL_MISMATCH");
  return next;
}
function checkpointReconstruct(state, ownReference) {
  checkpointKeys(state, ["format", "reference", "inventory", "fields", "observations"], "INVALID_OWN_CHECKPOINT");
  checkpointNeed(state.format === "verislop.own-view-availability-checkpoint/0.1"
    && checkpointWire(state.reference) === checkpointWire(ownReference)
    && Array.isArray(state.observations) && state.observations.length > 0, "UNMATCHED_OWN_CHECKPOINT");
  let derived = null;
  for (const observation of state.observations) {
    checkpointKeys(observation, ["pending", "confirmation"], "INVALID_OWN_OBSERVATION");
    derived = checkpointAdvance(derived, observation.pending, observation.confirmation, ownReference);
  }
  checkpointNeed(checkpointWire(derived.inventory) === checkpointWire(state.inventory)
    && checkpointWire(derived.fields) === checkpointWire(state.fields), "OWN_CHECKPOINT_REPLAY_MISMATCH");
  return derived;
}
function checkpointConfirm(state, pending, confirmation, ownReference) {
  const before = state === undefined ? null : checkpointReconstruct(state, ownReference);
  const next = checkpointAdvance(before, pending, confirmation, ownReference);
  const observations = state === undefined ? [] : state.observations;
  return {format: "verislop.own-view-availability-checkpoint/0.1", reference: ownReference,
    inventory: next.inventory, fields: next.fields, observations: observations.concat([{pending, confirmation}])};
}
function checkpointSummary(state) {
  const fields = {};
  for (const selector of ["/system", "/user"]) {
    const field = state.fields[selector];
    fields[selector] = {next_char: field.next_char, next_utf8_byte: field.next_utf8_byte,
      field_chars: field.field_chars, field_utf8_bytes: field.field_utf8_bytes, field_eof: field.field_eof};
  }
  return {format: "verislop.own-view-availability-summary/0.1", availability_only: true,
    semantic_consumption: "UNATTESTED", semantic_acceptance_authority: false, fields};
}
const NEXT_CHECKPOINT = checkpointConfirm(load(CHECKPOINT_KEY), load(PENDING_KEY), CONFIRM, OWN_REFERENCE);
store(CHECKPOINT_KEY, NEXT_CHECKPOINT);
text(checkpointSummary(NEXT_CHECKPOINT));
