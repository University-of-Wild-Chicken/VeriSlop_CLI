"""Seal this auditor's prepared stage016 input observation only."""
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/augustus/VeriSlop_CLI')
OUT = ROOT / 'validation/tier2-d21-scope-audit-016'
STAGE = ROOT / 'synthetic_dataset/bootstrap/stages/tier2-source-facets-016'
PROJECT = STAGE / 'project'
RUN = STAGE / 'run'


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def record(path):
    assert path.is_file() and not path.is_symlink()
    data = path.read_bytes()
    return {'path':str(path.relative_to(ROOT)), 'byte_length':len(data), 'sha256':digest(data)}


def write_once(path, data):
    with path.open('xb') as stream:
        stream.write(data)


plan_seal_bytes = (OUT / 'plan-seal.json').read_bytes()
assert digest(plan_seal_bytes) == (OUT / 'plan-seal.sha256').read_text().strip()
plan_seal = json.loads(plan_seal_bytes)
for row in plan_seal['files']:
    assert record(ROOT / row['path']) == row
plan = json.loads((OUT / 'frozen-plan.json').read_text())
protocol = json.loads((RUN / 'protocol.json').read_text())
pre = json.loads((RUN / 'preregistration.json').read_text())
snapshot = json.loads((PROJECT / 'TIER2-SNAPSHOT.json').read_text())
expected = {
    'source_root':'sha256:384a84056b048b5019ef0c4ea81d3a8ab81dfd0f6b08a93e305b6a39c6de229c',
    'protocol_sha256':'sha256:b83d7ef1934cdfe9df2242862568fd1b55571dde42a5c1ec2182b7daba5ad3ab',
    'request_set_root':'sha256:846461144ed0dcaec457d5a20f414910ab82a3409562919b612261adc8ac910c',
}
assert digest((RUN / 'protocol.json').read_bytes()) == expected['protocol_sha256']
assert protocol['source_root'] == snapshot['source_root'] == pre['source_root'] == expected['source_root']
assert protocol['source_files'] == snapshot['source_files'] and len(protocol['source_files']) == 240
assert protocol['request_set_root'] == pre['request_set_root'] == expected['request_set_root']
assert protocol['generation_started'] is False and pre['generation_started'] is False
assert protocol['task_order'] == ['D21'] and protocol['project_path'] == str(PROJECT)
assert (protocol['tier'],protocol['endpoint'],protocol['require_state']) == (2,'restricted_source','END_TO_END_VERIFIED')
assert (protocol['language'],protocol['semantics'],protocol['profile']) == ('vscore/0.3','vscore-semantics/0.3','data-pipeline/0.3')
assert protocol['runtime_campaign_requested'] is False and protocol['positive_candidate_arguments'] == []
assert protocol['hidden_cases_loaded'] is False and protocol['python_grader_invoked'] is False and protocol['task_oracle_invoked'] is False
assert protocol['fork_turns'] == 'none' and protocol['fresh_agent_per_request'] is True and protocol['model_identity_attested'] is False
assert protocol['independent_clean_builds'] == 2
comparisons = []
for frozen in plan['pre_generation_public_inputs']:
    if '/tier2-source-facets-015/' not in frozen['path']:
        continue
    current = RUN / 'requests/D21' / Path(frozen['path']).name
    observed = record(current)
    assert observed['sha256'] == frozen['sha256'] and observed['byte_length'] == frozen['byte_length']
    comparisons.append({'current':observed, 'frozen_public_input':frozen['path'], 'equal_bytes_by_sha256':True})
