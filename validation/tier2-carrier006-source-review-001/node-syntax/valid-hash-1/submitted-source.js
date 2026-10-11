// @exec: {"max_output_tokens": 20000}
const OWN_REFERENCE = {"path": "/unrelated/reviewer006/empty-token-tab\tcomma,end\ud83d\ude42", "request_sha256": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "sha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"};
const CHECKPOINT_KEY = "verislop.own-view-checkpoint/0.1:{\"path\":\"/unrelated/reviewer006/empty-token-tab\\tcomma,end\\ud83d\\ude42\",\"sha256\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}";
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
// Fixed SHA-256 over strict Unicode scalar UTF-8; own memory only, zero tools.
function ownViewSha256(value) {
  const size = checkpointText(value);
  checkpointNeed(Number.isSafeInteger(size.bytes), "OWN_HASH_LENGTH_NOT_SAFE");
  const constants = [
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
  ];
  const digest = new Uint32Array([0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
    0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19]);
  const block = new Uint8Array(64), words = new Uint32Array(64);
  let used = 0;
  const rotate = (word, bits) => (word >>> bits) | (word << (32 - bits));
  function compress() {
    for (let i = 0; i < 16; i += 1) {
      const at = i * 4;
      words[i] = ((block[at] << 24) | (block[at+1] << 16) | (block[at+2] << 8) | block[at+3]) >>> 0;
    }
    for (let i = 16; i < 64; i += 1) {
      const x = words[i-15], y = words[i-2];
      const sigma0 = rotate(x,7) ^ rotate(x,18) ^ (x >>> 3);
      const sigma1 = rotate(y,17) ^ rotate(y,19) ^ (y >>> 10);
      words[i] = (words[i-16] + (sigma0 >>> 0) + words[i-7] + (sigma1 >>> 0)) >>> 0;
    }
    let [a,b,c,d,e,f,g,h] = digest;
    for (let i = 0; i < 64; i += 1) {
      const sigma1 = rotate(e,6) ^ rotate(e,11) ^ rotate(e,25);
      const choose = (e & f) ^ (~e & g);
      const first = (h + (sigma1 >>> 0) + (choose >>> 0) + constants[i] + words[i]) >>> 0;
      const sigma0 = rotate(a,2) ^ rotate(a,13) ^ rotate(a,22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const second = ((sigma0 >>> 0) + (majority >>> 0)) >>> 0;
      h = g; g = f; f = e; e = (d + first) >>> 0;
      d = c; c = b; b = a; a = (first + second) >>> 0;
    }
    for (const [i, word] of [a,b,c,d,e,f,g,h].entries()) digest[i] = (digest[i] + word) >>> 0;
  }
  function append(byte) {
    block[used++] = byte;
    if (used === 64) { compress(); used = 0; }
  }
  for (const char of value) {
    const point = char.codePointAt(0);
    if (point < 0x80) append(point);
    else if (point < 0x800) { append(0xc0 | (point >>> 6)); append(0x80 | (point & 0x3f)); }
    else if (point < 0x10000) {
      append(0xe0 | (point >>> 12)); append(0x80 | ((point >>> 6) & 0x3f)); append(0x80 | (point & 0x3f));
    } else {
      append(0xf0 | (point >>> 18)); append(0x80 | ((point >>> 12) & 0x3f));
      append(0x80 | ((point >>> 6) & 0x3f)); append(0x80 | (point & 0x3f));
    }
  }
  const bits = BigInt(size.bytes) * 8n;
  checkpointNeed(bits < (1n << 64n), "OWN_HASH_LENGTH_OUTSIDE_SHA256_DOMAIN");
  append(0x80);
  while (used !== 56) append(0);
  for (let shift = 56n; shift >= 0n; shift -= 8n) append(Number((bits >> shift) & 0xffn));
  return Array.from(digest, word => word.toString(16).padStart(8,"0")).join("");
}
const OWN_STATE = load(CHECKPOINT_KEY);
const OWN_FIELDS = checkpointReconstruct(OWN_STATE, OWN_REFERENCE).fields;
const FIELD_ROOTS = {}, FIELD_CHARS = {}, FIELD_BYTES = {};
for (const selector of ["/system", "/user"]) {
  const field = OWN_FIELDS[selector];
  checkpointNeed(field.field_eof && field.next_char === field.field_chars
    && field.next_utf8_byte === field.field_utf8_bytes, "OWN_FIELDS_NOT_COMPLETE");
  FIELD_ROOTS[selector] = "sha256:" + ownViewSha256(field.content);
  FIELD_CHARS[selector] = field.field_chars; FIELD_BYTES[selector] = field.field_utf8_bytes;
}
const OWN_HASH_RESULT = {format: "verislop.own-view-field-hashes/0.1", field_roots: FIELD_ROOTS,
  field_chars: FIELD_CHARS, field_utf8_bytes: FIELD_BYTES, field_eof: {"/system": true, "/user": true},
  availability_only: true, semantic_consumption: "UNATTESTED", semantic_acceptance_authority: false};
store("verislop.own-view-hash-result/0.1:{\"path\":\"/unrelated/reviewer006/empty-token-tab\\tcomma,end\\ud83d\\ude42\",\"sha256\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}", OWN_HASH_RESULT);
text(OWN_HASH_RESULT);
