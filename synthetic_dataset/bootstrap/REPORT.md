# Specification-first strict CLI coverage bootstrap

This is a sequence of single-instance engineering gates, not a 100-task benchmark.
The stopped full-corpus run remains unchanged. Every gate uses an original corpus
prompt through the full native Tier 0 CLI and a separately frozen source snapshot.
The original 100-task corpus root is unchanged:
`sha256:00e1b28846431c379cf8460d57d84897c5d0575ce49fa1481d7fb1ebc000c04e`.

## Specifications and generic coverage

The ordered protocol is [coverage-bootstrap.md](../../docs/coverage-bootstrap.md).
Detailed specifications preceded code:
[agent protocol/context](../../docs/bootstrap-agent-repair.md),
[contract primitives](../../docs/bootstrap-contract-coverage.md), and
[finite execution](../../docs/bootstrap-test-execution.md), and
[exhaustive finite campaigns](../../docs/bootstrap-finite-campaigns.md), and
[clause citations](../../docs/bootstrap-clause-citations.md), and
[quantifier readiness](../../docs/bootstrap-quantifier-readiness.md).

The language now covers unambiguous nullable values, conditional branches, exact
signed floor division, Int/Nat conversion, bounded input-dependent ranges, total
list indexing, ascending stable scalar sorting, first-occurrence deduplication,
and Unicode scalar ordering. Compiler emission, accepted Lean AST reconstruction,
independent denotation checking, host evaluation, serialization, generators,
shrinking, non-vacuity witnesses and concrete counterexample replay were extended
together. Third-party imports and arbitrary higher-order/comparator semantics were
not added. Fixed semantics remain checked against the pinned Lean kernel.

New native campaigns preflight each accepted reference in a fresh finite budget,
then execute the original formula against the linked target with a separate budget.
Preflight reads hash-bound accepted definition ASTs; it never supplies PASS.
Budget skips remain indeterminate and visible. Target calls bypass result caching
in new campaigns. Failed channels terminate immediately, reject mismatched request
IDs, and cannot produce stale-response counterexamples. Historical configurations
without the new opt-in preserve their original case-evaluation behavior.

## Retained gates

- `protocol-001`, original D21: 11 fresh responses; terminal formalization BLOCKED,
  with a retained capability report and no implementation or TESTED claim.
  Exact source/origin and all 605 sealed evidence files independently checked.
- `nullable-002`, original D21: 8 fresh responses; interpretation passed,
  formalization BLOCKED on sequence/ordering gaps; no TESTED claim.
  Exact source/origin and all 578 sealed evidence files independently checked.
- `arithmetic-002`, original A23: 6 fresh responses; reached accepted/proved/exported
  contract and model-generated Python. Native testing exposed execution-before-budget
  and channel-reuse defects. Explicitly stopped and sealed as INFRASTRUCTURE_FAILURE,
  with no final score or TESTED claim. All 657 evidence files and exact response
  origins checked; no model inference was interrupted.
- `arithmetic-003`, original A23: 7 fresh responses; generated/linked implementation,
  four of five native TESTED guarantees passed, two clean builds, and all 24 original
  case observations passed in the independent graders. Strict outcome BLOCKED:
  the closed public-example theorem has one exhaustive assignment but was required
  to supply twenty distinct samples. Release review supplied the concrete mechanical
  failure and rejected it. All 721 sealed evidence files and score/origin audits pass.
- `grouping-004`, original D21: frozen/prepared only, never run; superseded.
- `arithmetic-004`, original A23: 3 fresh responses; terminal interpretation BLOCKED
  on a double-escaped public-example quote, before formalization or generation.
  Native TESTED false; no code observations. Exact source/origin/score seals verified.
  This exposed citation transport duplication; a manifest-ID citation protocol was
  specified next, preserving model-authored meanings and strict completeness checks.
- `grouping-005`, original D21: frozen/prepared only, never run; the next source
  snapshot will additionally include the citation protocol.
- `arithmetic-005`, original A23: 8 fresh responses; first-response interpretation,
  accepted contract, successful autonomous proof repair, generated/linked Python,
  four of five native TESTED guarantees passed, two clean builds and all 24 original
  case observations passed. Strict outcome BLOCKED: the public-example conjunction
  contains a residual unbounded universal quantifier, which correctly remains
  UNKNOWN in the structured evaluator. Release review confirmed the concrete
  `TESTED:O3@1` mechanical failure. All 758 sealed files and score/origin audits pass.
  This exposed a readiness diagnostic that must reach authors before freezing.
- `grouping-006`, original D21: frozen/prepared only, never run; superseded by
  the next snapshot including quantifier-readiness diagnostics.
