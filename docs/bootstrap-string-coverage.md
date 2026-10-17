# VSCore Unicode string composition increment

This specification precedes implementation. The accepted contract DSL already
expresses string concatenation and Unicode scalar length, but VSCore 0.3 can
only construct and compare strings. Add two generic operations to the existing
pure data profile without changing the meaning of any existing program.

The motivating follow-up project is the pure planning component of a release
manifest publisher: select enabled nonempty asset paths, preserve order and
duplicates, concatenate a requested prefix with each path, report destination
character counts and sum asset sizes. This document supplies no project program,
accepted contract or proof to generation agents. Network publishing, filesystem
effects, normalization, security policy and execution performance are outside
the restricted-source endpoint.

## Closed syntax and normative meaning

Add canonical expression `string_append` with exactly `left`, `right` and `tag`
fields, and `string_length` with exactly `tag` and `value`. Append requires two
String operands and returns String. Length requires String and returns Nat.
Surface syntax is `String.append(left, right)` and `String.length(value)`.
These operations require the existing `string` feature, including when nested
in a helper or when the result type is only Nat. Source/budget/version/profile
policies otherwise remain unchanged. Unknown fields and arities remain errors.

Normative compiled meaning is exactly Lean `String.append` and `String.length`
under the pinned toolchain. Length counts Unicode scalar values, not UTF-8 bytes
or grapheme clusters. Appending preserves every scalar and its order, including
NUL, supplementary-plane scalars and combining marks; it performs no Unicode
normalization. Empty strings retain their ordinary identity behavior. Surrogates
and out-of-range literals remain rejected by the existing scalar admission rule.
The admitted language remains total, deterministic, pure and immutable.

Update the closed schema, surface grammar, host decode/encode/type inference,
feature derivation, Lean literal rendering, normative syntax/decoder/compiler,
safe structural traversals, accepted-AST reconstruction and readable denotation
together. The readable renderer emits the same pinned String operations. Its
existing universal compiler equality must pass before CHECKED selection; no
string sample or rendered source text establishes refinement.

## Evidence boundary and checks

Use unrelated Unicode fixtures and generated kernel checks. Cover empty input,
ASCII, NUL, combining sequences, supplementary scalars and the upper scalar
boundary. Demonstrate a concrete multibyte string whose scalar length differs
from encoded byte length, and an unnormalized combining sequence whose length
differs from its grapheme count. Reject wrong operand types, wrong arities,
unknown fields, missing string feature and invalid scalars.

Replay the new expression constructors from actual Lean ASTs and compare exact
canonical delivered bytes. Check readable whole-function equality and an actual
accepted-contract source bridge for independent universal append and length
equations. A type-correct source with reversed append operands or a constant
length must fail the unchanged exact refinement gate. Use the pinned Lean
kernel and two clean builds where the registered source/bridge check requires
them. Existing VSCore 0.1/0.2 behavior and earlier 0.3 examples must continue to
pass their relevant regressions.

These controls establish only the specified primitive and bridge behavior.
They do not qualify a natural-language project, transfer a historical VERIFIED
root or grant TESTED. A later fresh project trial must freeze the changed root
and run interpretation, contract proof, accepted reconstruction, implementation,
universal refinement, linkage, mechanical closure and concrete review normally.
No live model calls are part of this implementation increment.

The fresh public request is
`examples/project-bootstrap/G04-release-manifest.txt`. Its natural-language
project qualification is pending. Primitive/kernel/bridge fixture passes do not
count as a live G04 result. A future run must generate the interpretation,
contract, proof and source from that request under a separately frozen root.
