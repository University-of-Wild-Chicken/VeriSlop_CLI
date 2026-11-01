"""Opt-in distribution test: VERISLOP_TEST_DISTRIBUTION=1.

Builds with setuptools/wheel and installs offline into a temporary environment.
It does not run a model, Lean, or a generated implementation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import venv
import zipfile


REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get("VERISLOP_TEST_DISTRIBUTION") == "1",
                     "set VERISLOP_TEST_DISTRIBUTION=1 to build and install distributions")
class DistributionTests(unittest.TestCase):
    def test_sdist_wheel_install_contains_exact_runtime_resources(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

        def run(argv, cwd, *, payload=None):
            result = subprocess.run(argv, cwd=cwd, env=env, input=payload,
                                    text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout[-12000:])
            return result.stdout

        with tempfile.TemporaryDirectory(prefix="verislop-distribution-") as temp:
            root = Path(temp)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            run([sys.executable, "-c", "from setuptools.build_meta import build_sdist; "
                 "import sys; build_sdist(sys.argv[1])", str(artifacts)], REPO)
            sdist, = artifacts.glob("*.tar.gz")
            source = root / "source"
            source.mkdir()
            with tarfile.open(sdist) as archive:
                members = archive.getmembers()
                for member in members:
                    self.assertTrue((source / member.name).resolve().is_relative_to(source))
                    self.assertFalse(member.issym() or member.islnk())
                    self.assertNotIn(".verislop", Path(member.name).parts)
                    self.assertNotIn("validation", Path(member.name).parts)
                archive.extractall(source)
            unpacked, = source.iterdir()
            run([sys.executable, "-c", "from setuptools.build_meta import build_wheel; "
                 "import sys; build_wheel(sys.argv[1])", str(artifacts)], unpacked)
            wheel, = artifacts.glob("*.whl")

            expected = {}
            for path in (REPO / "schemas").glob("*.schema.json"):
                expected["schemas/" + path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            for relative in ("request.txt", "draft.json", "interpretation.json",
                             "formalization/Contract.lean", "formalization/formalization.json",
                             "python/bounded_increment.py", "python/bindings.json"):
                expected["examples/" + relative] = hashlib.sha256(
                    (REPO / "examples" / relative).read_bytes()).hexdigest()
            for path in (REPO / "verislop/web_assets").iterdir():
                if path.is_file():
                    expected["web_assets/" + path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            with zipfile.ZipFile(wheel) as archive:
                for relative, digest in expected.items():
                    self.assertEqual(hashlib.sha256(archive.read("verislop/" + relative)).hexdigest(), digest)
                self.assertFalse(any(".verislop/" in name or "/validation/" in name
                                     or "__pycache__/" in name for name in archive.namelist()))

            installed = root / "venv"
            venv.EnvBuilder(with_pip=True).create(installed)
            scripts = installed / ("Scripts" if os.name == "nt" else "bin")
            python = scripts / ("python.exe" if os.name == "nt" else "python")
            run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)], root)
            workspace = root / "workspace"
            workspace.mkdir()
            executable = scripts / ("verislop-ui.exe" if os.name == "nt" else "verislop-ui")
            self.assertIn("--workspace", run([str(executable), "--help"], workspace))
            self.assertIn("--port", run([str(python), "-I", "-m", "verislop", "ui", "--help"], workspace))
            result = run([str(python), "-I", "-c", INSTALLED_CHECK], workspace,
                         payload=json.dumps(expected))
            self.assertIn("installed resources and example launch paths passed", result)


INSTALLED_CHECK = r'''
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import verislop
from verislop import schemas, web

package = Path(verislop.__file__).resolve().parent
assert package.is_relative_to(Path(sys.prefix)), package
for relative, digest in json.load(sys.stdin).items():
    assert hashlib.sha256((package / relative).read_bytes()).hexdigest() == digest, relative
assert schemas.schema_dir() == package / "schemas"
assert not schemas.validate("draft", json.loads((package / "examples/draft.json").read_text()))
app = web.Workbench(Path.cwd())
try:
    assert app.meta()["example_prompt"] == (package / "examples/request.txt").read_text()
    with patch.object(web.subprocess, "Popen", side_effect=RuntimeError("captured-only")) as spawn:
        try:
            app.launch({"mode": "example", "tier": 0})
        except RuntimeError as error:
            assert str(error) == "captured-only", error
        else:
            raise AssertionError("example launch did not reach process boundary")
    command = spawn.call_args.args[0]
    for flag in ("--prompt-file", "--draft-candidate", "--ledger-candidate",
                 "--formalization-candidate", "--implementation-candidate"):
        path = Path(command[command.index(flag) + 1])
        assert path.is_relative_to(package / "examples"), (flag, path)
        assert path.exists(), (flag, path)
finally:
    app.close()
print("installed resources and example launch paths passed")
'''


if __name__ == "__main__":
    unittest.main()
