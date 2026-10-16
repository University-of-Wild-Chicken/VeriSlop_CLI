# Agent Effect DSL prototype v0.1

Source baseline: `267719bbb39d8bfdce147823788604528bf56169`.
This finite structured AST prototype adds no dependencies and leaves the default
execution flow unchanged. It is not a formal proof or a general agent language.

## Extracted existing contracts

| Semantic operation | Actual inputs | Model output (untrusted) | Required configured profile | Existing resource/acceptance constraints |
| --- | --- | --- | --- | --- |
| prove | Frozen Lean challenge, statements, previous candidate/errors/critique; optional frozen theorem headers | Complete Lean source, or theorem fragments assembled against frozen headers | proof_sandbox | Bounded proof attempts, optional proof-search deadline, Broker calls/output/retries; frozen scaffold/statement checks and Lean acceptance/export remain authoritative |
| prove-vscore | Accepted reference/packages/profile, fixed source and relation hashes, generated bridge goal, verifier library, toolchain, previous proof/checker diagnostics | Bridge proof source or fragments | proof_sandbox | Bounded source/proof proposals, MAX_PROOF_BYTES, ordinary VSCore bridge checker/build policy, Broker limits |
| review | Frozen review target root, packet, checkpoint guidance, lower-tier findings, prior ballot protocol feedback | Ballot with counterexample probes | review_readonly | min(MAX_BALLOT_PROTOCOL_ATTEMPTS, calls-per-instance), tier wall limit, Broker limits; ballot validation, probe replay, identity check and consensus |
| generate | Accepted IR/formulas/profile, binding manifest and fixed parameters; VSCore additionally fixed accepted context | Python files/bindings or VSCore program/relation and optional proof | candidate_writer | Python at most min(3, requested attempts, call cap); VSCore source/proof caps, source/relation/proof validation and Broker limits |

Extraction locations: `agents.recorded_call`, `_proof_completion`,
`implementer_agent`, `_vscore_implementation`, and `review.run`'s `review_slot`.
The profiles above are prototype requirements, not a claim that all legacy
prover/implementer role assignments were already constrained by config.resolve.
VSCore proof requests use legacy Broker purpose `generate` for complete-file
responses, and `prove-vscore` for theorem fragments. Purpose strings alone do not
identify authority. The DSL separates semantic operation from transport purpose.

## AST and typing

`agent_effects.parse` accepts strict canonical JSON or a structured dict:

```json
{"version":"0.1","steps":[{"op":"review","agent":"critic","instance":"R0/critic#1","artifact":{"kind":"review_packet","identity":"campaign/target","sha256":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"effects":["read","infer","propose_ballot"],"output_tokens":4096,"retries":2}],"limits":{"calls":1,"output_tokens":4096,"attempts":3}}
```

The AST is immutable `Artifact`, `Operation`, `Plan` dataclasses. `check(plan,
conf)` also validates directly constructed ASTs. Unknown fields, operations,
missing identities, malformed SHA-256 digests, booleans in numeric fields,
unknown agents, mismatched profiles and effect escalation fail closed.
Artifact types are `lean_challenge`, `vscore_goal`, `review_packet`, and
`accepted_contract`. These are host declarations; an identity and digest do not
prove provenance, existence or mathematical acceptance. No file is opened by the
checker. Outputs are respectively `proof_proposal`, `proof_proposal`,
`ballot_proposal`, `candidate_proposal`, all untrusted; there is deliberately no
rule that promotes a proposal to an accepted input or grants a capability.

Judgment: under trusted configuration Γ and artifact declaration A,
Γ ⊢ op(A) : Proposal ! E when A has the signature's input kind, the agent has
its required profile, and E equals the fixed signature. Proof operations have
{read,infer,propose_proof}; review has {read,infer,propose_ballot}; generate has
{read,infer,propose_candidate}. No shell/write/network-execution primitive is
exposed. `infer` means Broker inference (including its provider network request),
not arbitrary network access. `read` means consuming supplied artifact data,
not arbitrary filesystem reads. Broker transcript writes are trusted host
bookkeeping and are not reviewer write authority.

Sequential composition unions effects and adds call counts, output allocations
and worst-case transport attempts (1 + retries per call). Calls accumulate by
Broker instance key even across agents. Plans must fit declared plan limits,
configured per-instance calls and total-token ceiling for output allocations.
Annotations must exactly match Broker output/retry configuration so lowering
cannot silently request a larger allocation. No branching, loops, parallel
composition, artifact references between steps or implicit subeffect coercion
are supported. `check` returns the composed effect set and executes nothing.

## Opt-in review lowering and limits

Add `"agent_effect_dsl": {"enabled": true}` to a normal review configuration.
Omission or false preserves the existing Broker dispatch. `review_slot` now calls
`agent_effects.review_call`, which constructs and checks a one-operation plan
before delegating the exact existing arguments to Broker.call. An explicit
configuration argument must equal `broker.r.conf`; it cannot substitute another
agent profile or disable the enabled checker. Lowering uses the actual Broker
Budget's call/token limits and retry allowance, including an explicitly supplied
shared/custom Budget, without changing the stored configuration. Host code supplies
the target root and hashes the exact system/user/target payload. It never parses
capability declarations from model text. The response goes through all existing
review validators unchanged. A rejected effect check is retained as an
`effect_check_failed` attempt and missing reviewer in an incomplete consensus
certificate, without provider dispatch or an uncaught worker exception.
The generic four-operation checker is implemented;
only review lowering is integrated. There is no whole-campaign static plan.

The static output sum is an allocation check, **not** an upper bound on total
input+output usage. Broker still checks shared call/token counters and enforces
provider concurrency, configured output caps, retries, model pins and credential
checks. With the companion [token-budget patch](token-budget-audit.md), Broker
atomically reserves a prompt-byte/output estimate before dispatch, settles
reported usage after completion, and releases the reservation on all exits.
This is a shared soft admission policy; missing usage, retries and estimates
that understate actual usage can still cause overshoot. The static DSL check
adds no strict actual-token cap, OS sandbox, filesystem ACL, tier-deadline proof or provider timeout
proof. Rechecking a plan does not reserve budget or prevent replay; repeated
integrated calls remain bounded by the existing shared Broker counters.

Keep four results separate: DSL typing checks host-authored structure and
allocations; runtime isolation concerns actual tool/OS enforcement; Lean checks
specific submitted propositions under its existing trust boundary; model behavior
remains untrusted text. None implies formal verification of natural-language
reasoning or end-to-end permission safety.

Run deterministic tests (no credentials or inference):
`python -m unittest discover -s tests -p test_agent_effects.py -v`.

## Validation in this change

The results below came with the original patch. The combined local integration
and subsequent fixes are recorded in [the integration audit](patch-integration-audit-20261016.md).

- Eight DSL unit tests passed; sixteen review protocol/guidance tests passed,
  including the real review entry with DSL explicitly enabled and a local mock
  provider. No live inference was used.
- Broader `test_review*.py` run before adding the integration test: 39 tests,
  four failures and two setup errors. Errors report missing pinned Lean 4.34.1;
  failures report unavailable bubblewrap/user-namespace filesystem isolation.
  These checks remain unverified in this environment; protections were not relaxed.
- No Lean theorem was introduced or claimed proved by this prototype.
