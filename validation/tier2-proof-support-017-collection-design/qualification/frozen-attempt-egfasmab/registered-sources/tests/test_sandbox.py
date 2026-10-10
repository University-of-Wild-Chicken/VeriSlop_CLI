"""Real Linux containment tests; fixtures contain synthetic data, never user credentials."""

from __future__ import annotations

import json
import os
import socket
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from verislop import canonical, leanbridge, sandbox
from verislop.targets.python_target import Harness, HarnessError, byte_compile


@unittest.skipUnless(sandbox.filesystem_isolation_available(), "bubblewrap/user namespaces unavailable")
class FilesystemContainment(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="verislop-isolation-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.secret = self.root / "synthetic-secret"
        self.secret.write_text("synthetic-test-data")
        self.outside = self.root / "outside-write"

    def run_python(self, source, *args, **kwargs):
        return sandbox.run(["/usr/bin/python3", "-I", "-S", "-c", source, *map(str, args)],
                           self.stage, timeout=10, **kwargs)

    def test_outside_read_write_symlink_and_parent_proc_denied(self):
        (self.stage / "escape").symlink_to(self.secret)
        script = """
import json,os,pathlib,sys
secret,outside,parent=sys.argv[1:]
checks={}
def denied(name, action):
    try: action()
    except OSError: checks[name]=True
    else: checks[name]=False
denied('read', lambda: pathlib.Path(secret).read_bytes())
denied('write', lambda: pathlib.Path(outside).write_text('changed'))
denied('overwrite', lambda: pathlib.Path(secret).write_text('changed'))
denied('symlink_read', lambda: pathlib.Path('escape').read_bytes())
denied('symlink_write', lambda: pathlib.Path('escape').write_text('changed'))
denied('proc_root', lambda: pathlib.Path('/proc/'+parent+'/root'+secret).read_bytes())
denied('proc_environ', lambda: pathlib.Path('/proc/'+parent+'/environ').read_bytes())
pathlib.Path('positive').write_text('inside')
checks['staged_read']=pathlib.Path('positive').read_text()=='inside'
print(json.dumps(checks))
"""
        result = self.run_python(script, self.secret, self.outside, os.getpid())
        self.assertEqual(result.returncode, 0, result.stderr)
        checks = json.loads(result.stdout)
        self.assertTrue(all(checks.values()), checks)
        self.assertFalse(self.outside.exists())
        self.assertEqual(self.secret.read_text(), "synthetic-test-data")
        self.assertEqual((self.stage / "positive").read_text(), "inside")
        self.assertTrue(result.isolation["filesystem_read_isolation"])
        self.assertTrue(result.isolation["filesystem_write_isolation"])
        self.assertTrue(result.isolation["private_proc"])
        self.assertEqual(result.isolation["filesystem_backend"], "bubblewrap")
        self.assertEqual(result.isolation["writable_host_paths"], ["<stage>"])

    def test_explicit_toolchain_grant_is_readonly(self):
        toolchain = self.root / "toolchain"
        toolchain.mkdir()
        (toolchain / "data").write_text("toolchain-data")
        result = self.run_python("""
import pathlib,sys
p=pathlib.Path(sys.argv[1]); assert (p/'data').read_text()=='toolchain-data'
try: (p/'data').write_text('changed')
except OSError: pass
else: raise AssertionError('toolchain writable')
print('ok')
""", toolchain, read_only_paths=[toolchain])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), b"ok")
        self.assertEqual((toolchain / "data").read_text(), "toolchain-data")

    def test_environment_and_inheritable_host_fd_are_not_exposed(self):
        fd = os.open(self.secret, os.O_RDONLY)
        os.set_inheritable(fd, True)
        self.addCleanup(os.close, fd)
        with patch.dict(os.environ, {"VERISLOP_TEST_SECRET": "synthetic-token", "LEAN_PATH": "outside"}):
            result = self.run_python("""
import os,sys
assert 'VERISLOP_TEST_SECRET' not in os.environ
assert 'LEAN_PATH' not in os.environ
assert os.environ['HOME']==os.getcwd()==os.environ['TMPDIR']
try: os.read(int(sys.argv[1]),1)
except OSError: pass
else: raise AssertionError('inherited descriptor')
print('ok')
""", fd)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_hardlinked_stage_file_is_rejected_before_launch(self):
        os.link(self.secret, self.stage / "alias")
        with self.assertRaisesRegex(RuntimeError, "hardlinked"):
            self.run_python("raise AssertionError('must not execute')")

    def test_timeout_kills_namespace_processes(self):
        started = time.monotonic()
        result = sandbox.run(["/bin/sh", "-c", "sleep 60 & wait"], self.stage, timeout=0.2)
        self.assertTrue(result.timed_out)
        self.assertLess(time.monotonic() - started, 3)

    @unittest.skipUnless(sandbox.network_isolation_available(), "network namespaces unavailable")
    def test_host_loopback_listener_is_unreachable(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            result = self.run_python("""
import socket,sys
try: socket.create_connection(('127.0.0.1',int(sys.argv[1])), timeout=.5)
except OSError: print('denied')
else: raise AssertionError('host network reachable')
""", listener.getsockname()[1], require_network_isolation=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.isolation["network_namespace"])

    def test_real_lean_build_cannot_access_outside_files(self):
        try:
            tc = leanbridge.resolve_toolchain()
        except Exception as exc:
            self.skipTest(f"pinned Lean unavailable: {exc}")
        # JSON escaping is valid for these generated ASCII path literals in Lean.
        source = f"""import Lean
run_cmd do
  let mut readDenied := false
  try
    let _ ← IO.FS.readFile {json.dumps(str(self.secret))}
  catch _ => readDenied := true
  unless readDenied do throwError "outside read allowed"
  let mut writeDenied := false
  try
    IO.FS.writeFile {json.dumps(str(self.outside))} "changed"
  catch _ => writeDenied := true
  unless writeDenied do throwError "outside write allowed"
  IO.FS.writeFile "inside.txt" "lean-stage-write"
theorem fixture : 1 + 1 = 2 := by decide
"""
        result = leanbridge.compile_module(tc, source.encode(), self.stage, timeout=60)
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(result.olean.is_file())
        self.assertEqual((self.stage / "inside.txt").read_text(), "lean-stage-write")
        self.assertFalse(self.outside.exists())
        self.assertTrue(result.isolation["filesystem_read_isolation"])


class RequiredIsolation(unittest.TestCase):
    def test_unavailable_filesystem_backend_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            with patch.object(sandbox, "filesystem_isolation_available", return_value=False):
                with self.assertRaisesRegex(RuntimeError, "filesystem isolation required"):
                    sandbox.run(["/bin/sh", "-c", "touch must-not-run"], stage, timeout=5)
            self.assertFalse((stage / "must-not-run").exists())

    def test_secret_environment_override_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "environment overrides"):
                sandbox.run(["/bin/true"], Path(tmp), timeout=5,
                            env_extra={"VERISLOP_TEST_SECRET": "synthetic-token"})