- `arithmetic-006`, original A23: **VERIFIED / native PASS / TESTED**, with 8 fresh
  exact responses, successful autonomous proof repair, both configured review
  checkpoints, all 4 required TESTED guarantees passed (32 effective assignments
  each), two clean builds and all 24 original-case observations passed.
  All 742 sealed evidence files and score/origin audits independently pass.
  Source root `sha256:f5f52be31d48ae45719187fdbd71ada55146075f6fc25af71be7d2abb4258c51`.
  The sampled campaigns additionally retain 143 caller-guard discards and 3/4/4
  budget-indeterminate assignments in O2/S1/S2; these are excluded from the 32
  effective passes, and no exhaustive-domain claim is made.
  [Terminal result](stages/arithmetic-006/run/BOOTSTRAP-RESULT.json),
  [native report](stages/arithmetic-006/run/artifacts/A23/verislop/package/report.json),
  [evidence seal](stages/arithmetic-006/run/BOOTSTRAP-EVIDENCE-MANIFEST.json).
- `grouping-007`, original D21: 7 fresh exact responses; interpretation PASS,
  formalization BLOCKED on Python artifact layout/effect/library observations.
  Value-level aggregation is representable, but the accepted value-only contract
  cannot establish these structural source requirements. No implementation,
  TESTED claim or code observations. Origin/score/evidence audits independently pass.
  Structural boundary support is the next specification, preserving the original
  required guarantees and distinguishing model proof from source-bound checks.
- `native-source-001`, original A23: 6 fresh exact responses; interpretation,
  Lean contract acceptance, formal review, source admission, generation, linkage
  and TESTED passed. All 24 original-case observations and both clean builds
  passed. Overall strict result **BLOCKED**: release review abstained because
  the older value-only contract did not bind the requested `solution.py` filename;
  the captured implementation uses `implementation.py`. No vote was overridden.
  All 728 sealed evidence files and exact origin/retained-score audits independently
  pass. This increment checks actual source ownership/closed calls; it does not
  formalize the original layout or absence-of-floating-point requirements.
  The next native contract milestone binds these source requirements through
  accepted Lean ASTs and registered source receipts.
  [Terminal result](stages/native-source-001/run/BOOTSTRAP-RESULT.json),
  [native report](stages/native-source-001/run/artifacts/A23/verislop/package/report.json),
  [evidence seal](stages/native-source-001/run/BOOTSTRAP-EVIDENCE-MANIFEST.json).
- `native-contract-001`, original A23: **VERIFIED / native PASS / TESTED**,
  with 8 fresh exact responses. Lean accepted the ordinary value theorem and
  structural native theorems for the exact `solution.py` entry, purity/frame,
  determinism, standard runtime/no external I/O and absence of floating-point
  computation. The downstream packages reconstruct these requirements from the
  accepted AST, rather than copying candidate JSON. All 4 required TESTED
  guarantees passed with 32 effective cases each; both clean builds and all 24
  original-case observations passed. Source-only campaigns execute the entry
  twice per selected case and retain actual in-process frame/repeat observations.
  All 754 sealed files and exact origin/retained-score audits independently pass.
  Source root `sha256:44f4099db13bc19ca9e81f6def4747bf4ac4161922c4acea863c9c49af2270e0`.
  These native proofs establish the registered structural fact model; the Python
  parser, AST-to-facts/ownership checker and runtime remain declared trust.
  [Terminal result](stages/native-contract-001/run/BOOTSTRAP-RESULT.json),
  [native report](stages/native-contract-001/run/artifacts/A23/verislop/package/report.json),
  [evidence seal](stages/native-contract-001/run/BOOTSTRAP-EVIDENCE-MANIFEST.json).
- `native-grouping-001`, original D21: **VERIFIED / native PASS / TESTED**,
  with 20 fresh exact responses and one autonomous contract-repair round. The
  initial contract's separate public-example proofs failed under `rfl`,
  simplification and `decide`; those rejected artifacts remain retained. The model
  supplied a fresh universal value/native conjunction for the same ten interpreted
  obligation IDs and kept every guarantee required. Public examples remain in
  their interpreted obligations; the recovered formal artifact uses the universal
  reference relation rather than separate closed example theorems. Lean accepted
  all nine guarantees, and the CLI reconstructed their packages from the accepted
  AST. Generated `solution.py` passed all 9 required TESTED campaigns with 32
  effective cases each, both clean builds, and all 24 original-case observations
  (2 public and 10 hidden cases in two independent grader processes). Exact origin
  and retained-score audits pass; the root independently matched all 1,146 sealed
  files. This run used the native source root above; it did not yet use the later
  closed-computation proof-search addition. Natural-language correspondence remains
  the recorded interpretation assumption, and assurance remains finite Tier 0.
  The nine value campaigns also retained 42 indeterminate assignments; native
  repeat/frame campaigns retained 35, with 579 actual entry invocations. Their
  reasons were reference step/range budgets and output transport budgets. These
  assignments do not count among the 32 effective passes per campaign. The legacy
  sampled TESTED gate allows such unknowns when its effective-case quota is met;
  this result does not establish the stricter zero-unknown acceptance proposed in
  [tested-campaigns.md](../../docs/tested-campaigns.md).
  Exact counts, reasons and raw-evidence hashes are retained in the
  [campaign summary](validation/native-grouping-campaign-summary.json).
  [Terminal result](stages/native-grouping-001/run/BOOTSTRAP-RESULT.json),
  [native report](stages/native-grouping-001/run/artifacts/D21/verislop/package-repair-01/report.json),
  [evidence seal](stages/native-grouping-001/run/BOOTSTRAP-EVIDENCE-MANIFEST.json).

