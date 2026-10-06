# Concrete-counterexample adversarial review

Proposed protocol v0.2 · 2026-10-06

The CLI implementation enforces a narrow structured-probe subset through [supervisor counterexample replay](../verislop/review_counterexamples.py) and the [review workflow](../verislop/review.py). Reviewers construct closed `target_case`, `missing_requirement` or `mechanical_failure` proposals; they cannot supply executable commands or confirmation receipts. Every acceptance search needs at least one constructed probe, and every probe must replay as `NOT_REPRODUCED`. Unsupported or infrastructure-failed probes produce an effective `ABSTAIN`: unanimity remains incomplete, while a frozen quorum policy may permit configured abstentions. The complete rich finding format in §5 remains a proposed design; existing v0.1 stored findings and votes retain their recorded meaning but cannot satisfy the new gates.

The implemented target-case checker supports the registered Python target, strictly typed outer assignments and exact decidable residual formulas. It rejects unbounded residual sampling, requires a current reconstructed structural link and assigned receipt, and bounds execution and host-oracle arithmetic. Its source admission permits a narrow syntax of pure top-level functions, direct calls to admitted functions and literal exceptions. Name references are confined to admitted functions and each function's own parameters/locals; builtin aliases and nested function scopes are unsupported. Function defaults, annotations and decorators are unsupported evaluated metadata. Imports, attributes, reflection and I/O are unsupported: target-written protocol text cannot count as an observed harness result. This admission applies to review replay; legacy test campaigns keep their existing behavior. VSCore target-case execution remains unsupported; current mechanical-claim probes work at its supported checkpoints. Missing-requirement probes check exact request-span coverage, not natural-language semantic fidelity. These are finite supervisor checks with declared oracle/harness trust, not a proof of the supervisor or all oracle translations.

Adversarial reviewers MUST search for concrete counterexamples to named frozen claims. A technical rejection MUST cite either an independently confirmed counterexample within that claim's scope or an observed failure of its required mechanical acceptance predicate. Guesses about reliability, model quality, possible future failures or insufficient confidence are not technical blockers. Agents MUST NOT invent inputs, observed outputs, checker results or receipts to obtain a rejection.

## 1. Freeze the question and the search

Each configured review tier and each reviewer instance MUST receive the same immutable target for its assigned scope: exact claim IDs and revisions, accepted statement hashes, source and artifact inventory, assumptions, exclusions, endpoint, oracle/adapter identities, mechanical predicates and review policy. The packet binds the review target root and every referenced artifact by path and hash. A claim about Python execution cannot be refuted by a different implementation, and a claim about VSCore `restricted_source` does not assert behavior of an unadmitted host interpreter.

Before dispatch, freeze finite limits for each instance: provider calls/tokens, candidate witnesses, generated cases, replay attempts, shrink attempts, total wall time and permitted tools. A tier-level budget MUST also bound its aggregate work. A later tier MUST perform its assigned bounded search; copying an earlier verdict is not completing that search. Reconciliation and provider retries have their own frozen finite limits and cannot retry away a confirmed rejection.

Search may inspect boundary values, argument order, constructors, oracle decisions, assumptions, missing coverage and artifact/evidence bindings. Its outputs are concrete witness candidates and retained observations. A proposed mutation MUST be explicit, isolated from the frozen candidate and identified by both original and mutated hashes. Reviewers cannot mutate the candidate or rewrite evidence in place.

## 2. Candidate, replay and confirmation

A `CANDIDATE` finding names one frozen claim or required predicate, a concrete input or mutation, the expected result derived from that claim, and a replay recipe naming a registered operation and typed arguments. Arbitrary agent-supplied shell commands or code are not admitted. An observation the reviewer already obtained is retained with its actual provenance; an unexecuted candidate records no observed result. Neither a plausible example nor an agent's explanation confirms a finding.

The supervisor MUST replay the witness through the currently registered checker assigned to this claim or to an explicitly frozen counterexample-validation claim. Confirmation is independent of the reviewer's supplied outputs and verdict: the checker obtains the artifact and input bytes itself, validates their hashes and scope, executes the relevant operation, derives the expected predicate independently, and records the actual observation. Record its current checker ID/hash, environment, exact invocation, input/output inventory and immutable result receipt.

