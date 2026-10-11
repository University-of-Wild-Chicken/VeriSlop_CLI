"""Independent pure helper controls only; never import or invoke the binder."""
import copy
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'validation/tier2-d21-scope-audit-019-002'
OUTPUT = Path(__file__).parent / 'PURE_CONTROL_OBSERVATIONS.json'
raw_helper = (SOURCE / 'binding_schema.py').read_bytes()
assert hashlib.sha256(raw_helper).hexdigest() == '5d57a30a7cf89bc16251eb77459919aafdc101ac87b9f7eb9a751e0840393a69'
module_spec = importlib.util.spec_from_file_location('_independent_scope019_pure_helper', SOURCE / 'binding_schema.py')
helper = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(helper)
spec_schema = json.loads((SOURCE / 'pre-generation-binding-reader-schema-001.json').read_bytes())
activation_schema = json.loads((SOURCE / 'native-activation-binding-schema.json').read_bytes())
results = []
def observe(label, fn, rejection=False):
    try:
        value = fn()
        accepted, error = True, None
    except helper.SchemaError as exc:
        value, accepted, error = None, False, str(exc)
    assert accepted is not rejection, label + ': ' + str(error)
    results.append({'id': label, 'accepted': accepted, 'error': error, 'expected_rejection': rejection})

def example(root_schema, node):
    if 'const' in node:
        return copy.deepcopy(node['const'])
    if 'enum' in node:
        return copy.deepcopy(node['enum'][0])
    if '$ref' in node:
        return example(root_schema, helper.resolve(root_schema, node['$ref']))
    kind = node.get('type')
    if kind == 'object':
        return {name: example(root_schema, node['properties'][name]) for name in node.get('required', [])}
    if kind == 'array':
        return [example(root_schema, node['items']) for _ in range(node.get('minItems', 0))]
    if kind == 'string':
        pattern = node.get('pattern', '')
        if 'activation-amendment-001/' in pattern:
            return str(ROOT / 'validation/tier2-native-live-driver019-activation-amendment-001/synthetic-prerequisite.json')
        if 'qualification-' in pattern:
            return str(ROOT / 'validation/tier2-support-019-qualification-003')
        if 'support019-final-current-root-' in pattern:
            return 'support019-final-current-root-003'
        if '[0-9]{4}' in pattern:
            return '2026-10-10T00:00:00+00:00'
        if '[0-9a-f]{64}' in pattern:
            return 'sha256:' + '0' * 64
        if pattern == '^($|/)':
            return ''
        if pattern.startswith('^/'):
            return '/synthetic/isolated-artifact.json'
        return 'synthetic'
    if kind in ('integer', 'number'):
        return 1
    if kind == 'boolean':
        return False
    if kind == 'null':
        return None
    raise AssertionError('No synthetic constructor for registered schema node')

binding = example(spec_schema, spec_schema)
activation = example(activation_schema, activation_schema)
observe('registered_spec_schema_supported', lambda: helper.check_schema(spec_schema))
observe('registered_activation_schema_supported', lambda: helper.check_schema(activation_schema))
observe('synthetic_complete_spec_schema_only', lambda: helper.validate_closed_schema(spec_schema, binding))
observe('synthetic_complete_activation_schema_only', lambda: helper.validate_closed_schema(activation_schema, activation))
for label, schema, instance in [('spec', spec_schema, binding), ('activation', activation_schema, activation)]:
    extra = dict(instance, unexpected_binding_field=True)
    observe(label + '_extra_top_key', lambda s=schema, v=extra: helper.validate_closed_schema(s, v), True)
    nested = copy.deepcopy(instance)
    nested['native_driver']['unexpected_key'] = True
    observe(label + '_extra_nested_key', lambda s=schema, v=nested: helper.validate_closed_schema(s, v), True)
    missing = copy.deepcopy(instance)
    missing.pop('native_activation_amendment')
    observe(label + '_missing_dedicated_amendment', lambda s=schema, v=missing: helper.validate_closed_schema(s, v), True)
    wrong_driver = copy.deepcopy(instance)
    wrong_driver['native_driver']['path'] = str(ROOT / 'validation/tier2-native-live-driver-019/orchestration-specification.json')
    observe(label + '_wrong_json_driver', lambda s=schema, v=wrong_driver: helper.validate_closed_schema(s, v), True)
