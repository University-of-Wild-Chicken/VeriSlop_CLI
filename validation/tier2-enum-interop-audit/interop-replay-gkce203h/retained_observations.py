"""Read-only authentication of generic retained records; no kernel replay."""
from pathlib import Path
import hashlib,json,sys,datetime
ROOT=Path('/home/augustus/VeriSlop_CLI');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from verislop import canonical,formal_frontend as ff
from verislop.exprjson import name_str
source=ROOT/'validation/formalizer-enumerations/frontend-kernel-ck4v7gp4'
files=['response.json','frozen.json','origin.json','candidate/VeriSlopContract.lean','candidate-result.json','candidate-export.json','candidate-audit.json','actual-generated-name-inventory.json','constructor-extremes-result.json','constructor-extremes-export.json','composite-decisions-result.json','composite-decisions-audit.json','false-theorem-result.json']
bind=[]
for f in files:
 b=(source/f).read_bytes();p=OUT/'retained-generic-observations'/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);bind.append({'path':str(source/f),'snapshot':'retained-generic-observations/'+f,'sha256':canonical.digest(b),'size':len(b)})
rows=[]
def check(name,actual,expected=True):
 rows.append({'id':name,'ok':actual==expected,'actual':actual,'expected':expected})
 assert actual==expected,rows[-1]
def data(f):return json.loads((source/f).read_bytes())
obj=data('response.json'); frozen=data('frozen.json');generated=ff.compile_response((source/'response.json').read_bytes(),frozen,data('origin.json')['profile_id'])
check('retained-candidate-exact-source-replay',generated.source==(source/'candidate/VeriSlopContract.lean').read_bytes())
check('retained-candidate-exact-origin-replay',generated.receipt==data('origin.json'))
check('retained-candidate-compile-ok',data('candidate-result.json')['ok'])
for f in ['candidate-audit.json','composite-decisions-audit.json']:
 records=data(f)['defeq'];check('retained-'+f+'-all-records-defeq',bool(records) and all(r['result']=={'ok':True,'typechecks':True,'defeq':True} for r in records))
check('retained-false-theorem-rejected',data('false-theorem-result.json')['ok'],False)
check('retained-constructor-extremes-compile-ok',data('constructor-extremes-result.json')['ok'])
exports=[data('candidate-export.json'),data('constructor-extremes-export.json')]
decls={name_str(r['name']):r for e in exports for r in e['constants']}
for enum,ctors in [('Alpha',['alpha','beta']),('Singleton',['only']),('Many',['choice'+str(i) for i in range(64)])]:
 prefix='VeriSlopAST.'+enum+'.';all_names={n[len(prefix):] for n in decls if n.startswith(prefix)}
 direct={n for n in all_names if '.' not in n};generated_members=direct-set(ctors)
 members=ff.GENERATED_SINGLETON_MEMBERS if len(ctors)==1 else ff.GENERATED_TYPE_MEMBERS
 check('retained-'+enum+'-complete-direct-generated-member-guard',generated_members==members)
 check('retained-'+enum+'-root-derived-instance-name','VeriSlopAST.instDecidableEq'+enum in decls)
for record,fields in [('Inner',{'pick'}),('Packet',{'mode','choices','optional','outcome'})]:
 prefix='VeriSlopAST.'+record+'.';direct={n[len(prefix):] for n in decls if n.startswith(prefix) and '.' not in n[len(prefix):]}
 check('retained-'+record+'-complete-direct-generated-member-guard',direct-fields==ff.GENERATED_RECORD_MEMBERS)
freeze_path=ROOT/'validation/tier2-native-boundary-gate-016/source-freeze.json'; fb=freeze_path.read_bytes();freeze=json.loads(fb);(OUT/'source-freeze-016.json').write_bytes(fb)
checks=[]
for p,h in freeze['source_files'].items():
 checks.append({'path':p,'expected':h,'actual':canonical.digest((ROOT/p).read_bytes())})
check('current-240-source-freeze-file-hashes',all(x['expected']==x['actual'] for x in checks))
check('current-source-root-recomputed',canonical.digest_json(freeze['source_files']),freeze['source_root'])
before=json.loads((OUT/'source-before.json').read_text()); mismatches=[r['path'] for r in before['files'] if r['path'] in freeze['source_files'] and 'sha256:'+r['sha256']!=freeze['source_files'][r['path']]]
check('audited-production-snapshot-matches-final-freeze',mismatches,[])
result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':rows,'count':len(rows),'retained_record_bindings':bind,'freeze_path':str(freeze_path),'freeze_hash':canonical.digest(fb),'freeze_source_root':freeze['source_root'],'freeze_file_count':len(checks),'freeze_file_hash_checks':checks,'scope':'Retained engineer generic kernel observations inspected and hash bound; no independent kernel replay or two-build closure qualification performed.'}
(OUT/'retained-observations.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'observation_checks':len(rows),'freeze_files':len(checks),'root':freeze['source_root']}))
