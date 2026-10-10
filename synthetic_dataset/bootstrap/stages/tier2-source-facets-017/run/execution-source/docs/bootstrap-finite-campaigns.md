# Specification: exhaustive finite Tier 0 campaigns

Written before implementation. The arithmetic-003 live gate exposed a distinction
missing from the tester: a closed conjunction of the two public example calls has
exactly one binder assignment, both linked target calls passed, and two independent
graders passed every original A23 case; nevertheless the campaign required twenty
distinct assignments and blocked. The reviewer correctly reported this mechanical
failure. Preserve that outcome; do not pad formulas with dummy binders, change the
model's artifacts, lower the unbounded sampler threshold or rescore that run.

New frozen configurations gain an explicit finite-domain policy, bounded by 4,096
outer assignments. Compute the cardinality from the accepted leading binder sorts,
with a bounded traversal before materialization: Bool, Unit, enums, finite Option,
finite Result and acyclic records of finite fields. A closed formula has one empty
assignment. Nat, Int, String and arbitrary-length List domains remain non-finite.
A domain above the enumeration cap uses the existing sampled criteria and records
why exhaustive coverage is unavailable; it cannot claim exhaustion.

For a domain within the cap, enumerate each Cartesian assignment exactly once and
complete the whole domain even if cases_per_obligation is smaller. PASS requires
at least one actual effective target case, no failure, timeout or indeterminate
case, and every domain assignment accounted for as an effective exact case or an
exact target-free false caller antecedent discard. All-discarded, pure/no-target,
unknown residual quantifiers, partial enumeration and budget failures stay blocked.
Exact functional mismatches and channel failures keep their existing precedence.
New finite-policy campaigns also refresh the target evaluator budget for each
assignment in legacy profiles (200,000 steps, range limit 4,096); structured
reference-preflight campaigns keep their separately frozen per-case budgets.
The twenty-case minimum remains unchanged for every sampled campaign. Old frozen
configurations without this policy keep their historical behavior.

Persist mode, domain cardinality, enumeration cap, accounted assignments and exact
completion in native evidence/results and clean-build replay summaries. The finite
claim concerns this accepted property and linked target calls only; it does not
establish universal Python correctness or natural-language fidelity.

Regression checks must execute real correct and wrong-output closed properties,
a finite Boolean/record domain, a finite domain larger than requested samples,
a rejected all-discarded campaign, indeterminate/residual-unbounded behavior,
excess-cardinality sampling and old-config preservation. Rerun original A23 under
a new frozen source root, then D21. Positive contracts and code must still come
only from fresh live model responses to original prompts and native CLI contexts.