observe('bool_is_not_number', lambda: helper.validate_closed_schema({'type':'integer','const':1}, True), True)
for label, raw in [('duplicate_key', b'{"x":1,"x":2}'), ('malformed_utf8', b'"\xff"'),
                   ('nonfinite_nan', b'NaN'), ('overflow_number', b'1e9999')]:
    observe(label, lambda data=raw: helper.strict_json(data), True)
for label, schema in [('unsupported_keyword', {'type':'string','maxLength':3}),
                      ('unresolved_reference', {'$ref':'#/$defs/missing'}),
                      ('cyclic_reference', {'$defs':{'loop':{'$ref':'#/$defs/loop'}},'$ref':'#/$defs/loop'})]:
    observe(label, lambda s=schema: helper.check_schema(s), True)
expected_driver = copy.deepcopy(binding['native_driver'])
wrong_driver = dict(expected_driver, path=str(ROOT / 'validation/tier2-native-live-driver-019/orchestration-specification.json'))
observe('exact_driver_guard', lambda: helper.exact_driver_reference(wrong_driver, expected_driver), True)
expected = {key: copy.deepcopy(activation[key]) for key in ['qualification_root','qualification_closure_id','source_root','input_root','native_driver']}
for key, value in [('qualification_root', str(ROOT / 'validation/tier2-support-019-qualification-002')),
                   ('source_root', 'sha256:' + '1'*64),
                   ('native_driver', wrong_driver)]:
    changed = copy.deepcopy(activation)
    changed[key] = value
    observe('exact_activation_' + key, lambda v=changed: helper.exact_activation_binding(v, expected), True)
raw = json.dumps(activation, separators=(',',':'), sort_keys=True).encode('utf-8')
needle = b'"max_outstanding_authors":1'
assert raw.count(needle) == 1
counterexample_raw = raw.replace(needle, b'"max_outstanding_authors":1.0000000000000001')
rounded = helper.strict_json(counterexample_raw)
assert helper.validate_closed_schema(activation_schema, rounded) is True
assert Decimal('1.0000000000000001') != Decimal(1)
assert type(rounded['controller_policy']['max_outstanding_authors']) is float
counterexamples = [{'id':'SRC019-04-C01','literal_numeric_token':'1.0000000000000001',
                   'parsed_python_type':'float','parsed_value_repr':repr(rounded['controller_policy']['max_outstanding_authors']),
                   'actual_registered_schema':'native-activation-binding-schema.json',
                   'instance_pointer':'/controller_policy/max_outstanding_authors','required_schema_const':1,
                   'exact_decimal_equals_const':False,'schema_accepted':True,
                   'synthetic_instance_bytes_sha256':hashlib.sha256(counterexample_raw).hexdigest(),
                   'scope':'Complete synthetic activation instance only; no actual prerequisites or target binding'}]
for token, number in [('1.0000000000000001',1),('1e-9999',0)]:
    parsed = helper.strict_json(token.encode())
    assert helper.validate_closed_schema({'type':'integer','const':number}, parsed) is True
    assert Decimal(token) != Decimal(number)
    counterexamples.append({'id':'SRC019-04-GENERIC-' + str(number),'literal_numeric_token':token,
                           'parsed_python_type':type(parsed).__name__,'parsed_value_repr':repr(parsed),
                           'schema':{'type':'integer','const':number},'exact_decimal_equals_const':False,'schema_accepted':True})
report = {'format':'verislop.scope019-independent-pure-source-observations/1',
          'status':'CONCRETE_SOURCE_COUNTEREXAMPLE_FOUND','runtime_authority':False,
          'scope':'Only authenticated binding_schema.py pure helper functions; no binder/target imports/invocations',
          'ordinary_controls':results,'counterexamples':counterexamples,
          'helper_sha256':hashlib.sha256(raw_helper).hexdigest(),
          'spec_schema_sha256':hashlib.sha256((SOURCE/'pre-generation-binding-reader-schema-001.json').read_bytes()).hexdigest(),
          'activation_schema_sha256':hashlib.sha256((SOURCE/'native-activation-binding-schema.json').read_bytes()).hexdigest(),
          'actual_target_invocations':0,'actual_models':0,'actual_Lean_runs':0,
          'no_actual_qualification_record_constructed':True,'actual_task_positive_artifact_reads':[]}
with OUTPUT.open('x',encoding='utf-8') as stream:
    json.dump(report,stream,sort_keys=True,indent=2)
    stream.write('\n')
print(json.dumps({'status':report['status'],'ordinary_controls':len(results),'counterexamples':len(counterexamples),
                  'actual_registered_activation_schema_accepts_rounded_nonconstant':True,'target_invocations':0}))
