"""Replay only SRC019-04 and bounded lexical numeric controls in the pure helper."""
import copy
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'validation/tier2-d21-scope-audit-019-003'
HELPER = SOURCE / 'binding_schema.py'
assert hashlib.sha256(HELPER.read_bytes()).hexdigest() == '445168f6972e747b3f27e7d875dcd7de12382d27b86626e6b6d875ecd6f280b1'
module_spec = importlib.util.spec_from_file_location('_independent_scope019003_numeric_helper', HELPER)
helper = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(helper)
schema = helper.strict_json((SOURCE / 'native-activation-binding-schema.json').read_bytes())


def example(node):
    if 'const' in node:
        return copy.deepcopy(node['const'])
    if '$ref' in node:
        return example(helper.resolve(schema, node['$ref']))
    if node.get('type') == 'object':
        return {name: example(node['properties'][name]) for name in node.get('required', [])}
    if node.get('type') == 'string':
        pattern = node.get('pattern', '')
        if 'qualification-' in pattern:
            return str(ROOT / 'validation/tier2-support-019-qualification-003')
        if 'support019-final-current-root-' in pattern:
            return 'support019-final-current-root-003'
        if '[0-9]{4}' in pattern:
            return '2026-10-10T00:00:00+00:00'
        if '[0-9a-f]{64}' in pattern:
            return 'sha256:' + '0' * 64
        if pattern.startswith('^/'):
            return '/synthetic/isolated-artifact.json'
    raise AssertionError('Unregistered synthetic constructor')


record = example(schema)
raw = json.dumps(record, separators=(',', ':'), sort_keys=True).encode()
needle = b'"max_outstanding_authors":1'
assert raw.count(needle) == 1
results = []


def check(label, operation, reject):
    try:
        operation()
        accepted, error = True, None
    except helper.SchemaError as exc:
        accepted, error = False, str(exc)
    assert accepted is not reject, label + ': ' + str(error)
    results.append({'id': label, 'accepted': accepted, 'expected_rejection': reject, 'error': error})


for label, token, reject in [('valid_integer1', b'1', False),
                             ('SRC01904_exact_rounding_witness', b'1.0000000000000001', True),
                             ('decimal1_0', b'1.0', True), ('exponent1e0', b'1e0', True),
                             ('boolean_true', b'true', True), ('integer2', b'2', True),
                             ('integer0', b'0', True), ('huge_finite_exponent', b'1e9999', True)]:
    def operation(literal=token):
        item = helper.strict_json(raw.replace(needle, b'"max_outstanding_authors":' + literal))
        helper.validate_closed_schema(schema, item)
    check(label, operation, reject)
for label, token in [('nonfinite_NaN', b'NaN'), ('nonfinite_Infinity', b'Infinity'),
                     ('nonfinite_minus_Infinity', b'-Infinity')]:
    check(label, lambda literal=token: helper.strict_json(literal), True)
parsed_underflow = helper.strict_json(b'1e-9999')
assert type(parsed_underflow) is Decimal and parsed_underflow == Decimal('1e-9999') and parsed_underflow != 0
check('SRC01904_exact_underflow_integer_const0',
      lambda: helper.validate_closed_schema({'type': 'integer', 'const': 0}, parsed_underflow), True)
for label, value in [('binary_float1_0', 1.0), ('binary_float_inf', float('inf'))]:
    item = copy.deepcopy(record)
    item['controller_policy']['max_outstanding_authors'] = value
    check(label, lambda instance=item: helper.validate_closed_schema(schema, instance), True)
witness = helper.strict_json(b'1.0000000000000001')
assert type(witness) is Decimal and witness == Decimal('1.0000000000000001') and witness != 1
report = {'format': 'verislop.scope019-minimal-independent-numeric-observations/1',
          'status': 'SRC01904_EXACT_WITNESS_REJECTED_VALID_INTEGER_ACCEPTED', 'runtime_authority': False,
          'actual_target_invocations': 0, 'actual_models': 0, 'actual_Lean_runs': 0,
          'scope': 'Pure binding_schema.py only; complete synthetic actual activation schema; no binder or actual qualification record',
          'controls': results, 'control_count': len(results),
          'exact_witness_parsed_type': type(witness).__name__, 'exact_witness_value': str(witness),
          'exact_underflow_parsed_type': type(parsed_underflow).__name__, 'exact_underflow_value': str(parsed_underflow),
          'actual_schema_numeric_constraint': schema['properties']['controller_policy']['properties']['max_outstanding_authors'],
          'numeric_domain': 'Explicit lexical registration integer tokens; Decimal/exponent and binary float cannot satisfy integer consts',
          'helper_sha256': hashlib.sha256(HELPER.read_bytes()).hexdigest(),
          'activation_schema_sha256': hashlib.sha256((SOURCE / 'native-activation-binding-schema.json').read_bytes()).hexdigest(),
          'task_positive_artifact_reads': [], 'no_actual_runtime_claim_discharge': True}
with (Path(__file__).parent / 'PURE_CONTROL_OBSERVATIONS.json').open('x', encoding='utf-8') as stream:
    json.dump(report, stream, sort_keys=True, indent=2)
    stream.write('\n')
print(json.dumps({'status': report['status'], 'controls': len(results),
                  'actual_registered_schema_witness_rejected': True, 'target_invocations': 0}))
