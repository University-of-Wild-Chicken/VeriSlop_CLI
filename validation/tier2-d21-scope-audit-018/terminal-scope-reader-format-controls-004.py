#!/usr/bin/env python3
"""Unrelated format/control witnesses only; no task or qualified API execution."""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).absolute().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    output = Path(args.output_dir).absolute()
    if output.parent != HERE or output.exists():
        raise ValueError("control output must be a new direct scope-directory child")
    output.mkdir()
    spec = importlib.util.spec_from_file_location("scope018_format_reader004", HERE / "terminal-scope-reader-004.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # definitions/stdlib only; never main or Audit
    final_schema = json.loads((HERE/m.FINAL_SCHEMA_NAME).read_bytes())
    pre_schema = json.loads((HERE/m.PRE_SCHEMA_NAME).read_bytes())
    m.install_binding_schemas(final_schema,pre_schema)
    reader_specification = json.loads((HERE/m.SPEC_NAME).read_bytes())
    rows = []

    def test(name, function, blocked=False):
        try:
            function()
            actual = "ACCEPTED_FORMAT"
        except (m.Block, KeyError, ValueError, TypeError) as exc:
            actual = "REJECTED_FORMAT"
            reason = type(exc).__name__ + ": " + str(exc)
        desired = "REJECTED_FORMAT" if blocked else "ACCEPTED_FORMAT"
        rows.append({"id":name,"expected":desired,"actual":actual,"control_pass":actual == desired,
                     "reason":reason if actual == "REJECTED_FORMAT" else None})

    def stream(data):
        return {"byte_count":len(data),"sha256":"sha256:"+hashlib.sha256(data).hexdigest(),
                "content_b64":base64.b64encode(data).decode()}
    compiler = {"availability":"available","record":{"format":"verislop.lean-compile-process/1",
        "input":{"module":"UnrelatedControl"},"returncode":0,"timed_out":False,
        "requested_argv":["synthetic-compiler","UnrelatedControl.lean"],"launcher_argv":["synthetic-launcher"],
        "working_directory":str(output / "synthetic-build"),"stdout":stream(b"unrelated\x00output"),"stderr":stream(b"\xff\n")}}
    test("C17-available-envelope-unwrapped", lambda:m.compile_record(compiler,accepted=True,name="UnrelatedControl"))
    unavailable = {"availability":"unavailable","record":None}
    test("C17-unavailable-rejected",lambda:m.compile_record(unavailable,accepted=True,name="control"),True)
    test("C17-bare-record-rejected",lambda:m.compile_record(compiler["record"],accepted=True,name="control"),True)
    failed = copy.deepcopy(compiler); failed["record"]["returncode"] = 7
    test("C17-accepted-failure-rejected",lambda:m.compile_record(failed,accepted=True,name="control"),True)
    test("C17-documented-control-failure-preserved",lambda:m.compile_record(failed,accepted=False,name="control"))
    timed = copy.deepcopy(compiler); timed["record"]["timed_out"] = True
    test("C17-accepted-timeout-rejected",lambda:m.compile_record(timed,accepted=True,name="control"),True)
    fakeint = copy.deepcopy(compiler); fakeint["record"]["returncode"] = False
    test("C17-boolean-exit-rejected",lambda:m.compile_record(fakeint,accepted=True,name="control"),True)
    badlog = copy.deepcopy(compiler); badlog["record"]["stderr"]["sha256"] = "0"*64
    test("C17-lossless-log-mutation-rejected",lambda:m.compile_record(badlog,accepted=True,name="control"),True)

    probe = {"id":"UNRELATED-FORMAT-CONTROL","input":{"control":"unrelated"},"expected_output":["unrelated-output"]}
    row = {**probe,"status":"OBSERVED","output":["unrelated-output"]}
    test("C22-expected_output-exact",lambda:m.public_probe_row(probe,row))
    mismatch = {**row,"output":["changed-control-output"]}
    test("C22-observed-mismatch-rejected",lambda:m.public_probe_row(probe,mismatch),True)
    wrongalias = {k:v for k,v in row.items() if k != "expected_output"}; wrongalias["expected"] = probe["expected_output"]
    test("C22-obsolete-expected-alias-rejected",lambda:m.public_probe_row(probe,wrongalias),True)
    unsupported = {**row,"status":"UNSUPPORTED"}; unsupported.pop("output")
    test("C22-unsupported-no-fabricated-output",lambda:m.public_probe_row(probe,unsupported))

    claim = {"claim_id":"UNRELATED:CONTROL","required":True,"applicable":True,"root_kind":"semantic_edge_root"}
    checker = {"id":"UNRELATED-CHECKER","sha256":"sha256:"+"b"*64}
    preref={"path":str(output/"unrelated-pre-route.json"),"sha256":"sha256:"+"f"*64}
    pre={"format":m.PRE_FORMAT,"authorization":"root-explicit-terminal-after-all-authors-controller-stopped",
         "stage":"tier2-source-facets-018","project":str(m.PROJECT),"cohort":str(m.COHORT),
         "source_root":m.SOURCE_ROOT,"qualification_input_root":m.QUALIFICATION_ROOT,
         "preregistration_input_root_hash":"a8febb88f2615e49738194d1380f7441ab42e5bd808adc40bd20fbb57bbb7366",
         "registered_files":{name:"sha256:"+"a"*64 for name in ('terminal-scope-reader-004.py',m.SPEC_NAME,m.REG_NAME,m.ROUTE_NAME)},
         "actor_stop":{"path":str(output/'unrelated-actorstop.json'),"sha256":"sha256:"+"b"*64},
         "cohort_seal":{"path":str(output/'unrelated-cohort-seal.json'),"sha256":"sha256:"+"c"*64},
         "orchestration_seal":{"path":str(output/'unrelated-controller-seal.json'),"sha256":"sha256:"+"d"*64},
         "generation_started_at_utc":"1999-01-01T00:00:00+00:00","authorized_at_utc":"2000-01-01T00:00:00.500000+00:00",
         "terminal_nonce":"e"*64}
    final={**{field:pre[field] for field in m.PRE_COMMON_FIELDS},"format":m.FORMAT,
           "pre_route_authorization":preref,"terminal_authorized_at_utc":"2000-01-01T00:00:05+00:00",
           "transport_trace":{"path":str(output/'unrelated-transport.json'),'sha256':'a'*64},
           "scope_interpretation":None,"retained_validations":[],"public_probe_observations":None}
    record = {"retained_root":str(output / "control-retained"),"original_root":str(output / "control-removed"),
              "closure_root":"sha256:"+"c"*64,"claim_id":claim["claim_id"],"route_sha256":"sha256:"+"a"*64,
              "pre_route_authorization":preref,"terminal_nonce":pre["terminal_nonce"]}
    receipt = {"status":"NOT_REPRODUCED","expected":{"outcome":"PASS","root_kind":"semantic_edge_root","root":"sha256:"+"d"*64},
               "observed":{"outcome":"PASS"},"checker":checker,"proposal":{"kind":"mechanical_failure","claim_id":claim["claim_id"]},
               "checkpoint":"release","claim":{"claim_id":claim["claim_id"]},"input_bindings":{"binding:roots":"sha256:"+"e"*64}}
    result = {"format":"verislop.stage018-retained-route-result/4","mode":"second-probe","source_root":m.SOURCE_ROOT,
              "closure_root":record["closure_root"],"retained_root":record["retained_root"],"original_root":record["original_root"],
              "original_root_absent_before_reads":True,"claim_id":claim["claim_id"],"native_claim":claim,
              "registered_route":{"id":"D21-SCOPE-RETAINED-018-004","sha256":record["route_sha256"]},
              "pre_route_authorization":preref,"terminal_nonce":record["terminal_nonce"],
              "bound_inputs":{"first_read_file_hashes":{preref["path"]:preref["sha256"]}},
              "checker":checker,"status":"PASS","probe":receipt,"roots":{"semantic_edge_root":"sha256:"+"d"*64},
              "registered_internal_probe_timeout_seconds":5.0,"started_at_utc":"2000-01-01T00:00:02+00:00","ended_at_utc":"2000-01-01T00:00:03+00:00"}
    argv = m.retained_argv("second-probe",str(output/"unrelated-binding.json"),"sha256:"+"f"*64,record,str(output/"unrelated-result.json"))
    process = {"argv":argv,"cwd":str(m.PROJECT),"timeout_seconds":None,"returncode":0,"timed_out":False,
               "started_at_utc":"2000-01-01T00:00:01+00:00","ended_at_utc":"2000-01-01T00:00:04+00:00"}
    def retained(p=process,r=result,c=claim):
        return m.authenticate_retained_process(p,r,mode="second-probe",expected_argv=argv,record=record,
            removed_at="2000-01-01T00:00:00+00:00",checker=checker,native_claim=c)
    test("C21-exact-registered-format-witness",lambda:retained())
    test("C21-usr-bin-true-exit0-rejected",lambda:retained({**process,"argv":["/usr/bin/true"]}),True)
    test("C21-wrong-cwd-rejected",lambda:retained({**process,"cwd":str(output)}),True)
    test("C21-outer-timeout-change-rejected",lambda:retained({**process,"timeout_seconds":30}),True)
    test("C21-boolean-returncode-rejected",lambda:retained({**process,"returncode":False}),True)
    test("C21-before-removal-chronology-rejected",lambda:retained({**process,"started_at_utc":"1999-01-01T00:00:00+00:00"}),True)
    test("C21-null-probe-rejected",lambda:retained(r={**result,"probe":None}),True)
    confirmed = copy.deepcopy(result); confirmed["probe"]["status"] = "CONFIRMED"
    test("C21-CONFIRMED-probe-rejected",lambda:retained(r=confirmed),True)
    no_claim = {**claim,"required":False}
    test("C21-missing-required-claim-rejected",lambda:retained(c=no_claim),True)
    test("C21-unemitted-required-claim-rejected",lambda:retained(c=None),True)
    test("C21-stale-checker-rejected",lambda:retained(r={**result,"checker":{"id":"old-checker","sha256":"0"*64}}),True)
    no_bindings = copy.deepcopy(result); no_bindings["probe"]["input_bindings"] = {}
    test("C21-missing-input-bindings-rejected",lambda:retained(r=no_bindings),True)
    badroot = copy.deepcopy(result); badroot["probe"]["expected"]["root"] = "sha256:"+"0"*64
    test("C21-wrong-claim-root-rejected",lambda:retained(r=badroot),True)
    test("C21-stale-source-rejected",lambda:retained(r={**result,"source_root":"sha256:"+"0"*64}),True)
    test("C21-missing-original-root-absence-rejected",lambda:retained(r={**result,"original_root_absent_before_reads":False}),True)
    test("C21-acyclic-pre-route-common-binding",lambda:m.authenticate_pre_route(final,pre))
    test("C21-pre-route-output-refs-rejected",lambda:m.authenticate_pre_route(final,{**pre,"retained_validations":[{"control":"output"}]}),True)
    test("C21-pre-route-final-hash-ref-rejected",lambda:m.authenticate_pre_route(final,{**pre,"final_binding_sha256":"sha256:"+"f"*64}),True)
    for field,wrong in [('source_root','sha256:'+'0'*64),('qualification_input_root','sha256:'+'0'*64),
                        ('preregistration_input_root_hash','0'*64),('cohort',str(output/'wrong-control-cohort')),
                        ('terminal_nonce','0'*64),('actor_stop',{'path':str(output/'different-author.json'),'sha256':'sha256:'+'0'*64}),
                        ('registered_files',{**pre['registered_files'],m.ROUTE_NAME:'sha256:'+'0'*64})]:
        test('C21-incompatible-pre-route-'+field,lambda field=field,wrong=wrong:m.authenticate_pre_route(final,{**pre,field:wrong}),True)
    test('C21-both-stale-source-roots-rejected',lambda:m.authenticate_pre_route({**final,'source_root':'sha256:'+'0'*64},{**pre,'source_root':'sha256:'+'0'*64}),True)
    test('C21-final-before-pre-authorization-rejected',lambda:m.authenticate_pre_route({**final,'terminal_authorized_at_utc':'1999-12-31T23:59:59+00:00'},pre),True)
    test('C21-route-inside-authorization-interval',lambda:m.authenticate_route_interval(process,pre,final))
    test('C21-route-before-pre-authorization-rejected',lambda:m.authenticate_route_interval({**process,'started_at_utc':'2000-01-01T00:00:00.100000+00:00'},pre,final),True)
    test('C21-receipt-after-final-authorization-rejected',lambda:m.authenticate_route_interval({**process,'ended_at_utc':'2000-01-01T00:00:06+00:00'},pre,final),True)
    wrong_pre_result={**result,'pre_route_authorization':{**preref,'sha256':'sha256:'+'0'*64}}
    test('C21-result-wrong-pre-route-hash-rejected',lambda:retained(r=wrong_pre_result),True)
    test('C21-result-wrong-current-nonce-rejected',lambda:retained(r={**result,'terminal_nonce':'0'*64}),True)
    test('C21-result-final-binding-authority-rejected',lambda:retained(r={**result,'final_binding_sha256':'sha256:'+'0'*64}),True)
    test('C21-result-missing-pre-route-first-read-rejected',lambda:retained(r={**result,'bound_inputs':{'first_read_file_hashes':{}}}),True)
    def acyclic_hash_dag():
        def encode(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
        def hashed(value):return 'sha256:'+hashlib.sha256(encode(value)).hexdigest()
        pre_bytes=encode(pre); pre_hash=hashed(pre)
        ref={'path':str(output/'hash-dag-pre-route.json'),'sha256':pre_hash}
        rr={**result,'pre_route_authorization':ref,'bound_inputs':{'first_read_file_hashes':{ref['path']:pre_hash}}}
        produced_hash=hashed(rr)
        exact_argv=m.retained_argv('second-probe',ref['path'],pre_hash,record,str(output/'hash-dag-output.json'))
        pr={**process,'argv':exact_argv,'output_files':{'hash-dag-output.json':produced_hash}}
        process_hash=hashed(pr)
        rec={**record,'pre_route_authorization':ref,'second_probe_result':{'path':str(output/'hash-dag-output.json'),'sha256':produced_hash},
             'second_probe_process':{'path':str(output/'hash-dag-process.json'),'sha256':process_hash}}
        record_hash=hashed(rec)
        ff={**final,'pre_route_authorization':ref,'retained_validations':[{'path':str(output/'hash-dag-record.json'),'sha256':record_hash}]}
        final_hash=hashed(ff)
        if final_hash.encode() in pre_bytes or final_hash==pre_hash:raise AssertionError('pre-route depends on future final binding')
        m.authenticate_pre_route(ff,pre)
        dependency_order={'pre-route':[],'output':['pre-route'],'process':['pre-route','output'],'record':['pre-route','output','process'],'final':['pre-route','record']}
        completed=set()
        for node,deps in dependency_order.items():
            if not set(deps)<=completed:raise AssertionError('hash dependency cycle')
            completed.add(node)
        for path,value,expected in [('hash-dag-pre-route.json',pre,pre_hash),('hash-dag-output.json',rr,produced_hash),
                                    ('hash-dag-process.json',pr,process_hash),('hash-dag-record.json',rec,record_hash),('hash-dag-final.json',ff,final_hash)]:
            if m.publish(output/path,value)!=expected:raise AssertionError('serialized DAG bytes differ from input hash')
        m.publish(output/'acyclic-hash-dag.json',{'nodes':dependency_order,'pre_route_sha256':pre_hash,'output_sha256':produced_hash,
            'process_receipt_sha256':process_hash,'record_sha256':record_hash,'final_binding_sha256':final_hash,'scope':'unrelated format witness only; no actual retained task evidence'})
    test('C21-construct-pre-output-record-final-hash-DAG',acyclic_hash_dag)
    cyclic_argv=list(argv);cyclic_argv[5]=str(output/'unrelated-final-binding.json');cyclic_argv[7]='sha256:'+'0'*64
    test('C21-receipt-argv-final-binding-hash-rejected',lambda:retained({**process,'argv':cyclic_argv}),True)

    # The root002 chain is tested using definitions and specification metadata
    # only. No qualification output is opened by these controls.
    test('C03-ROOT002-constants-spec-authorized-chain',lambda:m.qualification_definition(reader_specification))
    def owned_definition_consistency():
        if reader_specification['retained_route']['record_format']!=m.RETAINED_RECORD_FORMAT:
            raise AssertionError('owned retained record schema/version differs')
        if set(reader_specification['terminal_binding_fields'])!=set(final_schema['required']):
            raise AssertionError('owned specification/final schema fields differ')
        if pre_schema['properties']['format']['const']!=m.PRE_FORMAT or final_schema['properties']['format']['const']!=m.FORMAT:
            raise AssertionError('owned final/pre schema format literals differ')
    test('C03-owned-source-schema-spec-definition-consistency',owned_definition_consistency)
    for field in ('root002_report','engineering_record','independent_report'):
        for part,wrong in (('path',str(output/'stale-qualified003.json')),('sha256','0'*64)):
            malformed=copy.deepcopy(reader_specification);malformed['qualification'][field][part]=wrong
            test('C03-spec-'+field+'-'+part+'-rejected',lambda malformed=malformed:m.qualification_definition(malformed),True)
    for constant in ('QUAL_REPORT','ENGINEERING','INDEPENDENT_REPORT','QUAL_REPORT_SHA','ENGINEERING_SHA','INDEPENDENT_REPORT_SHA'):
        def changed_constant(constant=constant):
            original=getattr(m,constant)
            try:
                setattr(m,constant,'0'*64 if constant.endswith('_SHA') else output/'stale-qualified003.json')
                m.qualification_definition(reader_specification)
            finally:setattr(m,constant,original)
        test('C03-constant-'+constant+'-rejected',changed_constant,True)
    def common_wrong_qualification_path():
        original=m.QUAL_REPORT;malformed=copy.deepcopy(reader_specification)
        try:
            m.QUAL_REPORT=output/'copied-but-wrong-qualification003.json'
            malformed['qualification']['root002_report']['path']=str(m.QUAL_REPORT)
            m.qualification_definition(malformed)
        finally:m.QUAL_REPORT=original
    test('C03-matching-wrong-constant-spec-still-rejected',common_wrong_qualification_path,True)

    # Genuine route canonicalization produces prefixed result/first-read hashes
    # while schemas and actual caller argv permit bare digests. Authentication
    # must compare the digest, preserving both actual representations.
    def mixed_common_refs():
        pp=copy.deepcopy(pre);ff=copy.deepcopy(final)
        for field in ('actor_stop','cohort_seal','orchestration_seal'):
            pp[field]['sha256']=m.plain_hash(pp[field]['sha256'])
        for key in ff['registered_files']:ff['registered_files'][key]=m.plain_hash(ff['registered_files'][key])
        before=json.dumps([pp,ff],sort_keys=True)
        m.authenticate_pre_route(ff,pp)
        if json.dumps([pp,ff],sort_keys=True)!=before:raise AssertionError('authentication rewrote raw references')
    test('C21-mixed-bare-prefixed-common-refs-preserved',mixed_common_refs)
    def mixed_route_formats(reverse=False):
        rr=copy.deepcopy(result);rec=copy.deepcopy(record);proc=copy.deepcopy(process)
        rec['pre_route_authorization']['sha256']=m.plain_hash(rec['pre_route_authorization']['sha256'])
        rec['route_sha256']=m.plain_hash(rec['route_sha256'])
        proc['argv'][proc['argv'].index('--pre-route-authorization-sha256')+1]=m.plain_hash(argv[7])
        if reverse:
            rr['pre_route_authorization']['sha256']=m.plain_hash(rr['pre_route_authorization']['sha256'])
            rr['bound_inputs']['first_read_file_hashes'][preref['path']]=m.plain_hash(preref['sha256'])
            rec['pre_route_authorization']['sha256']='sha256:'+m.plain_hash(preref['sha256'])
        before=json.dumps([rr,rec,proc],sort_keys=True)
        m.authenticate_retained_process(proc,rr,mode='second-probe',expected_argv=argv,record=rec,
            removed_at='2000-01-01T00:00:00+00:00',checker=checker,native_claim=claim)
        if json.dumps([rr,rec,proc],sort_keys=True)!=before:raise AssertionError('raw route/record/process data rewritten')
    test('C21-genuine-canonical-result-bare-record-argv',mixed_route_formats)
    test('C21-reverse-mixed-result-first-read-refs',lambda:mixed_route_formats(True))
    bad_digest_argv=list(argv);bad_digest_argv[7]='sha256:'+'0'*64
    test('C21-different-digest-argv-still-rejected',lambda:retained({**process,'argv':bad_digest_argv}),True)
    duplicate_flag_argv=list(argv)+['--pre-route-authorization-sha256','f'*64]
    test('C21-duplicate-authorization-digest-flag-rejected',lambda:retained({**process,'argv':duplicate_flag_argv}),True)
    altered_other_argv=list(argv);altered_other_argv[-1]=str(output/'different-actual-result.json')
    test('C21-other-argv-token-remains-exact',lambda:retained({**process,'argv':altered_other_argv}),True)
    test('C21-closed-reference-mixed-digest',lambda:m.same_ref(preref,{**preref,'sha256':'f'*64}))
    def wrong_path_identity():
        if m.same_ref(preref,{**preref,'path':str(output/'different-pre-route.json')}):
            raise AssertionError('same digest gave authority to a different path')
    test('C21-same-digest-different-path-distinct',wrong_path_identity)
    test('C21-extra-nested-reference-key-rejected',lambda:m.same_ref(preref,{**preref,'final_binding_sha256':'0'*64}),True)

    # Validate every required top-level field, constant/type/format constraint,
    # closed reference slot and verifier-map key/value in both real schemas.
    # Both route and reader use these same fully authenticated schema helpers.
    def validate_doc(kind,doc):
        return m.validate_pre_route(doc) if kind=='pre' else m.authenticate_pre_route(doc,pre)
    for kind,base,schema in (('pre',pre,pre_schema),('final',final,final_schema)):
        test('C-schema-'+kind+'-complete-valid',lambda kind=kind,base=base:validate_doc(kind,base))
        test('C-schema-'+kind+'-wrong-top-type',lambda kind=kind:validate_doc(kind,[]),True)
        for field in schema['required']:
            malformed=copy.deepcopy(base);malformed.pop(field)
            test('C-schema-'+kind+'-missing-'+field,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
        malformed={**copy.deepcopy(base),'future_result':{'path':str(output/'not-yet-produced.json'),'sha256':'0'*64}}
        test('C-schema-'+kind+'-extra-top-output-reference',lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
        for field,constraint in schema['properties'].items():
            if 'const' in constraint:
                malformed={**copy.deepcopy(base),field:'WRONG_REGISTERED_LITERAL'}
                test('C-schema-'+kind+'-constant-'+field,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
                malformed={**copy.deepcopy(base),field:{'nested':'wrong type'}}
                test('C-schema-'+kind+'-constant-type-'+field,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
            if constraint.get('type')=='string':
                malformed={**copy.deepcopy(base),field:False}
                test('C-schema-'+kind+'-string-type-'+field,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
            if constraint.get('format')=='date-time':
                for label,wrong in (('timezone','2000-01-01T00:00:00'),('calendar','2000-13-40T00:00:00Z'),('syntax','yesterday')):
                    malformed={**copy.deepcopy(base),field:wrong}
                    test('C-schema-'+kind+'-date-'+field+'-'+label,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
            if constraint.get('pattern'):
                for label,wrong in (('upper','E'*64),('length','e'*63),('newline','e'*64+'\n')):
                    malformed={**copy.deepcopy(base),field:wrong}
                    test('C-schema-'+kind+'-pattern-'+field+'-'+label,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
        ref_fields=['actor_stop','cohort_seal','orchestration_seal']
        if kind=='final':ref_fields+=['pre_route_authorization','transport_trace','scope_interpretation','public_probe_observations','retained_validations']
        for field in ref_fields:
            ref={'path':str(output/('unrelated-'+kind+'-'+field+'.json')),'sha256':'sha256:'+'a'*64}
            complete=copy.deepcopy(base)
            # Common references must match for positive final controls.
            if field in ('actor_stop','cohort_seal','orchestration_seal'):ref=copy.deepcopy(base[field])
            complete[field]=[ref] if field=='retained_validations' else ref
            test('C-schema-'+kind+'-valid-ref-'+field,lambda kind=kind,complete=complete:validate_doc(kind,complete))
            mutations=[('nested-final-hash',{**ref,'final_binding_sha256':'f'*64}),
                       ('nested-output',{**ref,'output':{'path':str(output/'future-output.json'),'sha256':'f'*64}}),
                       ('missing-path',{'sha256':ref['sha256']}),('missing-hash',{'path':ref['path']}),
                       ('relative-path',{**ref,'path':'relative.json'}),('path-type',{**ref,'path':False}),
                       ('hash-type',{**ref,'sha256':{'sha256':'a'*64}}),('hash-short',{**ref,'sha256':'a'*63}),
                       ('hash-newline',{**ref,'sha256':'a'*64+'\n'}),('ref-type',[])]
            for label,wrong in mutations:
                malformed=copy.deepcopy(complete);malformed[field]=[wrong] if field=='retained_validations' else wrong
                test('C-schema-'+kind+'-ref-'+field+'-'+label,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
        for key in base['registered_files']:
            malformed=copy.deepcopy(base);malformed['registered_files'].pop(key)
            test('C-schema-'+kind+'-map-missing-'+key,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
            for label,wrong in (('type',{}),('hash','not-a-digest'),('newline','a'*64+'\n')):
                malformed=copy.deepcopy(base);malformed['registered_files'][key]=wrong
                test('C-schema-'+kind+'-map-'+label+'-'+key,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
        for label,wrong in (('map-type',[]),('map-extra',{**base['registered_files'],'final_binding_sha256':'a'*64})):
            malformed={**copy.deepcopy(base),'registered_files':wrong}
            test('C-schema-'+kind+'-'+label,lambda kind=kind,malformed=malformed:validate_doc(kind,malformed),True)
    for field in ('scope_interpretation','public_probe_observations'):
        test('C-schema-final-nullable-'+field,lambda field=field:m.authenticate_pre_route({**final,field:None},pre))
        test('C-schema-final-invalid-nullable-'+field,lambda field=field:m.authenticate_pre_route({**final,field:False},pre),True)
    test('C-schema-final-retained-list-type',lambda:m.authenticate_pre_route({**final,'retained_validations':{}},pre),True)
    def copied_nested_future_ref():
        pp=copy.deepcopy(pre);ff=copy.deepcopy(final)
        pp['actor_stop']['final_binding_sha256']='f'*64
        ff['actor_stop']=copy.deepcopy(pp['actor_stop'])
        m.authenticate_pre_route(ff,pp)
    test('C21-copied-nested-future-hash-both-authorities-rejected',copied_nested_future_ref,True)
    test('C-schema-unknown-keyword-never-ignored',lambda:m.schema_definition({**pre_schema,'unevaluatedProperties':False}),True)
    test('C-schema-unsupported-nested-keyword-never-ignored',lambda:m.schema_definition({'type':'object','properties':{'ref':{'$ref':'future-schema'}}}),True)
    test('C-schema-unsupported-format-never-ignored',lambda:m.schema_definition({'type':'string','format':'unregistered-format'}),True)
    test('C-schema-bad-type-never-ignored',lambda:m.schema_definition({'type':['object','null']}),True)
    test('C-schema-bad-items-never-ignored',lambda:m.schema_definition({'type':'array','items':False}),True)

    def control_file(name):
        path = output / (name + ".txt"); path.write_bytes(b"unrelated-initial-control-bytes"); return path
    def repeated_same():
        r=m.Reads(); p=control_file("repeated-same"); r.raw(p); r.raw(p); r.finalize()
    test("C24-unchanged-duplicate-and-final-reread",repeated_same)
    def repeated_changed():
        r=m.Reads(); p=control_file("repeated-changed"); r.raw(p); p.write_bytes(b"unrelated-changed"); r.raw(p)
    test("C24-duplicate-path-change-rejected",repeated_changed,True)
    for kind in ("binding","interpretation","actorstop","seal","receipt","external-reference"):
        def changed_at_completion(kind=kind):
            r=m.Reads(); p=control_file("final-"+kind); q=control_file("final-unaffected-"+kind)
            r.raw(p); r.raw(q); p.write_bytes(b"changed-external-bound-control");
            try:r.finalize()
            finally:
                if not any(row["path"]==str(q) and row["purpose"].startswith("independent final") for row in r.rows):
                    raise AssertionError("completion skipped another bound file after mutation")
        test("C24-final-"+kind+"-mutation-rejected",changed_at_completion,True)
    def restored_mutation():
        r=m.Reads(); p=control_file("restored"); original=p.read_bytes(); r.raw(p); p.write_bytes(b"changed")
        try:r.raw(p)
        except m.Block:pass
        p.write_bytes(original); r.finalize()
    test("C24-mutation-restored-still-rejected",restored_mutation,True)
    def external_hook():
        r=m.Reads(); r.enable_hook=True; p=control_file("external-hook"); r.hook("open",(str(p),"rb",0))
        if str(p) not in r.first:raise AssertionError("external hooked read not bound")
        p.write_bytes(b"hooked-input-changed"); r.finalize()
    test("C24-external-hook-read-final-mutation-rejected",external_hook,True)
    def external_deleted():
        r=m.Reads(); p=control_file("external-deleted"); r.raw(p); p.unlink(); r.finalize()
    test("C24-bound-external-deletion-rejected",external_deleted,True)
    def unregistered_temporary():
        r=m.Reads(); r.enable_hook=True; p=output/"never-created-temporary"
        r.hook("tempfile.mkdtemp",(str(p),))
        if r.temporary_roots:raise AssertionError("unregistered temporary creator was trusted")
    test("C24-unregistered-temp-prefix-not-exempt",unregistered_temporary)
    def ephemeral_archive():
        # An unrelated lifetime-format witness, not a production API invocation.
        r=m.Reads(); root=output/"synthetic-ephemeral"; root.mkdir(); p=root/"control.bin"; p.write_bytes(b"ephemeral-control")
        r.archive_root=output/"synthetic-archive"; r.temporary_roots[root]={"root":str(root),"event":"SYNTHETIC_CONTROL_ONLY"}
        r._observe(p,p.read_bytes(),"unrelated generated lifetime format witness"); shutil.rmtree(root); r.finalize()
        if len(r.first)!=1 or not any(row.get("lifetime")=="ephemeral" for row in r.rows):raise AssertionError("ephemeral archive not retained")
    test("C24-generated-lifetime-lossless-archive",ephemeral_archive)

    report={"format":"verislop.d21-reader-format-controls/4","status":"CONTROL_PASS" if all(r["control_pass"] for r in rows) else "CONTROL_FAIL",
            "control_count":len(rows),"controls":rows,"scope":"unrelated fabricated format/control objects and isolated local bytes only",
            "qualified_api_calls":0,"terminal_audit_executions":0,"task_artifact_reads":0,"model_calls":0,"task_builds":0,"public_probe_calls":0,
            "reader_sha256":hashlib.sha256((HERE/"terminal-scope-reader-004.py").read_bytes()).hexdigest(),
            "assertion_limit":"These controls establish local format/authentication/lifetime boundaries only; no task or qualification claim is VERIFIED."}
    m.publish(output/"report.json",report)
    print(json.dumps({"status":report["status"],"control_count":len(rows),"report":str(output/"report.json")},sort_keys=True))
    return 0 if report["status"]=="CONTROL_PASS" else 2


if __name__=="__main__":raise SystemExit(main())
