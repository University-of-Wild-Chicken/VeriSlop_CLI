# Executable contract coverage bootstrap

This specification precedes the implementation. It extends the existing candidate grammar;
it does not introduce task templates, benchmark answers, or a second source of accepted IR.
Every accepted formula continues to be reconstructed from the kernel-accepted Lean AST and
checked against its independently constructed denotation. Candidate JSON remains untrusted.

## Increment 1: nullable values and conditional expressions

Contract DSL 0.2 gains `{"option": S}` denoting Lean `Option S`. The interpreter represents
`none` as `("none",)` and `some v` as `("some", v)`. Public helper functions construct these
values. Python maps `none` to `None` and `some v` to the ordinary Python representation of
`v`; it never changes a list, integer, string, boolean, record, or result into a tagged tuple.
The native wire protocol remains unchanged and sort-directed decoding distinguishes the
two constructors. `Option Unit` and `Option (Option S)` are rejected because Python `None`
would conflate their constructors. An option below a list or record is legal, since those
outer values map to a list or dict rather than `None`. Recursive records remain rejected.

Exact term shapes and judgments (all operands type-check before execution):

* `{"tag":"none","element_sort":S}` has sort `Option S`.
* `{"tag":"some","value":v}` has sort `Option sort(v)`.
* `{"tag":"option_get_or","value":o,"default":d}` requires `o : Option S`, `d : S`
  and returns `S`; denotation is `Option.getD o d`.
* `{"tag":"option_is_some","value":o}` requires `o : Option S` and returns `Bool`;
  denotation is `Option.isSome o`.
* `{"tag":"ite","condition":c,"then":a,"else":b}` requires `c : Bool` and exactly
  equal branch sorts. Its denotation is core Lean `cond c a b`. The interpreter evaluates
  only the selected branch; a resource failure in an unselected branch is not a failure.

Options participate in finite enumeration when their payload does, sampling, shrinking,
witness decoding and encoding, refutation assignments, and review examples. Invalid tags,
extra fields, mismatched defaults, ambiguous option sorts, malformed native values, and
proof/DSL denotation mismatches fail closed. Finite domains remain exhaustive; infinite
domains remain sampled and cannot turn sampling into a universal proof.

The first live bootstrap gate reruns the original D21 natural-language prompt through the
entire strict pipeline. It is allowed to reveal the next missing primitive. A domain report
or unsupported requested endpoint is retained and classified explicitly; it is never success.
No manually supplied formalization or implementation participates in this live gate.

## Increment 2: bounded enumeration and scalar ordering

The second increment is specified here. Code may be developed after the first increment's
coherent source snapshot is frozen; its live run starts after the preceding pipeline
outcome is retained. The arithmetic subincrement uses original A23 before grouping/order
coverage is checked with D21. It adds these generic terms:

* `{"tag":"list_range","stop":n}` for `n : Nat`, yielding `[0,...,n-1] : List Nat`;
  denotation `List.range n`. Enumeration consumes evaluator work budget before allocation.
* `{"tag":"list_get","value":xs,"index":i}` for `xs : List S`, `i : Nat`, yielding
  `Option S`; denotation the pinned core `List.get?Internal xs i`, definitionally equal
  to Lean's `xs[i]?` notation. Option ambiguity rules apply to the payload.
* `{"tag":"int_fdiv","left":a,"right":b}` for `Int` operands, denoting `Int.fdiv`:
  mathematical floor division for nonzero divisors, and zero when the divisor is zero.
  Native Python's raising `// 0` does not satisfy this total contract.
* `{"tag":"int_to_nat","value":a}` for `a : Int`, yielding `max(a,0) : Nat` and
  denoting `Int.toNat`; it is explicit, not an implicit coercion.
* `{"tag":"list_sort","value":xs}` for `List Nat`, `List Int`, or `List String`, yielding
  ascending stable scalar order and denoting core `List.mergeSort` with a fixed `decide (≤)`
  comparator. Arbitrary comparator proposals, locale sorting, and proposal-selected instances
  are outside this increment.
* `{"tag":"list_unique","value":xs}` for lists of `Nat`, `Int`, `String`, or `Bool`,
  preserving the first occurrence and denoting `List.eraseDups` with builtin decidable equality.

Formula `lt` and `le` additionally admit matching `String` operands. Strings are Unicode
scalar sequences. Lean's lexicographic character order and Python's code-point order agree
on the admitted values; surrogate-containing strings remain rejected. Denotations use the
fixed imported core instances and kernel equality checks, never candidate-provided instances.
Sorting and deduplication consume explicit per-element/comparison work budget.

The next live gate uses the same unchanged D21 prompt. New model calls receive the public
grammar and ordinary native diagnostics only. Success requires native `TESTED`, all strict
closure gates, two clean build checks, and independently scored corpus cases. Native contract
tests and held-out cases are reported separately. Neither gate claims `END_TO_END_VERIFIED`.

## Validation and explicit limits

Registered tests must exercise source generation, actual Lean elaboration, accepted-AST
reconstruction, kernel definitional equality, interpreter behavior, and native Python codec
round trips. Negative tests must include ambiguous options, bool-as-int rejection, branch
sort mismatch, malformed options, wrong source primitive that still compiles, Unicode order,
negative and zero division, out-of-range indices, and work-budget exhaustion. These are
frontend correctness tests; the live corpus gates independently test natural-language-to-
software capability without injecting hand-written solutions.

This increment does not admit arbitrary recursive JSON, arbitrary unions, dynamic record
keys, parsing, higher-order values, recursive candidate definitions, or third-party Lean
imports. It makes no universal natural-language/formal-contract equivalence claim. Tier 0
keeps the Python/runtime/compiler/serialization trust stated by its report.
