# Focused contract proof correction

Status: specification before implementation; engineering increment, not a live
model qualification. Existing frozen trials must remain unchanged and their
results remain attached to their original source/protocol roots.

## Observed problem and bounded claims

In the retained G01 trial, Lean's built-in portfolio elaborated the complete
contract with two unresolved declarations. Every portfolio body still contained
an unused `sorry` alternative, so lexical detection would report ten holes.
The prompt exposed all ten original theorem headers. A subsequent model fixed
the two native-facet proofs but broke an already solved arithmetic theorem.
The following request also repeated the same assembled candidate twice and
exceeded the local context budget.

This increment narrows *proof proposal work*. It grants no proof, acceptance,
coverage or milestone authority. The complete assembled module still undergoes
the existing compiler, acceptance, axiom, contract and bridge checks.

## Native diagnostic selection

1. The ordinary native compiler evaluation retains its sorry warning positions
   together with the exact compiled source hash, policy hash and toolchain
   identity. Only a successful evaluation of the current best baseline is
   eligible. Restored baselines are recompiled, as before; persisted or
   model-provided positions alone never authorize selection.
2. Supported frozen theorem headers and all non-hole scaffold bytes must match
   the baseline. Map every native warning location to exactly one original
   hole's declaration span. Validate position/count consistency and all input
   bindings. A missing, stale, malformed, ambiguous or out-of-span observation
   conservatively exposes all original holes. Unsupported original fragment
   syntax keeps its existing explicit rejection behavior.
3. Only a strict subset creates a focused dispatch. Its descriptor binds the
   frozen challenge, baseline, compiler observation and ordered selected names.
   Never identify unresolved work by lexical `sorry`: unused tactic branches
   are not unresolved Lean declarations.
4. A focused fragment may replace a nonempty subset of selected proof bodies.
   All omitted and nonselected bodies remain byte-for-byte baseline content.
   A focused complete-file proposal must preserve the same frozen scaffold and
   every nonselected proof body exactly; reject violations without repairing
   the proposal. Existing registry composition remains the ordinary pipeline's
   responsibility. Full candidate compilation and acceptance remain unchanged.
5. The focus is checked against its exact challenge/baseline before dispatch.
   Malformed/stale descriptors are rejected. Calls without a strict focus and
   the VSCore bridge route retain the existing response protocol.

## Exact duplicate prompt projection

The contract prover constructs one structured context with current baseline,
previous proposal/result, complete current errors, critique, and retained router
rejection. Consider only four named source-string fields: current file, previous
candidate, retained rejection candidate, and retained raw response. Keep the
first occurrence of each byte-identical string inline. Replace subsequent exact
duplicates with explicit in-message references carrying the first field path,
UTF-8 size and SHA-256. Do not deduplicate arbitrary nested metadata or invent a
summary language. Empty and Unicode strings are preserved exactly.

The projected envelope records the original context digest. A deterministic
restorer follows only the four registered fields, rejects forward/cyclic,
unknown, stale or mistyped references, checks sizes/hashes and verifies the
restored context digest. Every unique source and every diagnostic remains
available in the prompt. Raw proposals, assembled candidates, router feedback
and diagnostic artifacts on disk remain unchanged. Routing job identity and
rejection hashes continue to bind full original content, not projected content.
The prompt renderer requires the complete registered top-level context shape;
unknown fields cause an explicit error instead of silently disappearing.

## Required validation and compatibility

- A real Lean fixture with ten lexical sorry alternatives but only two native
  warnings selects exactly the two unresolved declarations.
- Completing selected fragments preserves solved bodies, then the entire module
  compiles without sorry warnings. An invalid selected proof is still rejected
  by Lean; out-of-scope body edits are rejected for fragments and full files.
- Missing positions, stale hashes/toolchains/policies, invalid columns and
  ambiguous mappings select all holes conservatively. Native observations are
  used only after successful exact-baseline compilation.
- Context restoration is exact for repeated and distinct Unicode source bytes,
  empty strings, full errors, arbitrary metadata and raw-response differences;
  tampered references/digests fail. Existing role/routing and response decoding
  tests remain passing. No live model calls are part of this qualification.

The declaration mapper deliberately retains the existing restricted fragment
syntax. It is not a general Lean AST parser. A conservative fallback may retain
large prompts or redundant proof work; no context truncation, proof weakening
or silent assurance downgrade is permitted.

## Engineering validation

The isolated implementation passed 60 distinct tests: the 59-test proof-focus,
fragment, native proof feedback, JSON response, hybrid routing, small-prover
routing and VSCore fragment-guidance suite, plus a native compiler-to-routed-role
workflow test. Native Unicode fixtures cover literal U+0085, U+2028 and U+2029
inside a string before declarations; these are not Lean line breaks. The mapper
uses literal LF and Unicode-scalar columns, matching the pinned Lean FileMap.

A separate read-only replay of the exact retained G01 built-in portfolio source
(`sha256:5192143889f8c45c7e44ede66e97b8f96f0819f8b8a2b7d008308fa1da73da3f`)
had ten lexical fallback sorries but only two native warnings; selection correctly
returned `safety` and `totality_determinism`. No candidate body was changed.

Pinned-tokenizer replay of the previously rejected Qwen prompt, keeping all ten
original headers, measured 30,905 input tokens before projection and 22,490
afterward. With the unchanged 8,192 output allowance, the latter requires 30,682
tokens within a 32,768 context. This is an offline prompt measurement, not a model
completion or a fresh pipeline qualification. Further formalization/context or
model-capability failures remain possible and must be retained by the next run.
