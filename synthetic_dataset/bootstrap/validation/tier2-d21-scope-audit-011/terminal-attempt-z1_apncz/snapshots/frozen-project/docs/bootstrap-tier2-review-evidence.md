# Specification-first review of scoped bridge evidence

This specification precedes the correction. The sealed A23 stage 006 has a
VERIFIED mechanical execution and matching clean builds, but its release ballot
replays as ABSTAIN. Its advertised, required
`BRIDGE:implementation:vscore-refinement` claim passes at a non-null semantic-edge
root in the registered mechanical result. The generic mechanical-probe replay
instead looks only in the top-level package evidence store and uses no
semantic-edge root. It reports PENDING with a null expected root. The claim ID is
valid; this is an evidence-resolution discrepancy, not a software counterexample.
Preserve the entire failed stage and its terminal BLOCKED status.

## Replay requirements

For a mechanical-failure probe, resolve the exact required, applicable claim at
the current checkpoint. Preserve its assigned verifier, predicate, premises,
scope and root kind. Use the selected backend's registered evidence resolver for
its frozen selected bridge: structural evidence belongs to the bridge bundle;
semantic evidence belongs to the selected semantic edge. Its current root must
be derived from the exact current plan, artifact inventory and selected edge.
Do not reinterpret that root as the contract or closure root, synthesize a PASS,
alias an arbitrary similarly named claim or trust the reviewer's supplied data.

At a post-mechanical VSCore release checkpoint, a registered validated mechanical
execution may provide the bound claim/evidence observation. Validate its complete
manifest, claim inventory, current input root, evidence references, selected
bridge, verifier hashes, source-policy bytes, and scoped roots before using it.
A report flag or projection alone is not authority. Bind every receipt to the
exact mechanical result and verification-relevant input inventory used for that
observation. Missing, duplicate, changed or stale bindings remain unresolved.

The unchanged decision rules apply: a current authorized PASS is NOT_REPRODUCED;
an authorized observed FAIL or UNSUPPORTED is CONFIRMED; unavailable or stale
evidence is UNSUPPORTED; tooling failure is INFRASTRUCTURE_FAILURE. These replay
receipts establish finite review observations only. They assign no TESTED,
IMPLEMENTED, LINKED or END_TO_END_VERIFIED state on their own. Confirmed failures
still veto acceptance, and unsupported searches still cannot accept.

Preserve explicit version dispatch and the existing Python, VSCore 0.1 and 0.2
boundaries. Correct the supervisor's evidence lookup rather than teaching an
author to avoid a legitimate required mechanical claim.

## Gates and fresh task execution

Use unrelated source-contract fixtures to reproduce the missing semantic-edge
and structural-bundle lookup. Verify exact receipt roots/evidence identities,
all advertised required mechanical claims, and release review acceptance with
those probes after a real complete mechanical execution. Exercise concrete
negative cases for changed source, bridge inputs, policy, claim inventory,
verifier identity and execution/evidence bindings. Unknown claims, absent
execution, stale execution and actual failure must not become successful probes.

Run the affected review tests and the complete native source-pipeline gate with
the pinned Lean kernel and two isolated clean builds. Freeze new specification,
source and harness inputs before fresh stateless A23 roles, followed by D21.
Do not reuse task candidates, prior proofs or old model replies. Retain all JSON,
Lean, counterexample receipts and terminal artifacts. No inference deadline is
introduced. Release still requires normal configured concrete adversarial
review and the complete current claim graph.

# Specification amendment: authenticated mechanical receipt reuse

Gate 007 exposes a concrete compatibility regression: a second valid mechanical
execution has the same registered review projection, but changes the current
execution pointer and retained physical artifact paths. A release ballot bound
to the first execution becomes stale before projection equivalence is checked.
Retain the failed gate and exact package; do not change its result.

The next revision shall validate the reuse context before rechecking a release
ballot. Both original and current executions must validate against the current
frozen claim inventory, selected scoped roots, verifier identities, closure root
and complete retained file inventories. The campaign's original packet,
inventory, projection and target must match their reconstructed values. Reuse
requires equality of the registered normalized projections and unchanged
reviewer membership, model policy and contract/source inputs.

Reconstruct each original mechanical probe observation from its exact retained
execution using the registered typed assessment. Authenticate its saved receipt
including checker, claim, expected root, outcome, reason, evidence identity and
complete binding set. For the historical pointer, accept only the exact digest
of the producer's canonical one-field pointer to that original mechanical
result. Do not rewrite receipts or replace the current package pointer.

Define a versioned, closed observation projection. Only the authenticated
execution pointer, exact result path, full execution inventory and declared
evidence wrapper metadata may be represented by their registered normalized
identities. No arbitrary field, name or path-prefix filtering is permitted.
All remaining bindings and semantic observations compare exactly. Missing or
extra bindings, changed retained artifacts, invented observations, wrong scoped
roots, unequal projections and verifier changes block reuse. Projection
equality never authorizes an execution on its own.

Fresh replay against the current execution remains decisive. Concrete confirmed
failures veto acceptance; unresolved and infrastructure outcomes cannot accept.
Nonmechanical probes, pre-mechanical checkpoints and Python behavior retain
their existing exact replay rules. This amendment adds no lifecycle state or
claim of native Python/compiler verification.

Qualification shall include the existing real VSCore 0.1 fresh-rerun reuse
regression and the analogous VSCore 0.3 source fixture, plus concrete receipt,
inventory, pointer, observation and projection tampering cases. Freeze the next
source revision and run affected tests with two clean kernel builds before
fresh stateless task authoring. No task-specific program or proof is supplied.