For an implementation guarantee `∀ x, A(x) → P(x)`, confirmation requires a checked admissible witness `x` with `A(x)` and a faithfully observed behavior for which the sound admitted oracle or proof checker establishes `¬P(x)`. Expected explicit errors are values, not automatically defects. An undeclared exception, malformed result or forbidden nondeterministic behavior can refute a separately named totality, result-profile or behavior predicate. A timeout alone cannot refute an unbounded mathematical termination claim. Any oracle equivalence that remains trusted MUST be declared in the confirmation boundary; a known invalid oracle inference cannot confirm a counterexample.

For a mechanical predicate, confirmation records the actual predicate failure and its exact dependency identities. Missing mandatory coverage, a stale issuer or an invalid accepted output is a concrete failure when the frozen predicate requires it. No implementation input is necessary when the witness is an exact artifact/evidence state rather than a function argument.

Only this successful validation permits `CANDIDATE → CONFIRMED`. A refuted witness is `REFUTED`. Unavailable isolation, failed infrastructure, cancelled execution or a checker unable to decide produces `REPLAY_INCOMPLETE`; it is not a confirmed violation. A syntactically valid receipt, matching hash or checker crash is not successful replay. Confirmation MUST NOT consume the finding's own proposed confirmation as an input or accept a candidate-provided PASS/FAIL field.

Inputs outside the accepted assumptions, excluded surface or endpoint cannot refute the covered claim. They may motivate a separately authorized contract revision, but reviewers MUST NOT silently enlarge the existing claim. Request-to-contract omissions likewise require a named fidelity/coverage predicate and a concrete checked request-span/claim mismatch; a speculative concern about natural-language interpretation is insufficient.

## 3. Tier decisions and mechanical vetoes

Every reviewer reports its completed search, concrete findings, actual replay dispositions, consumed budgets and uninspected material. Every reviewer MUST construct at least one concrete probe even when it finds no defect. A completed accepting search requires every constructed probe to replay as `NOT_REPRODUCED`; its conclusion is `NO_COUNTEREXAMPLE_FOUND`. This means no confirmed witness was found within the recorded finite search; it is not a proof, a confidence estimate or a promise about future inputs.

A fully completed bounded search may support `ACCEPT` or escalation under the frozen consensus policy without fabricating a defect in correct code. Failed required inspection, execution or replay remains `INCOMPLETE`/`ABSTAIN` as appropriate, even when no counterexample was found. Infrastructure incompleteness has its own terminal reason and cannot be disguised as either a technical rejection or completed acceptance.

An unresolved `CONFIRMED` violation of a required claim vetoes acceptance at every tier. An observed required mechanical predicate failure also vetoes acceptance regardless of votes. The latter is already mechanical evidence and needs no reviewer invention of an additional input. Other reviewers may challenge the witness through a bounded independent replay; an opinion or majority vote cannot dismiss a still-valid confirmation.

All tiers, slots and responses remain in the configured denominator. Missing or malformed responses cannot become acceptance. Repairs create a new candidate/root and rerun affected checks and review; they do not erase the old finding or make its historical observation false.

## 4. Witness preservation and new campaigns

Shrinking is finite search for a smaller witness of the same named violation. Preserve the original input and its successful confirmation. Each retained smaller witness MUST independently reproduce the violation under the same assumptions, endpoint and artifact identity. Store its input hash, replay receipt and relation to the original. A smaller input that only times out, changes the violated claim or falls outside assumptions cannot replace the original. Do not claim global minimality merely because a bounded shrinker stopped.

A counterexample outside a completed sampled case set can refute a required implementation guarantee and block release. The original finite campaign's historical `TESTED: PASS` remains a true statement about that campaign's recorded cases and criteria. Do not rewrite its plan, receipt or outcome as though the new input had been tested earlier. Add the discovered input to a new frozen campaign, retain discovery provenance, and execute it through that campaign's registered backend. Review/release targets change according to their frozen evidence policy.

An oracle counterexample may instead show that a campaign's claimed acceptance predicate was not established. That is a distinct finding about the oracle or evidence claim; it does not fabricate a target-function counterexample or silently reinterpret legacy receipts as v0.2 results. Preserve the original observation and attach the invalidation/failure evidence for the precise claim that was refuted.

## 5. Proposed closed finding format

