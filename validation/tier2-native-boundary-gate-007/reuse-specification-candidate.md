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
