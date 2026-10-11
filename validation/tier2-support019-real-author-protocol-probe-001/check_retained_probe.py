"""Read-only validation of this probe's already-retained observations.

This does not submit recipes, execute VIEW, confirm a checkpoint, or hash through
the protocol. Its independent fixture hashes were registered before execution.
"""
from pathlib import Path
import hashlib
import json


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main():
    registration = read("PRE_CALL_REGISTRATION.json")
    registered = [registration[key] for key in (
        "carrier", "original_request", "reference", "independent_own_literal_hashes",
        "production_source", "specification")]
    registered.extend(registration["exact_literal_recipes"].values())
    for item in registered:
        raw = (ROOT / item["path"]).read_bytes()
        assert digest(raw) == item["sha256"], item["path"]
        if "byte_count" in item:
            assert len(raw) == item["byte_count"], item["path"]
    expected = read("independent-own-literal-field-hashes.json")
    carrier = read("own-carrier.json")
    reference = read("own-reference.json")
    actual_hash = read("hash-actual-observation.json")["actual_visible_result"]
    for key in ("field_roots", "field_chars", "field_utf8_bytes", "field_eof"):
        assert actual_hash[key] == expected[key], key
    for selector in ("/system", "/user"):
        literal = carrier[selector[1:]]
        assert digest(literal.encode("utf-8", errors="strict")) == expected["field_roots"][selector]
        assert len(literal) == expected["field_chars"][selector]
        assert len(literal.encode("utf-8", errors="strict")) == expected["field_utf8_bytes"][selector]
        assert expected["field_eof"][selector] is True

    views = (
        ("initial-actual-observation.json", "initial-functions-exec.js", "e40e5b", None),
        ("system-actual-observation.json", "next-system-functions-exec.js", "cee331", "/system"),
        ("user-actual-observation.json", "next-user-functions-exec.js", "0da97b", "/user"),
    )
    result_objects = []
    for filename, source, chunk, selector in views:
        observed = read(filename)
        result = observed["actual_nested_result"]
        assert result == observed["own_pending"]["result"]
        assert observed["own_pending"]["reference"] == reference
        assert result["chunk_id"] == observed["nested_chunk_id"] == chunk
        assert type(result["exit_code"]) is int and result["exit_code"] == 0
        assert "session_id" not in result
        assert observed["outer_response_observed_intact"] is True
        assert observed["exact_registered_source"] == source
        body = json.loads(result["output"])
        assert body["status"] == "ok"
        assert body["carrier_path"] == reference["path"]
        assert body["carrier_sha256"] == reference["sha256"]
        assert body["request_sha256"] == reference["request_sha256"]
        assert body["request_id"] == carrier["request_id"]
        assert body["output_cap_bytes"] == 8192 and body["metadata_reserve_bytes"] == 2048
        recipe = (HERE / source).read_text(encoding="utf-8")
        assert recipe.count("await tools.exec_command(") == 1
        assert recipe.count("text(ACTUAL_RESULT)") == 1
        assert "max_output_tokens: 16384" in recipe
        if selector is None:
            assert body["operation"] == "inventory"
        else:
            assert body["operation"] == "field" and body["selector"] == selector
            assert body["content"] == carrier[selector[1:]]
            assert body["start_char"] == body["start_utf8_byte"] == 0
            assert body["end_char"] == body["next_char"] == expected["field_chars"][selector]
            assert body["end_utf8_byte"] == expected["field_utf8_bytes"][selector]
            assert body["field_eof"] is True
        result_objects.append(observed["own_pending"])

    template = (HERE / "confirm-template-functions-exec.js").read_text(encoding="utf-8")
    assert template.count("COPY_ACTUAL_CHUNK_ID") == 1
    for index, label in enumerate(("inventory", "system", "user")):
        observed = read(f"confirm-{label}-actual-observation.json")
        source = f"confirm-{label}-functions-exec.js"
        chunk = views[index][2]
        assert (HERE / source).read_text(encoding="utf-8") == template.replace("COPY_ACTUAL_CHUNK_ID", chunk)
        assert observed["exact_submitted_source"] == source
        assert observed["actual_tools_inside_confirmation"] == 0
        assert observed["actual_VIEWs_inside_confirmation"] == 0
        checkpoint = observed["own_checkpoint_after"]
        assert len(checkpoint["observations"]) == index + 1
        for number, item in enumerate(checkpoint["observations"]):
            assert item["pending"] == result_objects[number]
            assert item["confirmation"] == {"chunk_id": views[number][2], "outer_output_intact": True}
        summary = observed["visible_pure_output"]
        assert summary["availability_only"] is True
        assert summary["semantic_consumption"] == "UNATTESTED"
        assert summary["semantic_acceptance_authority"] is False
        for selector in ("/system", "/user"):
            state = checkpoint["fields"][selector]
            visible = summary["fields"][selector]
            assert visible == {key: state[key] for key in (
                "next_char", "next_utf8_byte", "field_chars", "field_utf8_bytes", "field_eof")}
            complete = index >= (1 if selector == "/system" else 2)
            assert state["field_eof"] is complete
            if complete:
                assert state["content"] == carrier[selector[1:]]
                assert state["next_char"] == expected["field_chars"][selector]
                assert state["next_utf8_byte"] == expected["field_utf8_bytes"][selector]
            else:
                assert state["next_char"] == state["next_utf8_byte"] == 0
    hash_observed = read("hash-actual-observation.json")
    assert hash_observed["actual_operation_tool_calls"] == hash_observed["actual_operation_view_calls"] == 0
    assert actual_hash["availability_only"] is True
    assert actual_hash["semantic_consumption"] == "UNATTESTED"
    assert actual_hash["semantic_acceptance_authority"] is False
    assert "await tools." not in template
    assert "await tools." not in (HERE / "hash-functions-exec.js").read_text(encoding="utf-8")
    print(json.dumps({
        "status": "RETAINED_BOUNDED_INTERFACE_PROBE_CHECKS_PASSED",
        "registered_input_and_literal_hashes_checked": len(registered),
        "actual_VIEW_completions": 3,
        "actual_pure_CONFIRM_completions": 3,
        "actual_pure_HASH_completions": 1,
        "actual_nested_chunk_ids": [item[2] for item in views],
        "field_roots": actual_hash["field_roots"],
        "field_chars": actual_hash["field_chars"],
        "field_utf8_bytes": actual_hash["field_utf8_bytes"],
        "field_eof": actual_hash["field_eof"],
        "production_source_before": registration["source_before"],
        "production_source_after": digest((ROOT / registration["production_source"]["path"]).read_bytes()),
        "semantic_consumption": "UNATTESTED",
        "qualification_authority": False,
        "task_TESTED_authority": False,
        "explains_prior_author_stop": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
