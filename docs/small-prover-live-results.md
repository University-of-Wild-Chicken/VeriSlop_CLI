# Pythagoras-Prover-4B: bounded local evaluation

On 2026-10-13, the corrected theorem-fragment interface accepted **3/6 frozen
contracts** through the actual Lean acceptance and IR export stages. The built-in
tactic portfolio accepted **5/6**. Pythagoras solved the record/enum contract that
the portfolio left unresolved. Routing is implemented and remains optional,
disabled by default; token or monetary savings have not been established.

The installed model is `verislop-pythagoras:4b-f16` at
`http://127.0.0.1:11435`. It is F16 GGUF converted from the pinned official
[`Pythagoras-LM/Pythagoras-Prover-4B`](https://huggingface.co/Pythagoras-LM/Pythagoras-Prover-4B)
weights. The [evaluation protocol](small-prover-evaluation.md) records checkpoint,
conversion and Ollama digests. Lean was pinned to 4.34.1 with Std and the supplied
VeriSlop libraries. The model received no reference proof or supervisor-authored
proof corrections. Model generation had no wall timeout; each contract allowed
at most three proposals, with 16384 context tokens and 8192 output tokens.

## Results and limits

- List map, list filter and record/enum: accepted on the first model proposal.
  Accepted obligation inventories and statement hashes matched the frozen inputs.
- Natural arithmetic, signed arithmetic and list fold: unresolved after three
  proposals each. The responses used unavailable tactics such as `norm_num` or
  `ring_nf`, including after exact diagnostics were supplied.
- The deterministic portfolio accepted the first five mathematical contracts and
  left the record/enum job unresolved. The independent arms' success sets cover
  all six contracts; a combined full-pipeline success rate was not measured.
- Twelve model requests completed, reporting 21658 input and 3594 output tokens.
  Total measured request-wrapper time was 60495 ms, including the separately
  rejected bridge preflight. No provider transport failure occurred.
- The Tier 2 bridge probe required **54864 input tokens**, or **63056** including
  its output budget. It was rejected before inference against the configured
  16384-token context. Ollama reports a 40960-token maximum for this model, also
  below the full input alone. No prompt was truncated and no bridge proof was
  established. The legacy summary field `failed_calls: 1` counts this pre-dispatch
  wrapper failure; its usage record has `provider_elapsed_ms: null`.

This measures proof generation on six published, proof-free contract ASTs.
Natural-language interpretation, implementation generation, TESTED software and
END_TO_END_VERIFIED are outside this evaluation. A model's failure to find a proof
does not establish that the theorem is false.

## Corrections and preserved earlier measurements

The complete-file run accepted 0/6 model contracts: responses omitted the frozen
file scaffold or used unavailable tactics. The first fragment run also recorded
0/6, but inspection found a concrete adapter defect: valid Lean `@` applications
were rejected even inside exact frozen theorem headers. Both results remain
unchanged in their original directories.

The retry fixed token classification by theorem scope, retaining exact headers,
frozen scaffolds and Lean proof-term parsing through EOF. It also corrected the
optional bridge evaluator to use the production fragment adapter. Fresh inference
used the same cohort, challenge bytes, obligation IDs and statement hashes as the
original run; comparison was checked before inference. No old response or proof
was edited to manufacture a benchmark success.

## Live enabled-route check

A separate diagnostic smoke selected the natural-arithmetic and record/enum jobs
after the cohort results. Both configured route roles deliberately used the same
local model, so it tests dispatch and persistence, with no cloud-model comparison.
The deterministic portfolio was disabled to exercise model routing directly.

- Record/enum: one initial-model call, zero fallback calls, accepted through Lean
  and IR export.
- Natural arithmetic: three initial calls, then two fallback calls before the
  ordinary repetition stop. Resume consumed the one remaining fallback slot.
  A further exhausted resume made zero calls and preserved all counters.
- Seven real model calls in total; every registered routing check passed.
  The first smoke setup was rejected before any inference because its copied
  initial agent used the wrong tool profile. That failed setup is retained; the
  fresh retry explicitly used `proof_sandbox`.

Focused tests passed **64/64**. Broader related regressions passed **42/43**.
The failing existing provider/review integration test reproduced identically on
clean HEAD `bf12ed037178ba7f5c1fa52ce7d20b541d00e6bc`: critic replay could not
synthesize `Decidable` for O17 and stopped formalization with `REVIEW_INCOMPLETE`.
That preexisting problem is not fixed by this proof-routing change.

## Evidence and use

Raw evidence stays local under ignored `validation/` paths:

- `pythagoras-4b-live-cohort-20261013-002/summary.json`: complete-file measurement.
- `pythagoras-4b-live-cohort-20261013-003/summary.json`: original fragment measurement.
- `pythagoras-4b-live-cohort-20261013-004/summary.json`: corrected fresh measurement;
  adjacent `FREEZE_BEFORE_INFERENCE.json` and `COMPARISON_BEFORE_INFERENCE.json`
  bind sources, model inputs and unchanged contracts.
- `pythagoras-4b-route-smoke-20261013-002/results/summary.json`: live routing check.
- `pythagoras-4b-regression-head-20261013-002/result.json`: clean-HEAD failure replay.

Enable the feature through the [routing instructions](small-prover-routing.md)
and [disabled example configuration](../examples/small-prover-routing-config.json).
Keep the built-in tactics: they solved three jobs this model did not solve. The
record/enum result supports further evaluation as a contract-proof fallback;
the full Tier 2 context currently needs a separately specified context-reduction
interface or a model with sufficient context capacity.
