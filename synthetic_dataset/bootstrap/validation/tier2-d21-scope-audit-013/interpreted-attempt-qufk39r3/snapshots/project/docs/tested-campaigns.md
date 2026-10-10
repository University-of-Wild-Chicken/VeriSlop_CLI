# TESTED: specification and formalism

**Status: proposed campaign protocol `verislop.test-campaign/0.2`.** This document specifies a stricter, versioned campaign and a future VSCore campaign backend. It does not enable that backend or reinterpret existing Python campaign evidence. The accompanying [Lean design model](../formal/TestingModel.lean) checks finite acceptance rules; it does not prove the current Python harness, oracle, planner or supervisor correct.

`TESTED` is one of the eight obligation milestones. Tier 0 uses tests as its implementation bridge; Tier 1 can also run campaigns, and a proof-backed Tier 2–4 endpoint may independently require them. Numeric bridge tiers and milestone outcomes remain separate. In the current release, Python Tier 0/1 campaigns exist; VSCore campaigns remain unsupported.

## 1. Public claim and prerequisites

For obligation `O@r`, `TESTED: PASS` means that a registered campaign executed the exact selected target artifact and satisfied its **frozen, finite** criteria. Its public scope names the artifact, obligation revision, contract statement, oracle mode, execution endpoint, case set and environment. It does not establish the obligation for untested inputs, another artifact or another environment.

Required prerequisites are `IMPLEMENTED: PASS`, `TYPECHECKED: PASS`, and a mechanically unique binding from the accepted contract's expression and symbol references to the tested objects and oracle. The whole `LINKED` inventory and `PROVED` are not logical prerequisites of this milestone. An implementation workflow may impose additional acceptance gates; the current workflow reads fully accepted IR and a checked link record.

Inputs MUST come from the checked/reconstructed contract artifact, never from the original LLM obligation JSON. The checked case-plan derivation MUST preserve the full accepted predicate and guard; selecting one true conjunct from a false conjunction cannot count as testing the original obligation. Unsupported opaque terms, unbounded liveness and physical-resource guarantees retain their actual applicability and `UNSUPPORTED` outcomes; they receive no fabricated oracle. Declarations, assumptions and non-vacuity witnesses retain the base lifecycle's `NOT_APPLICABLE` test outcomes.

There are two explicit oracle assurance modes:

- `contract_instance`: a registered certificate establishes that the case checker implements the instantiated accepted predicate, including its representation adapters. Passing cases support the finite semantic conclusion in §4.
- `trusted_oracle`: that equivalence is declared trusted. Passing cases establish the observed oracle verdicts under that trust boundary. The report MUST say that the translation is unproved; an `exact` Boolean field is not an equivalence certificate.

The mode is frozen before execution. Both modes can produce a qualified `TESTED` milestone; neither creates `PROVED` or `END_TO_END_VERIFIED` for the implementation's universal contract.

## 2. Campaign inputs and identity

A campaign is the tuple

```text
C = (I, O, B, Q, K, G, E, V, T)
```

Here `I` is the exact target inventory; `O` the accepted obligation revisions and expression packages; `B` the unique symbol/argument/result bindings; `Q` the frozen case plan; `K` the executable oracle and its adequacy evidence or declared trust; `G` the generator/shrinker version and discovery provenance; `E` the execution profile; `V` the registered verifier identities; and `T` the declared trusted components.

For each selected obligation, freeze:

1. The case representation, type-correct outer assignments, guard policy and oracle mode.
2. Mandatory effective fixtures and required coverage tokens, each with its registered measurement rule. A mandatory effective fixture cannot disappear as a discarded guard.
3. `minimum_distinct_effective`, at least one, and any independent minimum of distinct target input tuples or required entry/branch observations. A requested effective quota is this acceptance threshold, not a suggestion.
4. Finite generation, case, invocation, evaluation-step, range-enumeration, per-call, total execution and shrink budgets. The unit and enforcement point of each limit are explicit.
5. The repeat policy, fresh-process/state-reset rule, allowed memoization and output-comparison rule. Repeated invocations do not become new distinct cases.
6. The replay policy and the exact output fields permitted to vary, such as execution timestamps and durations. No recursive removal of arbitrary `id` or `time` fields is allowed.

