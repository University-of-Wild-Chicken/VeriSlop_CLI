import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from synthetic_dataset.tools import recheck_p03 as r
from verislop import canonical as c, fsutil

GOOD = "def solve(d):\n a=[d['prefix']+x for x in d['labels'] if x != '']\n return {'labels':a,'count':len(a)}\n"

class OfflineRecheckTests(unittest.TestCase):
    def test_real_harness_known_fixtures(self):
        variants = {'correct': GOOD,
                    'trim': GOOD.replace("x != ''", 'x.strip()'),
                    'normalize': 'import unicodedata\n'+GOOD.replace("d['prefix']+x", "d['prefix']+unicodedata.normalize('NFC',x)"),
                    'deduplicate': GOOD.replace("return {'labels':a", "a=list(dict.fromkeys(a))\n return {'labels':a"),
                    'count': GOOD.replace('len(a)', "len(d['labels'])"),
                    'empty_prefix': GOOD.replace("d['prefix']+x", "(d['prefix'] or 'X')+x")}
        observations = {}
        for name, code in variants.items():
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root/'requested.py').write_text(code)
                before = fsutil.manifest_tree(root)
                # Only known fixture source runs without namespaces; production stays fail-closed.
                real = r.pt.Harness
                def fixture_harness(*args, **kwargs):
                    kwargs.update(require_network_isolation=False, require_filesystem_isolation=False)
                    return real(*args, **kwargs)
                with patch.object(r.pt, 'Harness', fixture_harness):
                    outcome = r.boundaries(root)
                outcome['fixture_only_without_required_namespaces'] = True
                self.assertEqual('PASS' if name=='correct' else 'FAIL', outcome['status'], outcome)
                self.assertEqual(before, fsutil.manifest_tree(root))
                observations[name] = outcome
        self.__class__.observations = observations

    def test_source_archive_tampering(self):
        import gzip
        import io
        import tarfile
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = b'print("frozen")\n'
            with tarfile.open(root/'source.tar.gz', 'w:gz') as archive:
                info = tarfile.TarInfo('verislop/a.py')
                info.size = len(source)
                archive.addfile(info, io.BytesIO(source))
            hashes = {'verislop/a.py':c.digest(source)}
            archive_hash = c.digest_file(root/'source.tar.gz')
            protocol = {'source_hashes':hashes, 'source_root':c.digest_json(hashes),
                        'run_inputs':{'source.tar.gz':archive_hash},
                        'source_archive':{'path':'source.tar.gz','sha256':archive_hash,'members':1}}
            (root/'protocol.json').write_bytes(c.dumps(protocol))
            (root/'FREEZE_BEFORE_INFERENCE.json').write_bytes(c.dumps(
                {'protocol_sha256':c.digest_file(root/'protocol.json')}))
            self.assertEqual('CONSISTENT',r.audit(root)['historical_records']['source_binding']['status'])
            with (root/'source.tar.gz').open('ab') as stream:
                stream.write(b'tamper')
            self.assertIsNone(r.audit(root)['historical_records']['source_binding'])

    def test_missing_history(self):
        with tempfile.TemporaryDirectory() as temp:
            outcome = r.audit(Path(temp)/'absent')
            self.assertEqual('INCOMPLETE', outcome['status'])
            self.assertFalse(outcome['independent_reexecution'])

    def test_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('../escape', '/tmp/escape'):
                with self.assertRaises(Exception):
                    r.inside(root, name)
            (root/'link').symlink_to('/tmp')
            with self.assertRaises(ValueError):
                r.inside(root, 'link/x')

    def test_tampered_receipt(self):
        cases = c.load_file(r.old.PROTOCOL/'withheld'/f'{r.TASK}.json')['cases']
        with tempfile.TemporaryDirectory() as temp:
            pkg = Path(temp)
            rows = [{**x, 'passed':True, 'observations':[
                {'passed':True, 'response':{'op':'result','id':i+1,'value':x['expected_wire']}} for _ in range(2)]}
                for i,x in enumerate(cases)]
            receipt = {'format':'verislop.data-pipeline-request-oracle/0.1',
                'native_gate_passed':True, 'input_bytes_unchanged':True, 'diagnostics':[],
                'isolation':[{'network_namespace':True, 'filesystem_read_isolation':True,
                              'filesystem_write_isolation':True} for _ in range(2)], 'cases':rows, 'distinct_cases':160, 'repeats':2,'passed_cases':160,
                'failed_cases':0,'incomplete_cases':0,'observations':320,'passed_observations':320,
                'observations_hash':c.digest_json(rows),'task':r.TASK,'status':'VERIFIED',
                'preregistration_root':r.old.check_preregistration()['root'],
                'package_root':fsutil.manifest_root(fsutil.manifest_tree(pkg))}
            self.assertEqual('CONSISTENT',r.receipt_check(receipt,pkg)['status'])
            rows[0]['observations'][0]['response']['value'] = {'int':'0'}
            receipt['observations_hash'] = c.digest_json(rows)
            with self.assertRaises(ValueError):
                r.receipt_check(receipt,pkg)

if __name__=='__main__':
    unittest.main()
