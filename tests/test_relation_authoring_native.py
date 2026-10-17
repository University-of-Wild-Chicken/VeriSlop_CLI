"""Unrelated accepted Packet/Int fixture: names never repair semantic defects."""
import copy
import tempfile
import unittest
from pathlib import Path

from verislop import canonical, export, relation_authoring
from verislop.bridges import vscore3_checker as checker
from verislop.targets import vscore3_source as source
from test_vscore3_pipeline import accepted_fixture, SURFACE, RELATION, PROOF


class RelationNativeNoninterferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='verislop-relation-native-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.pkg = accepted_fixture(Path(cls.temp.name))
        ir, _, cert, errors = export.verified_ir(cls.pkg)
        if errors:
            raise AssertionError([e.to_json() for e in errors])
        profile = canonical.load_file(cls.pkg.root / cert['artifacts']['profile']['path'])
        fixed = {'accepted_ir': ir, 'accepted_profile': profile, 'lean_toolchain': cert['toolchain']['pin']}
        cls.authority = relation_authoring.prepare(cls.pkg, fixed)
        cls.program = canonical.loads(source.compile_surface(SURFACE))
        cls.alias = copy.deepcopy(RELATION)
        for row in cls.alias['bindings']:
            row['symbol'] = profile['symbols'][row['symbol']]['lean_decl']
        cls.alias['bindings'].sort(key=lambda row: row['symbol'])

    def attempt(self, program, rel=None, *, proof=None):
        rel = rel if rel is not None else self.alias
        response = canonical.dumps({'program': program, 'relation': rel, 'proof_source': PROOF.decode()})
        normalized = relation_authoring.normalize_attempt(self.pkg,
            self.pkg.root / 'agents/vscore-attempts' / self._testMethodName,
            self.authority, response, canonical.dumps(rel))
        return checker.preview(self.pkg, canonical.dumps(program), normalized, proof=proof)

    def test_unique_alias_does_not_repair_nat_int_signature(self):
        program = copy.deepcopy(self.program)
        program['entries'][0].update(result='nat', body={'tag': 'nat', 'value': '0'})
        with self.assertRaises(checker.EdgeFailure) as failure:
            self.attempt(program)
        self.assertIn('STATEMENT_MISMATCH', {d.code for d in failure.exception.diagnostics})
        self.assertIn('signature differs', str(failure.exception))

    def test_unique_alias_does_not_repair_nominal_record_layout(self):
        program = copy.deepcopy(self.program)
        program['declarations'][0]['fields'].reverse()
        with self.assertRaises(checker.EdgeFailure) as failure:
            self.attempt(program)
        self.assertIn('exact accepted nominal layout', str(failure.exception))

    def test_unique_alias_does_not_hide_missing_entry_binding(self):
        rel = copy.deepcopy(self.alias)
        rel['bindings'] = rel['bindings'][1:]
        with self.assertRaises(checker.EdgeFailure) as failure:
            self.attempt(self.program, rel)
        self.assertIn('UNMAPPED_IMPLEMENTATION_OBJECT', {d.code for d in failure.exception.diagnostics})
        self.assertIn('every entry must have exactly one accepted binding', str(failure.exception))

    def test_unique_alias_does_not_hide_extra_source_entry(self):
        program = copy.deepcopy(self.program)
        extra = copy.deepcopy(program['entries'][0]); extra['id'] = 'unbound'
        program['entries'].append(extra)
        with self.assertRaises(checker.EdgeFailure) as failure:
            self.attempt(program)
        self.assertIn('UNMAPPED_IMPLEMENTATION_OBJECT', {d.code for d in failure.exception.diagnostics})

    def test_unique_alias_does_not_prove_false_refinement(self):
        program = copy.deepcopy(self.program)
        # Reuse the existing independent bridge fixture's proof verbatim. A
        # different integer operation cannot satisfy its unchanged refinement.
        program['entries'][0]['body']['right']['value'] = '-4'
        with self.assertRaises(checker.EdgeFailure) as failure:
            self.attempt(program, proof=PROOF)
        self.assertIn('CANDIDATE_BUILD_FAILURE', {d.code for d in failure.exception.diagnostics})


if __name__ == '__main__':
    unittest.main()