All authoritative formats are closed and versioned. Each configuration field must be enforced by its assigned verifier; an ignored field cannot influence a claimed policy. A seed without a generator version, algorithm, parameters and recorded case list is insufficient to reproduce a campaign.

The supervisor creates the case IDs from canonical semantic case keys. A key binds the obligation revision, instantiated predicate, assignment/fixture and declared scenario state; a new arbitrary ID cannot turn an identical case into another effective case. Record distinct assignments, target input tuples, invocations and effective cases separately. Record shared/cached receipts explicitly; they cannot be described as fresh calls.

Discovery may be seeded, hint-guided, adaptive or agentic, but is bounded and untrusted. Discovery calls and shrink calls do not satisfy the main campaign merely because they happened. For the first `0.2` profile, materialize the finite case plan before the validating execution. Target-dependent discovery must retain its actual provenance and does not acquire an IID statistical interpretation.

Define exact-byte hashes `H` and canonical JSON hashes `J`, using the repository's registered codecs:

```text
campaign_root = J({
  format: "verislop.test-root/0.2",
  target_inventory_hash, accepted_contract_hash,
  obligation_inventory_hash, bindings_hash,
  campaign_plan_hash, campaign_manifest_hash,
  verifier_registry_hash, schema_registry_hash, tcb_hash
})
```

The plan and manifest contain inputs and prospective output slots, never future results or their own hashes. The manifest includes exact oracle, harness, adapters, generator, case-list, runtime/toolchain and policy dependencies. Executions, outcomes, votes and reports are outputs; they cannot be hidden inputs to their own root. Changing a relevant input requires a new campaign instance. Historical evidence remains historical.

## 3. Case semantics and exactness

For the common accepted obligation

```text
φ_O = ∀ x : X, A_O(x) → P_O(x, implementation observations)
```

a case fixes `x`, executes the target calls referenced by the predicate, strictly decodes the returned values, and evaluates the guard and conclusion. A target receipt identifies the exact entry, canonical inputs, outputs or fault, scenario, artifact inventory and current execution. Every effective case MUST have a nonempty target-call footprint contributing to its accepted predicate check, and every contributing call must resolve to a receipt; a reference-function evaluation, unused dummy invocation or supplied output is insufficient.

For example, a checker that short-circuits `True ∨ target(x) = x` without calling `target` has made a pure logical observation, not an effective target case. It records `MISSING_TARGET_OBSERVATION` and cannot meet the campaign quota. Adding an unrelated call does not repair that missing contribution.

The checker uses three semantic judgments, with evidence or explicitly declared oracle trust:

```text
ExactTrue(P)   entails P
ExactFalse(P)  entails ¬P
Unknown(P)    entails neither
```

Sampled consistency is a separate observation, not either exact judgment. Case outcomes are:

- `EFFECTIVE_PASS`: the guard is exactly true, the required residual predicate is exactly true, and all contributing target calls have valid current receipts.
- `DISCARDED`: the guard is exactly false. This is terminal accounting, but contributes zero effective cases.
- `COUNTEREXAMPLE`: the guard is exactly true and the conclusion exactly false, with its concrete target observations and checked negative witness retained.
- `TARGET_VIOLATION`: an observed behavior violates the frozen execution profile, such as an undeclared exception or invalid result encoding. Name that profile claim; do not pretend every target fault refutes the logical conclusion.
- `UNKNOWN` / `INDETERMINATE`: a guard, predicate, witness or binding cannot be decided within the supported semantics or budget.
- `TIMEOUT` / `CANCELLED` / `INFRASTRUCTURE_FAILURE`: retain the failed operation and partial receipts. A target timeout does not prove unbounded nontermination or a physical-time guarantee.

