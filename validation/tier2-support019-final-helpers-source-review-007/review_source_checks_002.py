"""Bounded source/opaque-hash and unrelated pure-renderer comparisons only.

Never imports a producer module, target verifier or task. Only the explicitly
registered six constants and eighteen pure string-emitter function ASTs are
loaded from the authenticated production definition for source comparison.
No emitted recipe or embedded reader/JavaScript program is executed.
"""
from pathlib import Path
import ast
import copy
import difflib
import hashlib
import json

ROOT = Path(__file__).absolute().parents[2]
HERE = Path(__file__).absolute().parent
CAND = ROOT/'validation/tier2-support-019-qualification-adapters-006'
OLD = ROOT/'validation/tier2-support-019-qualification-adapters-005'
CARRIER = ROOT/'validation/tier2-carrier-context-support-019-implementation-004'
INSTALLED = ROOT/'synthetic_dataset/tools/bootstrap_tier2_carrier_view.py'
EXPECTED_MANIFEST = 'sha256:904e981a2b38a4153ef66d700d8394ac4b2251c3adb90383d4f9462526508bbc'


def sha(raw):
    return 'sha256:'+hashlib.sha256(raw).hexdigest()


def raw(path):
    assert path.is_file() and not path.is_symlink() and path.resolve()==path.absolute(),path
    return path.read_bytes()


def doc(path):
    return json.loads(raw(path))


def identity(path):
    data=raw(path)
    return {'path':path.relative_to(ROOT).as_posix(),'sha256':sha(data),'byte_count':len(data)}


def authenticate_manifest(path,key='files',relative=False):
    value=doc(path);entries=value[key]
    assert type(entries) is dict and entries
    for name,record in entries.items():
        target=path.parent/name if relative else ROOT/name
        data=raw(target)
        assert sha(data)==record['sha256'],target
        size=next((record[k] for k in ('byte_count','bytes','size') if k in record),None)
        assert size is None or type(size) is int and size==len(data),target
    return len(entries)


def seal(path):
    tokens=raw(path.parent/'SEAL.sha256').decode('ascii').strip().split()
    assert len(tokens) in (1,2) and tokens[0].removeprefix('sha256:')==sha(raw(path))[7:]
    assert len(tokens)==1 or tokens[1]==path.name


def dump(node):
    return ast.dump(node,include_attributes=False)


def method(tree,cls,name):
    target=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    return next(n for n in target.body if isinstance(n,ast.FunctionDef) and n.name==name)


