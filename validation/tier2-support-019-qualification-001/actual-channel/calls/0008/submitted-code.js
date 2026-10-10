// @exec: {"max_output_tokens": 20000}
const PREFIX = load("verislop.exact-carrier-session/0.1:{\"path\":\"/home/augustus/VeriSlop_CLI/validation/tier2-carrier-context-support-019-implementation-002/fixture-current-whole-gate-001/own-unrelated-carrier.json\",\"sha256\":\"sha256:d4cc395ba626c77d6149952f552dc0960a9affd297d69816fce2f1a6ef5efaef\"}");
if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }
const VIEW = {"metadata_reserve_bytes": 2048, "operation": "field", "output_cap_bytes": 8192, "selector": "/user", "start_char": 13319};
const cmd = PREFIX + "VIEW = json.loads(" + JSON.stringify(JSON.stringify(VIEW))
  + ")\nraise SystemExit(emit_view(REFERENCE, VIEW))\nVERISLOP_EXACT_CARRIER_VIEW\n";
const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});
text(ACTUAL_RESULT);
store("verislop.observable-carrier-collector-result/0.1:{\"case_id\":\"AC002-001\",\"path\":\"/home/augustus/VeriSlop_CLI/validation/tier2-carrier-context-support-019-implementation-002/fixture-current-whole-gate-001/own-unrelated-carrier.json\",\"sha256\":\"sha256:d4cc395ba626c77d6149952f552dc0960a9affd297d69816fce2f1a6ef5efaef\"}", {result: ACTUAL_RESULT, view: VIEW});
