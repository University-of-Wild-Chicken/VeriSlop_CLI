#!/usr/bin/env python3
"""Registered read-only retained route; never executed during preparation.

Only an existing root-authorized retained-removal claim may supply this route's
actual process receipts. It creates no carrier, removes no original root and
performs no model call, rebuild, repair, or fixed public-probe campaign.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).absolute().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("validation", "second-probe"), required=True)
    parser.add_argument("--pre-route-authorization", required=True)
    parser.add_argument("--pre-route-authorization-sha256", required=True)
    parser.add_argument("--retained-root", required=True)
    parser.add_argument("--original-root", required=True)
    parser.add_argument("--closure-root", required=True)
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--output-file", required=True)
    args = parser.parse_args()
    started = datetime.now(timezone.utc).isoformat()
    sys.dont_write_bytecode = True
    module_spec = importlib.util.spec_from_file_location("scope018_retained_reader006", HERE / "terminal-scope-reader-006.py")
    reader = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(reader)
    original = reader.strict_path(args.original_root)
    retained = reader.strict_path(args.retained_root)
    reader.need(not original.exists() and original != retained and not retained.is_relative_to(original),
                "STALE_OR_UNBOUND_EVIDENCE", "original root is present before any retained read")
    reader.need(retained.is_relative_to(reader.COHORT) and Path.cwd() == reader.PROJECT,
                "VERIFIER_MISMATCH", "exact retained root/cwd differs")
    reads = reader.Reads()
    binding = reads.obj(args.pre_route_authorization, args.pre_route_authorization_sha256,
                        "immutable pre-route authorization: closed frozen inputs, no final/output references")
    pre_ref = {"path":str(reader.strict_path(args.pre_route_authorization)),
               "sha256":"sha256:"+reader.plain_hash(args.pre_route_authorization_sha256)}
    reader.need(reader.utc(binding["authorized_at_utc"]) <= reader.utc(started),
                "STALE_OR_UNBOUND_EVIDENCE", "route started before pre-route authorization")
    registered = binding["registered_files"]
    reader.need(set(registered) == {"terminal-scope-reader-006.py", reader.SPEC_NAME, reader.REG_NAME, reader.ROUTE_NAME},
                "VERIFIER_MISMATCH", "exact registered retained route membership differs")
    for name, digest in registered.items():
        reads.raw(HERE / name, digest, "exact registered post-stop retained route/input")
    registration = reads.obj(HERE / reader.REG_NAME)
    reader.need(reader.plain_hash(registration["retained_route_sha256"]) == reader.plain_hash(registered[reader.ROUTE_NAME]) and
                reader.plain_hash(registration["verifier_sha256"]) == reader.plain_hash(registered["terminal-scope-reader-006.py"]) and
                reader.plain_hash(registration["specification_sha256"]) == reader.plain_hash(registered[reader.SPEC_NAME]),
                "VERIFIER_MISMATCH", "retained route/reader/specification registration differs")
    reader.install_binding_schemas(
        reads.obj(HERE/reader.FINAL_SCHEMA_NAME,registration["binding_schema_sha256"],"registered final binding schema"),
        reads.obj(HERE/reader.PRE_SCHEMA_NAME,registration["pre_route_schema_sha256"],"registered closed frozen-input authorization schema"))
    reader.qualification_definition(reads.obj(HERE/reader.SPEC_NAME))
    reader.validate_pre_route(binding)
    output = reader.strict_path(args.output_file)
    reader.need(output.is_relative_to(HERE) and not output.exists() and output.parent.is_dir(),
                "INPUT_MUTATION", "retained result must be new audit-directory output")
    audit = reader.Audit(reads, binding, output.parent)
    audit.pre_route_ref = pre_ref
    audit.stop_and_seal()
    # This revalidates the exact frozen qualified source/public plan. All task
    # reads above already passed explicit stopped-actor/sealed-root admission.
    audit.preparation()
    from verislop.package import Package
    from verislop.backends import vscore3, vscore3_closure
    from verislop.bridges import vscore3_checker
    from verislop import review_counterexamples, verifiers, schemas
    pkg = Package(retained, resolve_root=False)
    selection = vscore3.selection(pkg)
    reader.need(selection["bridge_id"] == "implementation" and selection["edge_claim_id"] == args.claim_id,
                "UNRESOLVED_REQUIRED_CLAIM", "retained route must name exact selected implementation edge")
    accepted, pending, diagnostics = vscore3_checker.verify_published(pkg, "implementation", rebuild=False)
    reader.need(bool(accepted) and pending == [] and diagnostics == [],
                "STALE_OR_UNBOUND_EVIDENCE", "registered retained publication admission failed")
    snapshot = vscore3_closure.mechanical_snapshot(pkg)
    reader.need(snapshot is not None and snapshot["closure_root"] == args.closure_root and
                snapshot["mechanical_status"] == "VERIFIED", "STALE_OR_UNBOUND_EVIDENCE", "retained current snapshot differs")
    claims = vscore3_closure._claims(pkg)
    native_claim = next((c for c in claims if c["claim_id"] == args.claim_id), None)
    reader.need(native_claim is not None and native_claim["required"] and native_claim["applicable"] and
                any(row["claim_id"] == args.claim_id and row["outcome"] == "PASS" for row in snapshot["claims"]),
                "UNRESOLVED_REQUIRED_CLAIM", "required retained mechanical claim is absent/unresolved")
    roots = vscore3_closure._roots(pkg, selection, snapshot["closure_root"])
    checker = {"id":review_counterexamples.VERIFIER,"sha256":verifiers.verifier_hash(review_counterexamples.VERIFIER)}
    probe = None
    if args.mode == "second-probe":
        # Exact qualification retained-route API/default budget; no new input,
        # fixed public probe, timeout override or authored verdict is admitted.
        probe = review_counterexamples.replay(pkg, "release", {"kind":"mechanical_failure", "claim_id":args.claim_id})
        reader.need(not schemas.validate("review-counterexample-receipt", probe) and
                    probe["status"] == "NOT_REPRODUCED" and probe["checker"] == checker and
                    probe["expected"]["outcome"] == probe["observed"]["outcome"] == "PASS" and
                    probe["expected"]["root"] == roots[native_claim["root_kind"]] and
                    bool(probe["input_bindings"]), "UNRESOLVED_REQUIRED_CLAIM", "registered retained second probe did not pass")
    reader.need(not original.exists(), "INPUT_MUTATION", "original root reappeared during retained validation")
    complete = reads.finalize()
    result = {"format":"verislop.stage018-retained-route-result/6", "mode":args.mode, "status":"PASS",
              "source_root":reader.SOURCE_ROOT, "closure_root":snapshot["closure_root"],
              "retained_root":str(retained), "original_root":str(original), "original_root_absent_before_reads":True,
              "claim_id":args.claim_id, "native_claim":native_claim, "mechanical_snapshot":snapshot,
              "accepted":accepted, "roots":roots, "checker":checker, "probe":probe,
              "registered_route":{"id":"D21-SCOPE-RETAINED-018-006", "sha256":"sha256:"+reader.plain_hash(registered[reader.ROUTE_NAME])},
              "pre_route_authorization":pre_ref,"terminal_nonce":binding["terminal_nonce"],
              "registered_internal_probe_timeout_seconds":5.0, "outer_timeout_seconds":None,
              "started_at_utc":started, "ended_at_utc":datetime.now(timezone.utc).isoformat(),
              "bound_inputs":complete, "task_models":0, "task_repairs":0, "new_builds":0,
              "root_removal_trust":"original root is actually absent before any retained read; independent caller captures completed exact registered process"}
    digest = reader.publish(output, result)
    print(reader.json.dumps({"status":"PASS","result":str(output),"sha256":digest},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