def main():
    assert sha(raw(CAND/'hash-manifest.json'))==EXPECTED_MANIFEST
    seal(CAND/'hash-manifest.json');seal(OLD/'hash-manifest.json');seal(CARRIER/'hash-manifest.json')
    manifests={}
    for name in ('hash-manifest.json','predicate-reader-source-manifest.json','reconciler-hash-manifest.json','candidate-source-bindings.json'):
        manifests[name]=authenticate_manifest(CAND/name)
    manifests['baseline005']=authenticate_manifest(OLD/'hash-manifest.json')
    manifests['carrier004']=authenticate_manifest(CARRIER/'hash-manifest.json','files',True) if 'files' in doc(CARRIER/'hash-manifest.json') else authenticate_manifest(CARRIER/'hash-manifest.json','candidate_files',True)
    assert raw(INSTALLED)==raw(CARRIER/'bootstrap_tier2_carrier_view.py')
    manifest_paths=set(doc(CAND/'hash-manifest.json')['files'])
    actual_paths={p.relative_to(ROOT).as_posix() for p in CAND.iterdir() if p.is_file() and p.name not in ('hash-manifest.json','SEAL.sha256')}
    assert manifest_paths==actual_paths and len(manifest_paths)==80

    registration=doc(CAND/'source-controls-registration-006.json')
    receipt=doc(CAND/'source-controls-actual-receipt-006.json')
    assert type(receipt['exit_code']) is int and receipt['exit_code']==0
    assert type(receipt['actual_child_pid']) is int and receipt['actual_child_pid']==3413053
    assert receipt['argv']==registration['argv'] and receipt['cwd']==str(ROOT) and receipt['environment']==registration['environment']
    assert receipt['registration']=={'path':(CAND/'source-controls-registration-006.json').relative_to(ROOT).as_posix(),'sha256':sha(raw(CAND/'source-controls-registration-006.json'))}
    assert type(receipt['before']) is dict and receipt['before']==receipt['after']==registration['source_hashes'] and len(receipt['before'])==93
    for name,expected in receipt['before'].items():
        assert sha(raw(ROOT/name))==expected,name
    for entry in receipt['logs'].values():
        assert identity(ROOT/entry['path'])==entry
    assert raw(ROOT/receipt['logs']['stdout']['path'])==b''
    log=raw(ROOT/receipt['logs']['stderr']['path']).decode('utf-8','strict')
    controls=ast.parse(raw(CAND/'test_author_reconstruction_source.py'))
    test_cls=next(node for node in controls.body if isinstance(node,ast.ClassDef) and node.name=='AuthorReconstructionSourceControls')
    names=sorted(node.name for node in test_cls.body if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'))
    assert len(names)==registration['test_count']==15 and names==sorted(registration['tests'])
    assert set(line.split(' (')[0] for line in log.splitlines() if ' ... ok' in line)==set(names)
    assert 'Ran 15 tests in ' in log and log.rstrip().endswith('OK')
    assert all(receipt[k]==0 and type(receipt[k]) is int for k in ('runtime_claims_evaluated','actual_models','actual_VIEWs','actual_task_runs','actual_Lean_runs','actual_qualification_verifier_runs'))
    assert receipt['qualification_authority'] is False
    runner=raw(CAND/'run_source_controls006.py').decode()
    assert 'if actual != registration["source_hashes"]:' in runner and 'before = observe()' in runner and 'after = observe()' in runner
    assert 'process.wait()' in runner and 'timeout=' not in runner

    allowed={'predicate_reader.py':{'Reader.recipe_literals','Reader.fresh_author','Reader.author_protocol_module','Reader.author_message'},
             'additional_predicates.py':{'AdditionalPredicates.carrier_pure','AdditionalPredicates.fresh_author'}}
    projections={};trees={};changes={}
    for filename in ('predicate_reader.py','additional_predicates.py','assemble_ancillary_indexes.py','current_root_reconcile.py','materialize_adapter_configuration.py'):
        before=ast.parse(raw(OLD/filename));after=ast.parse(raw(CAND/filename));trees[filename]=(before,after)
        def methods(tree):
            return {cls.name+'.'+fn.name:dump(fn) for cls in tree.body if isinstance(cls,ast.ClassDef) for fn in cls.body if isinstance(fn,ast.FunctionDef)}
        before_methods,after_methods=methods(before),methods(after)
        changed=sorted(name for name in before_methods.keys() & after_methods.keys() if before_methods[name]!=after_methods[name])
        added=sorted(after_methods.keys()-before_methods.keys())
        assert set(changed+added)==allowed.get(filename,set())
        assert not before_methods.keys()-after_methods.keys()
        def project(tree):
            tree=copy.deepcopy(tree)
            for cls in (node for node in tree.body if isinstance(node,ast.ClassDef)):
                cls.body=[node for node in cls.body if not (isinstance(node,ast.FunctionDef) and cls.name+'.'+node.name in allowed.get(filename,set()))]
            return tree
        x,y=project(before),project(after)
        if filename=='predicate_reader.py':
            imports=[node for node in y.body if isinstance(node,ast.Import) and dump(node)==dump(ast.parse('import importlib.util').body[0])]
            assert len(imports)==1;y.body.remove(imports[0])
        assert dump(x)==dump(y),filename
        projections[filename]=True;changes[filename]={'changed':changed,'added':added}
        if filename not in allowed:
            assert raw(OLD/filename)==raw(CAND/filename)
    before,after=trees['predicate_reader.py']
    a,b=method(before,'Reader','fresh_author'),copy.deepcopy(method(after,'Reader','fresh_author'))
    assert dump(b.body[5])==dump(ast.parse('message=self.author_message(reference)').body[0]);b.body[5]=copy.deepcopy(a.body[5]);assert dump(a)==dump(b)
    assert dump(method(before,'Reader','recipe'))==dump(method(after,'Reader','recipe'))
    before,after=trees['additional_predicates.py']
    a,b=method(before,'AdditionalPredicates','fresh_author'),copy.deepcopy(method(after,'AdditionalPredicates','fresh_author'))
    class Pattern(ast.NodeTransformer):
        def visit_Subscript(self,node):
            if dump(node)==dump(ast.parse("literals['marker_pattern']",mode='eval').body):
                return ast.Constant(value='UNRELATED_019_002_[A-Za-z0-9_]+')
            return self.generic_visit(node)
    b=Pattern().visit(b);b.body[10]=copy.deepcopy(a.body[5]);b.body[3:9]=[copy.deepcopy(a.body[3])];assert dump(a)==dump(b)
    a,b=method(before,'AdditionalPredicates','carrier_pure'),method(after,'AdditionalPredicates','carrier_pure')
    class Hash(ast.NodeTransformer):
        def visit_Constant(self,node):
            return ast.Name(id='installed_hash',ctx=ast.Load()) if node.value=='sha256:9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366' else node
    assert [dump(n) for n in a.body[:2]]==[dump(n) for n in b.body[:2]]
    assert dump(Hash().visit(copy.deepcopy(a.body[2])))==dump(b.body[4])
    assert [dump(n) for n in a.body[3:]]==[dump(n) for n in b.body[5:]]
    assert b.body[2].targets[0].id=='installed_hash' and 'PURE_INSTALLED_SOURCE_NOT_CURRENT_FROZEN_INPUT' in ast.unparse(b.body[3])
    claims_docs=('predicate-reader-specification.json','reconciliation-specification.json','additional-witness-contract.json')
    assert all(raw(CAND/name)==raw(OLD/name) for name in claims_docs)
    assert doc(CAND/'runtime-contract.json')['additional_claims']==doc(OLD/'runtime-contract.json')['additional_claims']
    assert len(doc(CAND/'reconciliation-specification.json')['claims'])==18 and len(doc(CAND/'runtime-contract.json')['additional_claims'])==9

    helper_source=raw(CAND/'author_protocol_reconstruction.py');helper_tree=ast.parse(helper_source)
    assert {node.names[0].name for node in helper_tree.body if isinstance(node,ast.Import)}=={'ast','hashlib','json'}
    assert not any(isinstance(node,ast.ImportFrom) for node in helper_tree.body)
    forbidden={'exec','eval','compile','open','__import__','getattr','setattr'}
    assert not any(isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in forbidden for node in ast.walk(helper_tree))
    attrs={ast.unparse(node.func) for node in ast.walk(helper_tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)}
    assert not any(word in name for name in attrs for word in ('read','write','tools.','socket','subprocess','exec_command','spec_from_file'))
    h={'ast':ast,'hashlib':hashlib,'json':json};exec(compile(helper_tree,'authenticated-source-helper','exec'),h)
    source=raw(INSTALLED);literals=doc(CAND/'predicate-reader-carrier-literals.json')
    assert literals['source']['sha256']==sha(source) and literals['author_protocol']['reconstruction_source']=={'path':(CAND/'author_protocol_reconstruction.py').relative_to(ROOT).as_posix(),'sha256':sha(helper_source)}
    h['validate_literals'](source,literals)
    source_tree=ast.parse(source);selected=[]
    for node in source_tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in h['CONSTANT_NAMES']:
            assert type(ast.literal_eval(node.value)) is str;selected.append(node)
        if isinstance(node,ast.FunctionDef) and node.name in h['FUNCTION_NAMES']:
            selected.append(node)
    assert sum(isinstance(node,ast.FunctionDef) for node in selected)==18
    p={'json':json};exec(compile(ast.Module(body=selected,type_ignores=[]),'restricted-frozen-string-emitters','exec'),p)
    refs=doc(HERE/'SOURCE_COMPARISON_002_BEFORE_EXECUTION.json')['unrelated_references']
    pairs={'legacy_first':'initial_session_template','legacy_next':'next_session_template','author_first':'author_initial_session_template',
           'author_next':'author_next_session_template','confirm':'confirm_session_template','hash':'hash_session_template'}
    rendered=[]
    for ref in refs:
        actual=h['recipes'](literals,ref)
        assert set(actual)==set(pairs)
        for name,fn in pairs.items():assert actual[name]==p[fn](ref)
        message=h['author_message'](literals,ref);assert message==p['agent_message'](ref).encode('utf-8','strict')
        rendered.append({'reference':ref,'recipe_sha256':{name:sha(text.encode()) for name,text in actual.items()},'whole_message_sha256':sha(message),'whole_message_bytes':len(message)})
    ref=refs[0];view_results=[]
    for view in doc(HERE/'SOURCE_COMPARISON_002_BEFORE_EXECUTION.json')['closed_views']:
        values=h['recipes'](literals,ref,view=view)
        assert values['author_next']==p['author_next_session_template'](ref,view)
        assert values['legacy_next']==p['next_session_template'](ref,view)
        view_results.append({'view':view,'author_next_sha256':sha(values['author_next'].encode())})
    for confirmation in doc(HERE/'SOURCE_COMPARISON_002_BEFORE_EXECUTION.json')['closed_confirmations']:
        assert h['recipes'](literals,ref,confirmation=confirmation)['confirm']==p['confirm_session_template'](ref,confirmation)
    mutations=doc(HERE/'SOURCE_COMPARISON_002_BEFORE_EXECUTION.json')['literal_mutations'];rejected=[]
    for row in mutations:
        changed=copy.deepcopy(literals);value=changed
        for key in row['path'][:-1]:value=value[key]
        value[row['path'][-1]]=row['value']
        try:h['validate_literals'](source,changed)
        except (ValueError,KeyError,TypeError) as error:rejected.append({'path':row['path'],'actual_error':type(error).__name__+':'+str(error)})
        else:raise AssertionError('Literal mutation admitted:'+str(row['path']))
    malformed=doc(HERE/'SOURCE_COMPARISON_002_BEFORE_EXECUTION.json')['malformed_controls'];invalid=[]
    for row in malformed:
        kwargs={row['parameter']:row['value']}
        try:h['recipes'](literals,ref,**kwargs)
        except (ValueError,KeyError,TypeError) as error:invalid.append({'id':row['id'],'actual_error':type(error).__name__+':'+str(error)})
        else:raise AssertionError('Malformed selector/confirmation admitted:'+row['id'])
    capture=doc(CAND/'predicate-reader-capture-literals.json');capture_source=raw(ROOT/capture['source']['path']);assert sha(capture_source)==capture['source']['sha256']
    capture_tree=ast.parse(capture_source)
    capture_functions={n.name:sha(dump(n).encode()) for n in capture_tree.body if isinstance(n,ast.FunctionDef) and n.name in capture['function_ast_hashes']}
    capture_constants={n.targets[0].id:ast.literal_eval(n.value) for n in capture_tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in capture['constants']}
    capture_constants={name:list(value) if isinstance(value,tuple) else value for name,value in capture_constants.items()}
    assert capture_functions==capture['function_ast_hashes'] and capture_constants==capture['constants']
    old_literals=doc(OLD/'predicate-reader-carrier-literals.json')
    assert literals['marker_pattern']==old_literals['marker_pattern'].replace('UNRELATED_019_002_','UNRELATED_019_003_')
    assert literals['expected_markers']==[value.replace('UNRELATED_019_002_','UNRELATED_019_003_',1) for value in old_literals['expected_markers']]
    before=after={};wrong_reject=before!=after!={};required_reject=not (type(before) is dict and before and before==after)
    assert wrong_reject is False and required_reject is True
    counterexample={'id':'SRC006-PACKAGER-01','before':{},'after':{},'actual_chained_comparison_result':wrong_reject,
                    'required_equal_nonempty_guard_rejects':required_reject,'source_expression':'receipt["before"] != receipt["after"] != {}',
                    'scope':'Seal packager Boolean expression only; not executed, not a runtime verifier/admission predicate; actual current receipt has93 nonempty equal independently authenticated sources.'}
    report={'status':'SOURCE_COMPARISON_COMPLETE_RUNTIME_UNQUALIFIED','manifest_counts':manifests,'candidate_manifest_exact_current_file_set':True,
            'creator_actual_registered_tests':names,'creator_actual_pid':receipt['actual_child_pid'],'creator_actual_exit_code':receipt['exit_code'],
            'creator_registered_argv_and_logs_authenticated':True,'creator_current_source_guard_count':len(receipt['before']),
            'creator_before_after_registration_current_hash_maps_exact_nonempty':True,'complete_ast_projection':projections,'source_method_delta':changes,
            'all27_claim_objects_and_raw_document_bytes_preserved':True,'full_author_final_identity_roots_eof_noresampling_guards_preserved':True,
            'legacy_recipe_method_ast_preserved':True,'all_old30_pure_semantics_preserved':True,'helper_sha256':sha(helper_source),
            'helper_runtime_side_effects':'stdlib AST/hash/JSON closed rendering only; no producer API import/calls or file/tool/model/compiler/network/qualification calls',
            'current18_functions6_constants_and_capture_source_metadata_authenticated':True,'unrelated_reconstructions':rendered,'next_retry_cursor_controls':view_results,
            'literal_mutation_rejections':rejected,'malformed_control_rejections':invalid,'packager_boolean_counterexample':counterexample,
            'actual_VIEW_model_Lean_task_native_bootstrap_materializer_qualification_admission_calls':0,'qualification_authority':False,'activation_authority':False}
    print(json.dumps(report,sort_keys=True,ensure_ascii=True))


if __name__=='__main__':
    main()
