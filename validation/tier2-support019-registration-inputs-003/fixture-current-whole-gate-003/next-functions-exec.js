// @exec: {"max_output_tokens": 20000}
const PREFIX = load("verislop.exact-carrier-session/0.1:{\"path\":\"/home/augustus/VeriSlop_CLI/validation/tier2-support019-registration-inputs-003/fixture-current-whole-gate-003/own-unrelated-carrier.json\",\"sha256\":\"sha256:239c8ce8cdb48d7fd3cc28af2b3c0c8b498f5c4ad82f64015799da3410cb0ded\"}");
if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }
const VIEW = {"metadata_reserve_bytes": 2048, "operation": "field", "output_cap_bytes": 8192, "selector": "/system", "start_char": 0};
const cmd = PREFIX + "VIEW = json.loads(" + JSON.stringify(JSON.stringify(VIEW))
  + ")\nraise SystemExit(emit_view(REFERENCE, VIEW))\nVERISLOP_EXACT_CARRIER_VIEW\n";
text(await tools.exec_command({cmd, max_output_tokens: 16384}));
