# Qwen and Luna: raw generation versus strict VeriSlop

**Partial snapshot; no final benchmark conclusion is claimed.**

Corpus: 100 tasks; common completed pairs across models: 18. Audit: 2026-10-08T07:31:38.720426+00:00.

Metrics below use only the common completed task pairs. All recorded arm metrics and exact observations are in `comparison.json`.

## qwen-local-003

Recorded 42/100 complete pairs; final valid manifest: False.

- **Raw coding:** 15/18 successful tasks; 154/167 hidden cases; 32/36 public cases; 18 artifacts; 18 calls; 274.850 generation seconds.
- **Full strict CLI:** 0/18 successful tasks; 0/167 hidden cases; 0/36 public cases; 0 artifacts; 134 calls; 7961.763 generation seconds.

Calls with unavailable token usage on these pairs: raw=0; verislop=5. Native token totals include only known usage; simulation token totals remain null.

All recorded within-model paired outcomes: both_success=0; raw_only=34; verislop_only=0; neither_success=8.

Pipeline stages passing on recorded tasks: {"accept": 4, "export": 4, "formalize": 4, "interpret": 37, "prove": 4}.

Primary failure codes (tasks): {"CANDIDATE_BUILD_FAILURE": 20, "INVALID_CANDIDATE": 1, "MISSING_WITNESS": 2, "PROVIDER_FAILURE": 12, "REVIEW_INCOMPLETE": 3, "UNSUPPORTED_SEMANTICS": 6}. Terminal stages: {"formalize": 33, "interpret": 5, "review:formal_contract": 4}.

All recorded diagnostic counts, including downstream closure effects: {"CANDIDATE_BUILD_FAILURE": 20, "INVALID_CANDIDATE": 1, "MISSING_WITNESS": 2, "ORPHAN_CLAIM": 168, "PROVIDER_FAILURE": 12, "REVIEW_INCOMPLETE": 7, "REVIEW_NOT_RUN": 80, "UNCOVERED_SOURCE_CLAUSE": 1, "UNSUPPORTED_SEMANTICS": 8, "VERIFIER_NOT_RUN": 84}.

Concrete recorded counterexamples:

- `G03/raw` case `G03-public-1`: input `{"edges": [[0, 1, 2], [1, 2, -3], [2, 1, 1], [2, 3, 4], [4, 4, -1]], "n": 5, "source": 0}`; expected `[0, "-inf", "-inf", "-inf", null]`; observed `["-inf", "-inf", "-inf", -5, null]`.
- `G03/raw` case `G03-hidden-1`: input `{"edges": [[0, 1, 0], [1, 1, -1], [1, 2, 0], [3, 3, -1]], "n": 4, "source": 0}`; expected `[0, "-inf", "-inf", null]`; observed `["-inf", "-inf", -4, null]`.
- `G03/raw` case `G03-hidden-4`: input `{"edges": [[0, 0, -1], [0, 1, 3], [3, 3, -5], [2, 0, -5]], "n": 4, "source": 2}`; expected `["-inf", "-inf", 0, null]`; observed `["-inf", -5, "-inf", null]`.

## luna-agents-002

Recorded 18/100 complete pairs; final valid manifest: False.

- **Raw coding:** 17/18 successful tasks; 162/167 hidden cases; 35/36 public cases; 18 artifacts; 18 calls; 1186.830 generation seconds.
- **Full strict CLI:** 0/18 successful tasks; 0/167 hidden cases; 0/36 public cases; 0 artifacts; 119 calls; 17556.916 generation seconds.

Calls with unavailable token usage on these pairs: raw=18; verislop=119. Native token totals include only known usage; simulation token totals remain null.

All recorded within-model paired outcomes: both_success=0; raw_only=17; verislop_only=0; neither_success=1.

Pipeline stages passing on recorded tasks: {"accept": 1, "export": 1, "formalize": 2, "interpret": 9, "prove": 1}.

Primary failure codes (tasks): {"CANDIDATE_BUILD_FAILURE": 3, "INVALID_CANDIDATE": 9, "KERNEL_REJECTION": 1, "MISSING_WITNESS": 2, "PROOF_UNRESOLVED": 1, "REVIEW_INCOMPLETE": 1, "UNCOVERED_SOURCE_CLAUSE": 1, "UNSUPPORTED_SEMANTICS": 3}. Terminal stages: {"accept": 1, "formalize": 7, "interpret": 9, "review:formal_contract": 1}.

All recorded diagnostic counts, including downstream closure effects: {"CANDIDATE_BUILD_FAILURE": 3, "INVALID_CANDIDATE": 95, "KERNEL_REJECTION": 2, "MISSING_WITNESS": 2, "ORPHAN_CLAIM": 72, "PROOF_UNRESOLVED": 13, "REVIEW_INCOMPLETE": 2, "REVIEW_NOT_RUN": 35, "UNCOVERED_SOURCE_CLAUSE": 10, "UNSUPPORTED_SEMANTICS": 3, "VERIFIER_NOT_RUN": 35}.

Concrete recorded counterexamples:

- `G13/raw` case `G13-public-1`: input `{"edges": [[0, 1], [1, 2], [0, 2], [0, 2]], "n": 3}`; expected `[[0, 1], [1, 2]]`; observed `[[0, 2]]`.
- `G13/raw` case `G13-hidden-1`: input `{"edges": [[0, 1], [1, 2], [2, 3], [0, 2], [0, 3], [1, 3]], "n": 4}`; expected `[[0, 1], [1, 2], [2, 3]]`; observed `[[0, 2], [0, 3], [1, 3]]`.
- `G13/raw` case `G13-hidden-2`: input `{"edges": [[0, 1], [0, 1], [0, 1]], "n": 2}`; expected `[[0, 1]]`; observed `[]`.

## Interpretation and audit boundary

Within each model: one raw call versus at most 32 full-CLI calls and two contract repairs; unequal prompt, compute and token budgets. Qwen uses native pinned-model service; Luna is a fresh-agent simulation with unobservable actual model snapshot, sampling, tokens and tool-policy enforcement. Concurrent host use affects timings. Stopped historical runs are excluded.

Recorded-evidence audit; no candidate reruns, oracle proof, model/hardware attestation or universal correctness claim. Tier 0 cannot establish END_TO_END_VERIFIED.

A successful raw task requires worker exit zero and every public/hidden case to pass. A successful CLI task additionally requires the returned active package, all strict stages, VERIFIED Tier 0 TESTED report and every required milestone to pass. Missing artifacts retain all failed-case denominators. Repaired package lineage is audited; failed parent artifacts cannot substitute.

The auditor checks frozen dataset/source/configuration hashes, complete final evidence inventories, exact case observations and Boolean/integer distinctions, artifact hashes/unique solve entry, actual CLI invocation/stages/report, task/arm order, call accounting, native identity/token evidence and hash-bound fresh-agent simulation receipts. It reads authoritative evidence without changing it.

[Offline viewer](viewer.html) · [Reproducible comparison JSON](comparison.json) · [Auditor](../tools/compare_runs.py).

Additional observer evidence (separate from scored task totals):

- [Separate supported-profile control](SUPPORTED_CONTROL.md)
- [Observed infrastructure failures](INFRASTRUCTURE_NOTES.md)
- [Concrete interpretation counterexample](INTERPRETATION_COUNTEREXAMPLES.md)
- [Concrete prompt/output counterexample](PROMPT_COUNTEREXAMPLES.md)
