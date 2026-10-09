from pathlib import Path
import sys, os, json, hashlib, datetime
ROOT=Path('/home/augustus/VeriSlop_CLI')
STAGE=ROOT/'synthetic_dataset/bootstrap/stages/tier2-source-facets-010'
PROJECT=STAGE/'project'; RUN=STAGE/'d21-run'; PKG=RUN/'artifacts/D21/verislop/package'
OUT=Path(__file__).parent
sys.path.insert(0,str(PROJECT))
from synthetic_dataset.tools import bootstrap_tier2 as H
from verislop import canonical
checks=[]; observed={}; snapshots={}
def check(name,value,detail=None):
    row={'name':name,'pass':bool(value)}
    if detail is not None: row['detail']=detail
    checks.append(row)
    if not value: raise AssertionError(name)
def snap(path,key):
    assert path.is_file() and not path.is_symlink()
    data=path.read_bytes(); digest=canonical.digest(data)
    target=OUT/'snapshots'/key
    target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
    observed[str(path)]={'sha256':digest,'snapshot':str(target.relative_to(OUT))}
    snapshots[str(target.relative_to(OUT))]=digest
    return data
before=os.environ.get('VERISLOP_CONFIG_HOME')
with H._frozen_provider_context(RUN/'config.json'):
    protocol=H.verify_inputs(RUN)
check('frozen_input_validator_and_provider_configuration_passed',True)
check('provider_context_restored',os.environ.get('VERISLOP_CONFIG_HOME')==before)
for name in ('protocol.json','preregistration.json'):
    snap(RUN/name,'cohort/'+name)
for name,digest in protocol['input_files'].items():
    data=snap(RUN/name,'cohort/'+name)
    check('input_hash:'+name,canonical.digest(data)==digest)
for name,digest in protocol['source_files'].items():
    check('frozen_project_hash:'+name,canonical.digest_file(PROJECT/name)==digest)
    check('retained_execution_source_hash:'+name,canonical.digest_file(RUN/'execution-source'/name)==digest)
for name in ('synthetic_dataset/tools/bootstrap_tier2.py','verislop/source_policy.py','verislop/source_contract.py','schemas/required-source-facets.schema.json'):
    snap(PROJECT/name,'generic/'+name)
public=snap(ROOT/'synthetic_dataset/tasks/D21/prompt.txt','public/D21/prompt.txt')
original=(RUN/'requests/D21/original-prompt.txt').read_bytes()
revised=(RUN/'requests/D21/revised-prompt.txt').read_bytes()
meta=canonical.load_file(RUN/'requests/D21/original-metadata.json')
revision=canonical.load_file(RUN/'requests/D21/delivery-revision.json')
policy=canonical.load_file(RUN/'requests/D21/source-policy.json')
check('original_public_prompt_exact',public==original)
check('historical_positive_bytes_not_read_declared',meta['old_positive_candidate_bytes_read'] is False)
check('prior_python_assurance_unchanged',meta['previous_python_assurance']=='unchanged; no Tier 2 reinterpretation')
regen,regrev=H.revise_prompt(original,meta['identities'],operational_ids=('I1','S1'))
check('delivery_revision_exact_reconstruction',regen==revised and regrev==revision)
check('source_policy_exact_reconstruction',H.source_policy(meta['identities'],operational_ids=('I1','S1'))==policy)
check('explicit_delivery_revision_exactly_three',len(revision['edits'])==3)
check('functional_bytes_preserved_marker',revision['functional_bytes_preserved'] is True)
check('old_delivery_not_relabelled',revision['old_delivery_assurance_relabelled'] is False)
for i,s in enumerate(revision['segments']):
    if s['kind']=='preserved':
        a=original[s['original_start_byte']:s['original_end_byte']]
        b=revised[s['revised_start_byte']:s['revised_end_byte']]
        check('preserved_segment:'+str(i),a==b and canonical.digest(a)==s['sha256'])
