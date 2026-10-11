// @exec: {"max_output_tokens": 20000}
const OWN_REFERENCE = {"path": "/home/augustus/VeriSlop_CLI/validation/tier2-support019-real-author-protocol-probe-001/own-carrier.json", "request_sha256": "sha256:2ca53aa3c4513898541818aaf88d8f80e013eed0c0c074d0a2caa64376242ed5", "sha256": "sha256:bdd8605a3ccadc005264a1e820c9abfdc9f2cbdb2d4756d18f7c44668c0e2325"};
const PENDING_KEY = "verislop.own-view-pending/0.1:{\"path\":\"/home/augustus/VeriSlop_CLI/validation/tier2-support019-real-author-protocol-probe-001/own-carrier.json\",\"sha256\":\"sha256:bdd8605a3ccadc005264a1e820c9abfdc9f2cbdb2d4756d18f7c44668c0e2325\"}";
const PREFIX = load("verislop.exact-carrier-session/0.1:{\"path\":\"/home/augustus/VeriSlop_CLI/validation/tier2-support019-real-author-protocol-probe-001/own-carrier.json\",\"sha256\":\"sha256:bdd8605a3ccadc005264a1e820c9abfdc9f2cbdb2d4756d18f7c44668c0e2325\"}");
if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }
const VIEW = {"metadata_reserve_bytes": 2048, "operation": "field", "output_cap_bytes": 8192, "selector": "/system", "start_char": 0};
const cmd = PREFIX + "VIEW = json.loads(" + JSON.stringify(JSON.stringify(VIEW))
  + ")\nraise SystemExit(emit_view(REFERENCE, VIEW))\nVERISLOP_EXACT_CARRIER_VIEW\n";
const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});
text(ACTUAL_RESULT);
store(PENDING_KEY, {reference: OWN_REFERENCE, view: VIEW, result: ACTUAL_RESULT});
