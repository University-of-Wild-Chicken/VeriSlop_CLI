// @exec: {"max_output_tokens": 20000}
const PREFIX = load("verislop.exact-carrier-session/0.1:{\"path\":\"/unrelated/support019/own-carrier.json\",\"sha256\":\"sha256:1111111111111111111111111111111111111111111111111111111111111111\"}");
if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }
const VIEW = {"metadata_reserve_bytes": 2048, "operation": "field", "output_cap_bytes": 8192, "selector": "/system", "start_char": 0};
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
text(await tools.exec_command({cmd, max_output_tokens: 16384}));
