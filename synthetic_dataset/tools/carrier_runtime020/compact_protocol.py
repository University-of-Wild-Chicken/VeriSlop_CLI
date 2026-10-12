"""Versioned compact transport; legacy006 APIs remain in their exact module.

These recipes permit only the explicitly registered generic local runtime.
The runtime and acknowledgment provide availability, never semantic authority.
"""
from pathlib import Path
import ast
import hashlib
import json
import os
import shlex

API_REVISION = "support025-running-result-DEVELOPMENT_ONLY/1"
REQUEST_FORMAT = "verislop.carrier-runtime-request/0.1"
EXEC_PRAGMA = '// @exec: {"max_output_tokens": 20000}\n'
NODE_PATH = "/usr/bin/node"
PYTHON_PATH = "/usr/bin/python3.12"
LAUNCHER_SOURCE = '''import hashlib,json,os,sys
r=json.loads(sys.argv[1]);c=r["code"]
assert c["node_path"]=="/usr/bin/node" and c["python_path"]=="/usr/bin/python3.12"
for k in ("runtime","reader"):
 p=c[k+"_path"];assert os.path.isabs(p) and os.path.realpath(p)==p
 with open(p,"rb") as f: actual="sha256:"+hashlib.sha256(f.read()).hexdigest()
 if actual!=c[k+"_sha256"]:raise SystemExit("REGISTERED_CODE_HASH_MISMATCH")
os.execv(c["node_path"],[c["node_path"],c["runtime_path"],sys.argv[1]])
'''
SHELL_SAFE_JS = '''function wire(value) {
  if (Array.isArray(value)) return "[" + value.map(wire).join(",") + "]";
  if (value !== null && typeof value === "object") return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + wire(value[key])).join(",") + "}";
  return JSON.stringify(value);
}
function posixQuote(value) { return "'" + value.replaceAll("'", "'\\\"'\\\"'") + "'"; }
'''


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _reference(reference):
    if type(reference) is not dict or set(reference) != {"path", "sha256", "request_sha256"}:
        raise ValueError("INVALID_OWN_REFERENCE")
    if not all(type(value) is str for value in reference.values()):
        raise ValueError("INVALID_OWN_REFERENCE")
    reference["path"].encode("utf-8", "strict")
    if not os.path.isabs(reference["path"]) or os.path.normpath(reference["path"]) != reference["path"]:
        raise ValueError("INVALID_OWN_REFERENCE_PATH")
    for key in ("sha256", "request_sha256"):
        value = reference[key]
        if len(value) != 71 or not value.startswith("sha256:") or any(c not in "0123456789abcdef" for c in value[7:]):
            raise ValueError("INVALID_OWN_REFERENCE")
    return dict(reference)


def code_bindings(session_directory):
    """Read fixed source identities only; never open a carrier/session here."""
    if type(session_directory) is not str or not os.path.isabs(session_directory) or os.path.normpath(session_directory) != session_directory:
        raise ValueError("INVALID_OWN_SESSION_DIRECTORY")
    directory = Path(__file__).resolve().parent
    result = {"node_path": NODE_PATH, "python_path": PYTHON_PATH,
              "session_directory": session_directory}
    for kind, name in (("runtime", "carrier_runtime.js"), ("reader", "reader.py")):
        path = directory / name
        result[kind + "_path"] = str(path)
        result[kind + "_sha256"] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _code(code):
    names = {"runtime_path", "runtime_sha256", "reader_path", "reader_sha256",
             "node_path", "python_path", "session_directory"}
    if type(code) is not dict or set(code) != names or not all(type(v) is str for v in code.values()):
        raise ValueError("INVALID_RUNTIME_CODE_BINDING")
    for key in ("runtime_sha256", "reader_sha256"):
        value = code[key]
        if len(value) != 71 or not value.startswith("sha256:") or any(c not in "0123456789abcdef" for c in value[7:]):
            raise ValueError("INVALID_RUNTIME_SOURCE_IDENTITY")
    if code["node_path"] != NODE_PATH or code["python_path"] != PYTHON_PATH:
        raise ValueError("INVALID_RUNTIME_INTERPRETER_BINDING")
    for key in ("runtime_path", "reader_path", "session_directory"):
        if not os.path.isabs(code[key]) or os.path.normpath(code[key]) != code[key]:
            raise ValueError("INVALID_RUNTIME_CODE_PATH")
    return dict(code)


