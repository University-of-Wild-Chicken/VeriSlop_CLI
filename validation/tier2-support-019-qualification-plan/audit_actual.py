#!/usr/bin/env python3
"""Future independent binding/admission helper; no target verifier execution.

NOT RUN in preparation. A reviewed and freshly executed independent predicate
reader is a mandatory input. This helper does not turn labels, exit codes, or
producer self-reports into semantic evidence. It checks actual schema fields,
exact suite floor, all registered claims, direct-process/log/report identities,
observable carrier bytes, and declared unavailable/UNATTESTED boundaries.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from registration_lib import (Block, digest, file_map, load, map_digest, need, parse, process_receipt,
                              ref, regular, source_names, timestamp, verify_map, write_once)

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
UNAVAILABLE = {"hidden_outer_http_mcp_envelope": "UNAVAILABLE", "separate_stdout": "UNAVAILABLE",
               "separate_stderr": "UNAVAILABLE", "pid": "UNAVAILABLE", "never_fabricate_or_relabel": True}


class Audit:
    def __init__(self, gate, index_hashes):
        self.gate = gate
        self.spec = load(gate / "qualification-specification.json")
        self.manifest = load(gate / "qualification-inputs.json")
        self.freeze = load(gate / "source-freeze.json")
        self.prereg = load(gate / "preregistration.json")
        self.claims = load(HERE / "claims.json")
        self.floor = load(HERE / "mandatory-floor.json")
        self.controls = load(HERE / "control-registration.json")
        self.source_root = self.manifest["source_root"]
        self.input_root = self.manifest["input_root"]
        self.reads, self.processes = {}, {}
        self.frozen_at = self.freeze["created_at_utc"]
        self.index_hashes = index_hashes

    def index(self, key):
        # Output identities cannot be known at source freeze. The actual caller
        # supplies their exact completed hashes in this fresh audit invocation;
        # the source specification freezes only their prospective output paths.
        path = self.spec[key + "_path"]
        raw = regular(ROOT, path).read_bytes()
        need(digest(raw) == self.index_hashes[key], "EXTERNAL_EVIDENCE_INDEX_HASH_MISMATCH")
        return self.doc({"path": path, "sha256": digest(raw), "byte_count": len(raw)})

    def evidence(self, record):
        name = record["path"]
        need(any(name.startswith(prefix.rstrip("/") + "/")
                 for prefix in self.spec["fresh_evidence_prefixes"]), "EVIDENCE_NOT_NEW_CURRENT_RUN:" + name)
        raw = ref(ROOT, record)
        if name in self.reads:
            need(self.reads[name] == record, "EVIDENCE_MUTATION:" + name)
        self.reads[name] = record
        return raw

    def doc(self, record):
        # Strict unique-key parsing uses the common file reader after authenticating bytes.
        self.evidence(record)
        return load(regular(ROOT, record["path"]))

    def bound(self, obj):
        need(obj["closure_id"] == self.spec["closure_id"] and obj["source_root"] == self.source_root
             and obj["input_root"] == self.input_root, "STALE_OR_UNBOUND_EVIDENCE")

    def guards(self):
        hashes = self.manifest["source_hashes"]
        need(map_digest(hashes) == self.input_root and
             map_digest(self.freeze["source_files"]) == self.source_root,
             "CANONICAL_ROOT_MISMATCH")
        verify_map(ROOT, hashes)
        inventory = load(HERE / "source-inventory-registration.json")
        need(file_map(ROOT, list(source_names(ROOT, inventory))) == self.freeze["source_files"],
             "COMPLETE_SOURCE_MAP_MUTATION")
        tests = file_map(ROOT, [p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").rglob("*.py")])
        need(tests == self.spec["test_sources"] == self.freeze["test_sources"], "COMPLETE_TEST_MAP_MUTATION")
        for name, sha in self.prereg["external_bindings"].items():
            need(digest((self.gate / name).read_bytes()) == sha, "EXTERNAL_PREREGISTRATION_MUTATION")
        need(self.prereg["source_root"] == self.spec["source_root"] == self.source_root and
             self.prereg["input_root"] == self.input_root and self.prereg["generation_started"] is False,
             "FINAL_PREREGISTRATION_STALE")
        ids = self.spec["registered_test_ids"]
        need(len(ids) == len(set(ids)) == self.spec["registered_test_count"] and
             set(self.floor["registered_test_ids"]).issubset(ids) and
             set(self.floor["test_modules"]).issubset(self.spec["test_modules"]), "EXACT180_OR15_FLOOR_MISSING")
        need(self.spec["claims_sha256"] == digest((HERE / "claims.json").read_bytes()), "CLAIM_MUTATION")
        need(self.spec["task_inputs"] is False and self.spec["prior_pass_inheritance"] is False and
             self.spec["core_model_calls"] == 0 and self.spec["ancillary_fresh_author_calls"] == 1,
             "PROHIBITED_INPUT_OR_MODEL_COUNT")
        for path, expected in self.spec["external_runtime_files"].items():
            need(digest(Path(path).read_bytes()) == expected, "TOOLCHAIN_RUNTIME_MUTATION")

    def admit_processes(self):
        index = self.index("actual_process_output_index")
        self.bound(index)
        need(index["format"] == "verislop.support019-process-output-index/1" and
             index["producer_path"] in self.manifest["source_hashes"] and
             index["producer_sha256"] == self.manifest["source_hashes"][index["producer_path"]],
             "ACTUAL_OUTPUT_INDEX_PRODUCER_UNBOUND")
        phases = self.spec["execution_phases"]
        need([p["id"] for p in phases] == self.floor["phase_order"], "ORIGINAL_FOUR_PHASES_MISSING")
        registered = phases + self.spec["additional_processes"]
        need(set(index["processes"]) == {p["id"] for p in registered}, "PROCESS_INVENTORY_MISMATCH")
        previous = timestamp(self.frozen_at)
        for entry in registered:
            bound = index["processes"][entry["id"]]
            receipt = self.doc(bound["receipt"])
            process_receipt(ROOT, entry, receipt, self.source_root, self.input_root, self.frozen_at)
            for stream in ("stdout", "stderr"):
                self.evidence(receipt[stream])
            need(previous <= timestamp(receipt["started_utc"]), "PROCESS_SERIAL_ORDER")
            previous = timestamp(receipt["completed_utc"])
            need(set(bound["outputs"]) == set(entry["outputs"]), "PROCESS_OUTPUT_INVENTORY_MISMATCH")
            for key, identity in bound["outputs"].items():
                need(identity["path"] == entry["outputs"][key], "PROCESS_OUTPUT_PATH_SUBSTITUTION")
                self.evidence(identity)
            self.processes[entry["id"]] = bound

    def output(self, process, key):
        return self.doc(self.processes[process]["outputs"][key])

    def suite(self):
        suite = self.output("registered-suite", self.spec["suite_result_output_key"])
        need(suite["format"] == "verislop.support018-suite-result/1", "SUITE_PRODUCER_SCHEMA_MISMATCH")
        ids = self.spec["registered_test_ids"]
        need(suite["registered_test_ids"] == suite["started_ids"] == ids and
             suite["registered_test_count"] == suite["tests_run"] == len(ids) and
             suite["test_observations"] == [{"test_id": oid, "status": "PASS"} for oid in ids],
             "EXACT_REGISTERED_SUITE_NOT_EXECUTED")
        need(all(type(suite[key]) is int and suite[key] == 0 for key in
                 ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")),
             "ADVERSE_OR_SKIPPED_TEST_OUTCOME")
        need(suite["source_root_before"] == suite["source_root_after"] == self.source_root and
             suite["input_root"] == self.input_root and all(suite[key] is True for key in
                 ("source_unchanged", "tests_unchanged", "qualification_inputs_unchanged")), "SUITE_INPUT_MUTATION")

    def equality(self):
        process = "equality-original44-new11-grouped"
        cases = []
        for key in self.spec["equality_result_output_keys"]:
            result = self.output(process, key)
            # Preserve real DEVELOPMENT_ONLY producer provenance. Authority comes
            # from this fresh current-root execution and independent predicate reader.
            need(isinstance(result["cases"], list), "EQUALITY_CASE_SCHEMA_MISMATCH")
            need(type(result["failed"]) is int and result["failed"] == 0 and
                 all(case["status"] == "PASS" for case in result["cases"]), "EQUALITY_CONTROL_FAILED")
            cases.extend(result["cases"])
        labels = [case["label"] for case in cases]
        required = self.controls["equality_original44"] + self.controls["equality_new11"]
        need(set(labels) == set(required) and len(labels) == len(set(labels)) == len(required),
             "EQUALITY_44_PLUS11_REQUIREMENT_INVENTORY_MISMATCH")
        need("source-analysis-wire-binding-negatives" in labels, "IMPROVED_GROUPED_BINDING_NOT_RUN")

    def fixture(self, entry):
        doc = self.doc(entry["identity"])
        reference = entry["reference"]
        need(reference["path"] == str(regular(ROOT, entry["identity"]["path"])) and
             reference["sha256"] == entry["identity"]["sha256"] and
             reference["request_sha256"] == doc["request_sha256"] and
             doc["format"] == "verislop.collaboration-carrier/0.1" and
             isinstance(doc["system"], str) and isinstance(doc["user"], str), "FRESH_FIXTURE_BINDING_MISMATCH")
        doc["system"].encode("utf-8", "strict")
        doc["user"].encode("utf-8", "strict")
        return doc, reference

    def intact(self, call, fixture, reference):
        result = self.doc(call["nested_result_ref"])
        raw = self.evidence(call["returned_output_ref"])
        need(isinstance(result["output"], str) and result["output"].encode("utf-8", "strict") == raw,
             "RETURNED_TOOL_OUTPUT_IDENTITY_MISMATCH")
        need(type(result.get("exit_code")) is int and result["exit_code"] == 0 and
             "session_id" not in result and "Warning: truncated output" not in result["output"],
             "INTACT_VIEW_NOT_COMPLETED")
        record = parse(raw)
        view = call["view"]
        need(record["format"] == "verislop.exact-carrier-view/0.1" and record["status"] == "ok" and
             record["carrier_path"] == reference["path"] and record["carrier_sha256"] == reference["sha256"] and
             record["request_sha256"] == reference["request_sha256"] and
             record["request_id"] == fixture["request_id"] and
             record["output_cap_bytes"] == view["output_cap_bytes"] and
             record["metadata_reserve_bytes"] == view["metadata_reserve_bytes"], "VIEW_IDENTITY_MISMATCH")
        wire = lambda obj: json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8", "strict")
        need(raw == wire(record) + b"\n" and len(raw) <= view["output_cap_bytes"], "WIRE_ENCODING_OR_CAP_MISMATCH")
        if view["operation"] == "inventory":
            need(record["operation"] == "inventory" and len(raw) <= view["metadata_reserve_bytes"] and
                 record["fields"] == [{"selector": "/" + name, "field_chars": len(fixture[name]),
                     "field_utf8_bytes": len(fixture[name].encode("utf-8")), "start_char": 0,
                     "end_char": len(fixture[name])} for name in ("system", "user")], "INVENTORY_MISMATCH")
            return record
        selector, start = view["selector"], view["start_char"]
        text = fixture[selector[1:]]
        end = record["end_char"]
        need(type(start) is int and type(end) is int and 0 <= start <= end <= len(text), "VIEW_CURSOR_TYPE_OR_RANGE")
        need(record["operation"] == "field" and record["selector"] == selector and
             record["start_char"] == start and record["content"] == text[start:end] and
             record["field_chars"] == len(text) and record["field_utf8_bytes"] == len(text.encode("utf-8")) and
             record["start_utf8_byte"] == len(text[:start].encode("utf-8")) and
             record["end_utf8_byte"] == len(text[:end].encode("utf-8")) and
             record["content_chars"] == end - start and
             record["content_utf8_bytes"] == len(text[start:end].encode("utf-8")) and
             record["next_char"] == end and record["field_eof"] is (end == len(text)), "ORIGINAL_SLICE_OR_EOF_MISMATCH")
        need(end > start or start == len(text), "NO_FIELD_PROGRESS")
        token_size = len(wire(record["content"]))
        need(token_size <= view["output_cap_bytes"] - view["metadata_reserve_bytes"] and
             len(raw) - token_size + 2 <= view["metadata_reserve_bytes"], "CONTENT_OR_METADATA_CAP_EXCEEDED")
        need(call["decision"] == "ACCEPT" and call["cursor_before"] == start and call["cursor_after"] == end,
             "UNVALIDATED_CURSOR_ADVANCEMENT")
        return record

    def channel(self):
        capture = self.index("actual_channel_evidence")
        self.bound(capture)
        need(capture["format"] == "verislop.support019-observable-channel-capture/1", "CHANNEL_CAPTURE_SCHEMA")
        need(capture["unavailable"] == UNAVAILABLE and capture["cases"] ==
             ["AC002-001", "AC002-002", "AC002-003", "AC002-004"], "CHANNEL_SCOPE_OR_CASE_MISMATCH")
        large, large_ref = self.fixture(capture["fresh_fixture"])
        empty, empty_ref = self.fixture(capture["empty_fixture"])
        need(len(large["user"]) > 400000 and empty["system"] == empty["user"] == "", "FIXTURE_DOMAIN_MISMATCH")
        calls = capture["calls"]
        need(calls and all(call["unavailable"] == UNAVAILABLE and call["actual_result_forwards"] == 1 and
             call["recipe_identity_verified"] is True for call in calls), "FORWARD_OR_RECIPE_SCOPE_MISMATCH")
        for call in calls:
            self.evidence(call["submitted_code_ref"])
        full = [call for call in calls if call["case_id"] == "AC002-001"]
        need(full and full[0]["view"]["operation"] == "inventory", "FULL_FIELD_INVENTORY_MISSING")
        need(all(call["view"]["output_cap_bytes"] == 8192 and call["view"]["metadata_reserve_bytes"] == 2048
                 and call["outer_max_output_tokens"] == 20000 and call["nested_max_output_tokens"] == 16384
                 for call in full), "NORMAL_FULL_FIELD_CAPS_CHANGED")
        self.intact(full[0], large, large_ref)
        selector, cursor, completed = "/system", 0, []
        for call in full[1:]:
            need(call["kind"] == "intact" and call["view"]["selector"] == selector and
                 call["view"]["start_char"] == cursor and call["outer_max_output_tokens"] == 20000 and
                 call["nested_max_output_tokens"] == 16384, "FULL_FIELD_ORDER_OR_CAP_MISMATCH")
            record = self.intact(call, large, large_ref)
            cursor = record["next_char"]
            if record["field_eof"]:
                completed.append(selector)
                selector, cursor = "/user", 0
        need(completed == ["/system", "/user"], "FULL_FIELD_EXPLICIT_EOF_MISSING")
        for case, kind, outer, nested in (("AC002-002", "nested-fault", 20000, 256),
                                         ("AC002-003", "outer-fault", 256, 16384)):
            pair = [call for call in calls if call["case_id"] == case]
            need(len(pair) == 2, "FAULT_RETRY_PAIR_MISSING")
            fault, retry = pair
            need(fault["kind"] == kind and fault["outer_max_output_tokens"] == outer and
                 fault["nested_max_output_tokens"] == nested and fault["decision"] == "REJECT" and
                 fault["cursor_before"] == fault["cursor_after"] == fault["view"]["start_char"] == 0 and
                 fault["view"]["selector"] == "/user", "FAULT_CURSOR_OR_BUDGET_MISMATCH")
            actual = self.doc(fault["nested_result_ref"])
            need(type(actual.get("exit_code")) is int and actual["exit_code"] == 0 and
                 "session_id" not in actual, "FAULT_TOOL_COMPLETION_UNAVAILABLE")
            need(self.evidence(fault["returned_output_ref"]) == actual["output"].encode("utf-8", "strict"),
                 "FAULT_OUTPUT_IDENTITY_MISMATCH")
            if kind == "nested-fault":
                need(type(actual.get("original_token_count")) is int and actual["original_token_count"] > nested
                     and "Warning: truncated output" in actual["output"], "ACTUAL_NESTED_TRUNCATION_NOT_OBSERVED")
            else:
                need(fault["rendered_outer_truncation_observed"] is True and
                     fault["observation_scope"] == "rendered_items_only", "ACTUAL_RENDERED_OUTER_TRUNCATION_NOT_OBSERVED")
                self.evidence(fault["rendered_observation_ref"])
            need(retry["kind"] == "retry" and retry["outer_max_output_tokens"] == 20000 and
                 retry["nested_max_output_tokens"] == 16384 and retry["view"] ==
                 {"operation": "field", "selector": "/user", "start_char": 0,
                  "output_cap_bytes": 4096, "metadata_reserve_bytes": 2048}, "SAME_CURSOR_RETRY_MISMATCH")
            self.intact(retry, large, large_ref)
        zero = [call for call in calls if call["case_id"] == "AC002-004"]
        need(len(zero) == 3 and zero[0]["view"]["operation"] == "inventory", "EMPTY_INVENTORY_AND_TWO_FIELDS_MISSING")
        need(all(call["outer_max_output_tokens"] == 20000 and call["nested_max_output_tokens"] == 16384
                 for call in zero), "EMPTY_NORMAL_CAPS_CHANGED")
        self.intact(zero[0], empty, empty_ref)
        for call, selector in zip(zero[1:], ("/system", "/user")):
            need(call["view"]["selector"] == selector and call["view"]["start_char"] == 0, "EMPTY_FIELD_ORDER")
            record = self.intact(call, empty, empty_ref)
            need(record["content"] == "" and record["next_char"] == record["field_chars"] == 0
                 and record["field_eof"] is True, "EMPTY_EXPLICIT_EOF_MISSING")
        need(len(calls) == len(full) + 7, "UNREGISTERED_CHANNEL_CALL")

    def author(self):
        author = self.index("actual_author_evidence")
        self.bound(author)
        need(author["format"] == "verislop.support019-single-fresh-author-evidence/1", "AUTHOR_EVIDENCE_SCHEMA")
        need(type(author["spawn_count"]) is int and author["spawn_count"] == 1 and
             author["requested_model"] == "gpt-6.1-sol" and author["fork_turns"] == "none" and
             author["model_identity"] == author["semantic_consumption"] == "UNATTESTED",
             "FRESH_AUTHOR_COUNT_OR_IDENTITY_OVERCLAIM")
        need(self.evidence(author["submitted_message_ref"]) == self.evidence(author["expected_literal_message_ref"]),
             "PLAIN_AGENT_MESSAGE_CHANGED")
        self.fixture(author["fresh_fixture"])
        final = self.evidence(author["literal_final_ref"])
        expected = self.evidence(author["evaluator_expectations_ref"])
        need(parse(final) == parse(expected),
             "LITERAL_AUTHOR_FINAL_MARKERS_ROOTS_TOTALS_EOF_MISMATCH")
        need(author["exposed_responses_refs"] and author["evaluator_expectations_sent_to_author"] is False and
             author["replacement_author_or_resampling"] is False, "AUTHOR_HISTORY_OR_EXPECTATION_CONTAMINATION")
        for item in author["exposed_responses_refs"]:
            self.evidence(item)

    def independent_claims(self):
        checked = []
        for claim in self.claims["original_claims"] + self.claims["additional_claims"]:
            registration = self.spec["independent_claim_checks"][claim["id"]]
            need(registration["predicate_implementation_reviewed"] is True, "PREDICATE_READER_NOT_REVIEWED")
            report = self.output(registration["process_id"], registration["output_key"])
            self.bound(report)
            need(report["status"] == "VERIFIED", "INDEPENDENT_PREDICATE_READER_BLOCKED")
            rows = report[registration["claim_rows_key"]]
            matches = [row for row in rows if row["claim_id"] == claim["id"]]
            need(len(matches) == 1, "MISSING_OR_AMBIGUOUS_INDEPENDENT_CLAIM")
            row = matches[0]
            self.bound(row)
            need(row["status"] == "VERIFIED" and row["blocking_reasons"] == [] and
                 row["original_statement"] == claim["statement"] and
                 row["original_pass_condition"] == claim["pass_condition"] and
                 row["trusted_dependencies"] == claim["dependencies_trusted"] and
                 row["checked_predicates"] == registration["required_predicate_names"] and
                 row["verifier_id"] == registration["verifier_id"] and
                 row["verifier_hash"] == self.manifest["source_hashes"][registration["verifier_path"]],
                 "INDEPENDENT_CLAIM_PREDICATE_OR_VERIFIER_MISMATCH:" + claim["id"])
            need(row["raw_evidence_refs"], "CLAIM_RAW_EVIDENCE_MISSING:" + claim["id"])
            for identity in row["raw_evidence_refs"]:
                self.evidence(identity)
            checked.append(claim["id"])
        need(len(checked) == 27, "ALL27_INDEPENDENT_CLAIMS_NOT_CHECKED")
        return checked

    def finish(self):
        self.guards()
        for record in self.reads.values():
            ref(ROOT, record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualification-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--process-output-index-sha256", required=True)
    parser.add_argument("--channel-index-sha256", required=True)
    parser.add_argument("--author-index-sha256", required=True)
    args = parser.parse_args()
    output = ROOT / args.output
    need(not output.exists() and output.is_relative_to(ROOT / "validation"), "AUDIT_OUTPUT_NOT_NEW")
    report = {"format": "verislop.support019-independent-admission-report/1", "status": "BLOCKED",
              "activation_authority": False, "manual_override_allowed": False,
              "model_identity": "UNATTESTED", "semantic_consumption": "UNATTESTED", "unavailable": UNAVAILABLE,
              "blocking_reasons": [], "infrastructure_errors": [], "claim_ids": [],
              "boundary": "Only frozen finite claims plus reviewed independent predicate implementations, actual process/tool evidence and declared trust; no semantic model consumption or production activation authority."}
    code = 1
    try:
        audit = Audit(ROOT / args.qualification_root, {
            "actual_process_output_index": args.process_output_index_sha256,
            "actual_channel_evidence": args.channel_index_sha256,
            "actual_author_evidence": args.author_index_sha256})
        audit.guards()
        audit.admit_processes()
        audit.suite()
        audit.equality()
        audit.channel()
        audit.author()
        report["claim_ids"] = audit.independent_claims()
        audit.finish()
        report.update({"status": "VERIFIED", "closure_id": audit.spec["closure_id"],
                       "source_root": audit.source_root, "input_root": audit.input_root,
                       "actual_registered_processes": list(audit.processes), "evidence": audit.reads,
                       "verifier_hash": digest(Path(__file__).read_bytes())})
        code = 0
    except (Block, KeyError, ValueError, TypeError, UnicodeError) as error:
        report["blocking_reasons"].append(str(error))
    except Exception as error:
        report["status"] = "INFRASTRUCTURE_FAILURE"
        report["infrastructure_errors"].append(type(error).__name__ + ":" + str(error))
        code = 2
    output.mkdir(parents=True)
    write_once(output / "report.json", report)
    print(json.dumps({"status": report["status"], "report": str(output / "report.json"), "exit_code": code}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