An expected `Result.error` value is ordinary contract data and can pass an error-semantics test. Unexpected exceptions are not automatically expected errors. A sampled false guard cannot justify discarding a case.

Logical propagation MUST preserve exactness:

```text
ExactTrue(P)  ⇒ ExactFalse(¬P)
ExactFalse(P) ⇒ ExactTrue(¬P)
Unknown(P)   ⇒ Unknown(¬P)

ExactTrue(∃ x, P x)  requires a concrete x and ExactTrue(P x).
ExactFalse(∃ x ∈ D, P x) requires complete finite D
                         and ExactFalse(P x) for every x ∈ D.
ExactTrue(∀ x ∈ D, P x) requires complete finite D
                        and ExactTrue(P x) for every x ∈ D.
ExactFalse(∀ x, P x) requires a concrete x and ExactFalse(P x).
```

Finding no witness among samples does not refute an unbounded existential. Finding no failing input among samples does not prove an unbounded universal. Negation and implication cannot erase this distinction.

The initial strict oracle profile instantiates leading universal binders and exactly evaluates the residual supported DSL, including finite sorts/ranges within frozen budgets and positive existentials with actual witnesses. A residual unbounded universal, or a negative existential over an unbounded domain, is unsupported/unknown unless a registered exact procedure covers it. A different sampled projection is allowed only with its own identity and narrower claim; its success cannot count as `EFFECTIVE_PASS` of the original residual formula.

## 4. Formal acceptance predicate and theorem

Let `R` be the immutable records from one execution. Let `Eff_O(R)` be its distinct effective semantic case keys for `O`; `Mand_O` its mandatory fixtures; `Cover_O(R)` its measured coverage; and `ReqCover_O` its frozen required coverage.

The finite acceptance rule is:

```text
Accept_O(C, R) ≜
  CurrentBoundEvidence(C, R)
  ∧ PrerequisitesPassed(O)
  ∧ ExactPlanAndRecordMembership(Q, R)
  ∧ UniqueCaseKeysAndReceiptIdentities(R)
  ∧ MandatoryEffective(Mand_O, R)
  ∧ |Eff_O(R)| ≥ minimum_distinct_effective_O ≥ 1
  ∧ ReqCover_O ⊆ Cover_O(R)
  ∧ EveryEffectiveCaseHasNonemptyRelevantTargetFootprint(R)
  ∧ AllEffectiveCasesHaveCompleteTargetReceiptsAndExactPasses(R)
  ∧ NoCounterexamplesOrTargetViolations(R)
  ∧ NoUnknownsTimeoutsSkippedCasesOrInfrastructureFailures(R)
  ∧ AllFrozenBudgetsRespected(R)
  ∧ RequiredRepeatAndReplayChecksPassed(R)
```

Counts and coverage are recomputed from validated receipts, not trusted because an agent or result JSON says `300` or `PASS`. Every planned case must be accounted for; permitted exact-false guards may be discarded, but cannot satisfy the effective quota. Below-quota budget exhaustion blocks rather than silently relaxing the quota. Completion of a small finite domain may use a smaller threshold only if that threshold and completeness rule were selected before execution.

For `contract_instance`, the semantic soundness statement is:

```text
Accept_O(C, R)
∧ ExecutionFaithful(I, R)
∧ BindingAndFootprintFaithful(O, B, R)
∧ OracleAdequate(O, K)
⇒ ∀ c ∈ Eff_O(R),
     A_O(input_c) ∧ P_O(input_c, actual_target_observations_c)
```

Faithful execution, correct bindings and oracle adequacy are separate premises, supplied by registered evidence or declared trust as appropriate; they are not proved by counting records. In `trusted_oracle` mode, the mechanically unconditional conclusion is that the frozen oracle reported passing verdicts for those observations. The claim about the accepted predicate remains conditional on its declared translation trust.

