# Specification: source-bound native facets of a strict contract

Written before implementation. Grouping-007 retained seven fresh responses and
ended BLOCKED. Its required O1 includes the Python entry/layout/purity/interface;
R1 requires standard-library-only code and no external I/O. The value DSL can
describe aggregation, but cannot observe those source requirements. Preserve both
IDs, kinds, roles and required flags. Do not turn them into exclusions, optional
metadata or caller preconditions, or substitute an unrelated value equality.

Independent in-memory audit also confirmed concrete gaps in current checks:
review admission accepts writes to input subscripts, append and += on borrowed
lists, and writes to borrowed nested records through a shallow copy. Duplicate
top-level functions let inventory select the first span while Python executes the
last definition. Native materialization currently lacks the review admission gate.
Those admissions are negative correctness fixtures, not live positive artifacts.

## Formal boundary and accepted artifact

Introduce a closed, versioned NativeRequirement algebra in a verifier-owned Lean
model. Initial constructors identify an accepted implementation symbol and request:
entry file/name/arity; closed pure JSON source; standard-runtime-only dependencies;
absence of target-attributable external I/O; preservation of input-reachable mutable
objects; deterministic local evaluation. Unknown constructors/policies fail closed.
Physical time/memory/I/O-count bounds and general liveness remain unsupported.

Define a restricted structural module model, its requirement predicate
`HoldsBoundary requirements module`, and `checkBoundary requirements module : Bool`.
The model has explicit entry identity, closed-name/call-graph facts and ownership
facts. Its evaluation primitives are the registered pure JSON primitives. If an
abstract fact model is used, the Python AST-to-fact computation is explicitly
trusted and source-bound; a theorem about facts is never described as a proof of
the Python parser, compiler or runtime.

The formal proof obligation is the exact transfer law:

```
∀ module, checkBoundary requirements module = true →
  HoldsBoundary requirements module
```

This proves the contract's structural model rule, not purity of arbitrary future
Python. The premise is an implementation-selection requirement. It is never a new
caller assumption, and cannot be left undischarged at LINKED or TESTED. Actual
generated source must supply a current registered checker receipt. Keep PROVED
scoped to the accepted formal model and native conformance scoped to that receipt.
Require kernel-checked admission inhabitation for a well-formed boundary policy;
an always-rejecting policy must not close the contract vacuously. This inhabitation
witness is a generic structural model witness, not a supplied live implementation.

Allow a guarantee to have a value facet, native facets, or both. A mixed guarantee
binds the conjunction of its value proposition and native transfer law(s); every
facet is required. Native-only R1 still has a real kernel-checked model theorem.
Any projected value formula must be mechanically related to the exact accepted
conjunction by kernel-checked projection/equivalence evidence, not copied from the
original candidate JSON. No facet can make another optional.

Extend typed proposals with native requirement definitions and explicit facet
bindings. Agents author the requirements, parameters, target symbol and bindings;
they provide no PASS fields, observations, ownership facts or checker receipts.
The compiler emits the registered Lean constructors and exact theorem obligations.
Proof agents/critics use the normal frozen-statement/kernel process. Reconstruct
native requirements, parameters, targets and value facets from the accepted Lean
AST and accepted registry. Check the exact transfer theorem type against its
requirement definition, model version and target declaration. Original proposal
JSON has provenance authority only. Persist all intermediate candidates and checks.

## Actual source checker

Create a registered, versioned source checker over the exact staged source bytes
and accepted requirement graph. It must independently re-parse the module and
compute observations; proposed receipts or Boolean assertions confer no authority.
The initial admitted language may be conservative, but must support the existing
pure data-pipeline loops, comprehensions, fresh lists/dicts and helper functions.
Conservative unsupported ownership patterns return a concrete AST diagnostic for
agent correction. They are not a counterexample to returned-value behavior.

Require unique top-level function names and a unique requested entry definition.
The file, normalized function name, arity and linked runtime callable must agree.
Reject imports, executable module statements, decorators, annotations, defaults,
classes, reflection, persisted mutable state and unsupported call constructs.
Calls resolve through lexical scope to admitted helpers or registered pure
primitives; reject shadowed/dynamic targets and unsupported/cyclic call graphs.

Arguments, indexed children, iterated children and unknown helper returns are
borrowed. Fresh list/dict allocation owns its root. A shallow copy owns its root
but its descendants remain borrowed. Subscript stores, append and mutating
augmented assignment require a proven fresh receiver. Track aliases through
assignments, branches, comprehensions and loops. Reject a pattern when its sound
ownership result cannot be established within explicit bounds. Never equate a
local variable name with fresh ownership. Helper parameters are borrowed; a
conservative checker may reject mutating helpers and unsupported return summaries.
Do not infer totality from purity. Reject mutation of active iterables or state its
supported rule precisely; candidate execution retains its finite resource limits.

