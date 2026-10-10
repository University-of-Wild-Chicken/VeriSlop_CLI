# Specification: supervisor-resolved clause citations

Written before implementation. Arithmetic-004 exhausted three model interpretation
attempts on a double-escaped public-example clause quote. Preserve the exact failed
responses and blocked result. Do not unescape arbitrary model text, replace model
obligations or manufacture coverage dispositions.

The existing supervisor manifest assigns deterministic clause IDs to exact UTF-8
byte spans in the hashed original request. Extend interpretation proposals so a
clause citation may identify its manifest clause without duplicating its quote.
An obligation source may likewise identify a request clause by ID. Resolve those
citations only against the current request's supervisor-owned manifest, reconstruct
spans and source hashes directly from that request, and retain the original model
response unchanged. The model must still author obligation meanings, kinds, roles,
dependencies, per-clause dispositions/refs, assumptions, ambiguities and defaults.

An unknown ID, duplicate/missing clause, invalid disposition/ref or attachment ID
misuse remains rejected by assembly or the unchanged ledger/draft validators.
Retain each parseable attempt's exact raw response, assembled draft/ledger and
diagnostics. Assembly errors must also block native acceptance if they remain at
exhaustion even when the assembled ledger happens to cover every source span;
they cannot be discarded by returning only the last draft/ledger tuple.
If a citation includes both ID and quote, require exact quote equality: a wrong,
double-escaped or conflicting quote is never silently normalized. Legacy quote-only
citations keep their existing exact-substring behavior. Request IDs do not confer
proof, implementation or test authority; accepted Lean artifacts remain the sole
source of downstream formal IR.

Prompt examples and schema guidance should prefer ID citations, including obligation
sources, while still exposing the exact request/manifest for interpretation. Persist
raw responses, validator diagnostics and deterministic assembled artifacts. Do not
change model transport, call/repair limits, completeness gates or independent graders.

Regressions must cover quotes, literal backslashes/newlines, non-ASCII byte spans,
unknown/duplicate/missing IDs, conflicting supplied quotes, attachment isolation,
legacy citations, and actual retained-response/assembled-artifact provenance. Then
freeze new source roots and rerun original A23 and D21 through the strict CLI, without
positive artifact injection or old model answers in fresh model context.
