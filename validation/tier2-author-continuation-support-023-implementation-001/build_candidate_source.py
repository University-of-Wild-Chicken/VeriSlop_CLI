"""Registered candidate-only narrow source construction; no verifier invocation."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import os

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "validation/tier2-support-019-qualification-adapters-008"
CLAIMS = ROOT / "validation/tier2-support-019-qualification-plan-012/claims.json"
ROOT_SPEC = ROOT / "validation/tier2-author-continuation-support-023-design/SPECIFICATION_BEFORE_IMPLEMENTATION.json"

def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def put(name, value):
    (HERE / name).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")

def method(data, class_name, name):
    tree = ast.parse(data)
    parent = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    node = next(node for node in parent.body if isinstance(node, ast.FunctionDef) and node.name == name)
    lines = data.decode().splitlines(keepends=True)
    return node, "".join(lines[node.lineno-1:node.end_lineno])

def replace_method(raw, class_name, replacement):
    node, old = method(raw, class_name, "fresh_author")
    lines = raw.decode().splitlines(keepends=True)
    return ("".join(lines[:node.lineno-1]) + replacement + "".join(lines[node.end_lineno:])).encode()

inputs = [BASE / name for name in ("predicate_reader.py", "additional_predicates.py", "assemble_ancillary_indexes.py")] + [CLAIMS, ROOT_SPEC]
before = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in inputs}
assert before[str(ROOT_SPEC.relative_to(ROOT))] == "sha256:913a01bd45c3ef828adf93b840ca0a47f8bfead9e7f104f697777d8f3a1b18a4"
for source in inputs:
    target = HERE / "preimages" / source.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())

reader = (BASE / "predicate_reader.py").read_bytes()
_, reader_method = method(reader, "Reader", "fresh_author")
reader_method = reader_method.replace("verislop.support019-single-fresh-author-evidence/1", "verislop.support023-single-fresh-author-evidence/1")
needle = "        need(self.fresh_ref(author['submitted_message_ref'])==self.fresh_ref(author['expected_literal_message_ref'])==message, 'ORIGINAL_PLAIN_AGENT_MESSAGE_BYTES_CHANGED')\n"
addition = """        contract=self.adapters['author_contract']['continuation_contract_source']
        need(type(contract) is dict and set(contract)=={'path','sha256'} and self.hashes.get(contract['path'])==contract['sha256'], 'CONTINUATION_HELPER_NOT_FROZEN')
        self.ref(contract)
        definition=importlib.util.spec_from_file_location('support023_registered_continuation_contract',self.path(contract['path']))
        need(definition is not None and definition.loader is not None,'CONTINUATION_HELPER_IMPORT')
        continuation=importlib.util.module_from_spec(definition); definition.loader.exec_module(continuation)
        need(wire(self.adapters['author_turn_policy'])==wire(continuation.POLICY),'CONTINUATION_POLICY_NOT_FROZEN')
        turn_result=continuation.validate_turn_ledger(author,self.fresh_ref,message,self.hashes)
        need(turn_result['structurally_complete'] is True,'CONTINUATION_BUDGET_EXHAUSTED')
"""
assert reader_method.count(needle) == 1
reader_method = reader_method.replace(needle, needle + addition)
(HERE / "predicate_reader.py").write_bytes(replace_method(reader, "Reader", reader_method))

additional = (BASE / "additional_predicates.py").read_bytes()
_, additional_method = method(additional, "AdditionalPredicates", "fresh_author")
additional_method = additional_method.replace("verislop.support019-single-fresh-author-evidence/1", "verislop.support023-single-fresh-author-evidence/1")
needle = "                expected_message, \"ORIGINAL_PLAIN_AUTHOR_MESSAGE_NOT_EXACT\")\n"
addition = """        contract = self.config["author_contract"]["continuation_contract_source"]
        require(type(contract) is dict and set(contract) == {"path", "sha256"} and self.hashes.get(contract["path"]) == contract["sha256"], "CONTINUATION_HELPER_NOT_FROZEN")
        self.read(self.path(contract["path"]), contract["sha256"])
        continuation = self.module("support023_registered_continuation_contract", self.path(contract["path"]))
        require(self.canonical.dumps(self.config["author_turn_policy"]) == self.canonical.dumps(continuation.POLICY), "CONTINUATION_POLICY_NOT_FROZEN")
        turn_result = continuation.validate_turn_ledger(index, self.additional_ref, expected_message, self.hashes)
        require(turn_result["structurally_complete"] is True, "CONTINUATION_BUDGET_EXHAUSTED")
