#!/usr/bin/env python3
"""Unrelated format/control witnesses only; no task or qualified API execution."""
from __future__ import annotations
import argparse
import ast
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).absolute().parent


class ControlOracleAssertion(AssertionError):
    """A failed control assertion is never an expected format rejection."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    output = Path(args.output_dir).absolute()
    if output.parent != HERE or output.exists():
        raise ValueError("control output must be a new direct scope-directory child")
    output.mkdir()
    spec = importlib.util.spec_from_file_location("scope018_format_reader008", HERE / "terminal-scope-reader-008.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # definitions/stdlib only; never main or Audit
    final_schema = json.loads((HERE/m.FINAL_SCHEMA_NAME).read_bytes())
    pre_schema = json.loads((HERE/m.PRE_SCHEMA_NAME).read_bytes())
    m.install_binding_schemas(final_schema,pre_schema)
    reader_specification = json.loads((HERE/m.SPEC_NAME).read_bytes())
    reader_registration = json.loads((HERE/m.REG_NAME).read_bytes())
    metadata_inventory = json.loads((HERE/'terminal-metadata-interface-inventory-008.json').read_bytes())
    metadata_fixtures = json.loads((HERE/'metadata-interface-control-fixtures-008.json').read_bytes())
    rows = []
    oracle_observations = []

    def format_observation(function, blocked=False):
        reason = None
        try:
            function()
            actual = "ACCEPTED_FORMAT"
        except AssertionError as exc:
            actual = "CONTROL_ASSERTION_FAILURE"
            reason = type(exc).__name__ + ": " + str(exc)
        except (m.Block, KeyError, ValueError, TypeError) as exc:
            actual = "REJECTED_FORMAT"
            reason = type(exc).__name__ + ": " + str(exc)
        desired = "REJECTED_FORMAT" if blocked else "ACCEPTED_FORMAT"
        return {"expected":desired,"actual":actual,"control_pass":actual == desired,"reason":reason}

    def test(name, function, blocked=False):
        rows.append({"id":name,**format_observation(function,blocked)})

    def exact_block_observation(function, expected_code):
        expected = "EXACT_BLOCK:" + expected_code
        reason = None
        try:
            function()
            actual = "AUTHENTICATOR_RETURNED_NORMALLY"
        except m.Block as exc:
            code, separator, _ = str(exc).partition(":")
            actual = "EXACT_BLOCK:" + code if type(exc) is m.Block and separator == ":" else "MALFORMED_OR_SUBCLASS_BLOCK"
            reason = type(exc).__name__ + ": " + str(exc)
        except Exception as exc:
            actual = "UNEXPECTED_EXCEPTION:" + type(exc).__name__
            reason = type(exc).__name__ + ": " + str(exc)
        passed = actual == expected
        return {"expected":expected,"actual":actual,"control_pass":passed,
                "status":"CONTROL_PASS" if passed else "CONTROL_FAIL","reason":reason}

    def test_exact_block(name, function, expected_code):
        rows.append({"id":name,**exact_block_observation(function,expected_code)})

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
         "registered_files":{name:"sha256:"+"a"*64 for name in ('terminal-scope-reader-008.py',m.SPEC_NAME,m.REG_NAME,m.ROUTE_NAME)},
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
    result = {"format":"verislop.stage018-retained-route-result/8","mode":"second-probe","source_root":m.SOURCE_ROOT,
              "closure_root":record["closure_root"],"retained_root":record["retained_root"],"original_root":record["original_root"],
              "original_root_absent_before_reads":True,"claim_id":claim["claim_id"],"native_claim":claim,
              "registered_route":{"id":"D21-SCOPE-RETAINED-018-008","sha256":record["route_sha256"]},
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

    prior_transport={'transport':'unrelated-old-label','relay_mode':'file','author':'UNRELATED_AUTHOR',
                     'request':'UNRELATED_REQUEST','text':'unrelated literal response'}
    accepted_transport={**prior_transport,'transport':'collaboration'}
    one_change={'changed_json_pointers':['/transport']}
    test('C02-exact-one-transport-field-correction',lambda:m.authenticate_transport_correction(prior_transport,accepted_transport,one_change))
    two_prior={**prior_transport,'relay_mode':'unrelated-old-relay'}
    test('C02-exact-two-allowed-field-correction',lambda:m.authenticate_transport_correction(two_prior,accepted_transport,{'changed_json_pointers':['/transport','/relay_mode']}))
    test('C02-empty-correction-rejected',lambda:m.authenticate_transport_correction(accepted_transport,accepted_transport,one_change),True)
    test('C02-overstated-change-pointers-rejected',lambda:m.authenticate_transport_correction(prior_transport,accepted_transport,{'changed_json_pointers':['/transport','/relay_mode']}),True)
    test('C02-missing-actual-change-pointer-rejected',lambda:m.authenticate_transport_correction(prior_transport,accepted_transport,{'changed_json_pointers':[]}),True)
    for field in ('author','request','text','new_nonmetadata_field'):
        test('C02-changed-'+field+'-rejected',lambda field=field:m.authenticate_transport_correction(prior_transport,{**accepted_transport,field:'changed-control'},one_change),True)
    test('C02-wrong-frozen-transport-rejected',lambda:m.authenticate_transport_correction(prior_transport,{**accepted_transport,'transport':'wrong-frozen-label'},one_change),True)
    test('C02-wrong-frozen-relay-rejected',lambda:m.authenticate_transport_correction(two_prior,{**accepted_transport,'relay_mode':'wrong-frozen-relay'},{'changed_json_pointers':['/transport','/relay_mode']}),True)
    test('C02-no-prior-envelope-rejected',lambda:m.authenticate_transport_correction(None,accepted_transport,one_change),True)
    test('C02-initial-submission-no-fictitious-diff',lambda:m.authenticate_transport_transition(None,prior_transport,{'metadata_only_correction':False,'changed_json_pointers':[]}))
    test('C02-unset-flag-cannot-hide-actual-diff',lambda:m.authenticate_transport_transition(prior_transport,accepted_transport,{'metadata_only_correction':False,'changed_json_pointers':[]}),True)
    test('C02-unset-flag-cannot-hide-nonmetadata-diff',lambda:m.authenticate_transport_transition(prior_transport,{**accepted_transport,'text':'changed'}, {'metadata_only_correction':False,'changed_json_pointers':[]}),True)
    test('C02-first-submission-cannot-claim-correction',lambda:m.authenticate_transport_transition(None,accepted_transport,{'metadata_only_correction':True,'changed_json_pointers':['/transport']}),True)

    control_envref={'path':str(output/'unrelated-submission-envelope.json'),'sha256':'a'*64}
    completed_attempt={'process_evidence':{'kind':'completed_process_receipt'},'observed_exit_code':0,'envelope':control_envref}
    completed_receipt={'returncode':0,'timed_out':False,'cwd':str(m.PROJECT),
        'argv':[m.PYTHON,'-c',m.SUBMIT_CODE,str(m.COHORT),control_envref['path']],
        'envelope_path':control_envref['path'],'envelope_sha256':'sha256:'+'a'*64}
    test('C02-full-completed-process-representation',lambda:m.authenticate_transport_evidence(completed_attempt,completed_receipt))
    test('C02-process-boolean-returncode-rejected',lambda:m.authenticate_transport_evidence(completed_attempt,{**completed_receipt,'returncode':False}),True)
    test('C02-unrelated-process-argv-rejected',lambda:m.authenticate_transport_evidence(completed_attempt,{**completed_receipt,'argv':['/usr/bin/true']}),True)
    test('C02-process-wrong-cwd-rejected',lambda:m.authenticate_transport_evidence(completed_attempt,{**completed_receipt,'cwd':str(output)}),True)
    test('C02-process-wrong-envelope-hash-rejected',lambda:m.authenticate_transport_evidence(completed_attempt,{**completed_receipt,'envelope_sha256':'0'*64}),True)
    test('C02-tool-exit-not-process-returncode',lambda:m.authenticate_transport_evidence(completed_attempt,{'exit_code':0}),True)
    invocation_ref={'path':str(output/'unrelated-archived-tool-invocation.json'),'sha256':'b'*64}
    tool_result_ref={'path':str(output/'unrelated-original-tool-result.json'),'sha256':'c'*64}
    tool_invocation={'tool_name':'functions.exec/tools.exec_command','arguments':{'cmd':'UNRELATED_CONTROL_NEVER_EXECUTED','workdir':str(m.PROJECT)}}
    tool_result={'exit_code':1,'output':'UNRELATED_CONTROL_FAILURE','chunk_id':'UNRELATED'}
    tool_attempt={'process_evidence':{'kind':'tool_invocation_result','invocation':invocation_ref,'result':tool_result_ref},
                  'observed_exit_code':1,'native_response_publication':False,'envelope':control_envref}
    tool_registration={'invocation_reference':invocation_ref,'tool_result_reference':tool_result_ref,'exact_tool_invocation':tool_invocation}
    def tool_auth(attempt=tool_attempt,result=tool_result,invocation=tool_invocation,registered=tool_registration):
        return m.authenticate_transport_evidence(attempt,result,invocation,registered)
    def exact_tool_representation():
        before=json.dumps([tool_attempt,tool_result,tool_invocation,tool_registration],sort_keys=True)
        observed=tool_auth()
        if observed['observed_tool_exit_code']!=1 or any(observed[k] is not None for k in
            ('actual_process_returncode','actual_process_argv','actual_process_pid','process_runtime_facts')):
            raise AssertionError('tool result was conflated with an invented process')
        if before!=json.dumps([tool_attempt,tool_result,tool_invocation,tool_registration],sort_keys=True):
            raise AssertionError('original archived tool facts were rewritten')
    test('C02-exact-registered-tool-rejection-distinct-preserved',exact_tool_representation)
    test('C02-missing-archived-invocation-unresolved',lambda:tool_auth(invocation=None),True)
    test('C02-missing-invocation-registration-unresolved',lambda:tool_auth(registered=None),True)
    test('C02-unrelated-tool-invocation-rejected',lambda:tool_auth(invocation={**tool_invocation,'arguments':{'cmd':'different-unrelated-control'}}),True)
    test('C02-wrong-invocation-reference-rejected',lambda:tool_auth(registered={**tool_registration,'invocation_reference':{**invocation_ref,'sha256':'0'*64}}),True)
    test('C02-wrong-tool-result-reference-rejected',lambda:tool_auth(registered={**tool_registration,'tool_result_reference':{**tool_result_ref,'sha256':'0'*64}}),True)
    test('C02-tool-boolean-exit-rejected',lambda:tool_auth(result={**tool_result,'exit_code':True}),True)
    test('C02-tool-result-wrong-exit-rejected',lambda:tool_auth(result={**tool_result,'exit_code':2}),True)
    test('C02-tool-success-no-native-success-authority',lambda:tool_auth(attempt={**tool_attempt,'observed_exit_code':0},result={**tool_result,'exit_code':0}),True)
    test('C02-tool-rejection-after-publication-rejected',lambda:tool_auth(attempt={**tool_attempt,'native_response_publication':True}),True)
    for field in ('argv','pid','returncode','started_at_utc','ended_at_utc','timed_out'):
        test('C02-tool-result-forged-process-'+field+'-rejected',lambda field=field:tool_auth(result={**tool_result,field:'invented-control-fact'}),True)
    test('C02-observed-exit-boolean-rejected',lambda:tool_auth(attempt={**tool_attempt,'observed_exit_code':True}),True)
    test('C02-unknown-evidence-kind-rejected',lambda:tool_auth(attempt={**tool_attempt,'process_evidence':{'kind':'authored-PASS'}}),True)
    literal_origin={'format':'verislop.literal-final/1','text':'unrelated literal \u03bb\n\x00'}
    literal_raw=literal_origin['text'].encode('utf-8')
    test('C02-exact-controller-literal-origin-UTF8',lambda:m.authenticate_literal_final_origin(literal_origin,literal_raw,'/text'))
    test('C02-literal-origin-copy-mutation-rejected',lambda:m.authenticate_literal_final_origin(literal_origin,literal_raw+b'changed','/text'),True)
    test('C02-literal-origin-wrong-pointer-rejected',lambda:m.authenticate_literal_final_origin(literal_origin,literal_raw,'/other'),True)
    test('C02-literal-origin-wrong-format-rejected',lambda:m.authenticate_literal_final_origin({**literal_origin,'format':'invented'},literal_raw,'/text'),True)
    test('C02-literal-origin-wrong-type-rejected',lambda:m.authenticate_literal_final_origin({**literal_origin,'text':{}},literal_raw,'/text'),True)
    test('C02-literal-origin-extra-field-rejected',lambda:m.authenticate_literal_final_origin({**literal_origin,'invented_output':'x'},literal_raw,'/text'),True)

    # These controls consume the independent preregistered normative lists and
    # Python AST, rather than only asking whether a helper accepts its own data.
    transport_policy = reader_specification['transport_trace']
    registered_transport_policy = reader_registration['transport_evidence_representation']
    source_tree = ast.parse((HERE/'terminal-scope-reader-008.py').read_bytes())
    source_functions = {n.name:n for n in source_tree.body if isinstance(n,ast.FunctionDef)}
    audit_class = next(n for n in source_tree.body if isinstance(n,ast.ClassDef) and n.name=='Audit')
    transport_method = next(n for n in audit_class.body if isinstance(n,ast.FunctionDef) and n.name=='transport')
    source_fields = next(ast.literal_eval(n.value) for n in source_tree.body if isinstance(n,ast.Assign) and
                         any(isinstance(t,ast.Name) and t.id=='TRANSPORT_FIELD_REQUIREMENTS' for t in n.targets))
    def source_spec_registration_identity():
        if source_fields != m.TRANSPORT_FIELD_REQUIREMENTS:
            raise ValueError('loaded source field lists differ from independent static AST')
        for key,value in source_fields.items():
            if transport_policy.get(key)!=value or registered_transport_policy.get(key)!=value:
                raise ValueError('SOURCE/SPEC/registration field list differs: '+key)
        if transport_policy != registered_transport_policy:
            raise ValueError('complete registered transport representations differ')
        m.transport_field_identity(transport_policy,registered_transport_policy)
    test('C006-SOURCE-SPEC-registration-exact-field-list-identity',source_spec_registration_identity)
    def source_path(node):
        if isinstance(node,ast.Name):return node.id,()
        if isinstance(node,ast.Subscript) and isinstance(node.slice,ast.Constant) and type(node.slice.value) is str:
            parent=source_path(node.value)
            if parent is not None:return parent[0],parent[1]+(node.slice.value,)
        return None
    def accessed_keys(tree,base,prefix=()):
        keys=set()
        for node in ast.walk(tree):
            path=source_path(node)
            if path is not None and path[0]==base and len(path[1])>len(prefix) and path[1][:len(prefix)]==prefix:
                keys.add(path[1][len(prefix)])
            if (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='get' and node.args and
                isinstance(node.args[0],ast.Constant) and type(node.args[0].value) is str):
                parent=source_path(node.func.value)
                if parent==(base,prefix):keys.add(node.args[0].value)
        return keys
    def exact_access_coverage(tree,base,key,prefix=()):
        if accessed_keys(tree,base,prefix)!=set(transport_policy[key]):
            raise ValueError('normative '+key+' differs from independent actual source dereferences')
    test('C006-AST-actual-top-level-dereferences-covered',lambda:exact_access_coverage(transport_method,'trace','required'))
    test('C006-AST-actual-request-dereferences-covered',lambda:exact_access_coverage(transport_method,'row','requests_required'))
    test('C006-AST-actual-literal-origin-dereferences-covered',lambda:exact_access_coverage(transport_method,'row','literal_final_origin_required',('literal_final_origin',)))
    auth=source_functions['authenticate_transport_evidence']
    completed_branch=next(n for n in auth.body if isinstance(n,ast.If))
    test('C006-AST-completed-result-dereferences-covered',lambda:exact_access_coverage(completed_branch,'result','completed_process_required'))
    tool_part=ast.Module(body=auth.body[auth.body.index(completed_branch)+1:],type_ignores=[])
    test('C006-AST-tool-result-dereferences-covered',lambda:exact_access_coverage(tool_part,'result','tool_result_required'))
    test('C006-AST-tool-invocation-dereferences-covered',lambda:exact_access_coverage(tool_part,'invocation','tool_invocation_required'))
    test('C006-AST-registered-tool-identity-dereferences-covered',lambda:exact_access_coverage(tool_part,'registered','registered_tool_invocation_required'))
    def submission_source_coverage():
        observed=accessed_keys(transport_method,'attempt') | accessed_keys(auth,'attempt')
        for name in ('authenticate_transport_transition','authenticate_transport_correction'):
            observed |= accessed_keys(source_functions[name],'attempt')
        if observed!=set(transport_policy['submission_required']+transport_policy['tool_submission_required']):
            raise ValueError('normative common/conditional submission fields differ from actual AST accesses')
        evidence_keys=set().union(*(set(v) for v in transport_policy['process_evidence_required'].values()),
                                  *(set(v) for v in transport_policy['process_evidence_optional'].values()))
        if accessed_keys(transport_method,'process')!=evidence_keys:
            raise ValueError('normative process-evidence variants differ from actual AST accesses')
    test('C006-AST-common-conditional-and-variant-dereferences-covered',submission_source_coverage)
    def validators_before_consumption():
        calls=[n for n in ast.walk(transport_method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='validate_transport_structure']
        first_access=min(n.lineno for n in ast.walk(transport_method) if source_path(n) is not None and source_path(n)[0]=='trace' and source_path(n)[1])
        if len(calls)!=1 or calls[0].lineno>=first_access:raise ValueError('trace dereferenced before normative validation')
        main=source_functions['main']
        identity_calls=[n for n in ast.walk(main) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='transport_field_identity']
        if len(identity_calls)!=1 or accessed_keys(identity_calls[0],'registration')!={'transport_evidence_representation'}:
            raise ValueError('main does not consume registered normative representation')
    test('C006-AST-normative-validation-precedes-trace-dereferences',validators_before_consumption)
    for key in source_fields:
        bad_spec=copy.deepcopy(transport_policy);bad_spec[key]=['obsolete_actual_process']
        test('C006-SPEC-mutated-'+key+'-rejected',lambda bad_spec=bad_spec:m.transport_field_identity(bad_spec),True)
        bad_reg=copy.deepcopy(registered_transport_policy);bad_reg[key]=['obsolete_actual_process']
        test('C006-registration-mutated-'+key+'-rejected',lambda bad_reg=bad_reg:m.transport_field_identity(transport_policy,bad_reg),True)
    full_completed_attempt={**completed_attempt,'literal_final_pointer':'/text','metadata_only_correction':False,
                            'changed_json_pointers':[],
                            'process_evidence':{'kind':'completed_process_receipt','record':{'path':str(output/'unrelated-actual-process.json'),'sha256':'d'*64}}}
    full_tool_attempt={**tool_attempt,'literal_final_pointer':'/text','metadata_only_correction':False,'changed_json_pointers':[]}
    origin_ref={'path':str(output/'unrelated-controller-literal-final.json'),'sha256':'e'*64}
    def trace_for(attempt):
        return {'format':transport_policy['format'],'stage':'tier2-source-facets-018','source_root':m.SOURCE_ROOT,'controller_count':1,
                'requests':[{'request_id':'UNRELATED_REQUEST','author_agent_id':'UNRELATED_AUTHOR','literal_final':origin_ref,
                    'literal_final_origin':{'record':origin_ref,'json_pointer':'/text'},'submissions':[copy.deepcopy(attempt)]}]}
    def normative_completed_positive():
        trace=trace_for(full_completed_attempt)
        m.validate_transport_structure(trace,transport_policy)
        m.authenticate_transport_evidence(trace['requests'][0]['submissions'][0],completed_receipt)
        if any(k in trace['requests'][0]['submissions'][0] for k in ('actual_process','returncode')):
            raise ValueError('unrelated positive trace relies on legacy aliases')
    test('C006-complete-normative-completed-trace-without-legacy-fields',normative_completed_positive)
    def normative_tool_positive():
        trace=trace_for(full_tool_attempt)
        m.validate_transport_structure(trace,transport_policy)
        m.authenticate_transport_evidence(trace['requests'][0]['submissions'][0],tool_result,tool_invocation,tool_registration)
    test('C006-complete-normative-authenticated-rejected-tool-trace',normative_tool_positive)
    for key,location in [('required',()),('requests_required',('requests',0)),
                         ('literal_final_origin_required',('requests',0,'literal_final_origin')),
                         ('submission_required',('requests',0,'submissions',0))]:
        for field in transport_policy[key]:
            def missing_field(location=location,field=field):
                trace=trace_for(full_completed_attempt);obj=trace
                for component in location:obj=obj[component]
                obj.pop(field);m.validate_transport_structure(trace,transport_policy)
            test('C006-normative-missing-'+key+'-'+field+'-rejected',missing_field,True)
    for kind,attempt in [('completed_process_receipt',full_completed_attempt),('tool_invocation_result',full_tool_attempt)]:
        for field in transport_policy['process_evidence_required'][kind]:
            def missing_variant(attempt=attempt,field=field):
                trace=trace_for(attempt);trace['requests'][0]['submissions'][0]['process_evidence'].pop(field)
                m.validate_transport_structure(trace,transport_policy)
            test('C006-normative-missing-'+kind+'-'+field+'-rejected',missing_variant,True)
    test('C006-normative-missing-tool-publication-rejected',lambda:m.validate_transport_structure(trace_for({k:v for k,v in full_tool_attempt.items() if k!='native_response_publication'}),transport_policy),True)
    control_oracle = reader_specification['control_oracle']
    expected_transport_block = 'UNRESOLVED_TRANSPORT_PROCESS_IDENTITY'
    def oracle_spec_registration():
        if control_oracle != reader_registration['control_oracle'] or control_oracle['expected_code'] != expected_transport_block:
            raise ControlOracleAssertion('SPEC/registration exact control-oracle identity differs')
        expected_values={'expected_exception_type':'Block','expected_exact_Block_status':'CONTROL_PASS',
            'normal_return_status':'CONTROL_FAIL','wrong_Block_code_status':'CONTROL_FAIL','assertion_failure_status':'CONTROL_FAIL',
            'unrelated_exception_status':'CONTROL_FAIL','generic_assertion_actual':'CONTROL_ASSERTION_FAILURE'}
        if any(control_oracle.get(k)!=v for k,v in expected_values.items()):
            raise ControlOracleAssertion('normative oracle conflates failure with expected rejection')
    test('C007-SPEC-registration-exact-control-oracle',oracle_spec_registration)
    def missing_invocation_unresolved(omit=False, authenticator=None):
        attempt=copy.deepcopy(full_tool_attempt)
        if omit:attempt['process_evidence'].pop('invocation')
        else:attempt['process_evidence']['invocation']=None
        trace=trace_for(attempt);m.validate_transport_structure(trace,transport_policy)
        if authenticator is None:authenticator=m.authenticate_transport_evidence
        return authenticator(attempt,tool_result,None,None)
    test_exact_block('C006-normative-null-invocation-retained-but-unresolved',missing_invocation_unresolved,expected_transport_block)
    test_exact_block('C006-normative-absent-invocation-retained-but-unresolved',lambda:missing_invocation_unresolved(True),expected_transport_block)
    def simulated_wrong_block(*_):raise m.Block('BINDING_INVALID: unrelated simulated authenticator fault')
    def simulated_expected_block(*_):raise m.Block(expected_transport_block+': unrelated simulated missing invocation')
    def simulated_value_error(*_):raise ValueError('unrelated simulated assertion fault previously false-PASS')
    def simulated_assertion_error(*_):raise ControlOracleAssertion('unrelated simulated control assertion failure')
    def oracle_witness(label,authenticator,expected_status,expected_actual):
        observed=exact_block_observation(lambda:missing_invocation_unresolved(authenticator=authenticator),expected_transport_block)
        oracle_observations.append({'scenario':label,**observed})
        if observed['status']!=expected_status or observed['actual']!=expected_actual:
            raise ControlOracleAssertion('exact Block oracle misclassified simulated '+label)
    test('C007-normal-authenticator-return-is-actual-control-failure',lambda:oracle_witness(
        'normal authenticator return',lambda *_:None,'CONTROL_FAIL','AUTHENTICATOR_RETURNED_NORMALLY'))
    test('C007-wrong-Block-code-is-actual-control-failure',lambda:oracle_witness(
        'wrong Block code',simulated_wrong_block,'CONTROL_FAIL','EXACT_BLOCK:BINDING_INVALID'))
    test('C007-expected-exact-Block-is-actual-control-pass',lambda:oracle_witness(
        'expected exact Block',simulated_expected_block,'CONTROL_PASS','EXACT_BLOCK:'+expected_transport_block))
    test('C007-ValueError-fault-is-actual-control-failure',lambda:oracle_witness(
        'ValueError fault',simulated_value_error,'CONTROL_FAIL','UNEXPECTED_EXCEPTION:ValueError'))
    test('C007-assertion-fault-is-actual-control-failure',lambda:oracle_witness(
        'assertion fault',simulated_assertion_error,'CONTROL_FAIL','UNEXPECTED_EXCEPTION:ControlOracleAssertion'))
    def generic_assertion_witness(blocked):
        observed=format_observation(lambda:simulated_assertion_error(),blocked)
        oracle_observations.append({'scenario':'generic assertion with blocked='+str(blocked),
                                    'status':'CONTROL_PASS' if observed['control_pass'] else 'CONTROL_FAIL',**observed})
        if observed['control_pass'] or observed['actual']!='CONTROL_ASSERTION_FAILURE':
            raise ControlOracleAssertion('generic harness counted an assertion as expected rejection')
    test('C007-generic-assertion-cannot-false-PASS-blocked-True',lambda:generic_assertion_witness(True))
    test('C007-generic-assertion-cannot-false-PASS-blocked-False',lambda:generic_assertion_witness(False))
    def owned_logic_unchanged():
        filenames=['terminal-scope-reader-specification','terminal-scope-reader-binding-schema',
            'retained-pre-route-authorization-schema','terminal-scope-reader','retained-validation-route',
            'terminal-scope-reader-registration','terminal-scope-reader-format-controls','terminal-scope-reader-prerepair-amendment']
        formats=['verislop.d21-terminal-scope-binding','verislop.d21-retained-pre-route-authorization',
            'verislop.stage018-retained-validation','verislop.stage018-retained-route-result',
            'verislop.d21-terminal-scope-reader-specification','verislop.d21-terminal-scope-report','verislop.d21-reader-format-controls']
        for stem in ('terminal-scope-reader','retained-validation-route'):
            changed=(HERE/(stem+'-008.py')).read_bytes().decode('utf-8')
            for name in filenames:
                for suffix in ('.py','.json'):changed=changed.replace(name+'-008'+suffix,name+'-007'+suffix)
            for name in formats:changed=changed.replace(name+'/8',name+'/7')
            changed=changed.replace('D21-SCOPE-RETAINED-018-008','D21-SCOPE-RETAINED-018-007').replace('scope018_retained_reader008','scope018_retained_reader007')
            old=(HERE/(stem+'-007.py')).read_bytes()
            if stem=='retained-validation-route':
                if changed.encode('utf-8')!=old:raise ControlOracleAssertion('008 changed retained-route logic')
                continue
            new_tree=ast.parse(changed);old_tree=ast.parse(old)
            additions={'metadata_field_identity','metadata_record','validate_protocol_metadata','validate_task_result_metadata','validate_aggregate_metadata'}
            removed_functions={n.name for n in new_tree.body if isinstance(n,ast.FunctionDef) and n.name in additions}
            if removed_functions!=additions:raise ControlOracleAssertion('registered metadata additions differ')
            new_tree.body=[n for n in new_tree.body if not (isinstance(n,ast.FunctionDef) and n.name in additions) and
                not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'METADATA_REQUIRED','METADATA_FORMAT'} for t in n.targets))]
            old_audit=next(n for n in old_tree.body if isinstance(n,ast.ClassDef) and n.name=='Audit')
            new_audit=next(n for n in new_tree.body if isinstance(n,ast.ClassDef) and n.name=='Audit')
            old_pre=next(n for n in old_audit.body if isinstance(n,ast.FunctionDef) and n.name=='preparation')
            old_need=next(n for n in old_pre.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and
                isinstance(n.value.func,ast.Name) and n.value.func.id=='need' and
                'protocol' in ast.unparse(n) and 'oracle_calls' in ast.unparse(n))
            for method in new_audit.body:
                if not isinstance(method,ast.FunctionDef):continue
                if method.name=='preparation':
                    replacements=[i for i,n in enumerate(method.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and
                        isinstance(n.value.func,ast.Name) and n.value.func.id=='validate_protocol_metadata']
                    if len(replacements)!=1:raise ControlOracleAssertion('protocol delta differs')
                    method.body[replacements[0]]=copy.deepcopy(old_need)
                if method.name=='native':
                    additions_here=[n for n in method.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and
                        isinstance(n.value.func,ast.Name) and n.value.func.id=='validate_task_result_metadata']
                    if len(additions_here)!=1:raise ControlOracleAssertion('native delta differs')
                    method.body=[n for n in method.body if n not in additions_here]
            new_main=next(n for n in new_tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
            main_additions=[n for n in new_main.body if (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='metadata_inventory' for t in n.targets)) or
                (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='metadata_field_identity')]
            if len(main_additions)!=2:raise ControlOracleAssertion('main metadata input delta differs')
            new_main.body=[n for n in new_main.body if n not in main_additions]
            if ast.dump(new_tree,include_attributes=False)!=ast.dump(old_tree,include_attributes=False):
                raise ControlOracleAssertion('008 changed reader logic beyond registered metadata interface correction')
    test('C008-reader-only-registered-metadata-delta-route-only-owned-versions',owned_logic_unchanged)

    metadata_policy=reader_specification['metadata_interfaces']
    def metadata_source_spec_registration():
        static=next(ast.literal_eval(n.value) for n in source_tree.body if isinstance(n,ast.Assign) and
                    any(isinstance(t,ast.Name) and t.id=='METADATA_REQUIRED' for t in n.targets))
        if static!=m.METADATA_REQUIRED or static!=metadata_inventory['required_keys']:
            raise ControlOracleAssertion('metadata literal SOURCE/inventory differs')
        m.metadata_field_identity(metadata_policy,reader_registration['metadata_interfaces'],metadata_inventory)
        for key,ref in metadata_inventory['registered_producer_constructors'].items():
            raw=Path(ref['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=m.plain_hash(ref['sha256']):raise ControlOracleAssertion('producer source changed')
            parsed=ast.parse(raw)
            dicts=[n for n in ast.walk(parsed) if isinstance(n,ast.Dict) and n.lineno==ref['constructor_line']]
            if len(dicts)!=1:raise ControlOracleAssertion('constructor selector missing/ambiguous')
            actual=sorted(k.value for k in dicts[0].keys if isinstance(k,ast.Constant) and type(k.value) is str)
            if len(actual)!=len(dicts[0].keys) or actual!=static[key]:raise ControlOracleAssertion('frozen producer keys differ '+key)
            observed=metadata_inventory['actual_authorized_metadata_key_inventories'][key]['actual_keys']
            if observed!=static[key]:raise ControlOracleAssertion('actual sealed metadata keys differ '+key)
        proto_keys=accessed_keys(source_functions['validate_protocol_metadata'],'protocol')
        row_keys=set().union(*(accessed_keys(n,'result') for n in [source_functions['validate_task_result_metadata'],
            next(n for n in audit_class.body if isinstance(n,ast.FunctionDef) and n.name=='native'),
            next(n for n in audit_class.body if isinstance(n,ast.FunctionDef) and n.name=='review'),
            next(n for n in audit_class.body if isinstance(n,ast.FunctionDef) and n.name=='evaluate')]))
        aggregate_keys=accessed_keys(source_functions['validate_aggregate_metadata'],'aggregate')
        if not proto_keys<=set(static['protocol']) or not row_keys<=set(static['task_result']) or not aggregate_keys<=set(static['aggregate']):
            raise ControlOracleAssertion('metadata consumer dereferences exceed frozen producer inventory')
        if {'oracle_calls','python_runtime_campaign'} & proto_keys or 'python_runtime_campaign' in aggregate_keys:
            raise ControlOracleAssertion('consumer conflates protocol/task/aggregate representations')
        if 'python_runtime_campaign' not in row_keys or 'oracle_calls' not in row_keys:
            raise ControlOracleAssertion('valid per-task no-runtime/no-oracle constraint removed')
        prep=next(n for n in audit_class.body if isinstance(n,ast.FunctionDef) and n.name=='preparation')
        if not accessed_keys(prep,'pre')<=set(static['pre_generation_binding']):raise ControlOracleAssertion('prebinding consumer mismatch')
    test('C008-independent-producer-AST-actual-inventory-SOURCE-SPEC-registration-consumer-coverage',metadata_source_spec_registration)
    fixture_interfaces=metadata_fixtures['interfaces']
    fixture_pre=metadata_fixtures['pre_binding_roots']
    test('C008-unrelated-protocol-real-fields-false-admitted',lambda:m.validate_protocol_metadata(fixture_interfaces['protocol'],fixture_pre))
    test('C008-unrelated-BLOCKED-task-row-no-runtime-admitted-without-success',lambda:m.validate_task_result_metadata(fixture_interfaces['task_result']))
    test('C008-unrelated-aggregate-distinct-shape-and-task-runtime-admitted',lambda:m.validate_aggregate_metadata(fixture_interfaces['aggregate']))
    for interface,fields in metadata_inventory['required_keys'].items():
        for field in fields:
            def missing_metadata(interface=interface,field=field):
                changed={k:v for k,v in fixture_interfaces[interface].items() if k!=field}
                if interface=='protocol':return m.validate_protocol_metadata(changed,fixture_pre)
                if interface=='task_result':return m.validate_task_result_metadata(changed)
                if interface=='aggregate':return m.validate_aggregate_metadata(changed)
                if interface in ('native_audit','origin_audit'):
                    row=copy.deepcopy(fixture_interfaces['task_result'])
                    row['native' if interface=='native_audit' else 'origin_audit']=changed
                    return m.validate_task_result_metadata(row)
                if interface=='protocol_task':
                    protocol=copy.deepcopy(fixture_interfaces['protocol']);protocol['tasks']=[changed]
                    return m.validate_protocol_metadata(protocol,fixture_pre)
                return m.metadata_record(interface,changed)
            test_exact_block('C008-missing-'+interface+'-'+field,missing_metadata,'METADATA_INTERFACE_MISMATCH')
    for field in metadata_policy['protocol_required_false_fields']:
        for index,value in enumerate((True,0,1,'false',None)):
            changed={**fixture_interfaces['protocol'],field:value}
            test_exact_block('C008-protocol-'+field+'-mutation-'+str(index),lambda changed=changed:m.validate_protocol_metadata(changed,fixture_pre),'SCOPE_LEAK')
    for interface,validator,flags in [('task_result',m.validate_task_result_metadata,['hidden_cases_loaded','python_runtime_campaign','model_identity_attested']),
                                     ('aggregate',m.validate_aggregate_metadata,['hidden_cases_loaded','model_identity_attested','original_python_assurance_relabelled'])]:
        for field in flags:
            for index,value in enumerate((True,0,1,'false',None)):
                changed={**fixture_interfaces[interface],field:value}
                test_exact_block('C008-'+interface+'-'+field+'-mutation-'+str(index),lambda changed=changed,validator=validator:validator(changed),'SCOPE_LEAK')
        for index,value in enumerate((False,True,1,0.0,'0',None)):
            changed={**fixture_interfaces[interface],'oracle_calls':value}
            test_exact_block('C008-'+interface+'-oracle_calls-mutation-'+str(index),lambda changed=changed,validator=validator:validator(changed),'SCOPE_LEAK')
    for legacy in ('oracle_calls','python_runtime_campaign'):
        changed={**fixture_interfaces['protocol'],legacy:0 if legacy=='oracle_calls' else False}
        test_exact_block('C008-protocol-rejects-task-row-legacy-'+legacy,lambda changed=changed:m.validate_protocol_metadata(changed,fixture_pre),'METADATA_INTERFACE_MISMATCH')
    changed={**fixture_interfaces['aggregate'],'python_runtime_campaign':False}
    test_exact_block('C008-aggregate-does-not-invent-top-runtime-field',lambda:m.validate_aggregate_metadata(changed),'METADATA_INTERFACE_MISMATCH')
    def aggregate_bad_row(missing=False):
        changed=copy.deepcopy(fixture_interfaces['aggregate'])
        if missing:changed['rows'][0].pop('python_runtime_campaign')
        else:changed['rows'][0]['python_runtime_campaign']=True
        return m.validate_aggregate_metadata(changed)
    test_exact_block('C008-aggregate-row-runtime-true-not-hidden-by-top-oracle0',aggregate_bad_row,'SCOPE_LEAK')
    test_exact_block('C008-aggregate-row-runtime-absent-never-default-false',lambda:aggregate_bad_row(True),'METADATA_INTERFACE_MISMATCH')
    test_exact_block('C008-task-result-cannot-be-replaced-by-aggregate',lambda:m.validate_task_result_metadata(fixture_interfaces['aggregate']),'METADATA_INTERFACE_MISMATCH')
    test_exact_block('C008-protocol-cannot-be-replaced-by-task-result',lambda:m.validate_protocol_metadata(fixture_interfaces['task_result'],fixture_pre),'METADATA_INTERFACE_MISMATCH')
    test_exact_block('C008-metadata-policy-mutated-inventory-rejected',lambda:m.metadata_field_identity(metadata_policy,reader_registration['metadata_interfaces'],{**metadata_inventory,'required_keys':{}}),'METADATA_INTERFACE_MISMATCH')
    test_exact_block('C008-metadata-policy-mutated-registration-rejected',lambda:m.metadata_field_identity(metadata_policy,{},metadata_inventory),'METADATA_INTERFACE_MISMATCH')

    for field in ('actual_process','returncode'):
        malformed=copy.deepcopy(full_completed_attempt)
        malformed[field]='obsolete-alias';malformed.pop('process_evidence' if field=='actual_process' else 'observed_exit_code')
        test('C006-legacy-'+field+'-cannot-substitute-required-field',lambda malformed=malformed:m.validate_transport_structure(trace_for(malformed),transport_policy),True)
    for kind,attempt in [('completed_process_receipt',full_completed_attempt),('tool_invocation_result',full_tool_attempt)]:
        malformed=copy.deepcopy(attempt);malformed['process_evidence']['invented_runtime']='unrelated'
        test('C006-evidence-'+kind+'-mixed-fields-rejected',lambda malformed=malformed:m.validate_transport_structure(trace_for(malformed),transport_policy),True)
    malformed=copy.deepcopy(full_completed_attempt);malformed['observed_exit_code']=True
    test('C006-normative-boolean-observed-exit-rejected',lambda:m.validate_transport_structure(trace_for(malformed),transport_policy),True)
    def nested_future_origin():
        trace=trace_for(full_completed_attempt);trace['requests'][0]['literal_final_origin']['final_binding_sha256']='f'*64
        m.validate_transport_structure(trace,transport_policy)
    test('C006-normative-closed-literal-origin-rejected',nested_future_origin,True)

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

    report={"format":"verislop.d21-reader-format-controls/8","status":"CONTROL_PASS" if all(r["control_pass"] for r in rows) else "CONTROL_FAIL",
            "control_count":len(rows),"controls":rows,"scope":"unrelated fabricated format/control objects and isolated local bytes only",
            "qualified_api_calls":0,"terminal_audit_executions":0,"task_artifact_reads":0,"model_calls":0,"task_builds":0,"public_probe_calls":0,
            "reader_sha256":hashlib.sha256((HERE/"terminal-scope-reader-008.py").read_bytes()).hexdigest(),
            "specification_sha256":hashlib.sha256((HERE/m.SPEC_NAME).read_bytes()).hexdigest(),
            "registration_sha256":hashlib.sha256((HERE/m.REG_NAME).read_bytes()).hexdigest(),
            "controls_source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "exact_Block_oracle_observations":oracle_observations,
            "metadata_inventory_sha256":hashlib.sha256((HERE/'terminal-metadata-interface-inventory-008.json').read_bytes()).hexdigest(),
            "metadata_fixture_sha256":hashlib.sha256((HERE/'metadata-interface-control-fixtures-008.json').read_bytes()).hexdigest(),
            "assertion_limit":"These controls establish local format/authentication/lifetime boundaries only; no task or qualification claim is VERIFIED."}
    m.publish(output/"report.json",report)
    print(json.dumps({"status":report["status"],"control_count":len(rows),"report":str(output/"report.json")},sort_keys=True))
    return 0 if report["status"]=="CONTROL_PASS" else 2


if __name__=="__main__":raise SystemExit(main())
