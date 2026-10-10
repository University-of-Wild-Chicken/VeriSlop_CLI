# Versioned finite-enumeration authoring

This is the specification before implementation. The finite verification surface
is generic authoring and accepted-source correspondence, with a fresh unrelated
fixture before any new task run. The retained stage015 run remains BLOCKED.

The executable contract DSL, accepted Lean exporter, data-pipeline profile and
VSCore source language already admit finite enumerations. The preferred typed
authoring frontend does not: its registry is fixed to an empty enumeration map
and its renderer rejects enumeration sorts. The raw Lean path already admits
nullary inductive enumerations. A model's unsupported-capability report is
untrusted feedback, and cannot establish a limitation of the other layers.

## Authoring contract

Add `verislop.formalizer-ast/0.2`, alongside unchanged `/0.1`. Version 0.2
requires an `enums` object in addition to the existing required fields. Its
entries are exactly `EnumName: {"constructors": ["alpha", "beta"]}`. An empty
map is valid. Names and constructors use the existing validated ASCII identifier
grammar; each enumeration has 1 through 64 distinct constructors. Bound the
aggregate constructor count to 4096 and count enumeration declarations in the
existing total declaration limit of 128. Preserve response, node and depth
limits. Reject unknown fields, shadowing, malformed names, duplicate constructors,
unknown sorts, foreign constructors and collisions with generated declaration
names before producing a candidate. The compiler must never interpret an enum
name as a record, primitive or unrestricted String.

Version 0.1 retains its exact closed envelope, schema and source generation;
it cannot silently accept new enumeration fields. Version 0.2 also admits:

* sort `{"enum": "EnumName"}`;
* term `{"tag": "enum", "sort": "EnumName", "constructor": "alpha"}`;
* entity declaration reference `{"kind": "enum", "name": "EnumName"}`.

These sorts may nest in records, lists, unambiguous Options and Results, and
occur in symbols, predicates, quantified formulas and witnesses. Propositional
equality of enums already exists. This milestone must also support enum Boolean
equality and decidable enum-equality guards: the current executable predicate
admission and independent denoter exclude them. This adds no arbitrary comparator,
enum pattern-matching language, enum-to-String coercion or custom wire codec.

Emit deterministic quoted Lean nullary inductives before dependent records and
definitions. Derive fixed computable DecidableEq machinery for enum guards.
The independent denoter must use an exact kernel-checked equality instance bound
to the nominal enum; it cannot invent a declaration name or accept an untyped
comparator. Derive the accepted instance binding and hash from actual accepted
declarations, reject ambiguity and stale/type-incompatible bindings, and require
the existing executable reference preflight. Old profiles without such a binding
retain enum carrier/equality-formula support and must explicitly reject enum
decisions requiring absent machinery. Candidate and accepted equality metadata
remain separate, and the latter comes only from accepted Lean. Their candidate
registry binds exact qualified type and
constructor names. Constructor names are the unchanged scalar wire strings in
the existing profile; only those constructor strings decode as that enum. This
milestone supports identifier-valued choices. Arbitrary string literals needing
a custom encoding remain outside this frontend.

The compiler's enum registry may contain
`candidate_decidable_eq: {"lean_decl": "Exact.Generated.Instance"}` for its
mandatory kernel fidelity checks. An accepted enum registry may instead contain
`decidable_eq: {"lean_decl": "Exact.Accepted.Instance", "decl_hash": "sha256:..."}`.
These are separate fields and authorities. Accepted reconstruction never copies
the candidate field, and accepted-profile validation rejects it. The accepted
binding must resolve to its exact current safe, computable declaration and
monomorphic nominal equality-instance type. A missing accepted binding cannot be
substituted with a guessed name, candidate binding or custom BEq. Corrupting its
name/hash/type must block admission or kernel correspondence.

For enum E with constructors c1 through cn, the admitted logical type has exactly
those alternatives. Its registered encoding is enc(ci) = the string ci, and
dec(enc(ci)) = ci. Distinct constructors have distinct wire strings. Every
enum reference, projection and conditional must resolve against that nominal
registry. Two enums with identical constructor lists remain different types.

## Proof and provenance contract

Compilation creates an untrusted Lean candidate and theorem holes. It cannot
assign PROVED, TESTED or END_TO_END_VERIFIED. The existing kernel statement/body
denotation audit, proof/witness checking, policy and accepted-AST reconstruction
remain mandatory. Downstream enum declarations and JSON obligations must come
from accepted Lean, rather than the proposal registry. No axiom, native-evaluation,
import, proof-policy or source-coverage exception is introduced.

Compiler receipts identify the selected compiler version and exact source,
response, frozen obligations and emitted artifacts. Origin reconstruction must
replay the same envelope version and reject altered constructors, nominal IDs,
source, declarations, receipts or binding order. The agent assembler, origin
audits, schemas, capabilities and formalizer/critic prompts must recognize both
versions. The default typed prompt presents the complete version 0.2 grammar,
including enums; legacy responses and raw Lean remain supported. A capability
report must identify the actual frontend boundary without claiming that existing
registered enum semantics or wire codecs are absent.

## Frozen qualification and fresh-task sequence

Use unrelated two- and three-choice examples, never retained benchmark solutions,
proofs, hidden cases or manually authored task answers. Check exact envelope
dispatch, legacy source stability, nominal separation, nesting, source generation,
constructor rejection, budgets, capture-origin replay and full prompt exposure.

Run actual pinned Lean compilation and kernel denotation audit for generic enum
definitions/formulas. Reconstruct the profile from accepted declarations; inspect
its exact constructors and wire round trips, every pair of constructors in enum
equality, both conditional outcomes, rejected nonconstructors and a rejected
false theorem. Check unknown, ambiguous, stale and incompatible equality-instance
bindings and primitive legacy stability. A source implementation fixture must
then reach the registered Tier 2 universal refinement/transfer checker and its
two isolated clean builds, deterministic comparison, retained-copy validation and
concrete release probe. No mocked build or manually asserted success qualifies.

Freeze current production/spec/schema/harness bytes before that qualification.
Preserve failed attempts. Only after actual current-source qualification may a
new strict natural-language task run start, in a separate frozen project with
fresh role authors and native repair/review budgets. The old stage015 seal and
BLOCKED outcome remain unchanged. Fresh model responses are copied literally;
no old task candidate or engineering fixture answer enters their authoring
context. Report the exact endpoint, domains, claims, trust and optional TESTED
status; this milestone adds no Python, compiler-chain or machine-code guarantee.