@unittest.skipUnless(sandbox.filesystem_isolation_available() and sandbox.network_isolation_available(),
                     "filesystem/network namespaces unavailable")
class StreamingHarnessContainment(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="verislop-harness-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.impl = self.root / "impl"
        self.impl.mkdir()

    def harness(self, source, **kwargs):
        target = self.impl / "target.py"
        target.write_text(source)
        return Harness(self.impl, {"target.py": canonical.digest_file(target)},
                       {"probe": ("target.py", "probe")}, **kwargs)

    def test_streaming_path_denies_escapes_and_preserves_readonly_inputs(self):
        secret = self.root / "synthetic-secret"
        secret.write_text("synthetic-test-data")
        secret.chmod(0o400)
        outside = self.root / "outside-write"
        source = f"""
import os,pathlib
def probe():
    checks=[]
    def denied(f):
        try: f()
        except OSError: checks.append(True)
        else: checks.append(False)
    secret=pathlib.Path({str(secret)!r})
    outside=pathlib.Path({str(outside)!r})
    denied(secret.read_bytes)
    denied(lambda: outside.write_text('changed'))
    link=pathlib.Path('escape'); link.symlink_to(secret)
    denied(link.read_bytes)
    denied(lambda: link.write_text('changed'))
    denied(lambda: pathlib.Path(__file__).write_text('changed'))
    denied(lambda: pathlib.Path('harness.py').write_text('changed'))
    checks.append('VERISLOP_TEST_SECRET' not in os.environ)
    pathlib.Path('scratch').write_text('inside')
    checks.append(pathlib.Path('scratch').read_text()=='inside')
    return all(checks)
"""
        with patch.dict(os.environ, {"VERISLOP_TEST_SECRET": "synthetic-token"}):
            harness = self.harness(source)
        try:
            result = harness.call("probe", [])
            self.assertEqual(result.get("value"), {"bool": True}, result)
            self.assertTrue(harness.isolation["filesystem_read_isolation"])
            self.assertIn("<stage>/artifact", harness.isolation["read_only_paths"])
        finally:
            harness.close()
        self.assertFalse(outside.exists())
        self.assertEqual(secret.read_text(), "synthetic-test-data")
        self.assertEqual(stat.S_IMODE(secret.stat().st_mode), 0o400, "cleanup followed malicious symlink")
        self.assertEqual((self.impl / "target.py").read_text(), source)

    def test_partial_response_cannot_bypass_call_timeout(self):
        harness = self.harness("import os,time\ndef probe():\n os.write(1,b'{')\n time.sleep(60)\n", per_call_timeout=0.2)
        try:
            started = time.monotonic()
            with self.assertRaises(HarnessError) as caught:
                harness.call("probe", [])
            self.assertEqual(caught.exception.kind, "timeout")
            self.assertLess(time.monotonic() - started, 2)
        finally:
            harness.close()

    def test_harness_and_byte_compile_fail_closed_without_backend(self):
        with patch.object(sandbox, "filesystem_isolation_available", return_value=False):
            with self.assertRaises(HarnessError) as caught:
                self.harness("def probe():\n return True\n")
            self.assertEqual(caught.exception.kind, "isolation")
            with self.assertRaisesRegex(RuntimeError, "filesystem isolation required"):
                byte_compile(self.impl, ["target.py"], self.root / "compile")

    def test_byte_compile_uses_same_filesystem_backend(self):
        (self.impl / "target.py").write_text("def probe():\n return 1\n")
        result = byte_compile(self.impl, ["target.py"], self.root / "compile")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["isolation"]["filesystem_read_isolation"])
        self.assertIn("target.pyc", result["pyc"])


if __name__ == "__main__":
    unittest.main()