Even with all semantic premises, this implication is invalid:

```text
(∀ c ∈ Eff_O(R), P_O(c)) ⇒ ∀ x : X, P_O(x)
```

For example, the implementation agrees with `x + 1` at inputs `0` and `1` but returns `0` at `2`. Both tested inputs pass, while universal refinement is false. The Lean model includes a concrete finite-sampling countermodel. Exhaustive finite enumeration strengthens the tested surface only when a checked certificate establishes domain completeness, representation coverage and faithful evaluation. Any resulting universal finite-domain theorem is separate proof evidence, not an automatic promotion of random tests.

## 5. Results, publication and lifecycle

Use a typed registered predicate `campaign-pass/0.2`, with `TESTED:<id>@<revision>` bound to `campaign_root`, endpoint, oracle mode, policy and producer hash. Every public result records the case-plan hash, immutable execution inventory, exact counts, complete call receipts, effective/discarded/unknown cases, coverage, faults, retained counterexamples, budgets and declared trust. Proposed paths are:

```text
tests/<campaign-id>/plan.json
tests/<campaign-id>/manifest.json
tests/<campaign-id>/cases.json
tests/<campaign-id>/executions/<attempt-id>/result.json
tests/<campaign-id>/executions/<attempt-id>/observations.jsonl
tests/<campaign-id>/executions/<attempt-id>/evidence/
```

These paths and new formats are a design, not current CLI output. A publication validates the complete output inventory before exposing `TESTED: PASS`. Missing or corrupt outputs, wrong issuers, unsupported predicates, stale roots, changed dependencies and unverifiable target invocations cannot pass. A replay attempt has a new immutable attempt ID; a mutable current pointer is not evidence.

Lifecycle outcomes and terminal command states remain distinct:

- `PASS`: all required campaign predicates pass.
- `FAIL`: a confirmed counterexample, target-profile violation or observed forbidden nondeterminism exists; preserve the concrete evidence.
- `PENDING`: not executed, omitted by policy, cancelled or incomplete for a reason that did not establish a counterexample. A required pending campaign blocks closure.
- `UNSUPPORTED`: no registered backend/oracle covers the demanded campaign.
- `STALE`: the record no longer binds to the current artifact, policy or dependency identity.
- `NOT_APPLICABLE`: only the frozen lifecycle rule makes tests inapplicable; unsupported guarantees cannot be erased this way.

Infrastructure failure yields terminal `INFRASTRUCTURE_FAILURE`, with a pending/unresolved milestone rather than a fabricated logical counterexample. Claim failure and incompleteness yield `BLOCKED`; successful standalone execution yields a qualified campaign pass. The separate whole-run `VERIFIED` closure additionally requires its full registered claims, two isolated builds/replays and defined deterministic comparisons. Campaign success alone does not assert that closure.

`TESTED` evidence cannot change `accepted-ir.json`, turn review acceptance into proof or silently satisfy an E2E semantic edge. An optional Tier 2 campaign stays `PENDING` when omitted. Required campaigns affect the separate frozen policy and must be admitted by an actual registered backend.

## 6. Adversarial review must produce counterexamples

All configured tiers and their individual reviewers follow the [concrete-counterexample review protocol](adversarial-counterexamples.md). A blocking finding MUST identify a frozen claim and a concrete witness, exact artifact/input identities, expected versus observed behavior, and an executable replay. A registered checker must confirm the violation before the finding counts as a confirmed rejection.

Examples include a specific input with a wrong result, a witness whose accepted predicate is false, a case-plan mutation accepted despite a missing mandatory fixture, or a replay showing a false exactness verdict. A statement such as “this generator might be unreliable” is not a finding. Reviewers can search for such failures; they cannot replace a witness with a reliability estimate.

