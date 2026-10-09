# Recursive source-schema validation increment

This specification precedes the performance correction. The current native
Tier 2 task stage and its frozen source tree remain unchanged. Its proposals,
diagnostics, proof obligations and eventual result retain that original root.

## Observed failure and required behavior

VSCore 0.3 expressions use a recursive oneOf schema. The local JSON Schema
validator explores recursive child fields in alternatives whose scalar tag
already fails a constant constraint. A small admitted source can consequently
require minutes of host CPU before a normal diagnostic is published. This is
host validation work, not model inference. Inference retains its existing
no-deadline policy.

Validation must accept exactly the same instances under the supported schema
language. In particular, oneOf still requires exactly one matching alternative;
anyOf, allOf, not and conditional branches keep their existing logical meaning.
Unknown tags, malformed operands, additional fields, missing required fields and
overlapping alternatives must not become accepted. No task, expression tag or
model identity receives an exemption. The intrinsically typed Lean checker,
exact source admission, universal refinement and closure checks remain required.

## Permitted optimization and evidence

Alternative selection may stop once a necessary constraint fails, because the
caller needs only whether that alternative matches. Check cheap scalar
constraints before recursively validating children. Keep ordinary published
validation diagnostics and paths intact; do not use a heuristic discriminator
that assumes alternatives are disjoint or skips matching alternatives. Any
per-invocation memoization must not persist results across changed instances,
schemas or registry state.

Reproduce the cost with unrelated nested list and integer expressions and retain
their exact canonical inputs, original validator hash, operation counts and
timings. Compare old and corrected acceptance on bounded positive and negative
instances, including absent/unknown tags, overlapping oneOf branches, references,
conditional branches and recursive child errors. Operation-count checks must
show the repeated subtree exploration is removed without relying on a machine
speed deadline.

Before a task uses the correction, freeze a new source root and run the schema
regressions and the full unrelated native Tier 2 source pipeline. Retain two
clean builds, exact source and policy mutation failures, per-ID bridge evidence
and the engineering record. No old task candidate, proof or expected value is
provided to a fresh task author. A successful engineering fixture is not a task
success or an END_TO_END_VERIFIED result for a retained benchmark instance.