def session_path(reference, code):
    reference = _reference(reference); code = _code(code)
    digest = hashlib.sha256(_json(reference).encode("utf-8")).hexdigest()
    return str(Path(code["session_directory"]) / ("verislop-runtime020-" + digest + ".json"))


def own_pending_key(reference):
    return "verislop.runtime020-own-pending/0.1:" + _json(_reference(reference))


def _request(reference, code, operation):
    return {"format": REQUEST_FORMAT, "operation": operation,
            "reference": _reference(reference), "code": _code(code),
            "session_path": session_path(reference, code)}


def runtime_command(request):
    """JSON is one POSIX-quoted data argument; it never becomes shell code."""
    return (shlex.quote(PYTHON_PATH) + " -I -B -c " + shlex.quote(LAUNCHER_SOURCE)
            + " " + shlex.quote(_json(request)))


def _view(view):
    names = {"operation", "output_cap_bytes", "metadata_reserve_bytes"}
    if type(view) is not dict:
        raise ValueError("INVALID_CLOSED_VIEW")
    if view.get("operation") == "field":
        names |= {"selector", "start_char"}
        if view.get("selector") not in ("/system", "/user") or type(view.get("start_char")) is not int or not 0 <= view["start_char"] <= 2**53 - 1:
            raise ValueError("INVALID_CLOSED_VIEW_RANGE")
    elif view.get("operation") != "inventory":
        raise ValueError("INVALID_CLOSED_VIEW")
    if set(view) != names or type(view["output_cap_bytes"]) is not int or not 256 <= view["output_cap_bytes"] <= 8192 or type(view["metadata_reserve_bytes"]) is not int or not 128 <= view["metadata_reserve_bytes"] < view["output_cap_bytes"]:
        raise ValueError("INVALID_CLOSED_VIEW_BOUNDS")
    return dict(view)


def own_context_key(reference):
    """Hash own reference metadata in the producer; emitted INIT never hashes."""
    digest = hashlib.sha256(_json(_reference(reference)).encode("utf-8")).hexdigest()
    return "verislop.runtime024-own-context/0.1:" + digest


def runtime_restore_template(reference, code):
    """Zero-I/O fixed data initialization; never change pending or accepted state."""
    prefix = shlex.quote(PYTHON_PATH) + " -I -B -c " + shlex.quote(LAUNCHER_SOURCE) + " "
    context = {"request": _request(reference, code, "view"), "prefix": prefix,
               "pending_key": own_pending_key(reference)}
    return (EXEC_PRAGMA + "store(" + _json(own_context_key(reference)) + ", " + _json(context) + ");\n"
            + 'text({format: "verislop.transport-context-availability/1", status: "STORED", availability_only: true, semantic_acceptance_authority: false});\n')


def _recipe(request, reference, *, view=None, confirmation=None):
    result = (EXEC_PRAGMA + "const CONTEXT = load(" + _json(own_context_key(reference)) + ");\n"
              + 'if (CONTEXT === undefined || CONTEXT === null) throw new Error("OWN_TRANSPORT_CONTEXT_ABSENT");\n'
              + 'if (typeof CONTEXT !== "object" || Array.isArray(CONTEXT) || Object.keys(CONTEXT).sort().join(",") !== "pending_key,prefix,request" || typeof CONTEXT.prefix !== "string" || typeof CONTEXT.pending_key !== "string" || typeof CONTEXT.request !== "object" || CONTEXT.request === null || Array.isArray(CONTEXT.request)) throw new Error("OWN_TRANSPORT_CONTEXT_INVALID");\n'
              + "const REQUEST = {...CONTEXT.request};\nREQUEST.operation = " + _json(request["operation"]) + ";\n")
    if view is not None:
        result += "const VIEW = " + _json(_view(view)) + ";\nREQUEST.view = VIEW;\n"
    if confirmation is not None:
        result += ("const CONFIRM = " + _json(confirmation) + ";\n"
                   + 'const PENDING = load(CONTEXT.pending_key);\n'
                   + 'if (PENDING === undefined || PENDING === null) throw new Error("OWN_PENDING_OBSERVATION_ABSENT");\n'
                   + "REQUEST.pending = PENDING;\nREQUEST.confirmation = CONFIRM;\n")
    result += (SHELL_SAFE_JS + "const cmd = CONTEXT.prefix + posixQuote(wire(REQUEST));\n"
               + "const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});\n")
    if view is not None:
        result += "store(CONTEXT.pending_key, {reference: REQUEST.reference, view: VIEW, result: ACTUAL_RESULT});\n"
    result += "text(ACTUAL_RESULT);\n"
    return result


