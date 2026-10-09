"""Run the fresh generic source-facet gate and retain failed setup inputs."""
from pathlib import Path
import shutil
import time
import traceback
import unittest

from tests import test_vscore3_source_pipeline as module
from verislop import canonical, fsutil
from synthetic_dataset.tools import bootstrap_tier2

repo = Path(__file__).resolve().parents[4]
cls = module.RegisteredVSCore3SourcePipelineTests
original_setup = cls.setUpClass

@classmethod
def retained_setup(actual_cls):
    try:
        return original_setup()
    except BaseException as exc:
        original = getattr(actual_cls, "root", None)
        if original is not None and original.exists():
            destination = repo / "synthetic_dataset/bootstrap/validation/tier2-source-pipeline-failed" / original.name
            shutil.copytree(original, destination / "attempt", symlinks=True)
            fsutil.atomic_write(destination / "failure.txt", traceback.format_exc().encode())
            inventory = bootstrap_tier2.source_inventory(repo)
            for rel in inventory:
                fsutil.atomic_write(destination / "source-snapshot" / rel, (repo / rel).read_bytes())
            files = {p.relative_to(destination).as_posix(): canonical.digest_file(p)
                     for p in sorted(destination.rglob("*")) if p.is_file()}
            fsutil.write_json(destination / "capture.json", {
                "format": "verislop.tier2-source-pipeline-failure/0.1",
                "captured_before_test_temp_cleanup": True,
                "error": str(exc), "files": files, "files_root": canonical.digest_json(files),
                "source_files_sampled_after_failure": inventory,
                "source_root": canonical.digest_json(inventory),
                "does_not_claim_successful_mechanical_closure": True})
            print("SOURCE_PIPELINE_FAILURE_CAPTURE", destination, flush=True)
        raise

cls.setUpClass = retained_setup
start = time.monotonic()
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
receipt = {
    "format": "verislop.tier2-source-pipeline-test-result/0.1",
    "status": "PASS" if result.wasSuccessful() else "BLOCKED",
    "tests_run": result.testsRun,
    "duration_seconds": format(time.monotonic() - start, ".6f"),
    "errors": [{"test": str(test), "traceback": error} for test, error in result.errors],
    "failures": [{"test": str(test), "traceback": error} for test, error in result.failures]}
receipt_path = Path(__file__).with_name("run-result.json")
if receipt_path.exists():
    raise FileExistsError("refuse to overwrite run result")
fsutil.write_json(receipt_path, receipt)
raise SystemExit(0 if result.wasSuccessful() else 1)
