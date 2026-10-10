# Shared Lean String literal rendering

The prospective finite contract, fixture corpus, verifier protocol and negative
plan live in `validation/tier2-unicode-literal-support-018/`. They were written
before the renderer change or any verification execution.

The shared `vscore_source.lean_string` helper is used by the vscore, vscore2 and
vscore3 aliases and the shared Expr Printer. Its output is a Lean string literal
for well-formed Unicode scalar text, without Unicode normalization. Invalid
Python surrogate text raises `SourceError`; it is never replaced or encoded as
a surrogate pair.

The canonical rendering keeps the formerly accepted ASCII bytes unchanged,
escapes quotes and backslashes, uses named newline/carriage-return/tab escapes,
two-digit `\x` for other C0/C1 controls and DEL, four-digit `\u` for other BMP
scalars, and raw UTF-8 for supplementary scalars. Pinned Lean 4.34.1 recognizes
exactly two hexadecimal digits after `\x` and four after `\u`; it does not
support eight-digit `\U` escapes. Source parser and DSL grammar remain separate
boundaries and receive no new accepted syntax from this renderer change.

The qualification compiles deterministic String definitions in frozen batches from actual shared
Printer output, replays the compiled declarations through the existing Lean
kernel tool, and compares each exported definition value to the original
`{"lit":{"str":text}}` Expr. Genuine negative Lean compilations cover malformed
escapes and an unequal literal theorem. Two fresh positive build rounds must agree on
module bytes and replayed inventory. No host evaluation establishes denotation.

The machine-readable report is authoritative only for the frozen finite corpus
and declared TCB. It does not establish universal Unicode correctness, evaluate
native tasks, or activate the repository-wide Tier2 support boundary.
