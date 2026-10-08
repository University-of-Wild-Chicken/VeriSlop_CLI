# Experiment failure diagnosis

Snapshot: 2026-10-08T00:36:54.789959+00:00. Counts are partial, not final benchmark results.

Qwen: 0/26 full-CLI tasks succeeded; direct 22/27. Luna: 0/3 full-CLI tasks succeeded; direct 3/3.

No completed full-CLI attempt reached implementation generation. Consequently the zero score currently measures failure to complete interpretation/formalization, rather than generated implementations failing the external tests. Missing artifacts fail every external case, as the original protocol requires.

Qwen first failed stage: {"before recorded stage": 1, "formalize": 9, "interpret": 16}. First diagnostics: {"CANDIDATE_BUILD_FAILURE": 8, "INVALID_CANDIDATE": 13, "PROVIDER_FAILURE": 1, "UNCOVERED_SOURCE_CLAUSE": 4}. One provider completion ended without a normal stop; the remaining recorded failures are obligation/coverage/schema or Lean statement/build failures. Downstream ORPHAN_CLAIM and REVIEW_NOT_RUN messages are consequences, not independent root causes.

## Actual dispatch stall and recovery

The Luna controller exhausted collaboration-agent slots after introducing a nested pair-controller layer. Removing that layer freed capacity; the supervisor dispatched the pending D21 request to a fresh Luna child and published its captured final. This did not alter benchmark code, gates, captured responses, scoring, or the no-generation-timeout policy. Qwen remained active and continued completing pairs.

## Concrete prompt and semantic failures

The formalizer system prompt shows an example binding `{"obligation":"N1"}` although the frozen G03 interpretation contains no N1. Luna copied that binding in its first G03 and G13 proposals; subsequent requests contain the statement-checker feedback `unknown obligation N1`. This is an avoidable template hazard. The interpreter also frequently emits missing dependency IDs, invalid dependency shapes, or incomplete verbatim clause coverage. The contract and schema checks must remain strict.

The current executable contract profile admits Nat, Bool, Unit, finite nullary enumerations and Except results. The corpus API accepts general JSON objects/arrays, strings, signed integers and graph/state structures. The generalized VSCore syntax does not expand that accepted contract profile. Faithful encodings and adapters are required; replacing a graph or JSON value with an unexplained natural-number code does not preserve the requirement.

The last G03 Luna proposal is a concrete semantic counterexample: its Lean reference `solve n source vertex` has no edges argument and reports `.null` for every non-source vertex. On the first public graph, vertex 1 must be `"-inf"` because a reachable negative cycle can reach it. A sandboxed Lean evaluation of `VeriSlop.solve 5 0 1` produced `"null"`. See [the exact counterexample](g03-counterexample.json) and [compiler/evaluation evidence](g03-candidate-eval-standard/compile-result.json). The candidate was blocked and still contains sorry proof placeholders; this is not a counterexample to an accepted theorem or an accepted implementation.

A separate mechanical control passed: `tests.test_providers_review.ProviderReviewTests.test_full_run_with_agents_for_every_role_and_review_gates` completed the bounded-increment workflow with mock model fixtures and four review checkpoints. This establishes that the supported fixture can traverse the pipeline; it does not establish live-model success or success on the corpus. An initial diagnostic evaluation with a 512 MiB Lean heap failed; evaluation succeeded with the normal compiler memory setting. That diagnostic resource failure did not occur in the measured benchmark.

## Interpretation and next correction

These results do not demonstrate that VeriSlop improves coding reliability. They show that this version of its full workflow cannot yet complete the sampled software tasks. The representation mismatch should have been highlighted and tested before starting the hard-corpus comparison. Continuing the frozen runs preserves their actual negative evidence; it cannot remedy the defects.

The next revision needs schema-valid examples with conditional bindings drawn only from actual obligation IDs, an explicit supported-profile preflight, and a mechanically bound JSON/signed-number/sequence interface for the corpus API. Reference contracts must preserve the actual task semantics and be checked against public examples before proof search. Run supported live-model controls before another hard-corpus comparison. Any revised benchmark must get a new run ID and source inventory; do not change requirements, silently downgrade, inject hidden-case feedback or repair recorded results to improve scores.

[Snapshot and source checks](snapshot.json) · [Qwen live summary](../../runs/qwen-local-002/summary.json) · [Luna live summary](../../runs/luna-agents-001/summary.json)
