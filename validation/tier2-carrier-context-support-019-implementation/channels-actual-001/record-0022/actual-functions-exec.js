// @exec: {"max_output_tokens": 20000}
const PREFIX = load("verislop.exact-carrier-session/0.1:{\"path\":\"/home/augustus/VeriSlop_CLI/validation/tier2-carrier-context-support-019-implementation/fixture-actual-001/own-unrelated-carrier.json\",\"sha256\":\"sha256:c25cd8a2a7cfef4f026367254b009a82a1a973c6433bb690313e7f026a6c35e5\"}");
if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }
const VIEW = {"metadata_reserve_bytes":2048,"operation":"field","output_cap_bytes":8192,"selector":"/user","start_char":39923};
if (VIEW === null || typeof VIEW !== "object" || Array.isArray(VIEW)
    || (VIEW.operation !== "inventory" && VIEW.operation !== "field")) {
  throw new Error("INVALID_CLOSED_VIEW");
}
const viewFields = Object.keys(VIEW).sort().join(",");
if ((VIEW.operation === "inventory" && viewFields !== "metadata_reserve_bytes,operation,output_cap_bytes")
    || (VIEW.operation === "field" && viewFields !== "metadata_reserve_bytes,operation,output_cap_bytes,selector,start_char")) {
  throw new Error("INVALID_CLOSED_VIEW_FIELDS");
}
if (!Number.isSafeInteger(VIEW.output_cap_bytes) || VIEW.output_cap_bytes < 256 || VIEW.output_cap_bytes > 8192
    || !Number.isSafeInteger(VIEW.metadata_reserve_bytes) || VIEW.metadata_reserve_bytes < 128
    || VIEW.metadata_reserve_bytes >= VIEW.output_cap_bytes) {
  throw new Error("INVALID_CLOSED_VIEW_BOUNDS");
}
if (VIEW.operation === "field" && ((VIEW.selector !== "/system" && VIEW.selector !== "/user")
    || !Number.isSafeInteger(VIEW.start_char) || VIEW.start_char < 0)) {
  throw new Error("INVALID_CLOSED_VIEW_RANGE");
}
const cmd = PREFIX + "VIEW = json.loads(" + JSON.stringify(JSON.stringify(VIEW))
  + ")\nraise SystemExit(emit_view(REFERENCE, VIEW))\nVERISLOP_EXACT_CARRIER_VIEW\n";
const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});
text(ACTUAL_RESULT);
store("verislop.cc019.collector.pending", {nested_result: ACTUAL_RESULT, cmd, view: VIEW, prefix: PREFIX});
