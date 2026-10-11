"""Preregistered support022 source controls, with unrelated SYNTHETIC observations.

Only actual OS process PIDs/status/raw stdout/stderr are process observations.
The deterministic finite driver is never an author recipe or qualification.
"""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import time
import traceback

ROOT = Path('/home/augustus/VeriSlop_CLI')
HERE = Path(__file__).resolve().parent
NODE = '/usr/bin/node'
PYTHON = '/usr/bin/python3.12'
IDS = ['S022-C' + str(i).zfill(2) for i in range(1, 19)]
REVISION = 'support022-compact-runtime/1'
EMPTY = {'format': 'verislop.own-view-availability-summary/0.1', 'status': 'EMPTY',
         'availability_only': True, 'semantic_consumption': 'UNATTESTED',
         'semantic_acceptance_authority': False}
SOURCE_LAYOUT = {'carrier_runtime.js': 'synthetic_dataset/tools/carrier_runtime020/carrier_runtime.js',
                 'reader.py': 'synthetic_dataset/tools/carrier_runtime020/reader.py',
                 'compact_protocol.py': 'synthetic_dataset/tools/carrier_runtime020/compact_protocol.py',
                 'carrier_runtime020-registration.json': 'synthetic_dataset/tools/carrier_runtime020-registration.json',
                 'bootstrap_tier2_runtime_integration.py': 'synthetic_dataset/tools/bootstrap_tier2_runtime_integration.py',
                 'author_protocol_reconstruction.py': 'independent/author_protocol_reconstruction.py',
                 'bootstrap_tier2_carrier_view.py': 'legacy/bootstrap_tier2_carrier_view.py',
                 'capture-amendment-003/collector_templates.py': 'legacy/capture-amendment-003/collector_templates.py',
                 'diagnostic_failure_parser.py': 'legacy/diagnostic_failure_parser.py'}


def need(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def parse(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, 'DUPLICATE_CONTROL_KEY')
            value[key] = item
        return value
    return json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=pairs)


def ref(path):
    raw = path.read_bytes()
    return {'path': str(path), 'sha256': sha(raw), 'byte_count': len(raw)}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def dump(node):
    return ast.dump(node, include_attributes=False)


def assignments(raw):
    return {node.targets[0].id: ast.literal_eval(node.value) for node in ast.parse(raw).body
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}


def definitions(raw):
    return {node.name: node for node in ast.parse(raw).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}


def diagnostic(view):
    return {'markers': [], 'field_roots': {}, 'field_eof': {'/system': True, '/user': False},
            'field_chars': {'/system': 0, '/user': 0},
            'failure': {'format': 'verislop.author-observed-failure/0.1', 'trust': 'UNATTESTED',
                        'stage': 'NEXT_USER',
                        'operation': {'chunk_id': 'SYNTHETIC_GENERIC_DIAGNOSTIC_NOT_ACTUAL',
                                      'selector': view['selector'], 'start_char': view['start_char'],
                                      'output_cap_bytes': view['output_cap_bytes'],
                                      'metadata_reserve_bytes': view['metadata_reserve_bytes']},
                        'observation': {'kind': 'literal', 'source': 'OWN_VISIBLE_PROTOCOL_STATE',
                                        'scope': 'complete', 'text': 'SYNTHETIC attempted-input error'},
                        'reproduction': {'template': 'NEXT', 'view': view, 'confirmation': None,
                                         'own_input_literal': None,
                                         'expected_observed_error_literal': 'SYNTHETIC attempted-input error',
                                         'availability': 'PROVIDED'},
                        'self_critique': {'violated_check': None, 'own_attempted_retry': None,
                                          'observed_retry_error_literal': None, 'recovery': 'UNAVAILABLE'}}}


def diagnostic_view(**changes):
    value = {'operation': 'field', 'selector': '/user', 'start_char': 0,
             'output_cap_bytes': 8192, 'metadata_reserve_bytes': 2048}
    value.update(changes)
    return value


def fails(procedure, expected=None):
    try:
        procedure()
    except Exception as error:
        if expected is not None:
            need(str(error) == expected, 'REJECTION_ERROR_DIFFERS:' + str(error))
        return {'type': type(error).__name__, 'literal': str(error)}
    raise AssertionError('EXPECTED_REJECTION_NOT_OBSERVED')


def guard(registration):
    actual = {}
    for name, expected in registration['source_guards'].items():
        path = Path(name) if name.startswith('/') else ROOT / name
        actual[name] = sha(path.read_bytes())
        need(actual[name] == expected, 'SOURCE_GUARD_MISMATCH:' + name)
    need(bool(actual), 'EMPTY_GUARDS')
    return actual


class Observer:
    def __init__(self, root):
        self.root = root
        root.mkdir()
        self.refs = []

    def run(self, argv, *, stdin=None, shell=False):
        process = subprocess.Popen(argv, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=shell,
                                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), cwd=self.root)
        started = time.monotonic()
        stdout, stderr = process.communicate(stdin)
        need(type(process.returncode) is int, 'ACTUAL_STATUS_NOT_INTEGER')
        prefix = self.root / ('process-' + str(len(self.refs) + 1).zfill(4))
        out, err = prefix.with_suffix('.stdout'), prefix.with_suffix('.stderr')
        out.write_bytes(stdout)
        err.write_bytes(stderr)
        value = {'format': 'verislop.support022-actual-generic-process/1',
                 'argv_or_shell_command': argv, 'shell': shell, 'observed_process_PID': process.pid,
                 'exit_code': process.returncode, 'elapsed_seconds': time.monotonic() - started,
                 'stdout_ref': ref(out), 'stderr_ref': ref(err),
                 'native_tool_metadata': 'NOT_OBSERVED; constructed tool-like metadata is SYNTHETIC'}
        path = prefix.with_suffix('.json')
        save(path, value)
        self.refs.append(ref(path))
        return {'exit_code': process.returncode, 'stdout': stdout, 'stderr': stderr,
                'observed_process_PID': process.pid, 'record_ref': ref(path)}