Each stage's directory contains source/corpus inventories, frozen specifications,
request/final receipts, raw intermediate JSON/Lean files, and terminal evidence
when available. Interrupted evidence is sealed in the stage parent. Never restart
an interrupted arm or modify in-flight source bytes.

## Validation and limits

Focused checks passed: 20 new contract primitive tests with actual Lean denotation
checks, 6 new protocol/context tests, 5 origin/nullable integration tests, 4 String
sampling tests, 14 execution/preflight tests 6 real-process channel tests, and 15 exhaustive finite-campaign tests.
The citation change additionally passed 11 new provenance/validation checks and
a combined 35-check citation/repair/memory/origin regression run, recorded in
[citation-checks.json](validation/citation-checks.json).
Quantifier readiness passed 34 regression executions including 10 new tests,
actual Lean equivalence/reconstruction and a retained two-attempt critic/author
repair. This is engineering evidence, separate from the fresh live run.
An independent rerun of the 10 new tests also passed, recorded in
[quantifier-checks.json](validation/quantifier-checks.json).
The native milestone passed 57 source/runtime/full-pipeline checks, a relevant
69-test regression group, and 55 additional checks in the isolated live snapshot.
The independent formal audit passed 14 native tests and four additional Lean
theorems without `sorry`. Its combined 39-test run had one closure mismatch while
source helpers were changing; the exact differing fields were not retained.
A preserved rerun passed with two matching builds. These overlapping engineering
groups and this limitation are recorded in [native-checks.json](validation/native-checks.json).
The specification-first closed-computation increment adds a bounded `cbv` proof
search alternative for typed formulas without forall/exists nodes. Its unrelated
compiler-generated sort/deduplicate/fold examples pass real compilation, kernel
replay and exact denotation checks without changing record carriers; deliberately
false examples remain blocked at acceptance. The 37 proof/recovery regressions
and 18 native/full-pipeline regressions passed. The initial fixture and tactic
sequencing failures and independent generic audit are retained in
[closed-computation-checks.json](validation/closed-computation-checks.json).
`closed-computation-001` is running with a fresh source/specification root frozen
before the preceding independent grading was read. It starts from the original
D21 prompt with fresh roles; the previous model answers and grading results are
not role context. Running status is not a completed live result.
Its snapshot was prepared while the preceding run was active, as the main bootstrap
protocol permits; execution began after that run's result was sealed and audited.
This differs from the detailed computation specification's stronger wording to
freeze only after the preceding seal. No in-flight source was edited.
Relevant regression suites passed: 21 data bridge/workflow tests, 14 cast/fold
kernel tests, 13 sandbox tests, 20 formal frontend tests, 32 concrete-review tests,
and 16 full-corpus harness tests. Each suite is a registered engineering check;
these checks do not substitute for a live bootstrap result.

Models receive the original prompt/public examples and normal CLI contexts only.
No positive hand-authored candidates, task dispatch, hidden cases, oracle answers,
old model answers or downstream grader feedback are supplied to generation. Every
role call uses a fresh GPT-6.1 Sol collaboration agent with no conversation fork.
Model identity/snapshot, sampling and token usage are unattested; carrier-only read
instructions are not mechanically enforced. The finite target surface has explicit
budgets and minimum effective-case gates. Tier 0 TESTED is neither universal Python
correctness nor END_TO_END_VERIFIED, and natural-language interpretation remains a
recorded semantic assumption.

The earlier native Python target packages its entry as `implementation.py`; the original
corpus prompts name `solution.py`. The independent graders execute the recorded
native entry file. These behavioral scores do not establish the original requested
delivery filename. The new native-contract milestone binds the requested layout
to accepted requirements and current source receipts; older results retain their
original filename limitation.