def runtime_initial_template(reference, code):
    return _recipe(_request(reference, code, "view"), reference,
                   view={"operation": "inventory", "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048})


def runtime_next_template(reference, code, view=None):
    if view is None:
        view = {"operation": "field", "selector": "/system", "start_char": 0,
                "output_cap_bytes": 8192, "metadata_reserve_bytes": 2048}
    return _recipe(_request(reference, code, "view"), reference, view=_view(view))


def runtime_confirm_template(reference, code, confirmation=None):
    if confirmation is None:
        confirmation = {"chunk_id": "COPY_ACTUAL_CHUNK_ID", "outer_output_intact": True}
    if type(confirmation) is not dict or set(confirmation) != {"chunk_id", "outer_output_intact"} or type(confirmation["chunk_id"]) is not str or not confirmation["chunk_id"] or type(confirmation["outer_output_intact"]) is not bool:
        raise ValueError("INVALID_CLOSED_CONFIRMATION")
    return _recipe(_request(reference, code, "confirm"), reference, confirmation=confirmation)


def runtime_hash_template(reference, code):
    return _recipe(_request(reference, code, "hash"), reference)


def runtime_checkpoint_template(reference, code):
    return _recipe(_request(reference, code, "checkpoint"), reference)



def runtime_wait_template(reference, code):
    """One explicit poll of the retained own execution; zero VIEW/state commits."""
    checked_reference = _reference(reference); checked_code = _code(code)
    return (EXEC_PRAGMA + "const CONTEXT = load(" + _json(own_context_key(reference)) + ");\n"
            + SHELL_SAFE_JS + """if (CONTEXT === undefined || CONTEXT === null) throw new Error("OWN_TRANSPORT_CONTEXT_ABSENT");
if (typeof CONTEXT !== "object" || Array.isArray(CONTEXT) || Object.keys(CONTEXT).sort().join(",") !== "pending_key,prefix,request" || typeof CONTEXT.pending_key !== "string" || typeof CONTEXT.request !== "object" || CONTEXT.request === null || Array.isArray(CONTEXT.request)) throw new Error("OWN_TRANSPORT_CONTEXT_INVALID");
const PENDING = load(CONTEXT.pending_key);
if (PENDING === undefined || PENDING === null) throw new Error("OWN_PENDING_OBSERVATION_ABSENT");
if (typeof PENDING !== "object" || Array.isArray(PENDING) || Object.keys(PENDING).sort().join(",") !== "reference,result,view" || wire(PENDING.reference) !== wire(CONTEXT.request.reference)) throw new Error("INVALID_OWN_PENDING");
const SEQUENCE_FORMAT = "verislop.actual-execution-result-sequence/0.1";
const IS_SEQUENCE = PENDING.result !== null && typeof PENDING.result === "object" && PENDING.result.format === SEQUENCE_FORMAT;
if (IS_SEQUENCE && (Array.isArray(PENDING.result) || Object.keys(PENDING.result).sort().join(",") !== "format,results" || !Array.isArray(PENDING.result.results) || PENDING.result.results.length < 2)) throw new Error("INVALID_RUNNING_RESULT_CHAIN");
const RESULTS = IS_SEQUENCE ? PENDING.result.results.slice() : [PENDING.result];
let SESSION;
for (const result of RESULTS) {
  if (result === null || typeof result !== "object" || Array.isArray(result) || typeof result.chunk_id !== "string" || result.chunk_id.length === 0 || typeof result.output !== "string" || !Number.isSafeInteger(result.session_id) || result.session_id < 0 || "exit_code" in result) throw new Error("OWN_EXECUTION_NOT_RUNNING");
  if (SESSION === undefined) SESSION = result.session_id;
  if (result.session_id !== SESSION) throw new Error("INVALID_RUNNING_RESULT_CHAIN");
  if ("original_token_count" in result && (!Number.isSafeInteger(result.original_token_count) || result.original_token_count < 0 || result.original_token_count > 16384)) throw new Error("NESTED_OUTPUT_TRUNCATION");
}
const BEFORE = wire(PENDING);
const LAST = RESULTS[RESULTS.length - 1];
const ACTUAL_RESULT = await tools.write_stdin({session_id: SESSION, max_output_tokens: 16384, yield_time_ms: 1000});
text(ACTUAL_RESULT);
const CURRENT = load(CONTEXT.pending_key);
if (CURRENT === undefined || CURRENT === null || wire(CURRENT) !== BEFORE) {
  store(CONTEXT.pending_key + "/unapplied-wait/" + LAST.chunk_id, {pending: JSON.parse(BEFORE), result: ACTUAL_RESULT});
  throw new Error("OWN_PENDING_OBSERVATION_REPLACED");
}
store(CONTEXT.pending_key, {reference: PENDING.reference, view: PENDING.view, result: {format: SEQUENCE_FORMAT, results: RESULTS.concat([ACTUAL_RESULT])}});
""")

def runtime_agent_message(reference, code):
    reference = _reference(reference); code = _code(code)
    return ("COMPACT DEVELOPMENT CARRIER RUNTIME — support025-running-result/1\n"
            "Read this own carrier completely through the exact fixed recipes below. This version explicitly permits invoking only the registered local runtime and its fixed reader/code guard. The runtime may read its fixed source files, this exact own carrier on VIEW only, and the declared own-session file. It may persist only that session. Other helpers, carriers, files, history, network, agents and expected-answer/root oracles are outside this permission.\n"
            "Reference: " + _json(reference) + "\nRegistered code: " + _json(code)
            + "\nOwn session file: " + session_path(reference, code) + "\n"
            "Run INIT_RESTORE unchanged before FIRST and explicitly after transport context is lost. INIT_RESTORE stores only fixed reference-bound request/launcher/pending-key data; it reads no files, calls no runtime or reader, computes no hashes and commits no accepted state. It never removes or replaces your original pending observation. Missing context raises OWN_TRANSPORT_CONTEXT_ABSENT with zero runtime calls; explicitly restore context, CHECKPOINT accepted availability, then issue the originally required explicit operation. Missing pending raises OWN_PENDING_OBSERVATION_ABSENT with zero calls; CHECKPOINT and explicitly re-request the SAME accepted cursor. No recipe restores, retries or retrieves automatically. FIRST requests inventory; NEXT requests one explicit closed VIEW per call. Every VIEW output_cap_bytes is an integer from 256 through 8192 inclusive; metadata_reserve_bytes is an integer with 128 <= metadata_reserve_bytes < output_cap_bytes. Field start_char is an exact nonnegative JSON-safe integer counting decoded Unicode scalars; selector is exactly /system or /user. Confirm inventory, complete /system EOF, then complete /user EOF. Edit ONLY NEXT VIEW selector/start_char/cap/reserve, never REQUEST, code, reference, session, launcher or wrapper. No recipe selects or retrieves the next cursor automatically. Every recipe forwards the complete actual tool result. FIRST/NEXT stage only that exact result under your bound own pending key and do not commit accepted state.\n"
            "If FIRST/NEXT returns an actually exposed running session_id, explicitly invoke the unchanged WAIT recipe once for that retained execution. WAIT performs zero VIEW, starts no process, chooses no cursor and polls only that exact session; invoke it explicitly again only if its actual return remains running. Every original/wait return is retained literally in order. Inspect each visible outer response for intactness; CONFIRM outer_output_intact=true asserts all those responses are intact. A wait yield is not a timeout or deadline. Do not edit WAIT, poll a replacement session, issue a new NEXT while a wait is outstanding, or manufacture a completed tool result.\n"
            "After observing complete integer-zero completion, its actually exposed chunk_id and intact outer response, use CONFIRM. Edit ONLY CONFIRM.chunk_id and outer_output_intact; true asserts that you checked the visible outer output is intact, not hidden-envelope attestation. CONFIRM performs zero VIEW but one explicitly permitted runtime tool call. It validates status, exact original identity/Unicode/UTF8/cursors/bounds and persists atomically only on success. Rejected/malformed/truncated/nonzero/running output never advances accepted state. For an observed INVALID_CLOSED_VIEW_BOUNDS or another rejected editable VIEW argument, criticize the actual selector/start_char/cap/reserve against the bounds above and explicitly issue a fresh valid NEXT at the SAME accepted selector and start_char, using output_cap_bytes 8192 and metadata_reserve_bytes 2048. Restore the last accepted selector/cursor if the rejected attempt used an invalid selector or cursor. Do not CONFIRM the rejected result, advance accepted state, or return an incomplete FINAL merely because this first editable request was rejected. For actual nested or outer truncation, explicitly retry that SAME accepted selector/cursor with output_cap_bytes 4096 and metadata_reserve_bytes 2048. Continue each permitted explicit VIEW and CONFIRM through both EOFs; incomplete reading or a large input alone is not a fixed-source blocker. Stop only when an actual exposed blocking operation cannot be corrected using permitted closed values, and report its concrete observed error or explicitly UNKNOWN/unavailable. OWN_SESSION_BUSY requires an explicit retry of the same confirmation; no automatic retry or retrieval is performed.\n"
            "Confirm inventory, then complete /system EOF, then complete /user EOF, including explicit EOF for empty fields. Use HASH only after both confirmed EOFs and complete totals. HASH is zero VIEW but one runtime tool call, reconstructs original accepted observations and hashes exact scalar UTF8 fields without reading the carrier. Do not invent roots or replace full field coverage with hashes or summaries. Validate each intact actual response. Own state survives compression as availability only.\n"
            "After compression, a lost accepted cursor, or a lost unconfirmed VIEW, and before every FINAL, explicitly execute the fixed CHECKPOINT recipe below. CHECKPOINT is zero VIEW: it reads only the accepted own-session observations, validates their exact replay and returns accepted availability cursors/totals/EOF without reading the carrier, invoking the reader, computing roots or committing state. An EMPTY report means no accepted inventory exists: resume FIRST and CONFIRM inventory. For an existing summary, continue the first incomplete field in the required /system then /user order by explicitly editing NEXT to its exact returned next_char, and then CONFIRM the intact result. If an unconfirmed VIEW was lost, re-request that SAME accepted cursor; no rejected or unconfirmed attempt advances it. If all fields have confirmed EOF, HASH remains the only fixed field-hash recipe. A checkpoint summary does not replace your inspection or any SYSTEM-defined requirement. If CHECKPOINT itself has an actual exposed blocker, retain that error without inventing a summary. No recipe automatically chooses a cursor, retries, loops over VIEW or retrieves content.\n"
            "Keep exact SYSTEM-defined response/review/search/proof requirements and literal FINAL. Report only concrete observed errors or explicitly UNKNOWN/unavailable; this revised transport does not explain the historical failure. Availability/checkpoints/hashes establish no semantic consumption, understanding, ACCEPT, proof, TESTED, lifecycle or end-to-end authority. No inference, retrieval or review deadline, resampling, additional agent or automatic VIEW loop is authorized.\n"
            "INIT_RESTORE functions.exec (execute unchanged; fixed data only):\n```javascript\n" + runtime_restore_template(reference, code)
            + "```\nFIRST functions.exec (execute unchanged after INIT_RESTORE):\n```javascript\n" + runtime_initial_template(reference, code)
            + "```\nNEXT functions.exec (edit ONLY closed VIEW):\n```javascript\n" + runtime_next_template(reference, code)
            + "```\nWAIT functions.exec (unchanged; one explicit poll of the retained actual execution):\n```javascript\n" + runtime_wait_template(reference, code)
            + "```\nCONFIRM functions.exec (edit ONLY closed confirmation after intact observed completion):\n```javascript\n" + runtime_confirm_template(reference, code)
            + "```\nCHECKPOINT functions.exec (execute unchanged after compression/lost cursor and before FINAL):\n```javascript\n" + runtime_checkpoint_template(reference, code)
            + "```\nHASH functions.exec (execute unchanged after both confirmed EOFs):\n```javascript\n" + runtime_hash_template(reference, code) + "```\n")


def source_profile(session_directory):
    """Expose source/literal/AST bindings for independent versioned reconstruction."""
    source = Path(__file__).read_bytes(); tree = ast.parse(source)
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            constants[node.targets[0].id] = ast.literal_eval(node.value)
    return {"format": "verislop.compact-runtime-source-profile/0.2", "api_revision": API_REVISION,
            "source": {"path": str(Path(__file__).resolve()), "sha256": "sha256:" + hashlib.sha256(source).hexdigest(), "byte_count": len(source)},
            "code": code_bindings(session_directory), "constants": constants,
            "function_ast_hashes": {node.name: "sha256:" + hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                                    for node in tree.body if isinstance(node, ast.FunctionDef)},
            "reconstruction": "Independent renderer must authenticate every source/code binding and reconstruct these versioned APIs; legacy006 reconstruction is a separate unchanged interface.",
            "availability_only": True, "qualification_authority": False}
