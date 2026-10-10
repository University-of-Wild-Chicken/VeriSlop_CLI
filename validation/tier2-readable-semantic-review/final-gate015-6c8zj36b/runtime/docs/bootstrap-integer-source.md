# Specification: source-level absence of floating-point computation

Written before implementation. The fresh A23 interpretation retains the explicit
required S2 prohibition on floating-point computation. A concrete independent
audit admitted `ignored = data["b"] / data["m"]` followed by an integer return
under the current closed-source checker. Value equality and integer result
decoding cannot establish that no intermediate floating-point computation occurs.
Do not replace this source obligation with a value tautology or omit it.

Extend native-boundary/0.1 to model version `verislop.native-boundary/0.2` with
`no_floating_point`. Its structural model
predicate and transfer law require a computed `noFloatingPoint` fact. The existing
constructive admission witness must remain kernel checked. Recover the constructor
from accepted Lean ASTs, pin the updated normative library, and preserve each
original obligation ID/kind/role/required flag. Instantiated theorem proofs still
go through normal proof agents and Lean acceptance.

The source checker computes exact file/AST sites that could introduce floating
point: `/`, float literals, and exponentiation without a closed nonnegative integer
literal exponent. The conservative initial policy allows integer `** 0`, `** 2`,
and other such literal powers because all admitted input scalars and originating
numeric literals exclude floating-point numbers. Other powers may be implemented
with admitted integer loops. No built-in float/complex conversion or dynamic call
is available. A potential site produces `FLOATING_POINT_OPERATION` for a required
native facet, even if the expression's result is ignored or zero. It is a concrete
source-policy violation, not a claim that a returned value differs.

Before implementing the next audit repair, extend this policy to augmented
division and exponentiation and to string formatting through `%` or `%=`.
The concrete expression `"%.1f" % (2**53 + 1)` converts an integer through
floating point, despite producing a string. Retain integer modulo only when the
left operand has established integer origin. Track this fact conservatively
through typed Nat/Int/Bool inputs, integer/bool literals, admitted integer
operations, comparisons, length/range, sums, helper returns and merges. Every
possible incoming value must have integer origin; unknown or string left operands
produce an exact source-policy site. This restriction applies only when the
accepted native facet requires no floating point. It may reject integer-only
string formats conservatively; it does not parse format strings or guess their
runtime conversions.

Generic source admission may retain these deterministic scalar operations when
this facet is absent. Bind the computed sites/fact to source bytes, accepted sorts,
checker identity and model/requirement hashes. Recheck at materialization, linkage,
TESTED, constructive source review and both clean closure builds. Native runtime
samples alone cannot establish this prohibition or override a negative source fact.

Regress dead division, negative/variable exponentiation, literal float, safe literal
powers, unchanged generic/legacy behavior, accepted-AST constructor reconstruction,
missing/forged facts, exact source-probe replay and proof/library pinning. After
the already frozen source-check increment terminates, freeze a new coherent native
snapshot and rerun an original arithmetic instance through the complete strict
pipeline before the grouping instance. No prior answer or hidden grader is model
context, and every historical outcome remains immutable. Tier 0 remains ineligible
for END_TO_END_VERIFIED.