class Fixture:
    def __init__(self, suite):
        self.suite = suite
        self.directory = suite.run / "public-fixture quote' dollar$ backtick` ;\n🧪"
        self.directory.mkdir()
        self.sessions = self.directory / 'own-sessions'
        self.sessions.mkdir()
        self.system = 'Unrelated system: é🧪e\u0301\nquote\"\t\x00'
        self.user = ('Aé🧪e\u0301\n\t\x00語語語語語語' * 80) + 'TAIL'
        self.carrier = self.directory / 'own-carrier.json'
        self.doc = {'format': 'verislop.collaboration-carrier/0.1', 'request_id': 'UNRELATED_SUPPORT022',
                    'request_sha256': sha(wire({'system': self.system, 'user': self.user}).encode()),
                    'system': self.system, 'user': self.user}
        self.carrier.write_bytes((wire(self.doc) + '\n').encode('utf-8'))
        self.reference = {'path': str(self.carrier), 'sha256': sha(self.carrier.read_bytes()),
                          'request_sha256': self.doc['request_sha256']}
        self.code = suite.api.code_bindings(str(self.sessions))
        self.state = Path(suite.api.session_path(self.reference, self.code))
        self.observations = []

    def accepted(self):
        return self.state.read_bytes() if self.state.exists() else None

    def request(self, operation, **extras):
        return {'format': 'verislop.carrier-runtime-request/0.1', 'operation': operation,
                'reference': self.reference, 'session_path': str(self.state), 'code': self.code, **extras}

    def invoke(self, request):
        return self.suite.observer.run([NODE, self.code['runtime_path'], wire(request)])

    def ok(self, request):
        actual = self.invoke(request)
        need(actual['exit_code'] == 0 and not actual['stderr'], 'GENERIC_OPERATION_FAILED:' + str(actual))
        return parse(actual['stdout'])

    def reject(self, request, expected=None):
        before = self.accepted()
        actual = self.invoke(request)
        need(actual['exit_code'] == 2 and not actual['stderr'], 'EXPECTED_EXACT_STATUS_TWO')
        need(self.accepted() == before, 'REJECT_MUTATED_ACCEPTED_STATE')
        value = parse(actual['stdout'])
        need(value['status'] == 'error' and value['semantic_acceptance_authority'] is False,
             'REJECT_CLAIMED_AUTHORITY')
        if expected is not None:
            need(value['code'] == expected, 'WRONG_REJECTION:' + value['code'])
        return value['code']

    def view(self, selector=None, start=0, cap=8192, reserve=2048):
        view = {'operation': 'inventory', 'output_cap_bytes': cap, 'metadata_reserve_bytes': reserve}
        if selector is not None:
            view.update(operation='field', selector=selector, start_char=start)
        before = self.accepted()
        actual = self.invoke(self.request('view', view=view))
        need(actual['exit_code'] == 0 and not actual['stderr'] and self.accepted() == before,
             'VIEW_FAILED_OR_ADVANCED_STATE')
        pending = {'reference': self.reference, 'view': view,
                   'result': {'chunk_id': 'SYNTHETIC_S022_CHUNK_' + str(len(self.suite.observer.refs)),
                              'exit_code': actual['exit_code'], 'output': actual['stdout'].decode('utf-8', 'strict')}}
        self.suite.synthetic_count += 1
        return pending

    def confirm(self, pending):
        confirmation = {'chunk_id': pending['result']['chunk_id'], 'outer_output_intact': True}
        result = self.ok(self.request('confirm', pending=pending, confirmation=confirmation))
        self.observations.append(copy.deepcopy(pending))
        return result

    def checkpoint(self):
        before = self.accepted()
        result = self.ok(self.request('checkpoint'))
        need(self.accepted() == before, 'CHECKPOINT_MUTATED_ACCEPTED_STATE')
        return result

    def independently_derived(self):
        # Pure Python reconstruction over this generic fixture's own confirmed
        # original output slices. Does not call the candidate JS or read state.
        inventory = parse(self.observations[0]['result']['output'].encode())
        fields = {item['selector']: {'next_char': 0, 'next_utf8_byte': 0,
                                    'field_chars': item['field_chars'],
                                    'field_utf8_bytes': item['field_utf8_bytes'], 'field_eof': False}
                  for item in inventory['fields']}
        for pending in self.observations[1:]:
            doc = parse(pending['result']['output'].encode())
            field = fields[doc['selector']]
            need(doc['start_char'] == field['next_char'] and doc['start_utf8_byte'] == field['next_utf8_byte'],
                 'GENERIC_CONTROL_SEQUENCE_GAP')
            need(len(doc['content']) == doc['content_chars'] and
                 len(doc['content'].encode('utf-8')) == doc['content_utf8_bytes'], 'SCALAR_BYTE_MISMATCH')
            field.update(next_char=doc['end_char'], next_utf8_byte=doc['end_utf8_byte'], field_eof=doc['field_eof'])
        return {'format': 'verislop.own-view-availability-summary/0.1', 'availability_only': True,
                'semantic_consumption': 'UNATTESTED', 'semantic_acceptance_authority': False, 'fields': fields}


