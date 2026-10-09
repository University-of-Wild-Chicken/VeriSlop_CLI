# Specification: repair campaign quantifier shape before freezing

Written before implementation. In the fresh arithmetic-005 run, Lean accepted a
public-example conjunction containing an additional unbounded universal equality.
The actual native campaign reports O3 TEST_INCOMPLETE while its four other
guarantees pass. Retain this result and every exact response; do not repair that
frozen contract or count an indeterminate campaign as TESTED.

When evaluated, the structured DSL evaluator intentionally returns UNKNOWN for
residual unbounded universal quantifiers, even after successful samples. Reference preflight likewise
cannot establish an unbounded existential with its empty candidate callback. The
campaign samples only a leading universal prefix. Kernel acceptance and DSL
reification therefore do not establish executable campaign readiness.

Extend the existing agent candidate-readiness check for required Python Tier 0/1
TESTED/test_campaign guarantees in structured DSL 0.2. Inspect the formula
reconstructed from Lean, remove only its leading forall prefix for inspection, and
report each residual forall/exists over a non-finite sort, with its exact formula
path, tag and sort. This syntactic readiness rule is conservative: a branch may
short-circuit before a residual quantifier, so do not claim that every such formula
necessarily evaluates to UNKNOWN. Use a bounded traversal and existing sort judgments; do not
materialize finite domains. Finite Bool/Unit/enumeration/record/Option/Result
quantifiers and explicit range quantifiers remain admitted. Preserve legacy
campaign behavior, other tiers/endpoints, standalone formalization and explicit
candidate behavior.

Return INVALID_CANDIDATE to the existing bounded author/critic repair loop before
the challenge freezes. Explain that this is a test-language representation issue,
not a counterexample to the Lean theorem or the software. Ask for a faithful
pointwise or finite-range representation preserving every obligation, dependency,
guard and requested domain. A leading universal binder may express an equivalent
pointwise conjunction when the admitted domain is inhabited; do not universally
replace an existential, bound an infinite domain, remove examples or weaken a
claim. The model must supply its own replacement, which undergoes the original
kernel/denotation/readiness/critic checks. No supervisor-supplied corrected source,
obligation, proof or implementation is permitted.

Give generic quantifier-shape guidance in the formalizer prompt. Persist rejection
diagnostics and raw/assembled candidates through the existing memory mechanism.
Do not change the test evaluator's three-valued semantics, sample minimums,
preflight, closure, grader inputs or origin rules. The diagnostic path and accepted
sort constitute a concrete mechanical failure; no speculative reliability report
or fabricated functional counterexample should be accepted.

Regressions must demonstrate rejection of unbounded residual forall/exists,
admission of equivalent leading-prefix formulas and finite/range quantifiers,
preservation of excluded modes and actual bounded agent repair with retained
response/diagnostic provenance. Then freeze new source roots and rerun original
A23 and D21 without historical answers or hidden grader feedback.
