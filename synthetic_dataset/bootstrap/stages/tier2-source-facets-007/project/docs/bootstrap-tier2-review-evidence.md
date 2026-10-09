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