Every reviewer receives a fixed case/search/shrink/time budget and reports confirmed counterexamples, unresolved replay attempts or `NO_COUNTEREXAMPLE_FOUND`. Absence of a found counterexample is bounded search completion, not universal correctness. Mechanical failures still veto consensus; failed infrastructure/replays remain separately unresolved. Lower-tier acceptance escalates the same bound candidate to the next configured tier. A new counterexample or artifact change invalidates the affected consensus.

Shrinking is itself bounded. Both the original witness and every retained smaller witness must reproduce the same violation. A smaller input that merely times out cannot replace a logical counterexample. Discovery additions enter a new frozen campaign; they do not secretly rewrite the completed campaign.

A counterexample outside a completed finite case set may refute a required implementation guarantee and block release, while the original campaign's historical `TESTED: PASS` remains a true claim about its recorded cases. Preserve that result and replay the discovered input in a new campaign. An input outside the accepted assumptions or requested endpoint cannot refute the covered guarantee.

## 7. VSCore campaign backend proposal

Add a separately registered `verislop.campaign.vscore-kernel/0.1` backend for the existing `vscore/0.1` pure values and accepted executable DSL. Its target execution is the **normative source evaluator**, with receipts bound to the exact delivered source, checked program, entry, arguments and adapters. It does not execute a native binary or widen the existing source E2E endpoint.

For each frozen case:

1. Revalidate exact source decoding, typing, accepted contract identity and unique entry bindings.
2. Run/reduce the target entry's `VSCore` evaluator on the concrete arguments. Do not substitute evaluation of the accepted reference function.
3. Check the instantiated accepted DSL using those target observations and validated representations.
4. Produce a separately checked case receipt. In `contract_instance` mode, replay an independently derived Lean proposition about that concrete target evaluation and its accepted predicate. The existing universal refinement certificate does not substitute for executing the planned cases.
5. Run the finite campaign acceptance checker over all receipts, counts, coverage and budgets; retain its complete execution inventory.

Kernel evaluation budgets measure campaign completion only. A host process duration does not become a physical-resource theorem about VSCore. Ordinary Lean VM/native evaluation, a Python interpreter or a new runner requires its own backend identity, declared runtime trust and correspondence boundary.

Ad hoc parser examples, previous proof attempts or reductions from semantic acceptance are not a campaign. Only the separately planned, actually executed and registered campaign can publish its `TESTED` evidence. Default optional tests remain optional; future `--require-tests` admission can succeed only once this backend and its release gates are implemented.

## 8. Statistical claims

No confidence score is part of `TESTED: PASS`. For an explicitly declared IID sampling experiment with distribution `μ`, faithful independent executions, an exact checker and a fixed plan of `n` draws, define

```text
p = Pr[x ∼ μ : A_O(x) ∧ ¬P_O(x)]
Pr[zero failures in n draws] = (1 - p)^n
```

If only admissible cases are drawn, use the corresponding conditional distribution and failure probability. Repeats remain draws but do not increase distinct-case coverage. The bound depends on the distribution and all independence assumptions; a biased generator may assign probability zero to the actual bug. Adaptive hints, distinct-value deduplication, retries, shrinking, rejection-conditioned stopping and post hoc seed selection do not automatically satisfy this experiment's assumptions. The legacy generator does not warrant this equation as a reported confidence bound.

Any future statistical report is a separately specified, bound experiment. It cannot authorize a deterministic campaign PASS, a correctness proof or review acceptance when required mechanical evidence is missing.

## 9. Compatibility and concrete legacy limitations

Current `verislop.python-tier0-campaign` evidence retains its original meaning and root formula. Its documented oracle translation is trusted, not proved. It has no claim to `campaign-pass/0.2` merely because the new design exists.

The inspected implementation currently:

