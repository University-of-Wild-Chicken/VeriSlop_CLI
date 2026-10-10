// @exec: {"max_output_tokens": 20000}
const OWN_REFERENCE = {"path": "/synthetic/own.json", "request_sha256": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "sha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"};
const PENDING_KEY = "verislop.own-view-pending/0.1:{\"path\":\"/synthetic/own.json\",\"sha256\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}";
const PREFIX = load("verislop.exact-carrier-session/0.1:{\"path\":\"/synthetic/own.json\",\"sha256\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\"}");
if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }
const VIEW = {"metadata_reserve_bytes": 2048, "operation": "field", "output_cap_bytes": 8192, "selector": "/system", "start_char": 0};
const cmd = PREFIX + "VIEW = json.loads(" + JSON.stringify(JSON.stringify(VIEW))
  + ")\nraise SystemExit(emit_view(REFERENCE, VIEW))\nVERISLOP_EXACT_CARRIER_VIEW\n";
const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});
text(ACTUAL_RESULT);
store(PENDING_KEY, {reference: OWN_REFERENCE, view: VIEW, result: ACTUAL_RESULT});
