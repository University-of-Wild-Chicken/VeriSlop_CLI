// @exec: {"max_output_tokens": 20000}
const PREFIX = load("verislop.exact-carrier-session/0.1:{\"path\":\"/home/augustus/VeriSlop_CLI/validation/tier2-carrier-context-support-019-implementation-002/fixture-current-whole-gate-001/own-unrelated-empty-carrier.json\",\"sha256\":\"sha256:af4edb1e6352124fa34732e86bb003bbccad9dcc0329bf16fe47676905ae3bda\"}");
if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }
const VIEW = {"metadata_reserve_bytes": 2048, "operation": "field", "output_cap_bytes": 8192, "selector": "/system", "start_char": 0};
const cmd = PREFIX + "VIEW = json.loads(" + JSON.stringify(JSON.stringify(VIEW))
  + ")\nraise SystemExit(emit_view(REFERENCE, VIEW))\nVERISLOP_EXACT_CARRIER_VIEW\n";
text(await tools.exec_command({cmd, max_output_tokens: 16384}));