"""
assert additional_method.count(needle) == 1
additional_method = additional_method.replace(needle, needle + addition)
(HERE / "additional_predicates.py").write_bytes(replace_method(additional, "AdditionalPredicates", additional_method))

assembler = (BASE / "assemble_ancillary_indexes.py").read_text()
assembler = assembler.replace('(\"author\",args.author_records,\"verislop.support019-single-fresh-author-evidence/1\",', '(\"author\",args.author_records,\"verislop.support023-single-fresh-author-evidence/1\",')
needle = "            if not (descriptor[\"model_identity\"]==descriptor[\"semantic_consumption\"]==\"UNATTESTED\"): raise ValueError(\"Unattested model boundary\")\n"
addition = """            import importlib.util
            contract=spec["adapters"]["author_contract"]["continuation_contract_source"]
            if not (type(contract) is dict and set(contract)=={"path","sha256"} and frozen_hashes.get(contract["path"])==contract["sha256"]):
                raise ValueError("Continuation helper not frozen")
            helper_path=ROOT/contract["path"]
            if read(helper_path)[1]["sha256"]!=contract["sha256"]: raise ValueError("Continuation helper changed")
            definition=importlib.util.spec_from_file_location("support023_registered_continuation_contract",helper_path)
            if definition is None or definition.loader is None: raise ValueError("Continuation helper import")
            continuation=importlib.util.module_from_spec(definition); definition.loader.exec_module(continuation)
            if wire(spec["adapters"]["author_turn_policy"])!=wire(continuation.POLICY): raise ValueError("Continuation policy not frozen")
            continuation.validate_turn_ledger(descriptor,lambda identity:fresh(identity)[0],submitted,frozen_hashes)
"""
assert assembler.count(needle) == 1
assembler = assembler.replace(needle, needle + addition)
(HERE / "assemble_ancillary_indexes.py").write_text(assembler)

claims = json.loads(CLAIMS.read_bytes())
new_claims = copy.deepcopy(claims)
claim = next(item for item in new_claims["additional_claims"] if item["id"] == "Q019-07")
claim["statement"] = "Exactly one fresh requested Sol author session with fork none receives the exact full frozen seed and own new unrelated carrier; every bounded same-session corrective turn and literal is retained, feedback contains only deterministic public structural counterexamples, and the first structurally complete literal or last budget-exhausted literal is selected unchanged without replacement sampling. Only exact private evaluator equality can pass."
claim["pass_condition"] = "fresh_author_spawn_count == 1 && requested_model == gpt_6_1_sol && fork_turns == none && final_root_bound && original_plain_agent_message_exact && own_new_unrelated_input_only && separate_continuation_inventory_exact && same_target_all_turns && followups <= 32 && author_turns <= 33 && deterministic_public_feedback_only && frozen_guards_unchanged_each_turn && first_structural_success_or_last_exhausted_literal_selected && all_literal_FINALs_unchanged && terminal_syntax_markers_roots_totals_EOF_exact && all_exposed_failures_preserved && identity_and_consumption_UNATTESTED"
boundary = next(item for item in new_claims["additional_claims"] if item["id"] == "Q019-08")
boundary["statement"] += " In this prospective revision ancillary_fresh_author_calls=1 counts the single fresh spawn only; at most32 same-session corrective followups are separately frozen and reported, without changing existing task/provider/ballot/repair/probe/transport limits."
assert claims["original_claims"] == new_claims["original_claims"]
assert all(left == right for left, right in zip(claims["additional_claims"],new_claims["additional_claims"]) if left["id"] not in ("Q019-07","Q019-08"))
put("candidate-claims.json", new_claims)
put("CLAIM_AND_COUNTING_AMENDMENT.json", {"format":"verislop.support023-candidate-claim-amendment/1", "authority":"SOURCE_ONLY_NO_QUALIFICATION_AUTHORITY", "changed_additional_claims":["Q019-07","Q019-08"], "unchanged_original_claims":18, "unchanged_other_additional_claims":7, "existing_ancillary_fresh_author_calls_meaning":"fresh_spawn_count; prospective revision only, never reinterpret prior roots", "new_author_turn_policy":{"max_corrective_followups":32,"max_author_turns":33,"ancillary_fresh_author_calls_meaning":"fresh_spawn_count","inference_timeout":None,"retrieval_timeout":None,"review_timeout":None}, "future_configuration_bindings":{"author_contract.continuation_contract_source":{"path":str((HERE/"continuation_contract.py").relative_to(ROOT)),"sha256":sha((HERE/"continuation_contract.py").read_bytes())},"author_turn_policy":"exact new_author_turn_policy above in adapters configuration"}, "unchanged_private_evaluator":True, "no_old_PASS_inheritance":True})
after = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in inputs}
assert before and before == after
put("SOURCE_CONSTRUCTION_OBSERVATION.json", {"actual_builder_pid":os.getpid(),"inputs_before":before,"inputs_after":after,"guards_unchanged":True,"candidate_only":True})
print(json.dumps({"actual_builder_pid":os.getpid(),"source_guard_count":len(before),"guards_unchanged":True,"helper_sha256":sha((HERE/"continuation_contract.py").read_bytes())}),flush=True)