class Suite:
    def __init__(self, run, registration):
        self.run = run
        run.mkdir()
        self.registration = registration
        self.before = guard(registration)
        self.build = run / 'isolated-source-root'
        self.build.mkdir()
        for source, target in SOURCE_LAYOUT.items():
            path = self.build / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((HERE / source).read_bytes())
            need(path.read_bytes() == (HERE / source).read_bytes(), 'ISOLATED_BUILD_COPY_MISMATCH')
        self.source = self.build / 'synthetic_dataset/tools/carrier_runtime020'
        self.api = module('s022_generator_' + run.name, self.source / 'compact_protocol.py')
        self.reader = module('s022_renderer_' + run.name, self.build / 'independent/author_protocol_reconstruction.py')
        self.old = module('s022_old_generator_' + run.name, ROOT / 'synthetic_dataset/tools/carrier_runtime020/compact_protocol.py')
        self.observer = Observer(run / 'actual-processes')
        self.controls = []
        self.synthetic_count = 0
        self.fixture = Fixture(self)

    def normalized(self, literal):
        return literal.replace(self.fixture.state.name, '<OWN_SESSION_BASENAME>').replace(str(self.run), '<RUN>')

    def checked(self, number, procedure):
        witness = procedure()
        self.controls.append({'id': IDS[number - 1], 'status': 'PASS', 'witness': witness})

    def template(self, recipe):
        shim = """import childProcess from 'node:child_process';
const MEMORY = new Map(); const CALLS = []; let FORWARDED;
const tools = {exec_command: async args => {
  const r = childProcess.spawnSync('/bin/sh', ['-c', args.cmd], {encoding:'utf8',maxBuffer:32768});
  if(r.error) throw r.error;
  const returned = {chunk_id:'SYNTHETIC_CHECKPOINT_TEMPLATE',exit_code:r.status,output:r.stdout};
  CALLS.push({args,returned,actual_child_PID:r.pid,actual_child_signal:r.signal,actual_child_stderr:r.stderr});
  return returned;
}};
function store(k,v){MEMORY.set(k,v);} function load(k){return MEMORY.get(k);}
function text(v){FORWARDED=v;}
"""
        tail = "\nconsole.log(JSON.stringify({fixture_kind:'SYNTHETIC_TRANSPORT_WITH_ACTUAL_OS_CHILD',calls:CALLS,forwarded:FORWARDED,memory:Object.fromEntries(MEMORY)}));\n"
        actual = self.observer.run([NODE, '--input-type=module', '-'], stdin=(shim + recipe + tail).encode())
        need(actual['exit_code'] == 0 and not actual['stderr'], 'TEMPLATE_EXECUTION_FAILED')
        value = parse(actual['stdout'])
        need(len(value['calls']) == 1 and value['forwarded'] == value['calls'][0]['returned']
             and value['memory'] == {}, 'CHECKPOINT_RECIPE_MUTATED_MEMORY_OR_DID_NOT_FORWARD_FULL_RESULT')
        call = value['calls'][0]
        need(type(call['actual_child_PID']) is int and type(call['returned']['exit_code']) is int
             and call['returned']['exit_code'] == 0 and call['actual_child_signal'] is None
             and call['actual_child_stderr'] == '', 'TEMPLATE_CHILD_FAILED')
        return value

    def c01(self):
        f = self.fixture
        need(f.checkpoint() == EMPTY and not f.state.exists() and list(f.sessions.iterdir()) == [], 'EMPTY_NOT_CLOSED_READ_ONLY')
        return {'closed_EMPTY': EMPTY, 'accepted_state_created': False}

    def c02(self):
        f = self.fixture
        f.confirm(f.view())
        f.confirm(f.view('/system'))
        f.confirm(f.view('/user', 0, 1536, 1280))
        summary = f.checkpoint()
        need(summary == f.independently_derived(), 'INDEPENDENT_PARTIAL_RECONSTRUCTION_MISMATCH')
        need(0 < summary['fields']['/user']['next_char'] < len(f.user)
             and not summary['fields']['/user']['field_eof'], 'NOT_ACTUALLY_PARTIAL')
        return {'summary': summary, 'independent_python_reconstruction_equal': True}

    def c03(self):
        f = self.fixture
        before = f.accepted()
        one, two = f.checkpoint(), f.checkpoint()
        need(one == two and f.accepted() == before, 'REPEATED_CHECKPOINT_NOT_READ_ONLY')
        return {'same_summary': True, 'state_bytes_equal': True}

    def c04(self):
        f = self.fixture
        raw = f.carrier.read_bytes()
        f.carrier.unlink()
        try:
            summary = f.checkpoint()
            need(summary == f.independently_derived(), 'CARRIER_ABSENT_CHECKPOINT_CHANGED')
        finally:
            f.carrier.write_bytes(raw)
        return {'carrier_absent_during_success': True, 'reader_process_required': False}

    def c05(self):
        f = self.fixture
        summary = f.checkpoint()
        cursor = summary['fields']['/user']['next_char']
        self.lost = f.view('/user', cursor, 1536, 1280)
        need(f.checkpoint() == summary and self.lost['view']['start_char'] == cursor, 'UNCONFIRMED_VIEW_ADVANCED_CURSOR')
        return {'accepted_cursor': cursor, 'lost_unconfirmed_does_not_advance': True}

    def c06(self):
        f = self.fixture
        start = f.checkpoint()['fields']['/user']['next_char']
        pending = f.view('/user', start, 1536, 1280)
        need(pending['result']['output'] == self.lost['result']['output'], 'EXPLICIT_SAME_CURSOR_NOT_EQUAL')
        f.confirm(pending)
        # Finite unrelated test-driver only; no loop enters runtime/author recipes.
        for _ in range(64):
            summary = f.checkpoint()
            if summary['fields']['/user']['field_eof']:
                break
            f.confirm(f.view('/user', summary['fields']['/user']['next_char'], 1536, 1280))
        else:
            raise AssertionError('FINITE_GENERIC_FIXTURE_DID_NOT_FINISH')
        state = parse(f.accepted())
        need(state['fields']['/user']['content'] == f.user and state['fields']['/system']['content'] == f.system,
             'ORIGINAL_UNICODE_CONTENT_MISMATCH')
        hashes = f.ok(f.request('hash'))
        need(hashes['field_roots']['/user'] == sha(f.user.encode('utf-8')), 'UNICODE_FIELD_HASH_MISMATCH')
        return {'explicit_resume_cursor': start, 'unicode_scalar_count': len(f.user),
                'utf8_byte_count': len(f.user.encode('utf-8')), 'original_fields_equal': True,
                'user_stdlib_hash': sha(f.user.encode('utf-8'))}

    def c07(self):
        f = self.fixture
        summary = f.checkpoint()
        need(summary == f.independently_derived(), 'COMPLETE_RECONSTRUCTION_MISMATCH')
        for selector, text in [('/system', f.system), ('/user', f.user)]:
            field = summary['fields'][selector]
            need(field['field_eof'] and field['next_char'] == len(text) == field['field_chars']
                 and field['next_utf8_byte'] == len(text.encode()) == field['field_utf8_bytes'], 'EOF_TOTAL_MISMATCH')
        before = f.accepted()
        result = f.ok(f.request('hash'))
        expected = {'/system': sha(f.system.encode()), '/user': sha(f.user.encode())}
        need(result['field_roots'] == expected and f.accepted() == before, 'OLD_HASH_MISMATCH_OR_MUTATION')
        return {'summary': summary, 'roots': expected, 'hash_read_only': True}

    def c08(self):
        f = self.fixture
        wrong_path = f.request('checkpoint')
        wrong_path['session_path'] += '.foreign'
        codes = [f.reject(wrong_path, 'UNMATCHED_OWN_SESSION_PATH')]
        request = copy.deepcopy(f.request('checkpoint'))
        request['reference']['request_sha256'] = 'sha256:' + '0' * 64
        newstate = Path(self.api.session_path(request['reference'], f.code))
        newstate.write_bytes(f.accepted())
        request['session_path'] = str(newstate)
        before = newstate.read_bytes()
        codes.append(f.reject(request, 'UNMATCHED_OWN_CHECKPOINT'))
        need(newstate.read_bytes() == before, 'FOREIGN_REFERENCE_STATE_MUTATED')
        newstate.unlink()
        return {'rejections': codes, 'both_state_files_unchanged': True}

    def c09(self):
        f = self.fixture
        original = f.accepted()
        cases = []
        mutations = [lambda state: state['fields']['/user'].__setitem__('next_char', 0),
                     lambda state: state['observations'][1]['pending']['result'].__setitem__('output', '{}\n')]
        try:
            for mutate in mutations:
                state = parse(original)
                mutate(state)
                f.state.write_bytes((wire(state) + '\n').encode())
                cases.append(f.reject(f.request('checkpoint')))
        finally:
            f.state.write_bytes(original)
        return {'concrete_tampered_state_rejections': cases, 'rejected_bytes_preserved': True}

    def c10(self):
        f = self.fixture
        errors = []
        for name, value in [('view', {}), ('pending', None), ('confirmation', None), ('extra', True)]:
            request = f.request('checkpoint')
            request[name] = value
            errors.append(f.reject(request, 'INVALID_RUNTIME_REQUEST'))
        return {'extra_keys_rejected': ['view', 'pending', 'confirmation', 'extra'], 'errors': errors}

    def c11(self):
        f = self.fixture
        errors = []
        for name in ['runtime_sha256', 'reader_sha256']:
            request = copy.deepcopy(f.request('checkpoint'))
            request['code'][name] = 'sha256:' + '0' * 64
            errors.append(f.reject(request, 'RUNTIME_SOURCE_IDENTITY_MISMATCH'))
        return {'pinned_hash_mismatch_rejections': errors}

    def c12(self):
        raw = (HERE / 'carrier_runtime.js').read_text()
        main = raw.split('function runtimeMain(request) {', 1)[1].split('\ntry {\n  checkpointNeed(process.argv.length', 1)[0]
        branch = main.split('    if (request.operation === "checkpoint") {', 1)[1].split('\n    if (request.operation === "hash")', 1)[0]
        need('spawnSync' not in branch and 'runtimeHash' not in branch and 'runtimeAtomicCommit' not in branch
             and 'runtimeView' not in branch and not re.search(r'\b(for|while)\s*\(', branch), 'CHECKPOINT_PERFORMS_AUTOMATIC_ACTION')
        recipe = self.api.runtime_checkpoint_template(self.fixture.reference, self.fixture.code)
        need(recipe.count('await tools.exec_command(') == 1 and 'store(' not in recipe
             and 'REQUEST.view' not in recipe and 'load(' not in recipe, 'CHECKPOINT_RECIPE_NOT_ZERO_VIEW_READ_ONLY')
        message = self.api.runtime_agent_message(self.fixture.reference, self.fixture.code)
        need('after compression/lost cursor and before FINAL' in message and 'exact returned next_char' in message
             and 'resume FIRST and CONFIRM inventory' in message, 'CHECKPOINT_RECOVERY_INSTRUCTION_ABSENT')
        return {'checkpoint_branch_no_view_hash_commit_loop': True, 'recipe_exactly_one_runtime_call': True,
                'no_automatic_cursor_choice': True}

    def c13(self):
        f = self.fixture
        names = ['runtime_initial_template', 'runtime_next_template', 'runtime_confirm_template', 'runtime_hash_template']
        hashes = {}
        for name in names:
            old = getattr(self.old, name)(f.reference, f.code)
            new = getattr(self.api, name)(f.reference, f.code)
            need(old == new, 'OLD_RECIPE_CHANGED:' + name)
            # Bound code/own path values are legitimate dynamic data, not recipe literals.
            hashes[name] = sha(self.normalized(new).encode())
        return {'old_recipes_equal_under_same_current_bindings': True, 'normalized_recipe_sha256': hashes}

    def c14(self):
        f = self.fixture
        engine = self.reader.PureTemplateAST((self.source / 'compact_protocol.py').read_bytes())
        produced = self.api.runtime_agent_message(f.reference, f.code)
        independent = engine.call('runtime_agent_message', f.reference, f.code)
        need(produced == independent, 'INDEPENDENT_WHOLE_MESSAGE_DIFFERS')
        message = self.run / 'independently-reconstructed-message.txt'
        message.write_bytes(independent.encode())
        descriptor = module('s022_integration_' + self.run.name,
                            self.build / 'synthetic_dataset/tools/bootstrap_tier2_runtime_integration.py')
        registration = descriptor.load_registration(self.build)
        need(registration['api_revision'] == REVISION and descriptor.source_inventory(self.build), 'NEW_INTEGRATION_BINDING_FAILED')
        need(descriptor.compact_message(self.build, registration, f.reference, str(f.sessions)) == produced,
             'REGISTERED_INTEGRATION_MESSAGE_DIFFERS')
        return {'whole_message_independently_reconstructed': True, 'byte_count': len(produced.encode()),
                'normalized_message_sha256': sha(self.normalized(produced).encode()),
                'new_integration_source_bindings_accepted': True}

    def c15(self):
        f = self.fixture
        recipe = self.api.runtime_checkpoint_template(f.reference, f.code)
        request_line = next(line for line in recipe.splitlines() if line.startswith('const REQUEST = '))
        request = json.loads(request_line[len('const REQUEST = '):-1])
        need(request == f.request('checkpoint') and set(request) == {'format', 'operation', 'reference', 'session_path', 'code'},
             'CHECKPOINT_TEMPLATE_REQUEST_NOT_CLOSED_OR_BOUND')
        engine = self.reader.PureTemplateAST((self.source / 'compact_protocol.py').read_bytes())
        need(engine.call('runtime_checkpoint_template', f.reference, f.code) == recipe, 'CHECKPOINT_TEMPLATE_RECONSTRUCTION_FAILED')
        before = f.accepted()
        actual = self.template(recipe)
        need(f.accepted() == before and parse(actual['forwarded']['output'].encode()) == f.independently_derived(),
             'LITERAL_CHECKPOINT_TEMPLATE_MUTATED_OR_RETURNED_WRONG_SUMMARY')
        return {'closed_request_key_count': 5, 'exact_reference_code_session': True,
                'synthetic_transport_fixture': True, 'actual_OS_child_integer_status': True,
                'full_result_forwarded': True, 'shell_quoted_unicode_quotes_newlines': True}

    def c16(self):
        baseline = ROOT / 'synthetic_dataset/tools/carrier_runtime020'
        old_js = (baseline / 'carrier_runtime.js').read_bytes()
        new_js = (HERE / 'carrier_runtime.js').read_bytes()
        prefix = b'function runtimeMain(request) {'
        tail = b'\ntry {\n  checkpointNeed(process.argv.length'
        need(old_js.split(prefix, 1)[0] == new_js.split(prefix, 1)[0]
             and old_js.split(tail, 1)[1] == new_js.split(tail, 1)[1], 'JS_OUTSIDE_RUNTIME_MAIN_CHANGED')
        expected_js = old_js.replace(b'["view", "confirm", "hash"].includes(request.operation)',
                                    b'["view", "confirm", "hash", "checkpoint"].includes(request.operation)', 1)
        insertion = b'''    if (request.operation === "checkpoint") {
      runtimeCodeGuard(request.code);
      return state === undefined
        ? {format: "verislop.own-view-availability-summary/0.1", status: "EMPTY",
          availability_only: true, semantic_consumption: "UNATTESTED", semantic_acceptance_authority: false}
        : checkpointSummary(state);
    }
'''
        expected_js = expected_js.replace(b'    if (request.operation === "hash") {', insertion + b'    if (request.operation === "hash") {', 1)
        need(new_js == expected_js, 'UNREGISTERED_RUNTIME_MAIN_DELTA')
        old_py = (baseline / 'compact_protocol.py').read_bytes()
        new_py = (HERE / 'compact_protocol.py').read_bytes()
        old_defs, new_defs = definitions(old_py), definitions(new_py)
        need(set(new_defs) - set(old_defs) == {'runtime_checkpoint_template'} and
             set(old_defs) - set(new_defs) == set(), 'PRODUCER_FUNCTION_SET_DELTA')
        changed = [name for name in old_defs if dump(old_defs[name]) != dump(new_defs[name])]
        need(changed == ['runtime_agent_message'], 'UNREGISTERED_PRODUCER_FUNCTION_DELTA')
        old_consts, new_consts = assignments(old_py), assignments(new_py)
        need({key for key in old_consts if old_consts[key] != new_consts[key]} == {'API_REVISION'}
             and set(old_consts) == set(new_consts) and new_consts['API_REVISION'] == REVISION, 'PRODUCER_CONSTANT_DELTA')
        before_msg = copy.deepcopy(old_defs['runtime_agent_message'])
        after_msg = copy.deepcopy(new_defs['runtime_agent_message'])
        class MaskStrings(ast.NodeTransformer):
            def visit_Constant(self, node):
                return ast.Constant(value='<literal>') if type(node.value) is str else node
        before_msg, after_msg = MaskStrings().visit(before_msg), MaskStrings().visit(after_msg)
        # Remove only the registered new appended CHECKPOINT recipe term from
        # the message expression, then compare all remaining nonliteral AST.
        def flattened(node):
            return flattened(node.left) + flattened(node.right) if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) else [node]
        old_return = next(n for n in before_msg.body if isinstance(n, ast.Return))
        new_return = next(n for n in after_msg.body if isinstance(n, ast.Return))
        filtered = [n for n in flattened(new_return.value)
                    if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'runtime_checkpoint_template')]
        new_expr = filtered[0]
        for n in filtered[1:]:
            new_expr = ast.BinOp(left=new_expr, op=ast.Add(), right=n)
        new_return.value = new_expr
        # The inserted recipe label also adds one literal concatenation term.
        old_terms, new_terms = flattened(old_return.value), flattened(new_return.value)
        need(len(new_terms) == len(old_terms) + 1, 'MESSAGE_DELTA_NOT_ONE_RECIPE_LABEL')
        matched = False
        for index, node in enumerate(new_terms):
            if not isinstance(node, ast.Constant):
                continue
            candidate = new_terms[:index] + new_terms[index + 1:]
            if [dump(n) for n in candidate] == [dump(n) for n in old_terms]:
                matched = True
                break
        need(matched, 'MESSAGE_UNAPPROVED_NONLITERAL_AST_DELTA')
        old_integration = (ROOT / 'synthetic_dataset/tools/bootstrap_tier2_runtime_integration.py').read_bytes()
        new_integration = (HERE / 'bootstrap_tier2_runtime_integration.py').read_bytes()
        need(new_integration == old_integration.replace(b'REVISION = "support020-compact-runtime/1"',
                                                        b'REVISION = "support022-compact-runtime/1"', 1), 'INTEGRATION_NONSCALAR_DELTA')
        old_renderer = (ROOT / 'validation/tier2-support-019-qualification-adapters-008/author_protocol_reconstruction.py').read_bytes()
        new_renderer = (HERE / 'author_protocol_reconstruction.py').read_bytes()
        expected_renderer = old_renderer.replace(b'"runtime_hash_template", "runtime_agent_message"}',
                                                 b'"runtime_hash_template", "runtime_checkpoint_template", "runtime_agent_message"}', 1)
        expected_renderer = expected_renderer.replace(b'self.constants.get("API_REVISION") == "support020-compact-runtime/1"',
                                                      b'self.constants.get("API_REVISION") == "support022-compact-runtime/1"', 1)
        need(new_renderer == expected_renderer, 'RENDERER_UNREGISTERED_AST_DELTA')
        old_descriptor = parse((ROOT / 'synthetic_dataset/tools/carrier_runtime020-registration.json').read_bytes())
        expected_descriptor = copy.deepcopy(old_descriptor)
        expected_descriptor['api_revision'] = REVISION
        for role, name in [('runtime', 'carrier_runtime.js'), ('generator', 'compact_protocol.py')]:
            expected_descriptor['source_files'][role]['sha256'] = sha((HERE / name).read_bytes())
        need(parse((HERE / 'carrier_runtime020-registration.json').read_bytes()) == expected_descriptor, 'DESCRIPTOR_UNREGISTERED_DELTA')
        exact = [('reader.py', baseline / 'reader.py'),
                 ('bootstrap_tier2_carrier_view.py', ROOT / 'validation/tier2-support019-author-recovery-implementation-006/bootstrap_tier2_carrier_view.py'),
                 ('capture-amendment-003/collector_templates.py', ROOT / 'validation/tier2-support019-author-recovery-implementation-006/capture-amendment-003/collector_templates.py')]
        for name, original in exact:
            need((HERE / name).read_bytes() == original.read_bytes(), 'EXACT_COPIED_SOURCE_CHANGED:' + name)
        old_parser = (ROOT / 'validation/tier2-carrier-runtime-support-021-implementation-001/diagnostic_failure_parser.py').read_bytes()
        expected_parser = old_parser.replace(b'"CONFIRM", "HASH", "FINAL_ASSEMBLY", "UNKNOWN"}',
                                             b'"CONFIRM", "HASH", "CHECKPOINT", "FINAL_ASSEMBLY", "UNKNOWN"}', 1)
        expected_parser = expected_parser.replace(b'{"FIRST", "NEXT", "CONFIRM", "HASH", "FINAL_SCHEMA", "UNAVAILABLE"}',
                                                 b'{"FIRST", "NEXT", "CONFIRM", "HASH", "CHECKPOINT", "FINAL_SCHEMA", "UNAVAILABLE"}', 1)
        need((HERE / 'diagnostic_failure_parser.py').read_bytes() == expected_parser, 'PARSER_UNREGISTERED_DELTA')
        return {'JS_changed_function': 'runtimeMain', 'all_other_JS_bytes_exact': True,
                'producer_changed_functions': changed, 'producer_new_function': 'runtime_checkpoint_template',
                'producer_changed_constant': 'API_REVISION', 'integration_REVISION_only': True,
                'renderer_one_PURE_FUNCTION_name_and_revision_only': True,
                'descriptor_API_and_two_hashes_only': True,
                'reader_legacy_capture_bytes_exact': True, 'parser_exactly_two_CHECKPOINT_labels': True}

    def c17(self):
        f = self.fixture
        errors = []
        for cap, reserve in [(65536, 2048), (True, 128), (8192, 8192)]:
            errors.append(f.reject(f.request('view', view={'operation': 'field', 'selector': '/user', 'start_char': 0,
                                                          'output_cap_bytes': cap, 'metadata_reserve_bytes': reserve}),
                                   'INVALID_CLOSED_VIEW_BOUNDS'))
        pending = copy.deepcopy(self.lost)
        original = copy.deepcopy(pending)
        for mutate, confirmation in [
            (lambda p: None, {'chunk_id': pending['result']['chunk_id'], 'outer_output_intact': False}),
            (lambda p: p['result'].__setitem__('exit_code', True), {'chunk_id': pending['result']['chunk_id'], 'outer_output_intact': True}),
            (lambda p: p['result'].__setitem__('output', p['result']['output'][:-8]), {'chunk_id': pending['result']['chunk_id'], 'outer_output_intact': True}),
            (lambda p: p['result'].__setitem__('original_token_count', 16385), {'chunk_id': pending['result']['chunk_id'], 'outer_output_intact': True})]:
            pending = copy.deepcopy(original)
            mutate(pending)
            errors.append(f.reject(f.request('confirm', pending=pending, confirmation=confirmation)))
        return {'invalid_VIEW_bounds_and_rejected_CONFIRM_codes': errors,
                'accepted_state_byte_exact_on_every_rejection': True,
                'outer_truncation_boolean_status_nested_truncation_checked': True}

    def diagnostic_controls(self):
        parser = module('s022_failure_parser_' + self.run.name,
                        self.build / 'legacy/diagnostic_failure_parser.py')
        old = module('s022_old_failure_parser_' + self.run.name,
                     ROOT / 'validation/tier2-carrier-runtime-support-021-implementation-001/diagnostic_failure_parser.py')
        outputs = []
        report = diagnostic(diagnostic_view())
        report['failure']['stage'] = 'CHECKPOINT'
        report['failure']['operation'] = None
        report['failure']['reproduction'].update(template='CHECKPOINT', view=None,
                                                own_input_literal=wire(self.fixture.request('checkpoint')))
        raw = wire(report).encode()
        admitted = parser.parse_failure(raw, fixture_failure_allowed=True)
        need(admitted['success'] is False and admitted['trust'] == 'UNATTESTED'
             and admitted['qualification_claims_discharged'] == [] and admitted['literal_final_sha256'] == sha(raw),
             'CHECKPOINT_DIAGNOSTIC_GRANTED_AUTHORITY')
        outputs.append({'id': 'S022-D01', 'status': 'PASS', 'witness': {'CHECKPOINT_failure_evidence_only': True,
                       'success': False, 'trust': 'UNATTESTED', 'claims': []}})
        errors = []
        for key, value, expected in [('view', diagnostic_view(), 'PROVIDED_IRRELEVANT_VIEW'),
                                     ('confirmation', {'chunk_id': 'SYNTHETIC', 'outer_output_intact': True},
                                      'PROVIDED_IRRELEVANT_CONFIRMATION')]:
            rejected = copy.deepcopy(report)
            rejected['failure']['reproduction'][key] = value
            errors.append(fails(lambda rejected=rejected: parser.parse_failure(wire(rejected).encode(),
                                                                               fixture_failure_allowed=True), expected))
        outputs.append({'id': 'S022-D02', 'status': 'PASS', 'witness': {'irrelevant_payload_rejections': errors}})
        groups = []
        maximum = 2**53 - 1
        variants = [diagnostic_view(output_cap_bytes=65536), diagnostic_view(start_char=-1),
                    diagnostic_view(metadata_reserve_bytes=8192), diagnostic_view(output_cap_bytes=-1),
                    diagnostic_view(metadata_reserve_bytes=-1),
                    diagnostic_view(start_char=-maximum, output_cap_bytes=-maximum, metadata_reserve_bytes=maximum),
                    diagnostic_view(start_char=maximum, output_cap_bytes=maximum, metadata_reserve_bytes=-maximum)]
        for number, attempt in enumerate(variants, 1):
            raw = wire(diagnostic(attempt)).encode()
            one = old.parse_failure(raw, fixture_failure_allowed=True)
            two = parser.parse_failure(raw, fixture_failure_allowed=True)
            need(one == two and two['report']['failure']['reproduction']['view'] == attempt
                 and two['literal_final_sha256'] == sha(raw) and two['trust'] == 'UNATTESTED'
                 and two['success'] is False and two['qualification_claims_discharged'] == [], 'OLD_DIAGNOSTIC_POSITIVE_CHANGED')
            groups.append({'group': number, 'old_new_equal': True, 'attempt': attempt, 'success': False})
        boolean_errors = []
        for location in ['operation', 'reproduction']:
            for key in ['start_char', 'output_cap_bytes', 'metadata_reserve_bytes']:
                report = diagnostic(diagnostic_view())
                target = report['failure']['operation'] if location == 'operation' else report['failure']['reproduction']['view']
                target[key] = True
                one = fails(lambda report=report: old.parse_failure(wire(report).encode(), fixture_failure_allowed=True))
                two = fails(lambda report=report: parser.parse_failure(wire(report).encode(), fixture_failure_allowed=True))
                need(one == two, 'BOOLEAN_DIAGNOSTIC_REJECTION_CHANGED')
                boolean_errors.append(two)
        groups.append({'group': 8, 'six_boolean_rejections_equal': boolean_errors})
        unsafe_errors = []
        for bad in [maximum + 1, -maximum - 1]:
            raw = wire(diagnostic(diagnostic_view(start_char=bad))).encode()
            one = fails(lambda raw=raw: old.parse_failure(raw, fixture_failure_allowed=True), 'UNSAFE_JSON_INTEGER')
            two = fails(lambda raw=raw: parser.parse_failure(raw, fixture_failure_allowed=True), 'UNSAFE_JSON_INTEGER')
            need(one == two, 'UNSAFE_NUMBER_REJECTION_CHANGED')
            unsafe_errors.append(two)
        groups.append({'group': 9, 'unsafe_integer_rejections_equal': unsafe_errors})
        raw = wire(diagnostic(diagnostic_view(start_char=0.5))).encode()
        one = fails(lambda: old.parse_failure(raw, fixture_failure_allowed=True), 'UNSUPPORTED_JSON_NUMBER')
        two = fails(lambda: parser.parse_failure(raw, fixture_failure_allowed=True), 'UNSUPPORTED_JSON_NUMBER')
        need(one == two, 'FLOAT_REJECTION_CHANGED')
        groups.append({'group': 10, 'float_rejection_equal': two})
        clean = wire(diagnostic(diagnostic_view())).encode()
        duplicated = clean.replace(b'"markers":[]', b'"markers":[],"markers":[]', 1)
        extra = diagnostic(diagnostic_view()); extra['failure']['operation']['extra'] = 0
        claim = diagnostic(diagnostic_view()); claim['failure']['trust'] = 'VERIFIED'
        malformed = []
        for raw, permitted, expected in [(duplicated, True, 'DUPLICATE_JSON_KEY'),
                                          (clean, False, 'FIXTURE_FAILURE_BRANCH_NOT_AUTHORIZED'),
                                          (wire(extra).encode(), True, 'INVALID_OWN_OPERATION'),
                                          (wire(claim).encode(), True, 'FAILURE_AUTHORITY_OVERCLAIM')]:
            one = fails(lambda raw=raw, permitted=permitted: old.parse_failure(raw, fixture_failure_allowed=permitted), expected)
            two = fails(lambda raw=raw, permitted=permitted: parser.parse_failure(raw, fixture_failure_allowed=permitted), expected)
            need(one == two, 'OLD_MALFORMED_DIAGNOSTIC_REJECTION_CHANGED')
            malformed.append(two)
        groups.append({'group': 11, 'closed_schema_rejections_equal': malformed})
        report = diagnostic(diagnostic_view())
        raw = wire(report).encode()
        one, two = old.parse_failure(raw, fixture_failure_allowed=True), parser.parse_failure(raw, fixture_failure_allowed=True)
        need(one == two and two['success'] is False and two['qualification_claims_discharged'] == []
             and two['historical_cause'] == 'UNAVAILABLE', 'OLD_FAILURE_AUTHORITY_CHANGED')
        ordinary = {key: report[key] for key in ['markers', 'field_roots', 'field_eof', 'field_chars']}
        raw = wire(ordinary).encode()
        one = fails(lambda: old.parse_failure(raw, fixture_failure_allowed=True), 'NOT_CLOSED_DIAGNOSTIC_FAILURE_BRANCH')
        two = fails(lambda: parser.parse_failure(raw, fixture_failure_allowed=True), 'NOT_CLOSED_DIAGNOSTIC_FAILURE_BRANCH')
        need(one == two, 'FOUR_KEY_SUCCESS_EXCLUSION_CHANGED')
        groups.append({'group': 12, 'failure_only_and_fourkey_success_exclusion_equal': True})
        rejected = []
        for attempt in [diagnostic_view(output_cap_bytes=65536), diagnostic_view(start_char=-1),
                        diagnostic_view(metadata_reserve_bytes=8192), diagnostic_view(output_cap_bytes=True),
                        diagnostic_view(start_char=True), diagnostic_view(metadata_reserve_bytes=True)]:
            one = fails(lambda attempt=attempt: self.old.runtime_next_template(self.fixture.reference, self.fixture.code, attempt))
            two = fails(lambda attempt=attempt: self.api.runtime_next_template(self.fixture.reference, self.fixture.code, attempt))
            need(one == two, 'OLD_ACCEPTED_VIEW_DOMAIN_CHANGED')
            rejected.append(two)
        groups.append({'group': 13, 'six_invalid_runtime_template_arguments_rejected_equal': rejected})
        for attempt in [diagnostic_view(), diagnostic_view(output_cap_bytes=4096)]:
            need(self.api.runtime_next_template(self.fixture.reference, self.fixture.code, attempt)
                 == self.old.runtime_next_template(self.fixture.reference, self.fixture.code, attempt), 'VALID_TEMPLATE_CHANGED')
        groups.append({'group': 14, 'valid8192_4096_templates_byte_exact': True})
        need(len(groups) == 14, 'REGRESSION_GROUPS_NOT_EXACT14')
        outputs.append({'id': 'S022-D03', 'status': 'PASS', 'witness': {'existing021_diagnostic_regression_groups': groups,
                       'old021_and_new022_results_equal': True, 'historical_author_literal_read': False}})
        return outputs

    def execute(self):
        for number in range(1, 18):
            self.checked(number, getattr(self, 'c' + str(number).zfill(2)))
        diagnostics = self.diagnostic_controls()
        after = guard(self.registration)
        need(after == self.before, 'SOURCE_CHANGED_DURING_CONTROLS')
        # Only deterministic evidence enters this report. All actual process
        # paths/PIDs/timing/raw output are separately retained verbatim.
        deterministic = {'format': 'verislop.support022-deterministic-controls/1', 'controls': self.controls,
                         'diagnostic_controls': diagnostics,
                         'candidate_sources': {name: sha((HERE / name).read_bytes()) for name in SOURCE_LAYOUT},
                         'actual_generic_process_count': len(self.observer.refs),
                         'synthetic_pending_fixture_count': self.synthetic_count,
                         'trust': 'Availability only; semantic consumption UNATTESTED; no qualification/task/model authority.'}
        save(self.run / 'deterministic-controls.json', deterministic)
        receipt = {'format': 'verislop.support022-control-worker-receipt/1', 'observed_process_PID': os.getpid(),
                   'exit_code': 0, 'controls': self.controls, 'diagnostic_controls': diagnostics,
                   'source_guards_before': self.before,
                   'source_guards_after': after, 'guards_unchanged': True,
                   'isolated_source_root': str(self.build), 'fresh_control_root': str(self.run),
                   'actual_generic_process_records': self.observer.refs,
                   'deterministic_report_ref': ref(self.run / 'deterministic-controls.json'),
                   'synthetic_observation_metadata': 'SYNTHETIC_S022_CHUNK and SYNTHETIC_CHECKPOINT_TEMPLATE are constructed fixtures, never native tool attestation.',
                   'model_task_Lean_current27_qualification_calls': 0, 'semantic_consumption': 'UNATTESTED'}
        save(self.run / 'worker-receipt.json', receipt)
        return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker')
    args = parser.parse_args()
    registration = parse((HERE / 'CONTROL_EXECUTION_REGISTRATION_002.json').read_bytes())
    contract = parse((HERE / 'CONTROL_CONTRACT_BEFORE_SOURCE.json').read_bytes())
    need([value['id'] for value in contract['controls']] == IDS and registration['control_ids'] == IDS,
         'PREREGISTERED_CONTROLS_NOT_EXACT18')
    before = guard(registration)
    if args.worker:
        need(args.worker in ['controls-run-003', 'controls-run-004'], 'UNREGISTERED_WORKER_ROOT')
        receipt = Suite(HERE / args.worker, registration).execute()
        print(wire({'worker': args.worker, 'actual_PID': os.getpid(), 'integer_status': 0,
                    'completed_control_count': len(receipt['controls']), 'guard_count': len(before)}))
        return
    observer = Observer(HERE / 'actual-worker-processes-002')
    for name in ['controls-run-003', 'controls-run-004']:
        result = observer.run([PYTHON, '-I', '-B', str(Path(__file__).resolve()), '--worker', name])
        need(result['exit_code'] == 0 and not result['stderr'], 'WORKER_FAILED:' + str(result['record_ref']))
    first = parse((HERE / 'controls-run-003/deterministic-controls.json').read_bytes())
    second = parse((HERE / 'controls-run-004/deterministic-controls.json').read_bytes())
    need(first == second, 'TWO_FRESH_RUNS_NOT_DETERMINISTIC')
    witness = {'fresh_isolated_source_control_roots': 2, 'deterministic_reports_equal': True,
               'deterministic_report_sha256': sha((HERE / 'controls-run-003/deterministic-controls.json').read_bytes()),
               'excluded_fields': contract['determinism_normalization']}
    runs = []
    for name in ['controls-run-003', 'controls-run-004']:
        worker = parse((HERE / name / 'worker-receipt.json').read_bytes())
        report = {'format': 'verislop.support022-finite18-source-report/1',
                  'controls': worker['controls'] + [{'id': IDS[17], 'status': 'PASS', 'witness': witness}],
                  'diagnostic_controls': worker['diagnostic_controls'],
                  'worker_receipt_ref': ref(HERE / name / 'worker-receipt.json'),
                  'all18_passed': True, 'source_readiness_only': True, 'qualification_authority': False}
        save(HERE / name / 'all18-report.json', report)
        runs.append({'name': name, 'actual_control_PID': worker['observed_process_PID'], 'exit_code': 0,
                     'report_ref': ref(HERE / name / 'all18-report.json'),
                     'actual_generic_process_count': len(worker['actual_generic_process_records'])})
    after = guard(registration)
    need(before == after, 'OUTER_SOURCE_GUARD_CHANGED')
    value = {'format': 'verislop.support022-actual-controls/1', 'observed_process_PID': os.getpid(), 'exit_code': 0,
             'control_ids': IDS, 'diagnostic_control_ids': ['S022-D01', 'S022-D02', 'S022-D03'],
             'clean_runs': runs, 'all18_each_run_passed': True, 'all3_diagnostic_each_run_passed': True,
             'deterministic_witness': witness, 'actual_worker_process_refs': observer.refs,
             'source_guards_before': before, 'source_guards_after': after, 'guards_unchanged': True,
             'historical_Q007_failure_cause': 'UNAVAILABLE', 'source_readiness_only': True,
             'qualification_authority': False, 'model_task_Lean_current27_calls': 0}
    save(HERE / 'ACTUAL_CONTROL_REPORT_002.json', value)
    print(wire({'actual_PID': os.getpid(), 'exit_code': 0, 'all18_each_run_passed': True,
                'guard_count': len(before), 'clean_runs': runs}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
