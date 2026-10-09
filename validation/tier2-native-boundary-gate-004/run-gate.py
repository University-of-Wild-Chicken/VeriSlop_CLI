"""Retain a fresh engineering gate and exact failed fixture inputs."""
from pathlib import Path
import shutil
import sys
import time
import traceback
import unittest

from tests import test_vscore3_source_pipeline as fixture
from verislop import canonical, fsutil
from synthetic_dataset.tools import bootstrap_tier2

repo = Path(__file__).resolve().parents[2]
output = Path(__file__).resolve().parent
original_setup = fixture.RegisteredVSCore3SourcePipelineTests.setUpClass

@classmethod
def retained_setup(cls):
    try:
        return original_setup()
    except BaseException as exc:
        original = getattr(cls, "root", None)
        if original is not None and original.exists():
            destination = output / "failed-fixtures" / original.name
            shutil.copytree(original, destination / "attempt", symlinks=True)
            fsutil.atomic_write(destination / "failure.txt", traceback.format_exc().encode())
            inventory = bootstrap_tier2.source_inventory(repo)
            for rel in inventory:
                fsutil.atomic_write(destination / "source-snapshot" / rel, (repo / rel).read_bytes())
            fsutil.write_json(destination / "capture.json", {
                "format": "verislop.tier2-engineering-failed-fixture/0.1",
                "captured_before_temp_cleanup": True, "error": str(exc),
                "source_root": canonical.digest_json(inventory), "source_files": inventory,
                "verification_success": False})
            print("FAILED_FIXTURE_CAPTURE", destination, flush=True)
        raise

fixture.RegisteredVSCore3SourcePipelineTests.setUpClass = retained_setup
modules = sys.argv[1:]
if not modules:
    raise ValueError("Explicit gate test modules are required")
test_sources = {name: canonical.digest_file(repo / (name.replace(".", "/") + ".py"))
                for name in modules}
before = bootstrap_tier2.source_inventory(repo)
suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
start = time.monotonic()
result = unittest.TextTestRunner(verbosity=2).run(suite)
after = bootstrap_tier2.source_inventory(repo)
stable = before == after
receipt = {"format": "verislop.tier2-native-boundary-gate/0.1",
           "status": "PASS" if result.wasSuccessful() and stable else "BLOCKED",
           "test_modules": modules, "test_sources": test_sources, "tests_run": result.testsRun,
           "source_root_before": canonical.digest_json(before),
           "source_root_after": canonical.digest_json(after), "source_unchanged": stable,
           "duration_seconds": format(time.monotonic() - start, ".6f"),
           "errors": [{"test": str(test), "traceback": error} for test, error in result.errors],
           "failures": [{"test": str(test), "traceback": error} for test, error in result.failures],
           "fresh_model_calls": 0, "scope": "engineering fixtures; no retained task solution transfer"}
bootstrap_tier2.write_once(output / "run-result.json", receipt)
raise SystemExit(0 if receipt["status"] == "PASS" else 1)
