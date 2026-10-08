# Fresh strict proof of concept: reservation

The native Qwen run completed the strict Tier 0 pipeline: **VERIFIED closure;
implementation assurance TESTED**. All five Lean reference guarantees are PROVED.
Both configured review checkpoints accepted, and two isolated clean builds matched.
The independent request oracle passed **400 distinct cases twice** (800 observations),
including zero, equality, both branches and values above 64 bits.

The stopped corpus experiments remain stopped and unsuccessful in their strict arms.
This fresh task is separate from the corpus; it neither changes those scores nor
demonstrates support for general JSON, strings, signed integers, graphs or collections.
The [stopped diagnosis](../stopped-experiments-003-002/DIAGNOSIS.md) records where every
completed strict arm failed, with exact artifact references and preserved scores.

## What the proof of concept actually did

The request specifies `reserve(balance, amount)` for every natural-number pair:
return `("ok", balance - amount)` when `amount <= balance`, and
`("error", "insufficient")` otherwise. Successful balances do not increase, and zero
reservations succeed. Non-natural inputs and JSON interfaces are explicitly excluded.

Qwen made six native calls: two interpretation calls, one formalization, one
implementation and two reviews. Its first interpretation referenced an undeclared
`N1`; the CLI supplied the exact error and previous proposal, and the second call
repaired it. The first formalization supplied a faithful `Nat × Nat → Except E Nat`
reference and guarded theorems. The checked tactic portfolio supplied the proofs.
No prewritten positive draft, formalization, proof or implementation candidate was used.
Model generation had no wall deadline; finite call/token/repair budgets and mechanical
verifier and candidate-test limits remained enabled.

The five guarantees cover success, error, zero, exact subtraction, and preservation of
the balance bound. Exact subtraction repeats the success value equation; five named
guarantees do not mean five independent behaviors. Each generated contract had 32
effective passing assignments, with zero failures, indeterminate cases or timeouts.
Discarded assignments do not count. Shared oracle caching means the 160 effective
obligation evaluations are not 160 distinct API inputs.

Accepted IR was reconstructed from the kernel-replayed accepted Lean environment,
including declaration and formula identities, and both clean rebuilds produced identical
IR. It was not copied from the interpreter's JSON. Review packets supplied the exact
proof source from the immutable certificate verified through that IR. The accepted
source contains unused tactic fallback `| sorry`; the actual accepted proof terms have
no forbidden `sorryAx`. Mechanical proof acceptance, rather than lexical token scanning
or a reviewer's narrative, decides PROVED.

## Concrete negative control

A separate supervisor-provided implementation changed `amount <= balance` to
`amount < balance`, retaining the accepted reference contract. It is a deliberate
mutation, not another native coding outcome.

At `reserve(0, 0)`, the mutant returned `("error", "insufficient")`; the request requires
`("ok", 0)`. Generated tests failed O1, O3 and O4. The native Qwen release reviewer
constructed four probes; supervisor replay confirmed the success-at-equality, zero,
and exact-subtraction violations, while the ordinary error probe was NOT_REPRODUCED.
The effective verdict was REJECT and release was BLOCKED. The independent oracle
found all 20 equality-boundary failures among 400 distinct cases, on both fresh executions.

The negative report also labels its failed aggregate `CLOSURE:provenance` as
`STALE_OR_UNBOUND_EVIDENCE`. This aggregate requires every required claim to pass;
the TESTED failures make it fail. The label alone is not evidence of byte corruption
or stale copied proof evidence. Actual IR, source and link integrity checks passed.

## Implemented workflow repairs

- Interpreter prompts now publish separate literal `kind` and `role` fields, complete
  assumption supplier fields, and exact ambiguity shapes, with schema-derived repair guidance.
- Prover retries receive the exact latest submission and compiler errors, independently
  of the retained best candidate. An incomplete compiling baseline no longer hides a
  rejected proposal's diagnostics.
- Safe recursive Lean definitions can be replayed despite excluded executable
  `_unsafe_rec` companions. Strictly validated companions remain unavailable as proof,
  binding or witness roots; unsafe user definitions and forbidden axioms still fail.
- Required Python TESTED agent contracts must mention admitted implementation symbols
  and have executable DSL statements before freezing. This catches empty profiles and
  constant-True/input-reflexivity substitutes. It does not prove arbitrary natural-language
  correspondence or reject every possible vacuous formula.
- Review packets use the immutable accepted certificate and its hash-checked proof
  source; repointing the mutable certificate alias to a `by sorry` template is rejected.
- A stale VSCore test mock now reads the actual bound review envelope. Runtime review
  semantics and test expectations were retained.

The workflow regression run passed 120 checks; the recursive/module/VSCore suites
passed 49, immutable accepted-review source tests passed 4, oracle checks passed 8,
and the corrected VSCore review suite passed 15. These are overlapping test groups,
not a total of distinct tests. The initial four stale mock-parser failures are retained
in the regression log and were resolved by the test-only parser correction.

## Evidence and reproduction

[Machine-readable summary](SUMMARY.json), [positive report](positive/package/report.json),
[accepted IR](positive/package/accepted/accepted-ir.json),
[generated implementation](positive/package/implementation/reserve.py),
[positive request oracle](controls/reservation-v1-request-oracle.json),
[negative report](negative/package/report.json), and
[negative request oracle](controls/reservation-boundary-negative-request-oracle.json)
are captured with their original bytes. `snapshot-manifest.json` hashes the snapshot.
Full package copies include accepted artifacts, expressions, evidence, native transcripts,
both review certificates and receipts, and clean-build records. The original packages
remain under `.verislop/proof-of-concept/runs/`; captured execution sources are included.
All 139 frozen execution/configuration files stayed unchanged during the control.

The pre-generation [protocol and run command](../../../examples/proof-of-concept/reservation/README.md)
describe a fresh native reproduction. Use a new run ID. The supplementary oracle is:

```sh
python -m synthetic_dataset.tools.check_reservation_poc \
  --package .verislop/proof-of-concept/runs/reservation-v1 \
  --out /tmp/reservation-new-oracle.json
```

Use a new output path: the checker writes once and leaves package evidence unchanged.
Its expectations come from the request and Python exact arithmetic, never the Lean reference.

PROVED concerns the Lean reference. TESTED concerns finite linked implementation
observations under the reported toolchain, verifiers, host, isolation, Python runtime,
transport and generators. Model identities depend on the configured local service's
metadata. Natural-language interpretation still requires correspondence review.
**END_TO_END_VERIFIED remains unsupported for this Tier 0 endpoint.**

Before another corpus benchmark, the next useful control is one real JSON-shaped corpus
API with admitted input/output representations, faithful formal semantics and an executable
bridge. Increasing retries cannot supply missing representations or establish that bridge.
