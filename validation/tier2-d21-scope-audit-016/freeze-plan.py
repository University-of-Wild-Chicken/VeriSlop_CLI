"""Audit-only public-scope freezing; no task generation or implementation."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/augustus/VeriSlop_CLI')
OUT = ROOT / 'validation/tier2-d21-scope-audit-016'
BASE = ROOT / 'synthetic_dataset/bootstrap/stages/tier2-source-facets-015/run/requests/D21'


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def record(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'byte_length': len(data), 'sha256': digest(data)}


original = (BASE / 'original-prompt.txt').read_bytes()
revised = (BASE / 'revised-prompt.txt').read_bytes()
metadata = json.loads((BASE / 'original-metadata.json').read_text())
revision = json.loads((BASE / 'delivery-revision.json').read_text())
policy = json.loads((BASE / 'source-policy.json').read_text())
assert original == (ROOT / 'synthetic_dataset/tasks/D21/prompt.txt').read_bytes()
assert digest(original) == revision['original_request_sha256']
assert digest(revised) == revision['revised_request_sha256']
assert digest((BASE / 'source-policy.json').read_bytes()) == revision['source_policy_sha256']
public_byte_checks = []
for segment in revision['segments']:
    a = original[segment['original_start_byte']:segment['original_end_byte']]
    b = revised[segment['revised_start_byte']:segment['revised_end_byte']]
    if segment['kind'] == 'preserved':
        assert a == b and digest(a) == segment['sha256']
        public_byte_checks.append({'check':'preserved_segment_bytes', 'original_span':[segment['original_start_byte'], segment['original_end_byte']], 'revised_span':[segment['revised_start_byte'], segment['revised_end_byte']], 'passed':True})
for edit in revision['edits']:
    assert original[edit['original_start_byte']:edit['original_end_byte']].decode() == edit['before']
    assert revised[edit['revised_start_byte']:edit['revised_end_byte']].decode() == edit['after']
assert set(i['id'] for i in metadata['identities']) == {'D1','A1','I1','S1','O1','O2','O3','O4','O5','O6','O7'}
assert set(policy['obligations']) == {'I1','S1','O1','O2','O3','O4','O5','O6','O7'}
properties = {'typed_total','deterministic','input_preserved','no_external_io','no_floating_point','pure_data','restricted_runtime_only'}
for oid, row in policy['obligations'].items():
    assert row['value_required'] == (oid not in {'I1','S1'})
    assert row['file'] == 'program.vscore.json' and row['entry'] == 'solve' and row['arity'] == 1
    assert set(row['properties']) == properties
identities = []
for row in metadata['identities']:
    entry = dict(row)
    entry['original_clause_texts'] = [original[s['start_byte']:s['end_byte']].decode() for s in row['source_spans']]
    entry['required_facet_classification'] = 'MIXED' if row['id'].startswith('O') else ('SOURCE_ONLY' if row['id'] in {'I1','S1'} else ('ASSUMPTION' if row['id'] == 'A1' else 'DECLARATION'))
    identities.append(entry)

clauses = [
    ('F01', 'Input has events records with group:string, time:integer, value:integer-or-null; start,end are integers; width is positive; start<=end; fill is exactly none or previous.'),
    ('F02', 'All distinct group names present anywhere in events are emitted in lexicographic Unicode scalar-codepoint order, including groups having no in-range events.'),
    ('F03', 'For each group, bucket starts are start,start+width,... strictly below end, covering [bucketStart,min(bucketStart+width,end)).'),
    ('F04', 'Only events of the group whose times are in the bucket and whose values are non-null contribute; count is the number of those occurrences and sum is their unbounded integer sum.'),
    ('F05', 'Every nonempty bucket emits its sum and makes that sum the latest previous nonempty value.'),
    ('F06', 'With fill none, every empty bucket emits value null.'),
    ('F07', 'With fill previous, an empty bucket emits the latest previous nonempty bucket sum, or null if there has been none; empty buckets never reset previous.'),
    ('F08', 'Events before start never seed previous. Events at or after end do not contribute, while their group names remain in the group domain.'),
    ('F09', 'A zero nonempty sum is a real previous value; duplicate event occurrences are counted independently.'),
    ('F10', 'Return a JSON-compatible list of records with exactly group,start,count,value structure in group order then increasing bucket order.'),
    ('F11', 'Both original public example input/output values are preserved verbatim; examples do not substitute for complete universal refinement.'),
    ('F12', 'Revised delivery is canonical program.vscore.json, vscore/0.3, one admitted typed pure solve entry of arity one under normative Lean vscore-semantics/0.3 and data-pipeline/0.3 serialization.'),
    ('F13', 'Admitted typed execution is total, deterministic, pure, input-immutable, has no external-effect constructors, uses unbounded mathematical integers without floating point, and strings contain Unicode scalar values.'),
    ('F14', 'No additional functional input bounds or preconditions. Invalid width, start>end, unsupported fill and structurally invalid inputs are excluded by the original request and are not semantic counterexamples.'),
]
all_ids = ['D1','A1','O1','O2','O3','O4','O5','O6','O7','I1','S1']
value_ids = ['O1','O2','O3','O4','O5','O6','O7']
claims = [
    {'id':'AUDIT-SCOPE', 'affected_original_ids':all_ids, 'pass_condition':'Actual new public request/revision preserves every frozen functional clause, example and exact ID/kind/role/required mapping and explicit delivery change.', 'block_condition':'Missing or changed clause, strengthened precondition, weakened requirement, or identity metadata unsupported by actual bytes.', 'evidence_type':'current input byte receipt and public clause/identity comparison'},
    {'id':'AUDIT-DOMAIN', 'affected_original_ids':['A1'] + value_ids, 'pass_condition':'Every original valid input is admitted, directly or by a broader carrier with the exact original validity predicate; all value statements quantify universally over the complete valid domain.', 'block_condition':'Extra bounds/restrictions, missing fill alternative, invalid guard, unreachable/empty domain or vacuous theorem.', 'evidence_type':'current accepted domain and complete quantified contract reconstruction'},
    {'id':'AUDIT-FACETS', 'affected_original_ids':value_ids + ['I1','S1'], 'pass_condition':'O1-O7 remain MIXED with complete functional formulas plus universal implementation refinement and all seven source properties; I1/S1 remain source-only with all seven properties; assumptions/NV are not source-policy rows.', 'block_condition':'Equality substitutes for source facts, MIXED becomes source-only, category bypasses default value facet, or source-only rows lose source requirements.', 'evidence_type':'kernel-reconstructed current accepted contract facets and actual policy comparison'},
    {'id':'AUDIT-NONVACUITY', 'affected_original_ids':['A1'] + value_ids, 'pass_condition':'Derived NV obligations occur only after actual formalization, with concrete valid checked witnesses bound to current accepted semantics and without weakening the universal domain.', 'block_condition':'Assumed inhabitedness, invalid/unbound witness, source-only substitute or before-formalization derivation.', 'evidence_type':'current derived NV inventory and checked witness evidence'},
    {'id':'AUDIT-REFINEMENT', 'affected_original_ids':value_ids, 'pass_condition':'Actual accepted Lean reconstruction and transfers prove complete current universal source implementation refinement and uniquely link exact admitted source/entry/contract/wire output across every declared semantic boundary.', 'block_condition':'Unaccepted theorem, examples/bounded tests only, model-only equality, stale candidate, absent/ambiguous correspondence or transfer.', 'evidence_type':'current accepted reconstruction, theorem inventory and transfer evidence'},
    {'id':'AUDIT-CLOSURE', 'affected_original_ids':all_ids, 'pass_condition':'Actual closure A/B bind current frozen input/source roots, registered verifier hashes, accepted state, witnesses, deterministic comparison, provenance, declared trust, and successful release probes.', 'block_condition':'Missing required verifier/build/probe, stale/unbound evidence, input mutation, incomplete provenance, nondeterminism or undeclared trust.', 'evidence_type':'actual current closure A/B and release-probe records; no heavy audit reruns'},
    {'id':'AUDIT-ORIGIN', 'affected_original_ids':all_ids, 'pass_condition':'Actual native origin provenance identifies current controller/fresh author events and artifacts and validates seals, without claiming model-identity attestation.', 'block_condition':'Old package/candidate reuse, invented participation, stale origin, broken seals or missing current event chain.', 'evidence_type':'actual new transport/origin/seal metadata'},
    {'id':'AUDIT-PROBES', 'affected_original_ids':value_ids, 'pass_condition':'Conditional on an executable current candidate after authors terminate, independent finite public-spec probes agree with expected JSON values/order; optional TESTED is not rescored.', 'block_condition':'Concrete valid-domain mismatch. Absent executable source is reported and never inferred to pass.', 'evidence_type':'audit-only current concrete execution evidence; distinct from proof'},
]
inputs = [record(ROOT / 'synthetic_dataset/tasks/D21/prompt.txt')] + [record(BASE / n) for n in ['original-prompt.txt','revised-prompt.txt','original-metadata.json','delivery-revision.json','source-policy.json']]
plan = {
    'schema_version':'verislop.independent-scope-audit-plan/0.1',
    'audit_id':'tier2-d21-scope-audit-016',
    'phase':'PLAN_FROZEN_PRE_GENERATION',
    'created_utc':datetime.now(timezone.utc).isoformat(),
    'role':'Independent read-only scope/terminal auditor; fresh collaboration simulation; no model identity attestation.',
    'allowed_read_surface':['public D21 prompt','five exact retained public stage015 request metadata files','generic source/spec/transport APIs needed','only actual NEW stage016 input/terminal artifacts later supplied by root'],
    'forbidden_read_surface':['hidden cases','task solutions/proofs/source candidates before terminal callback','old model answers','generic enum engineering fixture source/proofs','old packages/candidates'],
    'write_surface':'validation/tier2-d21-scope-audit-016 only',
    'prohibited_actions':['author D21 code/proofs','implementation hints to controller/authors/root','production/test/spec/task/native modifications','spawning agents/models','heavy builds','old-stage mutation','candidate patches','optional TESTED rescore'],
    'pre_generation_public_inputs':inputs,
    'public_byte_checks':public_byte_checks,
    'identity_metadata':identities,
    'delivery_identity_mapping':revision['identity_mapping'],
    'source_policy':policy,
    'functional_clauses':[{'id':i,'statement':s} for i,s in clauses],
    'public_examples':json.loads(original.decode().splitlines()[-1]),
    'public_examples_sha256':revision['public_examples_sha256'],
    'full_domain_checks':['empty events','start=end','any positive width including width>range','negative/zero/positive unbounded start,end,time,value','arbitrary finite event list with duplicates','null values','both fill alternatives','all groups including out-of-range-only groups','empty and Unicode scalar strings with codepoint lexical ordering'],
    'broader_carriers_rule':'Broader carriers are allowed only with the exact original validity predicate preserving the full original valid domain; original excluded inputs are not counterexamples.',
    'claims':claims,
    'input_receipt_sequence':['root supplies actual NEW stage016 paths','inspect actual new public request/revision/metadata/policy/protocol/source-root declaration','compare with frozen scope and manifest','seal new current input receipt','STOP this turn to reserve controller and one fresh author slots','resume only on root terminal callback'],
    'terminal_sequence':['read only actual NEW stage016 supplied artifacts','record exact reached native/formal/proof/acceptance/closure/release stages','evaluate frozen checks without repair','derive NV audit only from actual formalization','conditionally probe current executable after authors terminate','seal terminal evidence/report integrity','report current mechanically justified state and unresolved claims; no inferred assurance'],
    'evidence_rule':'LLM observations are CHECKED review under trusted natural-language correspondence, never sole mechanical proof/closure authority. VERIFIED must originate from registered current verifier evidence. Keep PROVED, TESTED, CHECKED, ASSUMED, TRUSTED and OUT_OF_SCOPE distinct.',
    'closure_boundary':{'trusted_surface':['natural-language correspondence','host tooling','pinned Lean kernel','hashing','OS/hardware as declared by actual protocol'],'excluded_surface':['machine-code/compiler/runtime/physical-resource assurance','old Python assurance relabelling','unlisted claims','future revisions','old results']},
    'final_state_policy':{'states':['VERIFIED','BLOCKED','INFRASTRUCTURE_FAILURE'],'unknown_is_blocking':True,'manual_override_allowed':False,'blocked_reporting':'exact reached stages and current evidence paths, with no inferred assurance'},
    'completion_rule':'Stop after frozen obligations are evaluated and report is sealed; all old results remain immutable.',
}
OUT.mkdir(parents=True, exist_ok=True)
path = OUT / 'frozen-plan.json'
assert not path.exists(), 'Refuse to replace frozen plan'
data = (json.dumps(plan, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()
path.write_bytes(data)
seal = {'schema_version':'verislop.scope-audit-seal/0.1','audit_id':plan['audit_id'],'phase':plan['phase'],'files':[record(path),record(Path(__file__))],'public_inputs':inputs}
seal_data = (json.dumps(seal,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
(OUT / 'plan-seal.json').write_bytes(seal_data)
(OUT / 'plan-seal.sha256').write_text(digest(seal_data)+'\n')
print(json.dumps({'plan':str(path.relative_to(ROOT)),'plan_sha256':digest(data),'seal_sha256':digest(seal_data),'identities':len(identities),'audit_claims':len(claims),'preserved_segments_checked':len(public_byte_checks)},sort_keys=True))
