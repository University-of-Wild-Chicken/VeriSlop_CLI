from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from copy import deepcopy
import json
from verislop import canonical, fsutil, review, review_counterexamples as replay, schemas
from verislop.bridges.manifest import InvalidPackage
Z = "sha256:" + "0" * 64
H = "sha256:" + "1" * 64
C = "CLOSURE:provenance"
results = []
def record(name, fn):
    fn()
    results.append({"name": name, "status": "PASS"})
with TemporaryDirectory(prefix="reuse-observation-pure-") as tmp:
    base = Path(tmp)
    fsutil.write_json(base / "closure/manifest.json", {"unrelated_fixture": True})
    pkg = SimpleNamespace(path=lambda name: base / name, rel=lambda path: str(Path(path).relative_to(base)))
    frozen = [{"path": "request/source-policy.json", "sha256": Z}]
    def fixture(attempt, evidence_digit, artifact_hash):
        path = "closure/executions/" + attempt + "/mechanical-result.json"
        eid = "ev-" + evidence_digit * 32
        artifacts = [{"path": "evidence/" + eid + ".json", "sha256": artifact_hash},
                     {"path": "raw/provenance.json", "sha256": artifact_hash}]
        snapshot = {"mechanical_result_path": path, "claims": [{"claim_id": C, "evidence_refs": ["evidence:" + eid]}]}
        projected = {"raw_inventory": {"mechanical_result_hash": artifact_hash, "execution_artifacts": artifacts,
                     "frozen_artifacts": frozen}, "projection": {"claims": [{"claim_id": C,
                     "result_format": "verislop.closure.result-adapter/0.1", "envelope": {"semantic": {"predicate": True}}}]},
                     "projection_hash": Z, "normalizer_registry_hash": H}
        binds = {"request/source-policy.json": Z,
                 "closure/manifest.json": canonical.digest_file(base / "closure/manifest.json"),
                 "binding:roots": canonical.digest_json({"contract_root": Z}),
                 "closure/current.json": canonical.digest_json({"mechanical_result": path}), path: artifact_hash}
        binds.update({str(Path(path).parent / a["path"]): a["sha256"] for a in artifacts})
        proposal = {"kind": "mechanical_failure", "claim_id": C}
        receipt = {"schema_version": "0.2", "format": replay.RECEIPT_FORMAT, "status": "NOT_REPRODUCED",
                   "proposal": proposal, "proposal_hash": canonical.digest_json(proposal), "checkpoint": "release",
                   "checker": {"id": replay.VERIFIER, "sha256": Z}, "input_bindings": binds,
                   "claim": {"claim_id": C, "result_predicate": "complete-provenance/0.1"},
                   "expected": {"root_kind": "closure_root", "root": Z, "outcome": "PASS"},
                   "observed": {"outcome": "PASS", "reason": "registered closure execution", "evidence_id": eid},
                   "diagnostics": []}
        assert schemas.validate("review-counterexample-receipt", receipt) == []
        return receipt, snapshot, projected
    old, old_snapshot, old_projected = fixture("old", "a", Z)
    new, new_snapshot, new_projected = fixture("new", "b", H)
    with patch.object(replay, "bound_roots", return_value={"contract_root": Z}):
        def obs(receipt, snapshot=old_snapshot, projected=old_projected):
            return review._mechanical_receipt_observation(pkg, receipt, snapshot, projected)
        def equivalent():
            assert obs(old) == obs(new, new_snapshot, new_projected)
        record("authenticated-invocation-path-hash-and-evidence-id-differences-normalize", equivalent)
        bad_bindings = {
            "omitted-frozen-binding": lambda r: r["input_bindings"].pop("request/source-policy.json"),
            "omitted-result-binding": lambda r: r["input_bindings"].pop(old_snapshot["mechanical_result_path"]),
            "omitted-pointer-binding": lambda r: r["input_bindings"].pop("closure/current.json"),
            "omitted-execution-artifact": lambda r: r["input_bindings"].pop("closure/executions/old/raw/provenance.json"),
            "extra-package-binding": lambda r: r["input_bindings"].update({"package.json": Z}),
            "extra-execution-prefix-binding": lambda r: r["input_bindings"].update({"closure/executions/old/unlisted.json": Z}),
            "wrong-historical-pointer-digest": lambda r: r["input_bindings"].update({"closure/current.json": new["input_bindings"]["closure/current.json"]}),
            "wrong-result-digest": lambda r: r["input_bindings"].update({old_snapshot["mechanical_result_path"]: H}),
            "wrong-execution-artifact-digest": lambda r: r["input_bindings"].update({"closure/executions/old/raw/provenance.json": H}),
            "wrong-frozen-artifact-digest": lambda r: r["input_bindings"].update({"request/source-policy.json": H}),
            "wrong-selected-evidence-id": lambda r: r["observed"].update(evidence_id="ev-" + "c" * 32),
            "unknown-observed-field": lambda r: r["observed"].update(invocation_id="unlisted"),
        }
        for name, mutate in bad_bindings.items():
            def rejected(mutate=mutate):
                r = deepcopy(old)
                mutate(r)
                try: obs(r)
                except InvalidPackage: return
                raise AssertionError("mutation was normalized")
            record(name, rejected)
        preserve = {
            "observed-reason-preserved": lambda r: r["observed"].update(reason="changed semantic reason"),
            "observed-outcome-preserved": lambda r: r["observed"].update(outcome="FAIL"),
            "receipt-status-preserved": lambda r: r.update(status="CONFIRMED"),
            "diagnostics-preserved": lambda r: r.update(diagnostics=["unresolved"]),
            "expected-scoped-root-preserved": lambda r: r["expected"].update(root=H),
            "claim-predicate-preserved": lambda r: r["claim"].update(result_predicate="different/0.1"),
            "checker-identity-preserved": lambda r: r["checker"].update(sha256=H),
        }
        for name, mutate in preserve.items():
            def distinct(mutate=mutate):
                r = deepcopy(old)
                mutate(r)
                assert obs(r) != obs(old)
            record(name, distinct)
        def changed_envelope():
            projected = deepcopy(old_projected)
            projected["projection"]["claims"][0]["envelope"]["semantic"]["predicate"] = False
            assert obs(old, projected=projected) != obs(old)
        record("normalized-semantic-envelope-identity-preserved", changed_envelope)
        def changed_registry():
            projected = deepcopy(old_projected)
            projected["normalizer_registry_hash"] = Z
            assert obs(old, projected=projected) != obs(old)
        record("normalizer-registry-identity-preserved", changed_registry)
    for checkpoint, proposal in [("formal_contract", {"kind": "mechanical_failure", "claim_id": C}),
                                 ("release", {"kind": "target_case", "obligation_id": "O1", "assignment": []})]:
        def guard(checkpoint=checkpoint, proposal=proposal):
            result = replay.replay(pkg, checkpoint, proposal, _mechanical_result_path=old_snapshot["mechanical_result_path"])
            assert result["status"] == "UNSUPPORTED"
            assert result["diagnostics"] == ["historical execution selection applies only to a release mechanical probe"]
            assert result["input_bindings"] == {}
        record("historical-selection-guard-" + checkpoint + "-" + proposal["kind"], guard)
print(json.dumps({"format": "pure-closed-observation-witness/0.1", "results": results, "total": len(results),
    "limit": "Contrived internal observation inputs; this isolates projection and dispatch guards, does not authenticate a mechanical execution or claim task success."}, sort_keys=True, indent=2))
