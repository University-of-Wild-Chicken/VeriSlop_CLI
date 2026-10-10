// @exec: {"max_output_tokens": 256}
const PREFIX = load("verislop.exact-carrier-session/0.1:{\"path\":\"/unrelated/quote' double\\\" backslash\\\\ \\u00e9\\ud83d\\ude42\\u2028\\ntext(await tools.exec_command({cmd, max_output_tokens: 16384}));\\nconst ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});\\r\\n/own-carrier.json\",\"sha256\":\"sha256:1111111111111111111111111111111111111111111111111111111111111111\"}");
if (typeof PREFIX !== "string") { throw new Error("OWN_CARRIER_PREFIX_ABSENT"); }
const VIEW = {"metadata_reserve_bytes": 2048, "operation": "field", "output_cap_bytes": 8192, "selector": "/user", "start_char": 0};
const cmd = PREFIX + "VIEW = json.loads(" + JSON.stringify(JSON.stringify(VIEW))
  + ")\nraise SystemExit(emit_view(REFERENCE, VIEW))\nVERISLOP_EXACT_CARRIER_VIEW\n";
const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});
text(ACTUAL_RESULT);
store("verislop.observable-carrier-collector-result/0.1:{\"case_id\":\"AC002-003\",\"path\":\"/unrelated/quote' double\\\" backslash\\\\ \\u00e9\\ud83d\\ude42\\u2028\\ntext(await tools.exec_command({cmd, max_output_tokens: 16384}));\\nconst ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});\\r\\n/own-carrier.json\",\"sha256\":\"sha256:1111111111111111111111111111111111111111111111111111111111111111\"}", {result: ACTUAL_RESULT, view: VIEW});
