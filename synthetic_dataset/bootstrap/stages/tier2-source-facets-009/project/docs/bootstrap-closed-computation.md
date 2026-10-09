# Specification: proof-producing reduction of closed contract examples

Written before implementation. The frozen native-grouping-001 run records failed
`rfl`/simplification proofs of public-example equalities; repetition of an already
rejected proof is not evidence that the contract is false. Preserve that run and
let its configured recovery finish. Never inject a supervisor-written positive
proof, corrected example or implementation into its model context.

An independent, unrelated catalogue fixture demonstrates the generic gap in the
existing portfolio. It combines String sorting/deduplication, signed quotient,
map/fold and record-valued output. Reflexivity fails; plain `decide` lacks record
equality instances. Derived equality plus `decide +kernel` still leaves the
computation stuck. Lean 4.34.1 `cbv` reduces it with proof-producing computation;
ordinary simplification then closes the resulting conjunction. Record equality
instances and a change in carrier semantics are unnecessary.

Add `(cbv <;> simp_all <;> done)` as an untrusted proof-search alternative for structured
value guarantees whose formula contains no logical forall/exists node. Inspect
only the reconstructed formula, using a bounded traversal. A malformed or
oversized formula is ineligible. Use the all-goals combinator because `cbv` may
already close the compiler-generated goal; unconditional subsequent tactics then
produce `No goals to be solved`. This is a conservative search eligibility rule,
not a new accepted contract language, a completeness claim or a decidability
judgment. Keep existing alternatives and existential witness search unchanged.
For an exact mixed value/native conjunction, the alternative may operate on that
existing conjunction; it cannot remove its native proof obligation. Native-only,
opaque and unregistered statements do not receive this alternative.

The compiled proof and every dependency still undergo the existing pinned Lean
kernel replay, axiom policy, frozen-definition/statement equality, accepted-AST
reconstruction, denotation and origin checks. Do not use `native_decide`, evaluator
observations, axioms, cached proofs or trusted assertions as proof evidence. Keep
all current finite candidate build limits; a failed or exhausted reduction is an
unresolved proof and never a disproof, PROVED milestone or weaker specification.
Add generic `cbv` guidance to the prover and autonomous critic prompts without a
task-specific proof. Remind proof-stage critics that definitions, instances and
imports are frozen, and that native reduction/axioms are forbidden. Corrections
are untrusted advice; ordinary proof checking remains the enforcement boundary.

Engineering checks must compile and kernel-replay unrelated structured closed
examples without record DecidableEq, verify exact original theorem denotation,
reject a deliberately incorrect example at acceptance, and retain unresolved
false/quantified goals. Check bounded eligibility and preservation of existential
and native-only behavior. Retain exact command results and source hashes.

After the preceding live outcome is sealed, freeze a new source/specification
root and run the original D21 natural-language prompt through every strict gate
using fresh model roles. No previous positive artifacts, hidden cases, graders or
oracle outputs enter generation. Required TESTED campaigns, concrete adversarial
review, two clean builds, exact origin audit and both original-case graders must
all pass. Tier 0 finite closure does not establish END_TO_END_VERIFIED.
