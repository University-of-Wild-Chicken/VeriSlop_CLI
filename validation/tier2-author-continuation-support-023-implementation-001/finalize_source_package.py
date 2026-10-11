"""Seal source-only evidence already produced by the registered finite controls."""
from pathlib import Path
import ast
import hashlib
import json
import os

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(raw):
    return "sha256:"+hashlib.sha256(raw).hexdigest()
def identity(path):
    raw=path.read_bytes()
    return {"path":str(path.relative_to(ROOT)),"sha256":sha(raw),"byte_count":len(raw)}
def put(name,value):
    (HERE/name).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")
registration=json.loads((HERE/"CONTROL_REGISTRATION_BEFORE_EXECUTION.json").read_bytes())
receipt=json.loads((HERE/"source-controls-001/actual-process-receipt.json").read_bytes())
assert type(receipt["pid"]) is int and receipt["pid"]>0 and type(receipt["returncode"]) is int and receipt["returncode"]==0
assert receipt["guards_before"]==receipt["guards_after"]==registration["guards"] and receipt["all_guards_unchanged"] is True
assert receipt["argv"]==registration["argv"] and len(registration["test_ids"])==16
for name,digest in registration["guards"].items():
    assert sha((ROOT/name).read_bytes())==digest
for stream in ("stdout","stderr"):
    actual=identity(ROOT/receipt[stream]["path"])
    assert actual==receipt[stream]
log=(HERE/"source-controls-001/stderr.log").read_text()
assert "Ran 16 tests" in log and log.endswith("\nOK\n")
assert all(name.rsplit(".",1)[1]+" (" in log for name in registration["test_ids"])
baseline=HERE/"preimages/validation/tier2-support-019-qualification-adapters-008"
source_map={name:identity(HERE/name) for name in ("continuation_contract.py","predicate_reader.py","additional_predicates.py","assemble_ancillary_indexes.py")}
def functions(raw,class_name):
    tree=ast.parse(raw)
    cls=next(item for item in tree.body if isinstance(item,ast.ClassDef) and item.name==class_name)
    return {item.name:sha(ast.dump(item,include_attributes=False).encode()) for item in cls.body if isinstance(item,ast.FunctionDef)}
preservation={}
for name,cls in (("predicate_reader.py","Reader"),("additional_predicates.py","AdditionalPredicates")):
    old=functions((baseline/name).read_bytes(),cls); new=functions((HERE/name).read_bytes(),cls)
    assert set(old)==set(new) and [key for key in old if old[key]!=new[key]]==["fresh_author"]
    preservation[name]={"changed_methods":["fresh_author"],"all_other_method_AST_hashes":{key:value for key,value in old.items() if key!="fresh_author"},"original_source":identity(baseline/name),"candidate_source":source_map[name]}
