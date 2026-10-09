"""Replay the immutable independent schema-depth witnesses; no cohort inputs."""
import importlib.util
from pathlib import Path
import sys
import time

from verislop import canonical, fsutil

ROOT = Path(__file__).resolve().parent
AUDIT = ROOT.parent / "tier2-schema-memoization-audit/attempt-6edm_4rh"
MODULES = {}
PATHS = {"baseline": AUDIT / "original-validator.py",
         "blocked_wrapper": ROOT / "blocked-wrapper-validator.py",
         "inline": ROOT / "inline-validator.py"}
for name, path in PATHS.items():
    spec = importlib.util.spec_from_file_location("schema_depth_replay_" + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    MODULES[name] = module

rows = []
for schema_name, input_name in (("recursive-array-schema.json", "array-depth-240.json"),
                               ("recursive-array-schema.json", "array-depth-250.json"),
                               ("vscore-v3-schema.json", "type-depth-100.json"),
                               ("vscore-v3-schema.json", "type-depth-125.json")):
    schema = canonical.load_file(AUDIT / schema_name)
    value = canonical.load_file(AUDIT / input_name)
    row = {"schema": schema_name, "input": input_name,
           "schema_sha256": canonical.digest_file(AUDIT / schema_name),
           "input_sha256": canonical.digest_file(AUDIT / input_name)}
    for name, module in MODULES.items():
        registry = module.Registry()
        registry.add(schema)
        started = time.process_time_ns()
        try:
            result = {"issues": [{"path": issue.path, "message": issue.message}
                                 for issue in registry.validate(value, schema["$id"])]}
        except Exception as exc:
            result = {"exception": type(exc).__name__, "message": str(exc)}
        result["cpu_ns"] = time.process_time_ns() - started
        if hasattr(registry, "_validation_cache"):
            result["cache_reset_after_call"] = registry._validation_cache.get() is None
        row[name] = result
    row["inline_matches_baseline"] = row["inline"].get("issues") == row["baseline"].get("issues")
    rows.append(row)

receipt = {"format": "verislop.inline-schema-depth-replay/0.1",
           "scope": "Exact independent generic structural-schema witnesses only; no source admission, model or lifecycle authority.",
           "python": sys.version, "recursion_limit": sys.getrecursionlimit(),
           "original_audit_path": str(AUDIT / "audit.json"),
           "original_audit_sha256": canonical.digest_file(AUDIT / "audit.json"),
           "validators": {name: {"path": str(path), "sha256": canonical.digest_file(path)} for name, path in PATHS.items()},
           "observations": rows,
           "all_inline_witnesses_match_baseline": all(row["inline_matches_baseline"] for row in rows),
           "production_or_frozen_artifacts_modified_by_replay": False}
fsutil.write_json(ROOT / "exact-witness-replay.json", receipt, once=True)
print(canonical.dumps(receipt).decode())
