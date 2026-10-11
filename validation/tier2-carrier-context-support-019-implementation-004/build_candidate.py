"""Source-only assembly; no view/model/Lean/task/verifier calls."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parents[1] / "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py"
assert not (HERE / "SEAL.sha256").exists(), "SEALED_CANDIDATE_MUST_NOT_BE_REBUILT"
assert hashlib.sha256(BASELINE.read_bytes()).hexdigest() == "9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366"
source = BASELINE.read_text(encoding="utf-8")
assert source.count("def agent_message(") == 1
source = source.replace("def agent_message(", "def legacy_agent_message(", 1)
runtime = (HERE / "checkpoint_runtime.js").read_text(encoding="utf-8")
sha_runtime = (HERE / "sha256_runtime.js").read_text(encoding="utf-8")
extension = r'''

# Separate author APIs keep the original view-only/capture APIs byte-exact.
CHECKPOINT_VALIDATOR_SOURCE = __CHECKPOINT_RUNTIME_LITERAL__
OWN_SHA256_SOURCE = __SHA256_RUNTIME_LITERAL__


def own_checkpoint_key(reference: dict[str, str]) -> str:
    return "verislop.own-view-checkpoint/0.1:" + json.dumps(
        {"path": reference["path"], "sha256": reference["sha256"]},
        sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def own_pending_key(reference: dict[str, str]) -> str:
    return "verislop.own-view-pending/0.1:" + json.dumps(
        {"path": reference["path"], "sha256": reference["sha256"]},
        sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def own_hash_key(reference: dict[str, str]) -> str:
    return "verislop.own-view-hash-result/0.1:" + json.dumps(
        {"path": reference["path"], "sha256": reference["sha256"]},
        sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _author_observer(recipe: str, reference: dict[str, str]) -> str:
    """Stage only; the actual outer result must be seen before CONFIRM commits."""
    old = "text(await tools.exec_command({cmd, max_output_tokens: 16384}));"
    lines = recipe.split("\n")
    if lines.count(old) != 1:
        raise ValueError("ONE_COMPLETE_FORWARDING_STATEMENT_REQUIRED")
    new = ('const ACTUAL_RESULT = await tools.exec_command({cmd, max_output_tokens: 16384});\n'
           'text(ACTUAL_RESULT);\n'
           'store(PENDING_KEY, {reference: OWN_REFERENCE, view: VIEW, result: ACTUAL_RESULT});')
    bindings = ('const OWN_REFERENCE = ' + json.dumps(reference, sort_keys=True, ensure_ascii=True) + ';\n'
                'const PENDING_KEY = ' + json.dumps(own_pending_key(reference), ensure_ascii=True) + ';\n')
    return _EXEC_PRAGMA + bindings + "\n".join(new if line == old else line for line in lines)[len(_EXEC_PRAGMA):]


def author_initial_session_template(reference: dict[str, str]) -> str:
    return _author_observer(initial_session_template(reference), reference)


def author_next_session_template(reference: dict[str, str], view: dict | None = None) -> str:
    return _author_observer(next_session_template(reference, view), reference)


def _checkpoint_bindings(reference: dict[str, str]) -> str:
    return ('const OWN_REFERENCE = ' + json.dumps(reference, sort_keys=True, ensure_ascii=True) + ';\n'
            'const CHECKPOINT_KEY = ' + json.dumps(own_checkpoint_key(reference), ensure_ascii=True) + ';\n')


def confirm_session_template(reference: dict[str, str], confirmation: dict | None = None) -> str:
    if confirmation is None:
        confirmation = {"chunk_id": "COPY_ACTUAL_CHUNK_ID", "outer_output_intact": True}
    if (type(confirmation) is not dict or set(confirmation) != {"chunk_id", "outer_output_intact"}
            or type(confirmation["chunk_id"]) is not str or not confirmation["chunk_id"]
            or type(confirmation["outer_output_intact"]) is not bool):
        raise ValueError("INVALID_CLOSED_CONFIRMATION")
    return (_EXEC_PRAGMA + _checkpoint_bindings(reference)
            + 'const PENDING_KEY = ' + json.dumps(own_pending_key(reference), ensure_ascii=True) + ';\n'
            + 'const CONFIRM = ' + json.dumps(confirmation, sort_keys=True, ensure_ascii=True) + ';\n'
            + CHECKPOINT_VALIDATOR_SOURCE
            + 'const NEXT_CHECKPOINT = checkpointConfirm(load(CHECKPOINT_KEY), load(PENDING_KEY), CONFIRM, OWN_REFERENCE);\n'
            + 'store(CHECKPOINT_KEY, NEXT_CHECKPOINT);\n'
            + 'text(checkpointSummary(NEXT_CHECKPOINT));\n')


def hash_session_template(reference: dict[str, str]) -> str:
    """Zero VIEW/tools; fixed SHA-256 over accepted own Unicode scalar fields."""
    return (_EXEC_PRAGMA + _checkpoint_bindings(reference) + CHECKPOINT_VALIDATOR_SOURCE + OWN_SHA256_SOURCE
            + 'const OWN_STATE = load(CHECKPOINT_KEY);\n'
            + 'const OWN_FIELDS = checkpointReconstruct(OWN_STATE, OWN_REFERENCE).fields;\n'
            + 'const FIELD_ROOTS = {}, FIELD_CHARS = {}, FIELD_BYTES = {};\n'
            + 'for (const selector of ["/system", "/user"]) {\n'
            + '  const field = OWN_FIELDS[selector];\n'
            + '  checkpointNeed(field.field_eof && field.next_char === field.field_chars\n'
            + '    && field.next_utf8_byte === field.field_utf8_bytes, "OWN_FIELDS_NOT_COMPLETE");\n'
            + '  FIELD_ROOTS[selector] = "sha256:" + ownViewSha256(field.content);\n'
            + '  FIELD_CHARS[selector] = field.field_chars; FIELD_BYTES[selector] = field.field_utf8_bytes;\n'
            + '}\n'
            + 'const OWN_HASH_RESULT = {format: "verislop.own-view-field-hashes/0.1", field_roots: FIELD_ROOTS,\n'
            + '  field_chars: FIELD_CHARS, field_utf8_bytes: FIELD_BYTES, field_eof: {"/system": true, "/user": true},\n'
            + '  availability_only: true, semantic_consumption: "UNATTESTED", semantic_acceptance_authority: false};\n'
            + 'store(' + json.dumps(own_hash_key(reference), ensure_ascii=True) + ', OWN_HASH_RESULT);\n'
            + 'text(OWN_HASH_RESULT);\n')


def agent_message(reference: dict[str, str]) -> str:
    message = legacy_agent_message(reference)
    message = message.replace("Each functions.exec call must execute exactly one view",
                              "Each FIRST/NEXT functions.exec call must execute exactly one view", 1)
    message = message.replace(initial_session_template(reference), author_initial_session_template(reference), 1)
    message = message.replace(next_session_template(reference), author_next_session_template(reference), 1)
    instruction = (
        "\nAUTHOR OWN-VIEW CHECKPOINT PROTOCOL (explicit new non-VIEW exceptions):\n"
        "The FIRST/NEXT recipes below still perform exactly one VIEW and forward exactly its full actual result. "
        "They now stage that result under only your own pending key. They never advance accepted state automatically. "
        "After seeing the complete intact outer functions.exec response, use the fixed CONFIRM recipe, editing ONLY "
        "its closed CONFIRM.chunk_id to the actual returned chunk_id. Leave outer_output_intact true ONLY after "
        "checking the visible outer response is intact. CONFIRM performs zero views and zero tools; its fixed pure "
        "validator commits the exact decoded original slice only after complete numeric status, identity, canonical "
        "JSON, codepoint/UTF-8 cursors, bounds and totals agree. If either nested or outer response is truncated, "
        "malformed, incomplete or inconsistent, DO NOT CONFIRM; retry the SAME explicit cursor with the existing "
        "4096-byte cap/2048 reserve. Complete and confirm inventory, then system EOF, then user EOF. Neither recipe "
        "chooses or executes your next cursor. Pure loops over own stored observations/Unicode scalars validate "
        "state only; loops over VIEW calls, automatic retrieval/cursor advancement and gap skipping remain forbidden.\n"
        "Exact own checkpoint original fields and raw observations may survive context compression. Read ONLY "
        "your explicitly bound own checkpoint key if you need these original spans; never other keys or helpers. "
        "CONFIRM prints only bounded availability cursor/EOF summaries. Checkpoints and acknowledgement establish "
        "availability under tool-forwarding trust, not actual hidden outer-envelope attestation, semantic consumption, "
        "understanding, ACCEPT, proof or lifecycle authority. No inference/retrieval/review deadline is imposed.\n"
        "After both fields have their complete explicitly confirmed EOF, use the fixed HASH recipe unchanged. "
        "This separate zero-VIEW, zero-tool own-state computation uses ONLY accumulated decoded original fields "
        "from your own checkpoint. Its fixed inline standard JavaScript SHA-256 routine strictly encodes Unicode "
        "scalars to UTF-8 in bounded blocks; it needs no Node/crypto package, child process or whole-field command. "
        "It reads no carrier, file, helper, expected answer, other agent, network or precomputed field-root oracle. "
        "Validate its intact printed own-memory JSON before using field_roots. HASH never computes marker answers, advances "
        "a VIEW cursor, claims semantic review, or replaces full inspection. Keep all inline source unchanged. "
        "Incomplete fields forbid HASH; preserve the existing incomplete-response protocol rather than inventing roots.\n"
        "Only closed VIEW/CONFIRM values may be edited in their respective fixed recipes. HASH is unchanged. "
        "The original read-only restriction concerns external input/files; these explicit own-memory confirmations "
        "and own-state hash computations are permitted without broadening external access. Preserve the complete "
        "scope/search/review/response requirements and original model/compiler/output budgets.\n")
    message = message.replace("\n\nCARRIER:\n", instruction + "\nCARRIER:\n", 1)
    return (message + "\nCONFIRM functions.exec (edit ONLY closed CONFIRM after intact actual outer response):\n```javascript\n"
            + confirm_session_template(reference) + "```\n"
            + "\nHASH functions.exec (own complete checkpoint only; execute unchanged; zero VIEW):\n```javascript\n"
            + hash_session_template(reference) + "```\n")
'''
extension = extension.replace("__CHECKPOINT_RUNTIME_LITERAL__", repr(runtime))
extension = extension.replace("__SHA256_RUNTIME_LITERAL__", repr(sha_runtime))
target = HERE / "bootstrap_tier2_carrier_view.py"
with target.open("w", encoding="utf-8") as stream:
    stream.write(source + extension)
print(target)