- stops generation at its requested effective quota or generation/duplicate-exhaustion limit, but can pass with only its fixed minimum of 20 effective cases;
- counts both exact and sampled positive verdicts, and permits nonzero indeterminate counts on a passing supported obligation;
- shares cached `(symbol, arguments)` observations across obligations, hints and shrinking, rechecking only the first 64 cache misses;
- can count a short-circuited formula without a target invocation;
- lacks dedicated closed campaign/result schemas, has recorded parameters that are not consistently enforced, and does not enforce its `test.run(timeout=120)` parameter as a campaign-wide limit;
- does not consistently separate harness infrastructure failure from a target counterexample.

An observed exactness defect also requires repair before the proposed strict oracle can be claimed. With inner Nat samples `[0, 1, 2]`, the current evaluator reports exact false for

```text
∃ b : Bool, ¬(∀ n : Nat, n ≤ 100)
```

but `b = false` and `n = 101` establish that this proposition is true. Its finite existential path fails to propagate sampled negative bodies. This concrete oracle counterexample is not a reliability speculation. The new exact-negative rule in §3 prevents that inference. A regression must reproduce it against the real evaluator, and its repair must not retroactively certify old results.

The following reproducer was executed against the current evaluator. Its assertion records the defect; it is not a proposed passing oracle implementation:

```python
from verislop import dsl

profile = dsl.Profile.from_json({
    "profile_id": "counterexample-demo", "enums": {},
    "symbols": {}, "predicates": {},
})
formula = {
    "tag": "exists", "sort": "Bool", "body": {
        "tag": "not", "body": {
            "tag": "forall", "sort": "Nat", "body": {
                "tag": "le", "left": {"tag": "var", "index": 0},
                "right": {"tag": "nat", "value": "100"},
            },
        },
    },
}
dsl.type_formula(formula, [], profile)
verdict = dsl.Evaluator(profile, {}, lambda body, env: [0, 1, 2]).formula(formula, [])
assert verdict.value is False and verdict.exact is True  # observed wrong verdict
assert not (101 <= 100)  # concrete refutation of the inner universal
```

## 10. Finite implementation and release gates

Implement this specification as a separate milestone, in this order:

1. Add closed `0.2` plan/manifest/case/receipt/result schemas, campaign registry, typed predicate and explicit legacy dispatch.
2. Repair and validate exactness propagation, instantiation, strict decoding, witnesses and call-footprint tracking. Bind oracle adequacy or declared trust without conflating the modes.
3. Materialize frozen cases, enforce all budgets/thresholds, retain transcripts and build the finite acceptance checker. Agentic discovery is proposed input only.
4. Add the normative VSCore campaign executor and independently derived kernel-checked concrete-case receipts; no host/native endpoint is implied.
5. Integrate evidence, fresh replay, view/report, optional-test admission and concrete-counterexample review. Enable capabilities only after the finite release cases pass.

Required release cases cover: real target calls instead of reference/dummy calls; guarded passes and all-discarded campaigns; duplicate case keys and cached receipts; threshold shortfall and a zero threshold; expected errors versus undeclared exceptions; unknown and sampled inner quantifiers; the concrete finite-existential defect above; false witnesses; every missing mandatory fixture/coverage token; malformed encodings; timeouts/cancellation/failed infrastructure; stale and mismatched roots/issuers; source mutation; changed oracle/generator/environment; differing replay outputs; direct and prepared VSCore routes; optional `TESTED: PENDING`; required unsupported campaigns; bounded review without a counterexample; fabricated or unreproducible review findings; and a confirmed counterexample surviving shrink and tier escalation. Legacy Python outcomes and root meanings must remain versioned and explicit.

The [Lean model](../formal/TestingModel.lean) supplies a finite acceptance specification and soundness lemmas under explicit external premises, plus quantifier and sampling counterexamples. It is a design artifact. Runtime conformance tests, oracle equivalence, truthful transcripts, hashing, isolation and implementation of this future campaign backend require their own evidence.