These rules establish the closed/pure/frame conditions under explicit CPython,
typed JSON adapter, parser and checker trust. Host staging/compilation/harness I/O
is outside target-attributable I/O. Only standard-runtime primitives are available.
The deterministic predicate is scoped to repeated evaluation of the same canonical
typed adapter input. Fixed records decode with their accepted field order, lists
retain element order, and fresh dictionaries follow deterministic insertion order.
This does not assert invariance under Python dictionary equality when two raw
objects have different insertion orders, nor behavior of arbitrary objects passed
directly to an unwrapped Python function. Retain this exact semantic domain in
checker receipts and declared trust. Value facets still specify actual result
ordering independently of the source determinism check.
Supporting every standard-library import is not required. A stricter closed subset
still satisfies a requirement allowing only standard-library facilities.

## Pipeline integration and claims

Derive requested entry layout from accepted native requirements, preserving the
legacy default only when no layout requirement exists. Validate safe relative
paths and consistent entry requirements. Tell the implementer the exact accepted
layout. Do not rename or patch a captured implementation response after generation.

Invoke the source checker on native materialization, linkage, test execution,
reviewer replay and both isolated closure rebuilds. A source violation produces
the exact file/AST path/rule and returns through the normal bounded implementer
repair loop. Bind receipts to the complete artifact inventory, entry identity,
accepted IR/requirement/transfer hashes, parser/runtime versions and checker rule
hashes. Changed files, requirements, parsers, rules or detached receipts invalidate
evidence. Duplicate definitions must be rejected before inventory/function binding.

Claim generation must include native-only guarantees and all mixed facets, even
when a facet has no runtime formula. Native IMPLEMENTED/LINKED/TESTED checks refer
to actual source compliance. Dispatch structural resource requirements by accepted
representation; retain rejection of unsupported physical resource predicates.
TESTED for a mixed obligation requires its original runtime campaign and every
source facet, with current TYPECHECKED, IMPLEMENTED and LINKED evidence. A
native-only structural predicate has an exact source-check surface,
reported separately from runtime samples, plus actual finite typed calls to its
bound entry. Reuse accepted argument sorts and caller guards, with the existing
sampling thresholds. Check serialization, input-frame preservation and repeat
outcomes, including modeled failures where supported. A zero-invocation campaign
cannot obtain TESTED. Capture pre/post arguments inside the harness when frame
observations are needed; host-side transport copies cannot establish that property.
For native-only runtime sampling, use the bound entry's accepted argument sorts.
Target-free leading guards common to every required value campaign of that exact
signature may select samples; retain their accepted package hashes and exact ASTs
in the sampling receipt. This is finite sample selection, not a new caller
assumption or a restriction of the static boundary check, which covers all source.
Each selected case executes twice with freshly decoded arguments. Compare actual
typed results or supported deterministic exception envelopes and both in-harness
pre/post snapshots. Timeout, missing snapshots and exhausted encoding budgets are
incomplete, not effective successful cases. Preserve actual invocation counts and
observation hashes; static admission never supplies runtime samples.
Do not fabricate software calls or pad static checks to twenty cases. Runtime value
guarantees retain their original oracle, actual target calls and all existing gates.

Reviewers must construct concrete source-violation probes (wrong entry, duplicate
definition, unclosed call or borrowed-write AST site) and replay the current
registered checker against exact artifact hashes. No speculation or invented
functional counterexample can reject a source facet. Checker infrastructure errors
remain incomplete and cannot become confirmed functional failures.
Use a closed review proposal with exactly `kind: source_violation`,
`obligation_id`, `file`, `ast_path` and `rule`. The rule is a registered diagnostic
code, and the file/AST path must exactly match a freshly computed scoped checker
diagnostic on current source bytes. Bind the receipt to the current accepted
statement/package and the entire source inventory. A cited site with no current
violation is NOT_REPRODUCED; unsupported analysis is incomplete, not a confirmed
source counterexample. Mixed value probes retain their existing exact runtime
oracle and must never execute rejected source.

## Ordered checks and fresh runs

1. Implement the independent closed-source/ownership checker and entry identity.
   Regressions include all audited mutations/duplicates, shallow nested aliases,
   helper-mediated mutation, shadowed calls, branch/loop alias merges, active
   iterable mutation, accepted fresh local writes and pure pipeline composition.
2. Implement the Lean native algebra, real kernel-checked transfer law,
   accepted-AST reconstruction, typed authoring and mixed-facet projection. Reject
   changed requirements/theorems/model versions, missing native facets and forged
   positive metadata. Keep every original interpreted obligation.
3. Bind native claim dispatch, all pipeline checks, layout, repair diagnostics,
   constructive review and two clean closure checks. Regress stale/forged receipts,
   wrong-file bindings, native-only and mixed obligations, resource scope and
   preservation of the old campaign/configuration behavior.

Freeze coherent sources after these registered checks. Run an original corpus
instance through the whole strict CLI at the first coherent native increment,
then original D21 with mixed value/native requirements. Use fresh model agents,
original natural-language prompts/public examples and normal native feedback only.
Never supply handwritten positive contracts/code or hidden grader answers. Retain
the actual outcome at every increment and keep old runs immutable. Completion
requires D21 native PASS/TESTED, all required facets, finite VERIFIED closure, two
clean builds, exact origin and all original cases in both independent graders.

Tier 0 remains ineligible for END_TO_END_VERIFIED. This milestone supplies no
machine/compiler-chain verification, universal Python totality proof or new
unbiased full-corpus benchmark.
