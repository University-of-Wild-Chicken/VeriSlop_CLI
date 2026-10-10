# Independent carrier003 source review (before checks)

{
  "affected_claims": [
    "Q019-04",
    "Q019-05",
    "Q019-06",
    "Q019-07",
    "Q019-08",
    "Q019-09"
  ],
  "baseline_sha256": "9930beff878848b05c8d69245fff12c1388f14254b6630504b36748c4c294366",
  "baseline_source": "synthetic_dataset/tools/bootstrap_tier2_carrier_view.py",
  "candidate": "validation/tier2-carrier-context-support-019-implementation-003",
  "excluded": [
    "model/Lean/qualification/target task calls",
    "hidden fixture expected answers",
    "task proofs/candidates/positive outcomes",
    "production installation",
    "Q003 runtime result"
  ],
  "format": "verislop.carrier003-source-review-specification/1",
  "invariants": [
    "legacy APIs/emit_view reader exact",
    "one VIEW fully forwarded then own pending only",
    "explicit intact-outer CONFIRM before cursor commit",
    "closed selectors/cursors",
    "contiguous/replay/system-first/empty EOF/Unicode scalar/UTF8",
    "own-key isolation",
    "zero-tool/hash only reconstructed complete own fields",
    "no helper/oracle/eval/automatic VIEW loop",
    "availability only and UNATTESTED authority"
  ],
  "mode": "READ_ONLY_STATIC_AND_ISOLATED_GENERIC_SOURCE",
  "novel_evidence": "independent source preservation/protocol checks and isolated unrelated JSON/Unicode/hash counterexamples",
  "possible_state_transition": "declared availability prerequisite PASS to BLOCK",
  "runtime_authority": false,
  "stop_after_bounded_review": true
}
