// @exec: {"max_output_tokens": 20000}
const REQUEST = {"code":{"node_path":"/usr/bin/node","python_path":"/usr/bin/python3.12","reader_path":"/home/augustus/VeriSlop_CLI/synthetic_dataset/tools/carrier_runtime020/reader.py","reader_sha256":"sha256:c917f273389e2b9ee56be04b5c6e56ed889c49a29e4262dbf1dfb68294d67e5f","runtime_path":"/home/augustus/VeriSlop_CLI/synthetic_dataset/tools/carrier_runtime020/carrier_runtime.js","runtime_sha256":"sha256:49437d060a0da10c84bd6c4483f9c55b0d57cf8512840a906b6ab98ae6b4feb7","session_directory":"/home/augustus/VeriSlop_CLI/validation/runtime020-actual-tool-smoke-001/runtime020-own-sessions"},"format":"verislop.carrier-runtime-request/0.1","operation":"view","reference":{"path":"/home/augustus/VeriSlop_CLI/validation/runtime020-actual-tool-smoke-001/own-public-'unicode🧪'.json","request_sha256":"sha256:eb593368e4cded797cc46e9be6648b6f651f752ffd75efbde408ffd169ef4b11","sha256":"sha256:5e584eb4d17f983ededf91a1f817e0b6ac3bc5946d5c151e6727811485939a95"},"session_path":"/home/augustus/VeriSlop_CLI/validation/runtime020-actual-tool-smoke-001/runtime020-own-sessions/verislop-runtime020-b9f081d7385e6b1d7e42c33c30e66f9f2ce662add6aeb6bb191515fc0b6fb648.json"};
const PENDING_KEY = "verislop.runtime020-own-pending/0.1:{\"path\":\"/home/augustus/VeriSlop_CLI/validation/runtime020-actual-tool-smoke-001/own-public-'unicode🧪'.json\",\"request_sha256\":\"sha256:eb593368e4cded797cc46e9be6648b6f651f752ffd75efbde408ffd169ef4b11\",\"sha256\":\"sha256:5e584eb4d17f983ededf91a1f817e0b6ac3bc5946d5c151e6727811485939a95\"}";
const VIEW = {"metadata_reserve_bytes":2048,"operation":"field","output_cap_bytes":8192,"selector":"/user","start_char":0};
REQUEST.view = VIEW;
function wire(value) {
  if (Array.isArray(value)) return "[" + value.map(wire).join(",") + "]";
  if (value !== null && typeof value === "object") return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + wire(value[key])).join(",") + "}";
  return JSON.stringify(value);
}
function posixQuote(value) { return "'" + value.replaceAll("'", "'\"'\"'") + "'"; }
const cmd = "/usr/bin/python3.12 -I -B -c 'import hashlib,json,os,sys\nr=json.loads(sys.argv[1]);c=r[\"code\"]\nassert c[\"node_path\"]==\"/usr/bin/node\" and c[\"python_path\"]==\"/usr/bin/python3.12\"\nfor k in (\"runtime\",\"reader\"):\n p=c[k+\"_path\"];assert os.path.isabs(p) and os.path.realpath(p)==p\n with open(p,\"rb\") as f: actual=\"sha256:\"+hashlib.sha256(f.read()).hexdigest()\n if actual!=c[k+\"_sha256\"]:raise SystemExit(\"REGISTERED_CODE_HASH_MISMATCH\")\nos.execv(c[\"node_path\"],[c[\"node_path\"],c[\"runtime_path\"],sys.argv[1]])\n' " + posixQuote(wire(REQUEST));
const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});
store(PENDING_KEY, {reference: REQUEST.reference, view: VIEW, result: ACTUAL_RESULT});
text(ACTUAL_RESULT);

store("runtime020_actual_tool_smoke_001:user", {request: REQUEST, command: cmd, result: ACTUAL_RESULT});