`verislop.adversarial-finding/0.2` is a proposed wire format, not a currently accepted production schema. Every object below is closed: all listed keys are required, unknown keys are rejected, and nullable fields are explicitly nullable. Artifact references contain exactly `path` and `sha256`; paths are safe relative inventory references and digests bind actual bytes. Referenced semantic values use the named bounded canonical encoding and are validated by the assigned checker. Free-form prose is explanation only and cannot supply authority.

The top-level keys are `schema_version`, `format`, `finding_id`, `status`, `kind`, `reviewer`, `target`, `witness`, `replay` and `shrinks`. Allowed status values are `CANDIDATE`, `CONFIRMED`, `REFUTED`, `REPLAY_INCOMPLETE`. Allowed kinds are `IMPLEMENTATION_COUNTEREXAMPLE`, `ORACLE_COUNTEREXAMPLE`, `MECHANICAL_PREDICATE_FAILURE`. `reviewer` has exactly the campaign, checkpoint, tier, slot, search-plan hash and transcript-prefix hash shown below.

`target` contains exactly the shown keys. `obligation_id`, `revision` and `accepted_statement_hash` are nullable only for a named internal mechanical claim without an obligation revision. The claim inventory reconstructs and validates the result predicate, scope, endpoint and assumptions; the finding cannot select weaker alternatives. `witness` contains exactly `encoding`, `input`, `replay_recipe`, `expected` and `observed`; `observed` is nullable until an observation actually exists.

`replay` is null before replay, otherwise an object with exactly `checker_id`, `checker_hash`, `registry_hash`, `environment_hash`, `invocation`, `execution_inventory`, `receipt` and `outcome`. Its outcome is `CONFIRMED`, `REFUTED` or `REPLAY_INCOMPLETE`. A `CONFIRMED` finding requires a non-null observed artifact, complete replay inventory/receipt, the assigned current checker and a successfully validated violation. A replay-incomplete receipt MUST identify the observed incomplete operation, not assert a logical counterexample. `shrinks` is a bounded list of closed objects containing exactly `input`, `replay` and `preserves_claim`; each retained entry requires a confirming replay for the original claim.

The following illustrates an **unexecuted candidate**, using placeholder identities. The input artifact would encode `increment(limit=1, input=0)` for an explicitly identified boundary mutant; the expected predicate is that `limitReached` is false. It supplies no observed result or confirmation and cannot reject a real candidate. Actual findings require the real artifact bytes, hashes and frozen claim inventory.

```json
{
  "schema_version": "0.2",
  "format": "verislop.adversarial-finding/0.2",
  "finding_id": "F-boundary-1",
  "status": "CANDIDATE",
  "kind": "IMPLEMENTATION_COUNTEREXAMPLE",
  "reviewer": {
    "campaign_id": "review-example",
    "checkpoint": "release",
    "tier_id": "R0",
    "slot_id": "critic-1",
    "search_plan_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "transcript_prefix_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  },
  "target": {
    "review_target_root": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "claim_id": "END_TO_END_VERIFIED:E1@1",
    "obligation_id": "E1",
    "revision": 1,
    "accepted_statement_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "result_predicate": "vscore-end-to-end/0.1",
    "endpoint": "restricted_source",
    "artifact_inventory": {
      "path": "review-inputs/artifacts.json",
      "sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    },
    "claim_inventory_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "scope_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "assumptions_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "exclusions_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  },
  "witness": {
    "encoding": "verislop.contract-instance/0.2",
    "input": {
      "path": "findings/F-boundary-1/input.json",
      "sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    },
    "replay_recipe": {
      "path": "findings/F-boundary-1/replay.json",
      "sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    },
    "expected": {
      "path": "findings/F-boundary-1/expected.json",
      "sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    },
    "observed": null
  },
  "replay": null,
  "shrinks": []
}
```

## 6. Concrete acceptance regressions

The future protocol MUST exercise real replayed fixtures, recording the actual expected/observed values and checker results:

