from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tempfile,json,sys
sys.path.insert(0,str(Path(__file__).parent/'runtime'))
sys.path.insert(0,str(Path(__file__).parent/'runtime/tests'))
from test_vscore3_readable_integration import ProductionReadableMetadata
from verislop import canonical,policy,fsutil
from verislop.bridges import prepare,check,vscore3_checker as C
from verislop.targets import vscore3_target as T,vscore3_source as S

factory=ProductionReadableMetadata();factory.setUp()
try:
 src=S.compile_surface('program "vscore/0.3" profile "data-pipeline/0.3"; entry echo(x:Bool)->Bool{x}')
 rel=canonical.dumps({'schema_version':'0.3','format':T.RELATION_FORMAT,'template':T.TEMPLATE,'source_slot':'vscore-source','proof_slot':'vscore-proof','bindings':[{'symbol':'echo','entry':'echo'}]})
 certificate_path='accepted/certificate.json';ir_path='accepted/accepted-ir.json'
 digest=canonical.digest(b'generic accepted statement');rec={'id':'GF','revision':1,'required':True,'role':'guarantee','kind':'behavior','formal':{'representation':'contract_dsl','statement_hash':digest,'formula_ref':'expr@'+canonical.digest(b'generic expression')}}
 imported_files={f'contract/{role}':b'generic '+role.encode() for role in ('source','profile','olean','environment_export','statements')}
 imported_files['contract/profile']=canonical.dumps({'profile_id':'generic-profile','symbols':{},'enums':{},'records':{}})
 cert={'artifacts':{role:{'path':f'contract/{role}','sha256':canonical.digest(imported_files[f'contract/{role}'])} for role in ('source','profile','olean','environment_export','statements')},'policy':{'id':policy.get('strict')['id'],'hash':policy.policy_hash(policy.get('strict'))},'gate':'accepted_and_proved','toolchain':{'pin':'generic-test'}}
 ir={'acceptance_certificate_ref':certificate_path,'obligations':{'GF':rec}}
 imported_files[certificate_path]=canonical.dumps(cert);imported_files[ir_path]=canonical.dumps(ir)
 imported=SimpleNamespace(ir_path=ir_path,certificate_path=certificate_path,files=imported_files,certificate=cert,ir=ir,replay_receipt={})
 observations=[]
 for case in ("legacy","selected","extra-diagnostic","extra-selection","extra-diagnostic-foreign","extra-selection-foreign","no-selection-diagnostic","no-selection-selection","no-selection-plan-only","selection-size","diagnostic-size","selection-logical-path","selection-foreign-owner"):
  selected=case!="legacy" and not case.startswith("no-selection")
  info={'proposition_hash':canonical.digest(b'generic proposition'),'obligations':['GF'],'model':b'generic model','profile':b'generic profile','readable_selection':factory.selection if selected else None,'readable_candidate_artifacts':{C.READABLE_SELECTION_PATH:factory.selection,**factory.ctx.readable_diagnostics} if selected else {}}
  candidates=C.candidate_files('generic-readable',info,src,rel,b'generic proof')
  proposal=canonical.loads(candidates['proposal.json'])
  if case.startswith('extra-') or case in ('no-selection-diagnostic','no-selection-selection'):
   role='readable_diagnostic' if 'diagnostic' in case else 'readable_selection'
   path='support/readable/unused-'+case+'.json';candidates[path]=b'undeclared extra readable metadata'
   proposal['artifacts'].append({'slot_id':'extra-'+case,'role':role,'node_id':'accepted-contract' if case.endswith('foreign') else C.NODE,'path':path})
   proposal['reproducible_slots'].append('extra-'+case);proposal['reproducible_slots'].sort()
  C._schema('bridge-proposal',proposal)
  files,plan,manifest=prepare._assemble(imported,proposal,canonical.dumps(proposal),candidates)
  if case=='no-selection-plan-only':
   plan['artifact_slots'].append({'slot_id':'plan-only-readable','role':'readable_diagnostic','node_id':C.NODE})
   next(n for n in plan['nodes'] if n['node_id']==C.NODE)['artifact_slots'].append('plan-only-readable')
  if case in ('selection-size','diagnostic-size'):
   slot=C.READABLE_SELECTION_SLOT if case=='selection-size' else 'vscore-readable-diagnostic-0'
   next(a for a in manifest['artifacts'] if a['slot_id']==slot)['size']+=1
  if case=='selection-logical-path':
   next(a for a in manifest['artifacts'] if a['slot_id']==C.READABLE_SELECTION_SLOT)['path']=C.READABLE_SELECTION_PATH
  if case=='selection-foreign-owner':
   next(a for a in plan['artifact_slots'] if a['slot_id']==C.READABLE_SELECTION_SLOT)['node_id']='accepted-contract'
   next(n for n in plan['nodes'] if n['node_id']==C.NODE)['artifact_slots'].remove(C.READABLE_SELECTION_SLOT)
   next(n for n in plan['nodes'] if n['node_id']=='accepted-contract')['artifact_slots'].append(C.READABLE_SELECTION_SLOT)
  files['plan.json']=canonical.dumps(plan);manifest['plan_hash']=canonical.digest(files['plan.json']);files['artifacts.json']=canonical.dumps(manifest)
  for value,name in [(plan,'bridge-plan'),(manifest,'bridge-artifacts')]:C._schema(name,value)
  try:check._graph(plan,{a['slot_id']:a for a in manifest['artifacts']});structural_graph='PASS'
  except Exception as exc:structural_graph={'type':type(exc).__name__,'message':str(exc)}
  actual_size_mismatches=[a['slot_id'] for a in manifest['artifacts'] if a['path'] in files and len(files[a['path']])!=a['size']]
  with tempfile.TemporaryDirectory(prefix='generic-readable-context-') as tmp:
   root=Path(tmp)
   for name,data in files.items():fsutil.atomic_write(root/name,data)
   try:
    with patch.object(C,'_obligation_from_package',return_value={'generic':'accepted service isolated'}):ctx=C.load_context(root,'generic-readable','reference-to-vscore')
    outcome={'kind':'RETURNED','selection':ctx.readable_selection is not None}
   except Exception as exc:outcome={'kind':'EXCEPTION','type':type(exc).__name__,'message':str(exc)}
   rows=[x for x in manifest['artifacts'] if x['role'] in ('readable_selection','readable_diagnostic')]
   observations.append({'case':case,'selected':selected,'outcome':outcome,'prepared_metadata_rows':rows,'returned_diagnostics':sorted(ctx.readable_diagnostics) if outcome['kind']=='RETURNED' else None,'structural_graph':structural_graph,'actual_size_mismatches':actual_size_mismatches})
  if selected:
   saved=Path(__file__).parent/('generic-prepared-bundle-'+case);saved.mkdir(exist_ok=True)
   for name,data in files.items():fsutil.atomic_write(saved/name,data)
 assert observations[0]['outcome']=={'kind':'RETURNED','selection':False}
 assert observations[1]['outcome']=={'kind':'RETURNED','selection':True}
 assert all(x['outcome']['kind']=='EXCEPTION' for x in observations[2:] if x['case'] not in ('no-selection-plan-only','selection-size'))
 result={'observations':observations,'real_boundaries':['canonical readable BASE schema/helper','candidate_files','prepare._assemble','bridge-plan/bridge-artifacts closed schemas','PackageReader','load_context'],'isolated_boundary':'_obligation_from_package + synthetic accepted contract metadata; no contract acceptance or semantic kernel claim','source':'fresh Bool echo fixture; no retained task/corpus artifact','notes':['original prefix/owner cases resolved','all four selected extra-role target/foreign-owner cases now reject','no-selection manifest roles reject','plan-only and selection-size direct loader results recorded alongside structural prerequisite rejection; no semantic acceptance claimed']}
 print(json.dumps(result,indent=2));(Path(__file__).parent/'prepared-context-witness.json').write_text(json.dumps(result,indent=2)+'\n')
finally:factory.doCleanups()