source_policy = json.loads((RUN / 'requests/D21/source-policy.json').read_text())
metadata = json.loads((RUN / 'requests/D21/original-metadata.json').read_text())
revision = json.loads((RUN / 'requests/D21/delivery-revision.json').read_text())
assert source_policy == plan['source_policy']
assert metadata['identities'] == [{k:v for k,v in item.items() if k not in ('original_clause_texts','required_facet_classification')} for item in plan['identity_metadata']]
assert revision['identity_mapping'] == plan['delivery_identity_mapping']
assert revision['public_examples_sha256'] == plan['public_examples_sha256']
top_level_names = sorted(p.name for p in RUN.iterdir())
assert set(top_level_names) == {'config.json','engineering-validation.json','execution-source','preregistration.json','protocol.json','provider-home','requests'}
helper = PROJECT / 'synthetic_dataset/tools/bootstrap_tier2.py'
code = "from pathlib import Path; import json; from synthetic_dataset.tools.bootstrap_tier2 import verify_inputs; from verislop import canonical; c=Path(" + repr(str(RUN)) + "); p=verify_inputs(c); print(json.dumps({'helper':'bootstrap_tier2.verify_inputs','status':'PASS','protocol_sha256':canonical.digest_file(c/'protocol.json'),'source_root':p['source_root'],'source_files':len(p['source_files']),'input_root':p['input_root'],'request_set_root':p['request_set_root'],'task_order':p['task_order'],'generation_started':p['generation_started']},sort_keys=True))"
process = subprocess.run(['python3','-B','-c',code],cwd=PROJECT,capture_output=True,text=True)
raw = {'invocation':['python3','-B','-c',code], 'cwd':str(PROJECT), 'exit_code':process.returncode, 'stdout':process.stdout, 'stderr':process.stderr, 'verifier_file':record(helper)}
assert process.returncode == 0 and not process.stderr
result = json.loads(process.stdout)
assert result['status'] == 'PASS' and result['source_files'] == 240
for key,value in expected.items():
    assert result[key] == value
receipt = {
    'schema_version':'verislop.independent-input-receipt/0.1',
    'audit_id':plan['audit_id'],
    'phase':'PRE_GENERATION_INPUT_RECEIPT_SEALED',
    'created_utc':datetime.now(timezone.utc).isoformat(),
    'audit_plan':record(OUT/'frozen-plan.json'),
    'audit_plan_seal':record(OUT/'plan-seal.json'),
    'current_stage':str(STAGE),
    'current_project':str(PROJECT),
    'current_run':str(RUN),
    'source_root':protocol['source_root'],
    'source_file_count':len(protocol['source_files']),
    'input_root':protocol['input_root'],
    'request_set_root':protocol['request_set_root'],
    'protocol':record(RUN/'protocol.json'),
    'preregistration':record(RUN/'preregistration.json'),
    'source_snapshot':record(PROJECT/'TIER2-SNAPSHOT.json'),
    'public_byte_comparisons':comparisons,
    'identity_count':len(metadata['identities']),
    'required_MIXED_ids':['O1','O2','O3','O4','O5','O6','O7'],
    'required_source_only_ids':['I1','S1'],
    'functional_scope_result':'CHECKED: exact retained PUBLIC bytes match frozen plan; no changed clauses, domain, examples, identities or source policy.',
    'generic_input_integrity_result':result,
    'generic_verifier_execution':raw,
    'execution_environment':{'os':platform.platform(),'runtime':platform.python_version()},
    'run_top_level_inventory':top_level_names,
    'native_generation_observation':'Protocol/preregistration record generation_started=false; current run contains prepared inputs only. No native artifacts or candidates were read.',
    'current_protocol_trust':protocol['trust'],
    'current_protocol_excluded':protocol['excluded'],
    'verification_boundary':'This receipt CHECKS prepared public scope and generic input integrity only. No actual formalization, non-vacuity derivation, candidate, acceptance, universal refinement, task closure A/B or release evidence yet exists in this observation; no task assurance inferred.',
    'engineering_note':'Engineering validation is hashed as a protocol input by the frozen helper; fixture solutions/proofs and old package content were not inspected.',
    'model_identity_attestation':False,
    'next_action':'Auditor STOP after receipt; resume only on root terminal callback after authors terminate.',
}
receipt_path = OUT / 'input-receipt.json'
write_once(receipt_path,(json.dumps(receipt,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode())
seal = {'schema_version':'verislop.scope-audit-seal/0.1','audit_id':plan['audit_id'],'phase':receipt['phase'],'files':[record(receipt_path),record(Path(__file__))]}
data = (json.dumps(seal,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
write_once(OUT/'input-receipt-seal.json',data)
write_once(OUT/'input-receipt-seal.sha256',(digest(data)+'\n').encode())
print(json.dumps({'receipt':str(receipt_path.relative_to(ROOT)),'receipt_sha256':record(receipt_path)['sha256'],'seal_sha256':digest(data),'phase':receipt['phase'],'source_files':len(protocol['source_files']),'public_files_equal':len(comparisons),'identities':len(metadata['identities'])},sort_keys=True))