- A boundary mutant returns `error(limitReached)` at `limit=1, input=0`, where the accepted error condition requires that error only at equality. The current good example must not be accused using the mutant's observation; the exact mutated source is the target of this fixture.
- The [observed legacy oracle reproducer](tested-campaigns.md#9-compatibility-and-concrete-legacy-limitations) evaluates `∃ b : Bool, ¬(∀ n : Nat, n ≤ 100)` with inner samples `[0,1,2]` as exact false, while `b=false, n=101` witnesses truth. Replay this concrete inference mismatch against the real evaluator and the named exact-negative predicate. The earlier audit observation is not a v0.2 finding receipt until this protocol's checker and bindings exist.
- Delete a mandatory case/call/coverage receipt from an isolated frozen-campaign copy. Its registered completeness validator must reject that exact inventory. If the validator accepts it, the accepted incomplete inventory and missing required identity are a concrete counterexample to the validator's meta-contract. Merely asserting that coverage “could be inadequate” is insufficient.
- Change a receipt's input or artifact hash, assigned issuer or expected predicate in an isolated copy. Retain whether the actual binding checker rejects it. An accepted mismatched receipt refutes a named binding predicate; a rejected mutation is a successful negative check, not a defect in the original candidate.
- Reject fabricated outputs, missing replay artifacts, wrong-scope inputs, stale checker hashes and shrinking that loses the original violation. Exercise completed bounded search with `NO_COUNTEREXAMPLE_FOUND`, missing required reviewers, required mechanical failure despite unanimous votes, and a new out-of-campaign witness that preserves the old finite campaign's historical PASS.

These regressions establish the finite protocol behavior that was exercised. They do not prove the supervisor, oracle, harness or all reviewed programs correct. The [campaign specification](tested-campaigns.md) defines the separate proposed `TESTED` claim and its external trust premises.

## 7. Implemented reviewer response and receipts

The current response records `verdict`, `reviewed_obligations`, `search`, `findings`, `limitations` and `rationale`. `search` has exactly `method`, `attempted_cases`, `probes` and `conclusion`. It must contain 1–8 distinct closed probes, and the count must equal their number. A `target_case` for the bounded-increment example is:

```json
{
  "kind": "target_case",
  "obligation_id": "E1",
  "assignment": [{"int": "0"}, {"int": "0"}]
}
```

These values instantiate the accepted leading universal binders in order. The supervisor derives the expected predicate from reconstructed accepted IR, executes the current linked target and evaluates the exact supported residual. The wrong-boundary implementation using `input <= limit` returns `ok(1)` here, where the accepted error guarantee requires `error(limitReached)`; this is a confirmed violation. The correct implementation does not reproduce it. Guards must hold before a logical counterexample can be confirmed. A totality/encoding fault names its separate target-profile predicate.

Each probe receives an immutable `verislop.review-counterexample-receipt/0.2` under `reviews/<campaign>/counterexamples/<slot>/`. The receipt retains the proposal/hash, checkpoint, checker identity/hash, exact input bindings, named claim, expected and observed results, and diagnostics. Bindings include only roots and inventories relevant to the checkpoint: generating an implementation later cannot stale an unchanged interpretation or formal-contract vote. Its status is `CONFIRMED`, `NOT_REPRODUCED`, `UNSUPPORTED` or `INFRASTRUCTURE_FAILURE`. The model supplies none of these authoritative receipt fields.

Saved ballots use `verislop.review-ballot/0.2`, preserving both reported and supervisor-derived verdicts and the ordered receipt references/hashes. A confirmed probe always produces a blocking effective `REJECT`, even if the model reports `ACCEPT` or marks its finding minor. An accepting effective vote requires a reported complete search and every probe `NOT_REPRODUCED`. Other dispositions become `ABSTAIN`; the configured unanimity/quorum rule then applies. A confirmed required violation vetoes both rules.

`review tally` and release gates parse the raw response again, validate the original bound inputs, independently replay the probes and reconstruct the effective vote. Mechanical replay may compare a newly issued evidence record with the original only after both validate: it excludes exactly the evidence-record/result binding keys and `observed.evidence_id`, retaining the claim, roots, outcome, reason and other observations. This limited projection preserves Tier 2 review reuse across equivalent fresh mechanical executions.

Current replay admits at most 32 target invocations per probe, a five-second target/oracle deadline, 4096-bit oracle arithmetic and 1024-digit numerals. The target syntax is deliberately narrow: pure function bodies, direct admitted calls, arithmetic/branches and literal exceptions; imports, I/O, reflection, nested functions, defaults, annotations and decorators are unsupported. Budget exhaustion cannot confirm a defect. Tests include an actual false-confirmation regression involving printed exception-shaped protocol text, and reject both direct output and builtin aliases before execution. No live-service LLM conformance is claimed by the mock-provider regressions.