examples=original.split(b'Public examples (additional held-out cases will be scored):\n',1)[1]
check('public_examples_exact',canonical.digest(examples)==revision['public_examples_sha256'] and examples in revised)
expected={
'D1':('declaration','entity'), 'I1':('guarantee','invariant'),
'O1':('guarantee','postcondition'),'O2':('guarantee','postcondition'),
'O3':('guarantee','postcondition'),'O4':('guarantee','postcondition'),
'O5':('guarantee','postcondition'),'O6':('guarantee','postcondition'),
'O7':('guarantee','postcondition'),'A1':('assumption','precondition'),
'S1':('guarantee','safety_property')}
ids={row['id']:row for row in meta['identities']}
check('original_identity_inventory_exact',len(ids)==len(meta['identities']) and set(ids)==set(expected))
mapping={r['id']:r for r in revision['identity_mapping']}
check('revision_identity_inventory_exact',set(mapping)==set(expected))
for key,(role,kind) in expected.items():
    row=ids[key]; mapped=mapping[key]
    check('identity_role_kind_required:'+key,(row['role'],row['kind'],row['required'])==(role,kind,True))
    check('identity_revision_role_kind_required:'+key,(mapped['role'],mapped['kind'],mapped['required'])==(role,kind,True))
    check('identity_source_span_inventory:'+key,len(row['source_spans'])==len(mapped['source_mappings']))
    for index,(span,ms) in enumerate(zip(row['source_spans'],mapped['source_mappings'])):
        check('identity_span_mapping:'+key+':'+str(index),(span['start_byte'],span['end_byte'])==(ms['original_start_byte'],ms['original_end_byte']) and 0<=span['start_byte']<span['end_byte']<=len(original))
        if not ms['delivery_revised']:
            check('unchanged_identity_clause:'+key+':'+str(index),original[span['start_byte']:span['end_byte']]==revised[ms['revised_start_byte']:ms['revised_end_byte']])
guarantees={'I1','S1'}|{'O'+str(i) for i in range(1,8)}
check('policy_exact_required_guarantee_ids',set(policy['obligations'])==guarantees)
check('policy_classification_explicit_and_default_true',revision['source_policy_classification']=={'value_required_default':True,'source_only_operational_ids':['I1','S1']})
props=['typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only']
for key,row in policy['obligations'].items():
    check('closed_source_policy_row:'+key,row=={'file':'program.vscore.json','entry':'solve','arity':1,'properties':props,'value_required':key not in {'I1','S1'}})
check('single_fresh_D21_cohort',protocol['task_order']==['D21'] and protocol['pair_order']==[{'task':'D21','arm':'verislop','pair_index':0}])
check('frozen_source_root',protocol['source_root']=='sha256:f72db4961eda28039e8e55ed5e7817ef194e0d8da50d8471aebcc7b33bf9f13f')
check('source_inventory_count',len(protocol['source_files'])==228)
check('new_preregistered_surface',all(protocol[k]==v for k,v in {'tier':2,'target':'vscore','backend_version':'0.3','endpoint':'restricted_source','require_state':'END_TO_END_VERIFIED','relay_mode':'file','fork_turns':'none','positive_candidate_arguments':[],'runtime_campaign_requested':False}.items()))
# Exact textual checks supplement the trusted manual NL correspondence review;
# these are scope-preservation checks, never a proof of an implementation.
clauses={
'input_and_only_stated_guards':"Input {events:[{group:string,time:int,value:int|null}],start:int,end:int,width:positive int,fill:'none'|'previous'}, start<=end.",
'all_names_including_out_of_range':'Groups are all unique event group names sorted lexicographically, including groups with no in-range events.',
'half_open_clipped_buckets':'For each group, emit buckets starting start,start+width,... strictly below end, each covering [bucketStart,min(bucketStart+width,end)).',
'null_exclusion_and_count':'Sum only non-null in-range values; count counts these values.',
'nonempty_sum_previous':'A nonempty bucket has value=sum and becomes previous value.',
'none_or_causal_previous':'Empty bucket value is null for fill none, or latest previous nonempty bucket sum for fill previous (null before first); empty buckets never reset previous.',
'no_before_start_seed':'Events before start never seed previous.',
'group_then_bucket_order':'Return [{group,start,count,value}] in group then bucket order.',
'zero_and_duplicates':'Zero sum is a real previous value, duplicates are counted.'}
for key,clause in clauses.items():
    check('public_functional_clause:'+key,clause.encode() in original and clause.encode() in revised)
check('normative_scalar_sort_request',b'Strings contain Unicode scalar values and lexicographic order compares scalar codepoints.' in revised)
check('normative_unbounded_integer_request',b'Arithmetic uses unbounded mathematical integers without floating point.' in revised)
check('no_added_input_bounds_request',b'There are no additional input bounds or preconditions beyond the functional specification.' in revised)
check('universal_complete_functional_request',b'Each functional guarantee requires its complete mathematical statement and universal implementation refinement' in revised)
check('mixed_functional_value_source_policy_request',b'For every value_required=true row also preserve the complete functional formula and universal source implementation refinement' in revised)
for name in ('request/prompt.txt','request/request.json','request/source-policy.json','package.json'):
    snap(PKG/name,'package/'+name)
