"""Build prospective static configuration only; imports no target modules.

This source uses only pathlib/AST/JSON/hash operations on generic definitions.
It does not run qualification, tests, a materializer, tools, Lean or a model.
"""
from pathlib import Path
import ast
import copy
import hashlib
import json
import sys

ROOT = Path(__file__).absolute().parents[2]
BASE = Path(__file__).absolute().parent
Q = 'validation/tier2-support-019-qualification-006'
CLOSURE = 'support019-final-current-root-006'
FIX = 'validation/tier2-support019-registration-inputs-006/fixture-current-whole-gate-006'
PLAN = 'validation/tier2-support-019-qualification-plan-011'
ADAPTERS = 'validation/tier2-support-019-qualification-adapters-008'
ORCH = 'validation/tier2-support019-orchestration-003'
EQ = 'validation/tier2-support019-equality-producers-005'
PURE = 'validation/tier2-support019-core-drivers-005'
RECORDER = 'validation/tier2-support019-channel-recorder-002'
CORE = 'validation/tier2-support019-core-drivers-001'
UNICODE = 'validation/tier2-unicode-literal-support-018'
GROUND = 'validation/tier2-ground-replay-support-018-design'
PYTHON = str(Path(sys.executable).resolve())
RELBASE = BASE.relative_to(ROOT).as_posix()
REG = 'validation/tier2-support019-registration-inputs-006'
PREFLIGHT = REG + '/preflight-006/stdout.log'
CANDIDATE = 'validation/tier2-support019-author-recovery-implementation-006'
PRODUCTION = 'synthetic_dataset/tools/bootstrap_tier2_carrier_view.py'
CHECKPOINT_TESTS = 'tests/test_tier2_carrier_checkpoints.py'
OLD_CONFIGURATION = 'validation/tier2-support019-final-configuration-002'
EXPECTED_CARRIER = 'sha256:f855de49fa8522cfc91053fe3f1f0db1ebd3c199260acbb97618d0f998c5eb4a'


def raw(name):
    p = Path(name)
    if not p.is_absolute(): p = ROOT / p
    if not p.is_file() or p.is_symlink() or p.resolve() != p.absolute():
        raise ValueError('Not a direct registered source/input: ' + str(p))
    return p.read_bytes()


def sha(data): return 'sha256:' + hashlib.sha256(data).hexdigest()
def load(name): return json.loads(raw(name).decode('utf-8'))
def wire(value): return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
def reference(name):
    data = raw(name)
    return {'path':name,'sha256':sha(data),'byte_count':len(data)}


def write(name, value, binary=False):
    path = BASE / name
    if not path.parent.is_relative_to(BASE): raise ValueError('Owned directory only')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(value if binary else (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=True,allow_nan=False)+'\n').encode())
    return reference(path.relative_to(ROOT).as_posix())


def expand(value):
    if type(value) is str:
        return value.replace('{qualification_root}',Q).replace('{repository_root}',str(ROOT)).replace('{python}',PYTHON)
    if type(value) is list: return [expand(v) for v in value]
    if type(value) is dict: return {k:expand(v) for k,v in value.items()}
    return value


def literal(node, names):
    if isinstance(node,ast.Name): return names[node.id]
    if isinstance(node,ast.Dict): return {literal(k,names):literal(v,names) for k,v in zip(node.keys,node.values)}
    if isinstance(node,(ast.List,ast.Tuple)): return [literal(v,names) for v in node.elts]
    return ast.literal_eval(node)


