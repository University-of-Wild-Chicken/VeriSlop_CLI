# Specification-first terminal validation for Tier 2 bootstrap runs

The sealed stage 008 A23 run contains a native CLI PASS (exit 0), a VERIFIED
mechanical execution with two matching clean builds, and accepted formal-contract
and release reviews. Its bootstrap aggregate remains BLOCKED. Preserve that run,
its source snapshot, all receipts and its terminal seal. Corrections require a new
source freeze and fresh author/reviewer requests; do not rescore the old run into
a successful experiment.

Two terminal discrepancies are concrete: the bootstrap counts the proved
contract-level non-vacuity witness as an implementation guarantee, although the
registered lifecycle marks implementation milestones NOT_APPLICABLE for that
kind; and its current review observation differs from the native report. Resolve
the latter's exact field-level cause before implementation. A summary flag is
never sufficient evidence for either correction.

## Required obligation coverage

Reconstruct obligation identity, role, kind, requiredness and current lifecycle
from the native package and compare them exactly with the report. Compute the
required implementation guarantee set using registered lifecycle applicability
on those validated records. Every applicable required guarantee must have a
current END_TO_END_VERIFIED PASS. Non-vacuity witnesses remain required at their
contract milestones, including PROVED, and do not acquire implementation claims.
Never infer applicability from a model-supplied outcome, missing field, arbitrary
ID prefix or an unsupported implementation guarantee. Missing, extra or altered
records and any applicable required PENDING, STALE, UNSUPPORTED or FAIL block.
An empty applicable implementation set cannot establish the endpoint.

Retain separate counts for all required guarantees, applicable implementation
guarantees, applicable PASS outcomes and required non-vacuity witnesses. The
complete native mechanical graph must still contain every applicable required
claim and every required claim must pass. No contract or source-policy obligation
is deleted, weakened or marked optional to obtain acceptance.

## Exact configured release observation

The bootstrap's read-only review revalidation must use the same frozen provider
configuration and endpoint-profile inputs as the native worker. Validate these
inputs against the preregistered inventory before selecting that context. Ambient
user profiles must not replace the cohort's endpoint resolution. Scope any
simulation environment to the read-only observation, restore all prior values
even on errors, and make no provider call or ballot mutation.

Compare the report with the current registered review gate at the exact fields
that the report publishes. Preserve every configured checkpoint, configuration
and model-resolution binding, consensus certificate, concrete probe receipt,
current review target and diagnostic. Any genuine disagreement remains BLOCKED;
do not discard diagnostics, trust the report's ACCEPTED flag or bypass replay.
Inspect the exact retained witness to determine whether a provider context or
report projection correction is necessary. Document that cause before changing
the corresponding code.

The retained read-only field comparison confirms the exact review discrepancy:
outside the worker's provider context, the production gate reports
CONFIGURATION_INVALID because the frozen `collaboration-simulation` endpoint
profile cannot resolve; its checkpoint map is empty. The native report contains
the two accepted checkpoint observations produced in that worker context. The
report serializes the gate without omitting fields. Correct the bootstrap's
provider context, retain the production gate and its diagnostic comparison, and
leave report serialization unchanged. The diagnostic comparison's full package
inventory was identical before and after the observation.

## Regression and bootstrap gates

Retain a field-level diagnostic of stage 008 outside its sealed cohort. Use
unrelated fixtures to exercise native bootstrap terminal validation with both
formal-contract and release reviews, two clean builds, source/value obligations,
and a required non-vacuity witness. Include concrete negatives for wrong ambient
profiles, altered frozen profiles, missing applicability fields, altered
requiredness/kind, failed applicable guarantees, unproved required non-vacuity,
missing review, forged report acceptance and mismatched consensus/diagnostics.
No test may treat an authored PASS flag as proof of a live task outcome.

Qualify the corrected generic harness and affected native source/review paths
before publishing a new source freeze. Then run A23 from its public natural
language prompt with fresh stateless model roles and the normal strict CLI,
without old candidates, proofs, hidden cases or task-specific patches. Audit and
seal its terminal outcome before starting the independently generated D21 run.
Keep TESTED pending and the endpoint restricted_source; this revision supplies no
Python, compiler or machine-code assurance and introduces no inference timeout.