pkgmeta=canonical.load_file(PKG/'package.json'); request=canonical.load_file(PKG/'request/request.json')
check('native_request_prompt_exact',(PKG/'request/prompt.txt').read_bytes()==revised)
check('native_request_source_policy_exact',(PKG/'request/source-policy.json').read_bytes()==canonical.dumps(policy))
check('native_request_hash_and_size',request['document_hash']==canonical.digest(revised) and request['byte_length']==len(revised))
check('native_policy_reference_exact',pkgmeta['source_policy']=={'format':'verislop.required-source-facets/0.1','path':'request/source-policy.json','sha256':canonical.digest_json(policy)})
check('native_requested_endpoint_exact',pkgmeta['requested']=={'backend_version':'0.3','endpoint':'restricted_source','policy':'strict','require_state':'END_TO_END_VERIFIED','schema_version':'0.1','target':'vscore','tier':2})
phase_paths=['contract/challenge/challenge.json','accepted/accepted-ir.json','implementation/program.vscore.json','bridges/implementation/plan.json','closure/current.json','report.json']
availability={name:(PKG/name).is_file() for name in phase_paths}
# Only request/provenance scope is judged; later-stage availability is observed,
# not silently promoted to any claim or inspected as proof in this initial audit.
for path,record in observed.items():
    check('snapshot_source_still_same:'+path,canonical.digest_file(Path(path))==record['sha256'])
manual_scope={
'domain':'Finite event list; arbitrary Unicode scalar group strings and unbounded signed event time/value/start/end/width; width > 0, start <= end, fill none or previous. No further event, group, bucket, string-length, or integer magnitude bounds occur in the functional request.',
'groups':'All distinct event names, including null-only and outside-range-only groups, scalar lexicographic order.',
'buckets':'Per group starts start+k*width strictly below end; last interval clipped at end; half-open membership. start=end produces no bucket records.',
'aggregation':'Only non-null values within the group and bucket contribute, with duplicate multiplicity and count independent of zero sum.',
'causal_state':'Previous initialized absent per group; only nonempty buckets update it; zero sum updates previous; before-start events do not seed it; empty buckets never reset it.',
'output':'Group-major then bucket-major list of exact group/start/count/value records; empty none mode null, previous mode last nonempty sum or null before first.',
'classifications':'I1/S1 are explicit approved source-only operational IDs. All corresponding causal/aggregation text remains present; later accepted-phase audit must independently establish full functional scope under O1-O7, particularly O4/O5.'}
audit={'format':'verislop.independent-readonly-scope-audit/0.1','task':'D21','stage':'tier2-source-facets-010-d21','phase':'initial_request_only','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cohort':str(RUN),'frozen_project':str(PROJECT),'source_root':protocol['source_root'],'protocol_sha256':canonical.digest_file(RUN/'protocol.json'),'input_root':protocol['input_root'],'request_set_root':protocol['request_set_root'],'conclusion':'No concrete mismatch found in bounded original-public-scope, exact request reconstruction, identity/requiredness, frozen provenance, or native request source-policy binding checks. This is not an accepted-contract or implementation verification.','checks_passed':len(checks),'checks_failed':0,'functional_scope_review':manual_scope,'required_identity_count':len(ids),'required_guarantee_count':len(guarantees),'value_required_guarantees':['O'+str(i) for i in range(1,8)],'explicit_source_only_guarantees':['I1','S1'],'artifact_availability_observation':availability,'pending':['accepted Lean formula/domain/assumptions/nonvacuity/certificate scope','actual source admission, syntax and endpoint identity','universal refinement, typed/raw coverage, adapter inverses and effect/source adequacy','per-ID transfers, mechanical closure, clean-build receipts and release review','final native/bootstrap terminal and exact retained report/gate/seal agreement'],'trust':['Natural-language correspondence in manual scope checklist','controller historical identity provenance metadata and exact copy mechanism','host Python/hash/file tooling; pinned code inspected as frozen inputs'],'restrictions_observed':['No model/provider/native/kernel/driver/closure/gate calls','No old task candidate/proof/solution, hidden case, or oracle read','No author/critic/reviewer/controller communication','No package/cohort/project/source mutation; only this new external audit directory written'],'observed_files':observed,'snapshot_root':canonical.digest_json(snapshots),'note':'Native package.json is a point-in-time request metadata observation, not lifecycle state authority. All request snapshots were rehashed unchanged after read.'}
(OUT/'checks.json').write_bytes(canonical.dumps(checks))
(OUT/'snapshot-manifest.json').write_bytes(canonical.dumps({'files':snapshots,'files_root':canonical.digest_json(snapshots)}))
(OUT/'audit.json').write_bytes(canonical.dumps(audit))
print(json.dumps({'audit':str(OUT/'audit.json'),'audit_sha256':canonical.digest_file(OUT/'audit.json'),'checks_passed':len(checks),'snapshots':len(snapshots),'availability':availability},sort_keys=True))