old_claims=json.loads((HERE/"preimages/validation/tier2-support-019-qualification-plan-012/claims.json").read_bytes())
new_claims=json.loads((HERE/"candidate-claims.json").read_bytes())
assert old_claims["original_claims"]==new_claims["original_claims"]
changed={old["id"]:sorted(key for key in set(old)|set(new) if old.get(key)!=new.get(key)) for old,new in zip(old_claims["additional_claims"],new_claims["additional_claims"]) if old!=new}
assert changed=={"Q019-07":["pass_condition","statement"],"Q019-08":["statement"]}
put("SOURCE_FIDELITY.json",{"format":"verislop.support023-source-fidelity/1","status":"SOURCE_CONTROLS_COMPLETE_UNQUALIFIED","source_map":source_map,"predicate_preservation":preservation,"normalized_whole_module_AST_projection":"Registered controls13/14 independently removed only closed new extension nodes and author-format scalar; all three whole-module ASTs equal raw008 baselines","private_evaluator":"Control15 directly exercised each new fresh_author method with complete wrong synthetic answers and observed the unchanged private mismatch exception; unrelated matching synthetic equality still succeeds without attesting consumption","changed_claim_fields":changed,"original18_preserved":True,"other7additional_claims_preserved":True,"other26claim_predicate_methods_preserved":True,"authority":False})
policy={"max_corrective_followups":32,"max_author_turns":33,"ancillary_fresh_author_calls_meaning":"fresh_spawn_count","inference_timeout":None,"retrieval_timeout":None,"review_timeout":None}
put("CONTINUATION_API_AND_FUTURE_BINDINGS.json",{"format":"verislop.support023-source-api-handoff/1","authority":"SOURCE_ONLY_NO_QUALIFICATION_AUTHORITY","helper":source_map["continuation_contract.py"],"pure_APIs":{"critique(raw_bytes)":"Public deterministic schema report; structurally_complete and counterexamples; acceptance_authority false; no expectation values","render_feedback(raw_bytes)":"Exact UTF8 fixed text+canonical critique; refuses structurally complete input","validate_turn_ledger(index,read_raw_ref_callback,expected_seed_bytes,expected_guards)":"Full separate spawn/continuation/turn/literal/guard/hash/policy/terminal binding; returns structural summary with acceptance_authority false"},"new_author_evidence_format":"verislop.support023-single-fresh-author-evidence/1","configuration":{"author_contract.continuation_contract_source":{"path":source_map["continuation_contract.py"]["path"],"sha256":source_map["continuation_contract.py"]["sha256"]},"author_turn_policy":policy,"ancillary_fresh_author_calls":1,"ancillary_fresh_author_calls_meaning":"fresh_spawn_count; new revision only"},"artifact_refs":"Exact path/sha256/byte_count; all paths current fresh prefixes enforced by caller","initial_spawn":"Original complete reconstructed frozen message, one actual singleton task_name native response, model gpt-6.1-sol/forknone","continuation_request":"Exact native followup_task arguments {target,message}; actual canonical target only; message decodeUTF8(render_feedback(previous unchanged FINAL))","followup_result":"Retain actual opaque native response bytes, not invented schema/PID/completion metadata","critic_artifact":"wire(critique(raw)) compact sorted JSON UTF8 without appended newline","guards":"Exact complete frozen source/input map before and after EVERY turn; collection/authentication responsibility remains explicit existing orchestration TCB","responses":"Top exposed_responses_refs equals flattened turn refs, distinct ordered response paths; each turn retains the literal raw bytes in exposed raw content","terminal":"First structurally complete FINAL; no subsequent followups; or final turn32 at exact budget exhaustion, BLOCKED. Every earlier literal retained unchanged. Private evaluator equality unchanged.","future_integration":"Root authorizes new adapters009/plan013/controller/config/materializer/schema registration and a fresh frozen root; current Q007 remains terminal blocked and immutable; no old PASS inheritance","trust":"Both candidate author predicates authenticate the same registered pure ledger helper; this is shared validation code, not two independently implemented ledger algorithms. Private equality bodies and all other predicate methods remain exact."})
put("SOURCE_READINESS.json",{"format":"verislop.support023-source-readiness/1","status":"SOURCE_READY_UNQUALIFIED","actual_finalizer_pid":os.getpid(),"registered_tests":16,"actual_process_receipt":identity(HERE/"source-controls-001/actual-process-receipt.json"),"actual_test_PID":receipt["pid"],"actual_integer_returncode":receipt["returncode"],"nonempty_guard_count":len(registration["guards"]),"all_guards_unchanged":True,"synthetic_observations":"SYNTHETIC_SOURCE_CONTROL_NO_ACTUAL_AGENT","runtime_model_qualification_native_Lean_task_calls":0,"production_mutated":False,"frozen_inputs_mutated":False,"sources":source_map,"source_fidelity":identity(HERE/"SOURCE_FIDELITY.json"),"API_handoff":identity(HERE/"CONTINUATION_API_AND_FUTURE_BINDINGS.json"),"historical_cause":"UNKNOWN","acceptance_proof_TESTED_admission_activation_authority":False})
files={str(path.relative_to(ROOT)):{"sha256":sha(path.read_bytes()),"byte_count":len(path.read_bytes())} for path in sorted(HERE.rglob("*")) if path.is_file() and path.name not in ("hash-manifest.json","SEAL.sha256")}
inputs={name:{"sha256":digest,"byte_count":len((ROOT/name).read_bytes())} for name,digest in registration["guards"].items() if not (ROOT/name).is_relative_to(HERE)}
put("hash-manifest.json",{"format":"verislop.support023-source-manifest/1","status":"SOURCE_READY_UNQUALIFIED","files":files,"inputs":inputs,"authority":False})
digest=hashlib.sha256((HERE/"hash-manifest.json").read_bytes()).hexdigest()
(HERE/"SEAL.sha256").write_text(digest+"  hash-manifest.json\n")
print(json.dumps({"actual_finalizer_pid":os.getpid(),"readiness":identity(HERE/"SOURCE_READINESS.json"),"fidelity":identity(HERE/"SOURCE_FIDELITY.json"),"manifest":identity(HERE/"hash-manifest.json"),"seal":identity(HERE/"SEAL.sha256"),"own_files":len(files),"stable_inputs":len(inputs)}),flush=True)
