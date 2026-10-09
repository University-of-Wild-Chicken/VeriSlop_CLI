# Specification-first Tier 2 pure-data bootstrap

This specification precedes implementation. Target instances are the original
A23 signed-arithmetic task and D21 grouping task retained in native-contract-001
and review-scope-001. Those source snapshots, contracts, results and seals remain
immutable. Standalone VSCore 0.2 admission is not an implementation refinement
and cannot assign END_TO_END_VERIFIED.

## Release boundary and contract revision

The new deliverable is canonical VSCore source under normative Lean semantics,
at Tier 2 / restricted_source. A new natural-language request explicitly revises
the language/delivery portion of each original task from Python solution.py to
program.vscore.json. Preserve all functional requirements, original public examples,
input domains, required flags and per-requirement identities in the revised
interpretation. Record the original request/package hashes and exact delivery
revision. Never rewrite the original contracts or silently discard their Python
facets. The old Python implementation/execution retains its previous assurance.

Pure source safety is stated in the new source language: admitted typed entries,
total typed execution, determinism, immutable input values, no external-effect
constructors and mathematical integer arithmetic without floating point. These
are properties of the restricted source semantics, not CPython or machine code.
Natural-language correspondence, host tooling, pinned Lean/kernel, hashing and
OS/hardware remain explicit trusted components. No Tier 3/4 claim is introduced.

## Ordered grammar increments

1. Introduce versioned vscore/0.3, profile data-pipeline/0.3 and VSCore3 modules;
   preserve 0.1/0.2 syntax and their registered meaning. Reuse the intrinsic total
   compilation architecture: successful checking produces typed Lean functions,
   and helper/declaration graphs remain acyclic. Checker budgets affect admission
   only, never truncate admitted execution.
2. Add unbounded Int and Unicode scalar String carriers, negative literals,
   exact add/subtract/multiply/comparison/negation, Int.fdiv (including zero and
   negative divisors), Int.ofNat/toNat and Unicode scalar lexicographic ordering.
   Keep natural subtraction truncated. Encode String literals as canonical arrays
   of scalar codepoints to preserve the existing ASCII core parser; reject
   surrogates, out-of-range codepoints and malformed signed literals.
3. Add total pure list length/range/index/append/reverse, ascending stable scalar
   sort and first-occurrence unique nodes alongside existing records, options,
   helpers and finite folds. Use the same pinned Lean constants as the accepted
   DSL denotation. Indexing returns Option; no undefined out-of-range access.
   Sort accepts only Nat/Int/String, with fixed ordering and no candidate comparator.
4. Extend authoring, closed canonical decode, type checking, Lean printing,
   accepted-AST reification, feature inventory and schemas together. Surface text
   remains advisory; exact canonical core bytes are the certified artifact.

The next generic increment adds typed list map/filter/sum nodes. Map and filter
bind one element before the ambient environment; sum accepts only Nat or Int.
Their denotations are exactly List.map, List.filter and List.sum with the pinned
scalar instances. This reduces unnecessary representation proofs when accepted
contracts already use those constants. They have no task-specific operation,
result, bound or ordering rule. Implement this increment only after the initial
record-and-binder bridge gate passes; freeze a new stage before live inference.

## Representation and semantic bridge

Each entry port must match the accepted type registry, nominal record identity,
ordered field names, constructor/projection hashes and exact argument/result types.
No machine-width bound or additional precondition may weaken the accepted domain.
An adapter to the checker-produced intrinsic shape must prove both typed inverse
laws, raw decode-after-encode, raw encoder injectivity and admitted-input coverage.
Do not assert these for arbitrary Shape: record R [] Nat encodes every Nat as the
same empty record, and malformed variants can similarly erase their payload.
Use exact canonical layout/shape proofs or adapter-specific raw laws.

Generate source_fn_f from the exact admitted compiled entry and these adapters.
The candidate must prove Refines_f : forall inputs, source_fn_f inputs = accepted_f
inputs, plus the exact raw evaluation equation/coverage connecting source_fn_f to
evalEntry. These are universal equations; example evaluation is insufficient.
Preserve accepted preconditions through transfer without narrowing refinement.
Derive each obligation's implementation predicate with source_fn symbols under
all binders, including lambdas, folds, maps and dependent conditionals. Prove its
transfer from accepted theorems by function equality; never hoist implementation
calls out of dependent binder scope. Cache shared goals but retain per-ID claims.

The supervisor owns exact source/profile/AST, adapters, goals, expected propositions
and transfer statements. Candidate proof code cannot change them. Kernel replay,
statement equality, axiom policy and zero-sorry acceptance are required. Reconstruct
implementation IR from accepted declarations and compare its canonical encoding to
delivered bytes. A source-check certificate alone supplies no bridge milestone.

## Workflow, evidence and bootstrap gates

Register a distinct 0.3 semantic edge/template with explicit version dispatch.
Unknown versions, native endpoints, unsupported properties, missing adapters,
weakened proofs and uncovered required obligations block with capability or
correctness diagnostics; never downgrade to Tier 0 or reuse an old certificate.
Integrate generation, linkage, independent mechanical closure, configured concrete
adversarial review and final release. Tier 2 release follows mechanical verification;
required closure/endpoint claims remain current. Runtime TESTED is separate and
cannot substitute for refinement; an explicitly required unsupported campaign
blocks rather than being waived.

Before live inference, check unrelated positive and concrete negative grammar,
typing, adapter and refinement fixtures with the pinned kernel and two clean
builds. Each increment gets a source/specification freeze and at least one complete
instance gate. Then run revised A23 before D21 with fresh roles, exact normal CLI
contexts, autonomous diagnostic repair, and no old positive candidates, hidden
graders or oracle answers supplied to authors. No hard inference deadline. Preserve
all JSON/Lean/proof proposals, counterexamples, roots and terminal results.

Publish only VERIFIED, BLOCKED or INFRASTRUCTURE_FAILURE under registered finite
mechanical closure. END_TO_END_VERIFIED applies only to the declared restricted
source semantics and complete required claim graph. Retain failed stages, and
freeze a new stage for each correction. Report implementation coverage separately
from task-language revision, normative source assurance and host execution.
