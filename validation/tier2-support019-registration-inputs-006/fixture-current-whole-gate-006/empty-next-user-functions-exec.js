// @exec: {"max_output_tokens": 20000}
const PREFIX = load("verislop.exact-carrier-session/0.1:{\"path\":\"/home/augustus/VeriSlop_CLI/validation/tier2-support019-registration-inputs-006/fixture-current-whole-gate-006/own-unrelated-empty-carrier.json\",\"sha256\":\"sha256:c72fd48e8130f81de69e788b5801b10f8c836363ab5b24791f16ff886a7a86b6\"}");
if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }
const VIEW = {"metadata_reserve_bytes": 2048, "operation": "field", "output_cap_bytes": 8192, "selector": "/user", "start_char": 0};
const cmd = PREFIX + "VIEW = json.loads(" + JSON.stringify(JSON.stringify(VIEW))
  + ")\nraise SystemExit(emit_view(REFERENCE, VIEW))\nVERISLOP_EXACT_CARRIER_VIEW\n";
text(await tools.exec_command({cmd, max_output_tokens: 16384}));