def strict_policy(path):
    tree=ast.parse(raw(path).decode()); values={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='BASELINE_AXIOMS':
            values['BASELINE_AXIOMS']=ast.literal_eval(node.value)
        if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id=='POLICIES':
            return literal(node.value,values)['strict']
    raise ValueError('Registered strict policy AST absent')


def original_slice(case, carrier):
    # Independent finite prefix calculation over new unrelated fields only.
    text=carrier['user']; cap,reserve=case['output_cap_bytes'],case['metadata_reserve_bytes']
    def value(end):
        content=text[:end]
        return {'format':'verislop.exact-carrier-view/0.1','status':'ok','carrier_path':case['literal_carrier_path'],
            'carrier_raw_bytes':case['carrier_raw_bytes'],'carrier_sha256':case['expected_carrier_sha256'],
            'request_sha256':carrier['request_sha256'],'request_id':carrier['request_id'],
            'char_unit':'decoded_unicode_code_points','byte_unit':'decoded_field_utf8','output_cap_bytes':cap,
            'metadata_reserve_bytes':reserve,'operation':'field','selector':'/user','field_chars':len(text),
            'field_utf8_bytes':len(text.encode()),'start_char':0,'end_char':end,'start_utf8_byte':0,
            'end_utf8_byte':len(content.encode()),'content_chars':end,'content_utf8_bytes':len(content.encode()),
            'content':content,'next_char':end,'field_eof':end==len(text)}
    end=min(len(text),cap-reserve)
    while end>=0:
        record=value(end)
        if len(wire(dict(record,content='')))+1<=reserve and len(wire(record['content']))<=cap-reserve and len(wire(record))+1<=cap:
            if end==0 and text: raise ValueError('No registered content capacity')
            return wire(record)+b'\n'
        end-=1
    raise ValueError('Registered metadata cannot fit')


def need(ok, code):
    if not ok:
        raise ValueError('PREPARATION_CAPABILITY_UNAVAILABLE:' + code)


def authenticate(identity):
    need(type(identity) is dict and set(identity)=={'path','sha256','byte_count'},'REFERENCE_SHAPE')
    need(type(identity['path']) is str and type(identity['byte_count']) is int and identity['byte_count']>=0,'REFERENCE_TYPES')
    actual=reference(identity['path'])
    need(actual==identity,'SOURCE_IDENTITY_CHANGED:'+identity['path'])
    return actual


def guard_dependencies(files):
    need(type(files) is dict and files,'DEPENDENCY_MAP_EMPTY')
    for name,identity in files.items():
        need(type(name) is str and identity['path']==name,'DEPENDENCY_PATH_MISMATCH')
        need(not name.startswith(('validation/tier2-support-019-qualification-001/','validation/tier2-support-019-qualification-002/','validation/tier2-support-019-qualification-003/','validation/tier2-support-019-qualification-004/','validation/tier2-support-019-qualification-005/')),
             'HISTORICAL_QUALIFICATION_RUNTIME_INPUT_FORBIDDEN:'+name)
        authenticate(identity)


def checkpoint_ids_from_source():
    # This derives source identities, never imports or collects the test module.
    tree=ast.parse(raw(CHECKPOINT_TESTS).decode('utf-8','strict'))
    classes=[node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='CarrierCheckpointTests']
    need(len(classes)==1,'CHECKPOINT_CLASS_NOT_SINGLE')
    methods=[node.name for node in classes[0].body if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')]
    need(len(methods)==len(set(methods))==17,'CHECKPOINT_METHOD_SOURCE_IDENTITY_COUNT')
    return sorted('tests.test_tier2_carrier_checkpoints.CarrierCheckpointTests.'+name for name in methods)


def manifest_guard(package, dependency_hashes):
    # Seals authenticate static source packages only; they are never input roots.
    need(type(package) is dict and set(package)=={'manifest','seal','entry_maps'},'SOURCE_PACKAGE_REFERENCE_SHAPE')
    manifest_ref=authenticate(package['manifest']); seal_ref=authenticate(package['seal'])
    for identity in (manifest_ref,seal_ref):
        need(dependency_hashes.get(identity['path'])==identity,'SOURCE_PACKAGE_NOT_IN_DEPENDENCY_MAP')
    tokens=raw(seal_ref['path']).decode('ascii','strict').strip().split()
    need(len(tokens) in (1,2) and tokens[0].removeprefix('sha256:')==manifest_ref['sha256'][7:],'SOURCE_SEAL_MISMATCH')
    if len(tokens)==2:
        need(tokens[1]==Path(manifest_ref['path']).name,'SOURCE_SEAL_MANIFEST_NAME')
    manifest=load(manifest_ref['path'])
    need(type(package['entry_maps']) is list and package['entry_maps'],'SOURCE_PACKAGE_ENTRY_MAPS_EMPTY')
    for map_name in package['entry_maps']:
        entries=manifest[map_name]
        need(type(entries) is dict and entries,'SOURCE_MANIFEST_MAP_EMPTY')
        for name,value in entries.items():
            path=name if name.startswith(('/', 'validation/','synthetic_dataset/','tests/','verislop/','docs/','formal/','grammar/','policies/','schemas/')) else (Path(manifest_ref['path']).parent/name).as_posix()
            data=raw(path)
            expected=value if type(value) is str else value['sha256']
            need(sha(data)==expected,'SOURCE_MANIFEST_HASH_CHANGED:'+path)
            if type(value) is dict:
                size_key=next((key for key in ('byte_count','bytes','size') if key in value),None)
                if size_key is not None:
                    need(type(value[size_key]) is int and len(data)==value[size_key],'SOURCE_MANIFEST_SIZE_CHANGED:'+path)
            need(path in dependency_hashes,'SOURCE_MANIFEST_FILE_UNREGISTERED:'+path)


def validate_preflight(preflight,floor,checkpoint_ids):
    need(preflight['format'] in ('verislop.support018-suite-preflight/1','verislop.support019-suite-preflight/1'),'PREFLIGHT_FORMAT')
    need(type(preflight['tests_executed']) is int and preflight['tests_executed']==0 and
         type(preflight['model_calls']) is int and preflight['model_calls']==0 and preflight['task_inputs'] is False,'PREFLIGHT_EXECUTION_BOUNDARY')
    ids,modules=preflight['test_ids'],preflight['test_modules']
    need(type(ids) is list and all(type(value) is str and value for value in ids) and len(ids)==len(set(ids)) and
         type(preflight['test_count']) is int and preflight['test_count']==len(ids),'CURRENT_EXACT_TEST_ID_INVENTORY')
    need(type(modules) is list and all(type(value) is str and value for value in modules) and len(modules)==len(set(modules)),'CURRENT_EXACT_MODULE_INVENTORY')
    need(len(floor['registered_test_ids'])==180 and len(floor['test_modules'])==15 and
         set(floor['registered_test_ids']).issubset(ids) and set(floor['test_modules']).issubset(modules),'MANDATORY180_15_FLOOR')
    old=load(OLD_CONFIGURATION+'/final-config.json')
    need(len(old['registered_test_ids'])==191 and len(old['test_modules'])==17 and
         set(old['registered_test_ids']).issubset(ids) and set(old['test_modules']).issubset(modules),'ALL_PRIOR191_17_SOURCE_IDENTITIES_PRESERVED')
    need(checkpoint_ids==checkpoint_ids_from_source() and set(checkpoint_ids).issubset(set(ids)-set(floor['registered_test_ids'])),'EXACT_CHECKPOINT_IDS_NOT_CURRENT')
    for field in ('source_files','test_sources'):
        entries=preflight[field]
        need(type(entries) is dict and entries,'PREFLIGHT_INVENTORY_MAP_EMPTY:'+field)
        for name,expected in entries.items():
            need(sha(raw(name))==expected,'PREFLIGHT_CURRENT_FILE_HASH:'+name)
    # The test map must have exact current paths, without importing any tests.
    current_tests={path.relative_to(ROOT).as_posix() for path in (ROOT/'tests').rglob('*.py') if path.is_file()}
    need(set(preflight['test_sources'])==current_tests,'PREFLIGHT_TEST_PATH_SET_STALE')
    registration=load(PLAN+'/source-inventory-registration.json')
    current_sources=set(registration['transport_files'])
    for directory,suffixes in registration['directory_suffixes'].items():
        current_sources.update(path.relative_to(ROOT).as_posix() for path in (ROOT/directory).rglob('*') if path.suffix in suffixes)
    current_sources.update(name for name in registration['optional_root_files'] if (ROOT/name).exists())
    need((ROOT/registration['required_source_file']).is_file() and set(preflight['source_files'])==current_sources,
         'PREFLIGHT_SOURCE_PATH_SET_STALE')
    need(sha(wire(preflight['source_files']))==preflight['source_root'],'PREFLIGHT_SOURCE_ROOT_DERIVATION')


def validate_current_bindings():
    # An unresolved source preparation has no executable substitute for this file.
    handoff=BASE/'generation-inputs-ready.json'
    need(handoff.is_file(),'ROOT_GENERATION_INPUT_HANDOFF_MISSING')
    ready=load(handoff)
    need(ready['status']=='ROOT_SOURCE_REVIEWED_READY_FOR_CONFIGURATION_GENERATION' and
         ready['actual_execution']==0 and ready['qualification_authority'] is False and ready['activation_authority'] is False,'ROOT_SOURCE_READY_HANDOFF_STATUS')
    need(ready['qualification_root']==Q and ready['closure_id']==CLOSURE and ready['input_root'] is None,'ROOT_HANDOFF_SCOPE')
    dependencies=ready['source_dependencies']
    guard_dependencies(dependencies)
    for identity in (ready['preflight'],ready['fixture_map'],ready['capture_registration']):
        authenticate(identity)
        need(dependencies.get(identity['path'])==identity,'HANDOFF_REFERENCE_NOT_BOUND')
    need(ready['preflight']['path']==PREFLIGHT and ready['fixture_map']['path']==REG+'/fresh-fixture-input-map.json' and
         ready['capture_registration']['path']==REG+'/capture003-registration.json','EXACT_CURRENT_PREPARATION_PATHS')
    mandatory=[PREFLIGHT,REG+'/preflight-006/actual-process-receipt.json',REG+'/preflight-006/registration-before-execution.json',
               REG+'/preflight-006/specification.json',REG+'/preflight-006/stderr.log',
               REG+'/fresh-fixture-input-map.json',REG+'/source-installation-observation.json',
               REG+'/checkpoint-control-identities.json',REG+'/CAPTURE003_REGISTRATION_SPECIFICATION_BEFORE_GENERATION.json',
               PRODUCTION,CHECKPOINT_TESTS,CANDIDATE+'/bootstrap_tier2_carrier_view.py',CANDIDATE+'/capture-amendment-003/collector_templates.py',
               PLAN+'/claims.json',PLAN+'/mandatory-floor.json',PLAN+'/materialize_registration.py',
               ADAPTERS+'/author_protocol_reconstruction.py',REG+'/fresh-author-carrier-literals-006.json',REG+'/fresh-author-capture-literals-006.json',
               PURE+'/verify_carrier_controls.py',PURE+'/WITNESS_SCHEMA.json',OLD_CONFIGURATION+'/final-config.json']
    need(set(mandatory).issubset(dependencies),'MANDATORY_CURRENT_SOURCE_DEPENDENCIES_MISSING')
    preflight_registration=load(REG+'/preflight-006/registration-before-execution.json')
    preflight_receipt=load(REG+'/preflight-006/actual-process-receipt.json')
    expected_argv=[PYTHON,str(ROOT/CORE/'gate.py'),'preflight','--qualification-root',str(ROOT/Q),
                   '--spec',str(ROOT/REG/'preflight-006/specification.json')]
    need(preflight_registration['argv']==expected_argv==preflight_receipt['argv'] and
         preflight_registration['cwd']==preflight_receipt['cwd']==str(ROOT) and
         preflight_registration['environment']==preflight_receipt['registered_environment']=={'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'} and
         preflight_registration['timeout_seconds'] is None and preflight_receipt['timeout_seconds'] is None and
         type(preflight_receipt['pid']) is int and preflight_receipt['pid']>0 and
         type(preflight_receipt['returncode']) is int and preflight_receipt['returncode']==0 and
         preflight_receipt['timed_out'] is False and preflight_receipt['qualification_authority'] is False and
         preflight_receipt['stdout']==ready['preflight'],'ACTUAL_REGISTERED_NONEXECUTING_PREFLIGHT_RECEIPT')
    authenticate(preflight_receipt['stderr'])
    need(preflight_registration['specification_sha256']==sha(raw(REG+'/preflight-006/specification.json')),
         'ACTUAL_PREFLIGHT_SPECIFICATION_HASH')
    need(sha(raw(PRODUCTION))==sha(raw(CANDIDATE+'/bootstrap_tier2_carrier_view.py'))==EXPECTED_CARRIER,'CURRENT006_NOT_BYTE_EXACT_INSTALLED')
    installation=load(REG+'/source-installation-observation.json')
    need(installation['status']=='SOURCE_REVIEWED_INSTALLED_RUNTIME_UNQUALIFIED' and installation['production_sha256']==EXPECTED_CARRIER and
         installation['test_sha256']==sha(raw(CHECKPOINT_TESTS)) and installation['activation_authority'] is False and installation['task_TESTED_authority'] is False,'ACTUAL_SOURCE_INSTALLATION_OBSERVATION')
    checkpoint_registration=load(REG+'/checkpoint-control-identities.json')
    need(checkpoint_registration['preflight_path']==PREFLIGHT and checkpoint_registration['preflight_sha256']==sha(raw(PREFLIGHT)) and
         checkpoint_registration['ids']==ready['checkpoint_control_ids'] and checkpoint_registration['qualification_authority'] is False,
         'ACTUAL_CHECKPOINT_IDENTITY_REGISTRATION')
    need(type(ready['sealed_packages']) is list and ready['sealed_packages'],'CURRENT_SEALED_SOURCE_PACKAGES_EMPTY')
    packages={package['manifest']['path'] for package in ready['sealed_packages']}
    need({PLAN+'/hash-manifest.json',ADAPTERS+'/hash-manifest.json',PURE+'/manifest.json',CANDIDATE+'/hash-manifest.json',
          'validation/tier2-carrier006-source-review-001/manifest.json'}.issubset(packages),'CURRENT_SOURCE_SEALS_MISSING')
    for package in ready['sealed_packages']:
        manifest_guard(package,dependencies)
    need(type(ready['independent_source_reviews']) is list and ready['independent_source_reviews'],'INDEPENDENT_SOURCE_REVIEW_REFS_MISSING')
    for identity in ready['independent_source_reviews']:
        authenticate(identity)
        need(dependencies.get(identity['path'])==identity,'INDEPENDENT_SOURCE_REVIEW_NOT_BOUND')
    need(type(ready['additional_static_inputs']) is list and all(type(path) is str and path in dependencies for path in ready['additional_static_inputs']),'ADDITIONAL_STATIC_INPUTS_NOT_AUTHENTICATED')
    checkpoint_ids=ready['checkpoint_control_ids']
    need(checkpoint_ids==checkpoint_ids_from_source(),'CHECKPOINT_ROOT_HANDOFF_SOURCE_ID_DISAGREEMENT')
    plan_tree=ast.parse(raw(PLAN+'/materialize_registration.py').decode('utf-8','strict'))
    constants={node.targets[0].id:ast.literal_eval(node.value) for node in plan_tree.body if isinstance(node,ast.Assign) and
               len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('EXPECTED_CARRIER','EXPECTED_CHECKPOINT_IDS')}
    need(constants.get('EXPECTED_CARRIER')==EXPECTED_CARRIER and constants.get('EXPECTED_CHECKPOINT_IDS')==tuple(checkpoint_ids),'PLAN011_CURRENT_CARRIER_AND_CHECKPOINT_BINDINGS_UNRESOLVED')
    adaptation=load(PLAN+'/predicate-reader-adaptation-specification.json')
    need(adaptation['adapter_revision']=='008' and adaptation['binding_status']=='ROOT_SOURCE_REVIEWED_FROZEN','PLAN011_ADAPTER008_BINDINGS_UNRESOLVED')
    author_literals=load(REG+'/fresh-author-carrier-literals-006.json')
    author_protocol=author_literals['author_protocol']['reconstruction_source']
    need(author_literals['source']['sha256']==EXPECTED_CARRIER and
         author_protocol=={'path':ADAPTERS+'/author_protocol_reconstruction.py','sha256':sha(raw(ADAPTERS+'/author_protocol_reconstruction.py'))},
         'CURRENT006_AUTHOR_PROTOCOL_SOURCE_BINDING')
    fixture_map=load(REG+'/fresh-fixture-input-map.json')
    roles={'own-unrelated-carrier.json','original-unrelated-request.json','reference.json','fixture-only-expected.json',
           'fresh-author-exact-message.txt','first-functions-exec.js','next-functions-exec.js','own-unrelated-empty-carrier.json',
           'original-unrelated-empty-request.json','empty-reference.json','empty-first-functions-exec.js',
           'empty-next-system-functions-exec.js','empty-next-user-functions-exec.js','preexecution-registration.json'}
    need(type(fixture_map) is dict and set(fixture_map)=={FIX+'/'+name for name in roles},'EXACT14_CURRENT_STATIC_FIXTURE_ROLES')
    for path,expected in fixture_map.items():
        need(sha(raw(path))==expected and path in dependencies,'CURRENT_STATIC_FIXTURE_HASH:'+path)
    # Definitions only: no result from qualification002 is inspected or inherited.
    current_claims=load(PLAN+'/claims.json'); previous_claims=load('validation/tier2-support-019-qualification-plan-007/claims.json')
    need(current_claims==previous_claims and len(current_claims['original_claims'])==18 and len(current_claims['additional_claims'])==9,'ALL27_CLAIM_OBJECTS_NOT_PRESERVED')
    need(raw(PURE+'/WITNESS_SCHEMA.json')==raw('validation/tier2-support019-core-drivers-002/WITNESS_SCHEMA.json'),'PURE30_SCHEMA_CHANGED')
    outputs=('final-config.json','adapter-bindings.json','static-input-bindings.json')
    need(not any((BASE/name).exists() for name in outputs),'CONFIGURATION_ALREADY_GENERATED_APPEND_ONLY')
    return ready,dependencies


def main():
    # All source-only configuration inputs were specified before this program.
    ready,dependency_hashes=validate_current_bindings()
    source_spec=load(RELBASE+'/specification-before-configuration.json')
    amendment=load(RELBASE+'/interface-amendment-before-bindings.json')
    final_amendment=load(RELBASE+'/final-version-amendment-003-before-bindings.json')
    preservation=load(RELBASE+'/source-preservation-input-amendment-before-bindings.json')
    preservation_paths=set(preservation['necessary_historical_bytes'])
    assert source_spec['actual_execution']==amendment['actual_calls']==final_amendment['actual_calls']==0
    assert final_amendment['qualification_plan']==PLAN
    assert final_amendment['qualification_adapters']==ADAPTERS
    assert final_amendment['orchestration']==ORCH
    preflight=load(PREFLIGHT)
    floor=load(PLAN+'/mandatory-floor.json')
    assert preflight['tests_executed']==preflight['model_calls']==0 and preflight['task_inputs'] is False
    validate_preflight(preflight,floor,ready['checkpoint_control_ids'])
    assert sha(wire(preflight['source_files']))==preflight['source_root']
    assert source_spec['registered_source_root'] in (None,preflight['source_root'])
    assert set(floor['registered_test_ids']).issubset(preflight['test_ids']) and len(floor['registered_test_ids'])==180
    baseline=load('validation/tier2-support-018-qualification-002/qualification-specification.json')
    source_root=preflight['source_root']
    fixture_map=load(REG+'/fresh-fixture-input-map.json')
    assert len(fixture_map)==14
    for path,expected in fixture_map.items(): assert sha(raw(path))==expected
    large=load(FIX+'/own-unrelated-carrier.json'); large_ref=load(FIX+'/reference.json')
    empty=load(FIX+'/own-unrelated-empty-carrier.json'); empty_ref=load(FIX+'/empty-reference.json')
    assert len(large['user'])>400000 and empty['system']==empty['user']==''
    fresh={'identity':reference(FIX+'/own-unrelated-carrier.json'),'reference':large_ref}
    empty_fresh={'identity':reference(FIX+'/own-unrelated-empty-carrier.json'),'reference':empty_ref}
    factory=CANDIDATE+'/capture-amendment-003/collector_templates.py'
    capture_registration=ready['capture_registration']['path']
    schema=load(PURE+'/WITNESS_SCHEMA.json')
    ids=[c['case_id'] for c in schema['case_contracts']]

    guard_dependencies(dependency_hashes)

    # Bind strict before/after policy and limits by static generic source ASTs.
    snapshot='synthetic_dataset/bootstrap/stages/tier2-source-facets-018/project'
    authority_names=['verislop/policy.py','verislop/accept.py','verislop/leanbridge.py','verislop/targets/vscore3_replay.py',
        'verislop/backends/vscore3_release.py','verislop/backends/vscore3_closure.py','verislop/bridges/vscore3_checker.py',
        'verislop/bridges/vscore3_readable_support.py','verislop/targets/vscore_source.py','verislop/classify.py']
    authority_pairs=[]
    for name in authority_names:
        before=snapshot+'/'+name
        assert raw(before)==raw(name), name
        authority_pairs.append({'left':reference(before),'right':reference(name),'relation':'equal'})
    before_policy=strict_policy(snapshot+'/verislop/policy.py'); after_policy=strict_policy('verislop/policy.py')
    assert before_policy==after_policy and sha(wire(after_policy))==baseline['policy_hash']
    policy_before=write('strict-policy-before.json',wire(before_policy),True)
    policy_after=write('strict-policy-current.json',wire(after_policy),True)
    recipe=load(GROUND+'/recipe-001.json')
    limits={'strict_policy':after_policy,'ground':{k:recipe[k] for k in ['options','whole_probe_deadline_seconds','max_polarity_compilations','polarity_order']},
        'unicode':load(UNICODE+'/spec.json')['budget']}
    limits_before=write('limits-before.json',limits); limits_current=write('limits-current.json',limits)
    policy_derivation=write('authority-source-derivation.json',{'format':'verislop.support019-static-authority-derivation/1',
        'source_pairs':authority_pairs,'policy_hash':baseline['policy_hash'],'policy_derivation':'Exact strict POLICIES AST using only literals and BASELINE_AXIOMS; canonical raw bytes without newline',
        'limits_sources':[reference(GROUND+'/recipe-001.json'),reference(UNICODE+'/spec.json')],
        'semantic_TCB_delta':[],'actual_calls':0,'task_inputs':False})

    # Prepared exact legacy slice inputs; later copy, never run a viewer here.
    original_root=Q+'/original-channel'
    carrier_raw=raw(FIX+'/own-unrelated-carrier.json')
    cases=[]; copies=[]
    carrier_input=write('original-channel-inputs/carrier.json',carrier_raw,True)
    copies.append({'source':carrier_input['path'],'target':original_root+'/carrier.json','sha256':carrier_input['sha256']})
    for case_id,cap,budget,delivery in [('intact',8192,16384,'intact'),('truncated',8192,100,'truncated'),('retry',4096,16384,'intact')]:
        case={'id':case_id,'selector':'/user','start_char':0,'output_cap_bytes':cap,'metadata_reserve_bytes':2048,
            'max_output_tokens':budget,'exit_code_expected':0,'expected_delivery':delivery,
            'carrier_ref':'carrier.json','carrier_ref_sha256':sha(carrier_raw),'expected_carrier_sha256':sha(carrier_raw),
            'expected_request_sha256':large_ref['request_sha256'],'literal_carrier_path':large_ref['path'],
            'carrier_raw_bytes':len(carrier_raw),'expected_stdout_ref':case_id+'.expected'}
        emitted=original_slice(case,large)
        expected_input=write('original-channel-inputs/'+case_id+'.expected',emitted,True)
        case['expected_stdout_sha256']=expected_input['sha256']
        if delivery=='truncated': case['retry_case_id']='retry'
        cases.append(case);copies.append({'source':expected_input['path'],'target':original_root+'/'+case_id+'.expected','sha256':expected_input['sha256']})
    case_plan={'format':'verislop.carrier-channel-case-plan/1','closure_id':CLOSURE,
        'required_case_ids':['intact','truncated','retry'],'required_complete_fields':[],'cases':cases}
    case_plan_ref=write('original-channel-inputs/channel-case-plan.json',case_plan)
    copies.append({'source':case_plan_ref['path'],'target':original_root+'/channel-case-plan.json','sha256':case_plan_ref['sha256']})
    orchestrator_ref=write('original-channel-orchestrator.js',raw('validation/tier2-support-018-qualification-002/channel-orchestrator.js'),True)
    original_registration=load('validation/tier2-support-018-qualification-plan/final-reconciliation-002/finalizer-registration.json')['channel']
    original_channel={**original_registration,'capture_root':original_root,'case_plan_sha256':case_plan_ref['sha256'],
        'orchestrator':orchestrator_ref['path'],'result':original_root+'/channel-result.json',
        'comparator_receipt':original_root+'/comparator-actual-process-receipt.json'}
    marker='tests.test_vscore3_collection_bridge.CollectionRegisteredTier2Tests.test_actual_frozen_collection_closure_and_retained_release_probe'
    cls,method=marker.rsplit('.',1);display=method+' ('+cls+') ... '
    marker_ref=write('marker-specification.json',{'format':'verislop.support019-collection-marker-specification/1','closure_id':CLOSURE,
        'collection_id':marker,'unittest_display_prefix':display,'exact_display_prefix':display,
        'markers':['COLLECTION_TIER2_FROZEN_ATTEMPT_CAPTURE','COLLECTION_TIER2_RETAINED_CHECK_CAPTURE'],'predicate_changes':[],'actual_calls':0})

    # Every runtime path is selected now; generated output hashes resolve later.
    common_env={'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'}
    unicode_run='qualification-019-006'
    unicode_directory=UNICODE+'/runs/'+unicode_run
    phases=[
        {'id':'registered-suite','producer_path':CORE+'/gate.py','argv':[PYTHON,str(ROOT/CORE/'gate.py'),'run','--qualification-root',str(ROOT/Q)],
         'outputs':{'run-result':Q+'/run-result.json','invocation':Q+'/invocation.json'}},
        {'id':'carrier-fixtures','producer_path':'validation/tier2-carrier-view-support-018-implementation/verify_carrier_views.py',
         'argv':[PYTHON,str(ROOT/'validation/tier2-carrier-view-support-018-implementation/verify_carrier_views.py'),'--manifest',str(ROOT/Q/'verification-source-manifest.json'),'--output',str(ROOT/Q/'carrier-fixtures')],
         'outputs':{'report':Q+'/carrier-fixtures/report.json'}},
        {'id':'unicode-kernel','producer_path':UNICODE+'/verify.py','argv':[PYTHON,str(ROOT/UNICODE/'verify.py'),'--run-id',unicode_run],
         'outputs':{'report':unicode_directory+'/report.json','manifest':unicode_directory+'/manifest.json','provenance':unicode_directory+'/provenance.json'}},
        {'id':'ground-kernel','producer_path':GROUND+'/qualification.py','argv':[PYTHON,str(ROOT/GROUND/'qualification.py'),'--output',str(ROOT/Q/'ground-kernel'),'--source-freeze',source_root,'--source-manifest',str(ROOT/Q/'verification-source-manifest.json')],
         'outputs':{'report':Q+'/ground-kernel/report.json','frozen-inputs':Q+'/ground-kernel/frozen-inputs.json'}}]
    for phase in phases: phase.update({'accepted_exit_code':0,'environment':common_env})
    additional=[
        {'id':'equality-original44-new11-grouped','producer_path':EQ+'/verify_equality.py','argv':[PYTHON,str(ROOT/EQ/'verify_equality.py'),'--qualification-root',str(ROOT/Q)],
         'outputs':{'index':Q+'/equality/equality-result.json','original-main':Q+'/equality/original-main/results.json','original-additional':Q+'/equality/original-additional/results.json','private-binding':Q+'/equality/private-binding/results.json'}},
        {'id':'carrier-pure-controls','producer_path':PURE+'/verify_carrier_controls.py','argv':[PYTHON,str(ROOT/PURE/'verify_carrier_controls.py'),'--qualification-root',str(ROOT/Q)],
         'outputs':{'result':Q+'/carrier-pure-result.json','semantic-witnesses':Q+'/semantic-witnesses.json'}},
        {'id':'current-root-reconciliation','producer_path':ORCH+'/run_adapter.py','argv':[PYTHON,str(ROOT/ORCH/'run_adapter.py'),'--qualification-root',str(ROOT/Q),'--kind','reconcile'],
         'outputs':{'report':Q+'/final-reconciliation/report.json','provenance':Q+'/final-reconciliation/provenance.json','child-receipt':Q+'/reconcile-child-process-receipt.json'}},
        {'id':'independent-predicate-reader','producer_path':ORCH+'/run_adapter.py','argv':[PYTHON,str(ROOT/ORCH/'run_adapter.py'),'--qualification-root',str(ROOT/Q),'--kind','reader'],
         'outputs':{'report':Q+'/independent-audit/report.json','child-receipt':Q+'/reader-child-process-receipt.json'}}]
    for phase in additional: phase.update({'accepted_exit_code':0,'environment':common_env})
    runtime=copy.deepcopy(load(ADAPTERS+'/runtime-configuration-template.json')['adapters'])
    child_processes={};child_maps={};equality_processes={}
    for name,source,env in [('original-main','test_candidate_019.py','EQUALITY019_RUN'),('original-additional','test_additional_controls_019.py','EQUALITY019_ADD_RUN'),('private-binding','test_revision002_private_and_binding.py','EQUALITY019_PRIVATE_RUN')]:
        directory=Q+'/equality/'+name;argv=[PYTHON,str(ROOT/EQ/source)]
        child_processes[name]={'argv':argv,'accepted_exit_code':0,'environment':{env:str(ROOT/directory),'PYTHONDONTWRITEBYTECODE':'1'},'output_directory':directory,'removed_environment_keys':['EQUALITY019_CASES','EQUALITY019_CONTROL']}
        equality_processes[name]={'argv':argv,'output_directory':directory}
        if name=='original-main': child_maps[name]={'candidate_sha256':EQ+'/contract_refutation_candidate.py','test_sha256':EQ+'/test_candidate_019.py'}
        else:
            sources=[source,'test_candidate_019.py','contract_refutation_candidate.py']+(['fixture_only_analysis_guard_mutant.py'] if name=='private-binding' else [])
            child_maps[name]={s:EQ+'/'+s for s in sources}
    representations={}
    for key,source in [('runtime_representation','runtime-representation-binding.json'),('collection_representation','collection-representation.json')]:
        definition=load('validation/tier2-support-018-independent-audit-002/'+source)
        definition['source_bindings']={name:sha(raw(name)) for name in definition['source_bindings']}
        definition['closure_id']=CLOSURE;definition['qualification_root']=Q
        representations[key]=definition
    authority={'source_pairs':authority_pairs,'policy_before_ref':policy_before,'policy_after_ref':policy_after,
        'limit_objects':{'existing_Lean_and_policy_limits':{'baseline_ref':limits_before,'current_ref':limits_current,
            'predicates':[{'left':{'role':'current','path':['ground','whole_probe_deadline_seconds']},'op':'eq','value':30},
                {'left':{'role':'current','path':['ground','max_polarity_compilations']},'op':'eq','value':2},
                {'left':{'role':'current','path':['ground','options']},'op':'eq','value':recipe['options']},
                {'left':{'role':'current','path':['strict_policy','gate']},'op':'eq','value':'accepted_and_proved'}]}},
        'observation_trust':'TCB-TOOL-FORWARDING','hidden_outer_native_envelope':'UNAVAILABLE','semantic_acceptance_authority':False,
        'activation_authority':False,'model_identity':'UNATTESTED','semantic_consumption':'UNATTESTED','derivation_ref':policy_derivation}
    carrier_literals=load(REG+'/fresh-author-carrier-literals-006.json')
    author_protocol_path=carrier_literals['author_protocol']['reconstruction_source']['path']
    assert author_protocol_path==ADAPTERS+'/author_protocol_reconstruction.py'
    assert sha(raw(author_protocol_path))==carrier_literals['author_protocol']['reconstruction_source']['sha256']
    author_contract={'case_id':'FA002-001','exact_count':1,'requested_model':'gpt-6.1-sol','fork_turns':'none',
        'fresh_fixture':fresh,'sole_readable_file':large_ref['path'],'submitted_message_path':FIX+'/fresh-author-exact-message.txt',
        'expected_literal_message_ref':reference(FIX+'/fresh-author-exact-message.txt'),'evaluator_expectations_ref':reference(FIX+'/fixture-only-expected.json'),
        'spawn_request_path':Q+'/fresh-author/spawn-request.json','spawn_result_path':Q+'/fresh-author/spawn-result.json',
        'literal_final_path':Q+'/fresh-author/literal-final.txt','exposed_responses_prefix':Q+'/fresh-author/exposed-responses',
        'observed_author_requests_schema':'exact singleton {spawn_request_ref,spawn_result_ref,agent_id}; raw spawn result exact singleton {task_name}; strict canonical task_name equals internal author_agent_id/observer agent_id and final path leaf equals requested task_name',
        'raw_spawn_response_schema':'exact singleton {task_name:string}; canonical /root(?:/[a-z0-9_]+)+ and request leaf [a-z0-9_]+',
        'internal_agent_id_semantics':'Canonical observable task_name string only; no hidden agent ID or PID',
        'author_protocol_reconstruction_ref':reference(author_protocol_path),
        'model_identity':'UNATTESTED','semantic_consumption':'UNATTESTED','expectations_sent_to_author':False,'replacement_or_resampling':False,
        'author_input_rule':'Only this exact own unrelated carrier and exact plain literal message; no expected answers or results'}
    runtime.update({'closure_id':CLOSURE,'qualification_root':Q,'specification':ADAPTERS+'/reconciliation-specification.json','report_schema':ADAPTERS+'/report-schema.json',
        'claims_file':PLAN+'/claims.json','mandatory_floor':PLAN+'/mandatory-floor.json','control_registration':PLAN+'/control-registration.json',
        'source_inventory_registration':PLAN+'/source-inventory-registration.json','gate_driver':CORE+'/gate.py','phase_launcher':ORCH+'/execute_phases.py',
        'unicode_directory':unicode_directory,'unicode_run_id':unicode_run,'unicode_verifier':UNICODE+'/verify.py','unicode_spec':UNICODE+'/spec.json','unicode_negative_plan':UNICODE+'/negative-plan.json',
        'ground_design':GROUND,'ground_verifier':GROUND+'/qualification.py','ground_verifier_registration':GROUND+'/qualification-registration-013.json',
        'marker_specification':marker_ref['path'],'original_channel':original_channel,'equality_producer_path':EQ+'/verify_equality.py','equality_guard_mutant_source':EQ+'/fixture_only_analysis_guard_mutant.py',
        'equality_case_contracts':expand(load(ADAPTERS+'/finite-equality-contracts-template.json')['cases']),
        'equality_processes':equality_processes,'equality_child_processes':child_processes,'equality_source_freeze_map':child_maps,
        'capture_factory':factory,'exact_pure_test_ids':ids,'pure_witness_contracts':schema,
        'pure_evidence':{'producer_path':PURE+'/verify_carrier_controls.py','schema_path':PURE+'/WITNESS_SCHEMA.json','semantic_witnesses_path':Q+'/semantic-witnesses.json',
            'actual_process_receipt_path':Q+'/carrier-pure-controls-actual-process-receipt.json','process_contract':{'argv':additional[1]['argv'],'accepted_exit_code':0,'environment':common_env}},
        'additional_evidence_paths':{'equality':Q+'/equality/equality-result.json','pure':Q+'/carrier-pure-result.json','carrier':Q+'/actual-channel/capture-index.json','author':Q+'/fresh-author/author-index.json'},
        'fresh_evidence_prefixes':[Q,FIX,unicode_directory],'policy_baseline':'validation/tier2-support-018-qualification-002/qualification-specification.json',
        'unchanged_authority_source_bindings':{name:sha(raw(name)) for name in authority_names},'authority_contract':authority,'author_contract':author_contract,
        'predicate_reader_specification':ADAPTERS+'/predicate-reader-specification.json','predicate_reader_carrier_literals':REG+'/fresh-author-carrier-literals-006.json',
        'predicate_reader_capture_literals':REG+'/fresh-author-capture-literals-006.json',**representations})

    # Register actual child commands via finite runtime hash slots; wrapper argv
    # remains static and its own actual receipt is a separate phase artifact.
    reconcile=load(ADAPTERS+'/finalizer-registration-template.json')
    reconcile.pop('input_root',None)
    reconcile['source_root']=source_root
    reconcile.update({'format':'verislop.support019-finalizer-registration/1','status':'PREPARED_FOR_ROOT_REVIEW_NOT_EXECUTED',
        'closure_id':CLOSURE,'verifier_id':'V019-CURRENT-ROOT-RAW-RECONCILIATION','verifier':reference(ADAPTERS+'/current_root_reconcile.py'),
        'specification':reference(ADAPTERS+'/reconciliation-specification.json'),'report_schema':reference(ADAPTERS+'/report-schema.json'),
        'required_sibling':reference(ADAPTERS+'/additional_predicates.py')})
    reconcile['invocation'].update({'cwd':str(ROOT),'environment':{},'outer_timeout_seconds':None})
    reader={'format':'verislop.support019-independent-predicate-reader-registration/1','status':'PREPARED_FOR_ROOT_REVIEW_NOT_EXECUTED','closure_id':CLOSURE,
        'verifier_id':'V019-INDEPENDENT-PREDICATE-READER','verifier':reference(ADAPTERS+'/predicate_reader.py'),
        'specification':reference(ADAPTERS+'/predicate-reader-specification.json'),'report_schema':reference(ADAPTERS+'/report-schema.json'),
        'invocation':{'argv_template':['{python}','{verifier}','--qualification-root','{qualification_root}','--final-report','{final_report}',
            '--finalizer-receipt','{finalizer_receipt}','--output','{output}','--equality-index-sha256','{equality_index_sha256}',
            '--carrier-index-sha256','{carrier_index_sha256}','--author-index-sha256','{author_index_sha256}','--pure-index-sha256','{pure_index_sha256}'],
            'cwd':str(ROOT),'environment':{},'outer_timeout_seconds':None,'accepted_exit_code':0,'output':'independent-audit'},
        'execution_authority':False,'producer_paths':[]}
    runtime['reconciler_registration']=RELBASE+'/reconciler-registration.json'
    runtime['predicate_reader_registration']=RELBASE+'/predicate-reader-registration.json'
    runtime['adapter_wrapper_registrations']={'reconcile':runtime['reconciler_registration'],'reader':runtime['predicate_reader_registration']}
    runtime['expected_capture_source_files']={path:sha(raw(path)) for path in [factory,capture_registration,CANDIDATE+'/bootstrap_tier2_carrier_view.py']}

    recorder_cases={}
    for case_id in ['AC002-001','AC002-002','AC002-003','AC002-004']:
        normal=[['inventory',20000,16384,8192,2048],['intact',20000,16384,8192,2048]]
        kinds=['inventory','intact']
        if case_id in ('AC002-002','AC002-003'):
            kind='nested-fault' if case_id=='AC002-002' else 'outer-fault';outer,nested=(20000,256) if case_id=='AC002-002' else (256,16384)
            normal += [[kind,outer,nested,8192,2048],['retry',20000,16384,4096,2048]];kinds += [kind,'retry']
        recorder_cases[case_id]={'kinds':kinds,'budgets':normal,'reference_file':FIX+('/empty-reference.json' if case_id=='AC002-004' else '/reference.json')}
    config=load(PLAN+'/final-config-template.json')
    config.update({'format':'verislop.support019-concrete-final-config-preparation/1','status':'UNSEALED_SOURCE_CONFIGURATION_PENDING_ACTUAL_INTERFACE_AND_ROOT_REVIEW',
        'qualification_root':Q,'closure_id':CLOSURE,'source_root':source_root,
        'toolchain':baseline['toolchain'],'kernel_tool_hash':baseline['kernel_tool_hash'],'policy_hash':baseline['policy_hash'],
        'claims_sha256':sha(raw(PLAN+'/claims.json')),'execution_phases':phases,'additional_processes':additional,
        'registered_test_count':preflight['test_count'],'registered_test_ids':preflight['test_ids'],
        'test_modules':preflight['test_modules'],'test_sources':preflight['test_sources'],
        'required_collection_inputs':preflight['required_collection_inputs'],
        'actual_process_output_index_path':Q+'/process-output-index.json','actual_channel_evidence_path':Q+'/actual-channel/capture-index.json',
        'actual_author_evidence_path':Q+'/fresh-author/author-index.json','actual_equality_evidence_path':Q+'/equality/equality-result.json',
        'actual_pure_evidence_path':Q+'/carrier-pure-result.json','fresh_evidence_prefixes':runtime['fresh_evidence_prefixes'],
        'newly_registered_test_ids':[i for i in preflight['test_ids'] if i not in floor['registered_test_ids']],
        'reviewed_regression_inventory_complete':True,'improved_grouped_binding_registered':True,
        'equality_result_output_keys':['original-main','original-additional','private-binding'],
        'final_capture_amendment':{'path':capture_registration,'sha256':sha(raw(capture_registration)),'revision':'003','status':'ROOT_SOURCE_REVIEWED_FROZEN'},
        'capture002_weird_path_control_ids':final_amendment['capture_amendment_new_control_ids'],
        'capture003_checkpoint_control_ids':ready['checkpoint_control_ids'],
        'adapters':runtime,'test_environment':{},'core_model_calls':0,'ancillary_fresh_author_calls':1,
        'inference_timeout':None,'retrieval_timeout':None,'review_timeout':None,'strict_implementation_proof_release_unchanged':True,
        'task_inputs':False,'prior_pass_inheritance':False,'activation_authority':False,
        'channel_recorder':{'producer_path':RECORDER+'/record_call.py','factory_source':factory,'cases':recorder_cases,'max_calls':10000},
        'pre_freeze_copies':copies,'verification_source_manifest_path':Q+'/verification-source-manifest.json','preflight_registration':reference(PREFLIGHT),
        'fresh_fixture_input_map':fixture_map,'review_flags_are_prerequisites':'These prospective True fields require actual root source/installation review before this config can be materialized; no actual predicate/test/channel/model outcome is asserted'})
    config.pop('input_root',None)
    config['input_root_derivation']='Final materializer canonical SHA256 of its completed exact source_hashes map; actual value published in qualification-inputs.json and preregistration.json only'
    assert set(config['capture002_weird_path_control_ids']).issubset(ids) and len(config['capture002_weird_path_control_ids'])==5
    assert config['capture003_checkpoint_control_ids']==checkpoint_ids_from_source()
    assert set(config['capture003_checkpoint_control_ids']).issubset(config['newly_registered_test_ids'])
    for row in config['independent_claim_checks'].values():
        row.update({'verifier_id':reader['verifier_id'],'verifier_path':reader['verifier']['path'],'predicate_implementation_reviewed':True})

    # Enumerate static input source paths only, never historical execution dirs.
    verification=set(preflight['required_collection_inputs'])|set(fixture_map)
    verification.update(runtime['unchanged_authority_source_bindings'])
    verification.update(pair['left']['path'] for pair in authority_pairs)
    folders=[PLAN,ADAPTERS,ORCH,EQ,PURE,RECORDER,'validation/tier2-support019-final-helpers-source-review-001',
        'validation/tier2-support019-final-helpers-source-review-002',
        'validation/tier2-support019-final-helpers-source-review-002-plan006-supplement',
        'validation/tier2-support019-final-helpers-source-review-004',
        REG,
        'validation/tier2-support019-qualification-repair-007',
        'validation/tier2-carrier-context-support-019-implementation-002',
        'validation/tier2-carrier-context-support-019-implementation-002/capture-amendment-001',
        'validation/tier2-carrier-context-support-019-implementation-002/capture-amendment-002',
        CANDIDATE,CANDIDATE+'/capture-amendment-003',
        'validation/tier2-carrier006-source-review-001']
    for folder in folders:
        for path in (ROOT/folder).iterdir():
            name=path.relative_to(ROOT).as_posix()
            if path.is_file() and (not any(token in path.name for token in ['.stdout.', '.stderr.', '-receipt.json']) or name in preservation_paths):
                verification.add(name)
    for obligation in preservation['source_obligations']:
        manifest=load(obligation['manifest'])
        matching=next(c for c in schema['case_contracts'] if c['case_id']==obligation['case_id'])
        assert any(o.get('kind')=='manifest_contract' and o['path']==obligation['manifest'] and o['entry_map']==obligation['entry_map'] for o in matching['source_only_obligations'])
        verification.update(manifest[obligation['entry_map']])
        verification.update(manifest.get('inputs',{}))
        for path in preservation_paths & set(manifest[obligation['entry_map']]):
            assert sha(raw(path))==manifest[obligation['entry_map']][path]['sha256']
    config['source_preservation_only_inputs']=sorted(preservation_paths)
    config['source_preservation_only_authority']='Opaque historical byte immutability only, no old PASS or runtime authority; every actual qualification channel/control is fresh'
    verification.update(load('validation/tier2-carrier-context-support-019-implementation-002/capture-amendment-002/hash-manifest.json')['inputs'])
    verification.update(dependency_hashes)
    verification.update(ready['additional_static_inputs'])
    verification.update([PRODUCTION,CHECKPOINT_TESTS,author_protocol_path])
    verification.update([CORE+'/gate.py',CORE+'/manifest.json',CORE+'/specification-before-implementation.json',PREFLIGHT,
        UNICODE+'/verify.py',UNICODE+'/spec.json',UNICODE+'/fixtures.json',UNICODE+'/negative-plan.json',UNICODE+'/verifier-plan.json',
        UNICODE+'/ledger-extension-001/design.json',UNICODE+'/ledger-extension-001/registration.json',UNICODE+'/ledger-extension-001/mock_shape_checks.py',UNICODE+'/ledger-extension-001/prior/verify.py',
        GROUND+'/qualification.py',GROUND+'/qualification-registration-013.json',GROUND+'/recipe-001.json',
        'validation/tier2-support-018-qualification-plan/scripts/verify-channel-records-v2.py',
        'validation/tier2-support-018-qualification-plan/channel-check-protocol-v2.json',
        'validation/tier2-support-018-independent-audit-002/runtime-representation-binding.json','validation/tier2-support-018-independent-audit-002/collection-representation.json',
        runtime['policy_baseline'],'validation/tier2-refutation-equality-support-019-implementation/contract_refutation_candidate.py'])
    verification.add('validation/tier2-carrier-context-support-019-implementation/bootstrap_tier2_carrier_view.py')
    ground_names=['explore.py','negative_controls.py','oracle_controls.py','name_control.py','deadline_controls.py','unit_controls.py','control_fixtures.py','baseline-vscore3_replay.py',
        'specification.json','qualification-plan.json','evidence-contract.json','activation-001.json','export-frontier-005-freeze.json','frontier-evidence-006-freeze.json',
        'negative-controls-007-freeze.json','clean-builds-008-freeze.json','qualification-hook-009-freeze.json','name-control-001-freeze.json',
        'diagnostic-controls-003-freeze.json','oracle-controls-002-freeze.json','verifier-amendment-011-freeze.json','output-routing-011-freeze.json','terminal-diagnostic-deadline-012-freeze.json']
    verification.update(GROUND+'/'+name for name in ground_names)
    final_review='validation/tier2-support019-final-helpers-source-review-003'
    verification.update(final_review+'/'+name for name in ['SPECIFICATION.md','SOURCES.json','REVIEW.json','REVIEW.md','manifest.json','SEAL.sha256'])
    if (ROOT/final_review).is_dir(): verification.update(p.relative_to(ROOT).as_posix() for p in (ROOT/final_review).iterdir() if p.is_file())
    verification.update([PLAN+'/admission-controls-registration-003.json',
        PLAN+'/test_admission_controls.py',
        PLAN+'/audit_actual.py'])
    verification.update([REG+'/final-installation-review-specification-before-record.json',
        REG+'/final-installation-review.json',
        REG+'/configuration-interface-inspection.json'])
    # Generic raw predicate templates remain source references, never old results.
    for definition in load(PLAN+'/specification-before-implementation.json')['baseline_definitions'] + load(PLAN+'/audit-evidence-contract.json')['amendments'] + load(PLAN+'/predicate-reader-adaptation-specification.json')['source_templates']:
        verification.add(definition['path'])
    required_verifiers={p['producer_path'] for p in phases+additional}|{ADAPTERS+'/current_root_reconcile.py',ADAPTERS+'/predicate_reader.py',ADAPTERS+'/additional_predicates.py',
        ADAPTERS+'/assemble_ancillary_indexes.py',ORCH+'/execute_phases.py',ORCH+'/index_process_outputs.py',PLAN+'/materialize_registration.py',PLAN+'/audit_actual.py',
        RECORDER+'/record_call.py',original_channel['comparator'],original_channel['orchestrator']}
    required_verifiers.update(load(PLAN+'/predicate-reader-adaptation-specification.json')['planned_sources'].values())
    verification.update(required_verifiers)
    interface_checker='validation/tier2-support019-qualification-repair-007/check_runtime_interfaces.py'
    verification.add(interface_checker)
    config['configuration_interface_registration']={
        'format':'verislop.support019-configuration-source-interface-registration/1',
        'checker':reference(interface_checker),
        'argv':[PYTHON,str(ROOT/interface_checker),'--spec',str(BASE/'final-config.json'),
                '--adapter-dir',str(ROOT/ADAPTERS),'--output',
                str(ROOT/REG/'configuration-interface-inspection.json')],
        'cwd':str(ROOT),'accepted_exit_code':0,'outer_timeout_seconds':None,
        'future_result_path':REG+'/configuration-interface-inspection.json',
        'future_result_sha256':None,'actual_calls':0,
        'scope':'Literal source/configuration interface inspection only; no runtime or lifecycle authority'}
    runtime['required_adapter_inputs']=sorted(verification)
    reconcile['producer_paths']=sorted(required_verifiers)
    reader['producer_paths']=sorted(required_verifiers)
    write('reconciler-registration.json',reconcile);write('predicate-reader-registration.json',reader)
    write('original-channel-comparator-registration.json',{'format':'verislop.support019-original-channel-comparator-registration/1','closure_id':CLOSURE,
        'verifier_id':'V018-CHANNEL-RECORDS','verifier':reference(original_channel['comparator']),'orchestrator':orchestrator_ref,
        'case_plan_input':case_plan_ref,'case_plan_destination':original_root+'/channel-case-plan.json','invocation':{'argv_template':original_channel['argv_template'],
            'cwd':str(ROOT),'environment':common_env,'accepted_exit_code':0,'outer_timeout_seconds':None},'receipt_path':original_channel['comparator_receipt'],
        'result_path':original_channel['result'],'actual_calls':0,'scope':'Exact original three actual /user start0 slices; no full-field inference'})
    write('orchestration-registration.json',{'format':'verislop.support019-fixed-orchestration-registration/1','closure_id':CLOSURE,
        'source_refs':[reference(ORCH+'/'+name) for name in ['execute_phases.py','run_adapter.py','index_process_outputs.py']],
        'sections':{s:[PYTHON,str(ROOT/ORCH/'execute_phases.py'),'--qualification-root',str(ROOT/Q),'--section',s] for s in ['core','additional-pre','additional-post']},
        'process_index_argv':[PYTHON,str(ROOT/ORCH/'index_process_outputs.py'),'--qualification-root',str(ROOT/Q)],
        'actual_child_receipts':{'reconcile':Q+'/reconcile-child-process-receipt.json','reader':Q+'/reader-child-process-receipt.json'},
        'wrapper_phase_receipts':{p['id']:Q+'/'+p['id']+'-actual-process-receipt.json' for p in additional[2:]},'outer_timeout_seconds':None,'actual_calls':0})
    write('channel-recorder-registration.json',{'format':'verislop.support019-channel-recorder-registration/1','closure_id':CLOSURE,
        'producer':reference(RECORDER+'/record_call.py'),'factory':reference(factory),'cases':recorder_cases,'max_calls':10000,
        'invocation_argv_template':[PYTHON,str(ROOT/RECORDER/'record_call.py'),'--payload','{actual_retained_call_payload}'],
        'inventory_cursor_before':None,'inventory_cursor_after':None,'scope':'Lossless recording of supplied actual result/VIEW, no viewer or model execution','actual_calls':0})
    write('ancillary-evidence-path-contract.json',{'format':'verislop.support019-ancillary-evidence-path-contract/1','closure_id':CLOSURE,
        'fresh_fixture':fresh,'empty_fixture':empty_fresh,'author_contract':author_contract,'capture_cases':['AC002-001','AC002-002','AC002-003','AC002-004'],
        'carrier_records_path':Q+'/actual-channel/carrier-records.json','author_records_path':Q+'/fresh-author/author-records.json',
        'assembler':reference(ADAPTERS+'/assemble_ancillary_indexes.py'),
        'assembler_argv':[PYTHON,str(ROOT/ADAPTERS/'assemble_ancillary_indexes.py'),'--qualification-root',str(ROOT/Q),
            '--carrier-records',str(ROOT/Q/'actual-channel/carrier-records.json'),'--author-records',str(ROOT/Q/'fresh-author/author-records.json')],
        'future_identity_derivation':'Each reference SHA/byte_count derives from exact actual retained bytes after completion; every raw call/spawn/response/failure is retained, no invented future hash or label authority',
        'future_hashes_at_source_preparation':None,'actual_calls':0})
    admission_registration=PLAN+'/admission-controls-registration-003.json'
    admission=load(admission_registration)
    assert len(admission['test_ids'])==5 and admission['models']==admission['compilers']==0 and admission['expected_exit_code']==0
    assert sha(raw(admission['argv'][1]))==admission['controls_sha256']
    assert sha(raw(PLAN+'/audit_actual.py'))==admission['source_sha256']
    assert raw(admission['argv'][1])==raw(PLAN+'/test_admission_controls.py')
    assert raw(PLAN+'/audit_actual.py')==raw(PLAN+'/audit_actual.py')
    admission_process={'id':'finite-five-admission-controls','registration':reference(admission_registration),
        'argv':admission['argv'],'cwd':str(ROOT),'environment':{'PYTHONDONTWRITEBYTECODE':'1'},'accepted_exit_code':0,
        'test_ids':admission['test_ids'],'source':reference(PLAN+'/audit_actual.py'),
        'controls':reference(admission['argv'][1]),'stdout_path':Q+'/admission-controls/stdout.log','stderr_path':Q+'/admission-controls/stderr.log',
        'actual_process_receipt_path':Q+'/admission-controls/actual-process-receipt.json','outer_timeout_seconds':None,
        'models':0,'compilers':0,'task_inputs':False,'prior_outcome_reuse':False,'actual_calls':0}
    write('admission-controls-registration.json',admission_process)
    config['ancillary_admission_controls']=admission_process
    # External runtime files are opaque hash bindings, never executed.
    external={str(Path(PYTHON).resolve()):sha(raw(str(Path(PYTHON).resolve())))}
    tool=Path.home()/'.elan/toolchains/leanprover--lean4---v4.34.1'
    paths={tool/'bin/lean'}
    paths.update(p for p in (tool/'lib').rglob('*') if p.is_file() and (any(p.name.endswith(s) for s in ['.olean','.olean.server','.olean.private','.ir','.ir.sig']) or '.so' in p.name))
    paths.update(tool/'src/lean'/name for name in ['Lean/Parser/Basic.lean','Init/Meta/Defs.lean','Init/Data/Char/Basic.lean'])
    for p in sorted({p.resolve() for p in paths}): external[str(p)]=sha(raw(str(p)))
    assert external[str((tool/'bin/lean').resolve())]==baseline['toolchain']['lean_binary_sha256']
    compact_descriptor=load('synthetic_dataset/tools/carrier_runtime020-registration.json')
    for interpreter in compact_descriptor['interpreters'].values():
        name=interpreter['path'];need(sha(raw(name))==interpreter['sha256'],'COMPACT_INTERPRETER_CHANGED:'+name);external[name]=interpreter['sha256']
    config['compact_runtime_registration']=reference('synthetic_dataset/tools/carrier_runtime020-registration.json')
    config['compact_runtime_trust']={'Node_and_Python':'Explicit external binary identities; source/hash/checkpoint runtime is trusted only for registered transport operations','author_index_owner':'registered ancillary assembler after completed author/equality/PURE evidence; author controller writes only author-records'}
    config['external_runtime_files']=external
    write('external-runtime-file-map.json',{'format':'verislop.support019-external-runtime-map/1','toolchain':baseline['toolchain'],'files':external,'actual_execution':0})
    write('pre-freeze-installation-contract.json',{'format':'verislop.support019-pre-freeze-installation-contract/1','qualification_root':Q,'copies':copies,
        'required_order':['root source/installation review','create new Qroot once','copy each exact authenticated declared static input to its registered Qroot destination','build verification-source-manifest.json from exact fully reviewed registered verification inputs','materialize complete input map/spec/sourcefreeze/prereg','rehash every input/source/test/externalruntime byte','then permit registered actual phases'],
        'verification_source_manifest_path':Q+'/verification-source-manifest.json','verification_source_manifest_schema':{'files':'exact current static verification input path→actualSHA map; no output/oldPASS'},
        'materializer':reference(PLAN+'/materialize_registration.py'),
        'actual_calls':0})
    # Own configuration files and copied future destinations are mandatory inputs.
    verification.update(p.relative_to(ROOT).as_posix() for p in BASE.rglob('*') if p.is_file())
    verification.update(copy['target'] for copy in copies)
    verification.add(Q+'/verification-source-manifest.json')
    verification.update(RELBASE+'/'+name for name in ['adapter-bindings.json','final-config.json','static-input-bindings.json',
        'configuration-source-manifest.json','HANDOFF.md','CONFIGURATION_METADATA_CHECKS.json','SEAL.sha256'])
    config['required_verifier_paths']=sorted(required_verifiers)
    config['verification_input_paths']=sorted(verification)
    config['adapters']['required_adapter_inputs']=sorted(verification-set(copy['target'] for copy in copies)-{Q+'/verification-source-manifest.json'})
    write('adapter-bindings.json',runtime)
    write('final-config.json',config)
    inputs={name:reference(name) for name in sorted(verification) if (ROOT/name).is_file() and name not in
        {RELBASE+'/static-input-bindings.json',RELBASE+'/configuration-source-manifest.json'}}
    write('static-input-bindings.json',{'format':'verislop.support019-final-static-input-bindings/1','source_root_from_actual_nonexecuting_preflight':source_root,
        'preflight':reference(PREFLIGHT),'files':inputs,'future_static_destinations':copies,
        'future_manifest_path':Q+'/verification-source-manifest.json','whole_input_root':None,'actual_calls':0})
    guard_dependencies(dependency_hashes)
    print(json.dumps({'status':'PREPARED_CONFIGURATION_ONLY_UNSEALED','qualification_root':Q,'closure_id':CLOSURE,'original_phases':4,'additional_gates':4,
        'tests':preflight['test_count'],'modules':len(preflight['test_modules']),'equality_contracts':len(runtime['equality_case_contracts']),'pure_contracts':len(ids),
        'external_runtime_files':len(external),'actual_verifier_test_model_calls':0},sort_keys=True))


if __name__=='__main__': main()
