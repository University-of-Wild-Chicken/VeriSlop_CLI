# Exact accepted relation names at the authoring boundary

This specification precedes implementation and implements the reviewed
`exact-relation-authoring-specification.json`, SHA-256
`c0dfd5798d7d7319679af44d786236f5492361dd76a57968b5e6f5fc7fdc3bb2`.
It provides authoring convenience only: no proof, linkage, TESTED, refinement or
acceptance authority. Trial005 remains closed. No project proof or retained
project candidate is repaired by this increment.

## Scope

For model-authored VSCore 0.3 relations in either canonical JSON or surface
source mode, translate exact accepted Lean declaration names to canonical
accepted-profile symbol IDs. Leave direct relation files, VSCore 0.1,
`load_relation`, native source admission, goal derivation, proof checking and
all acceptance gates unchanged. Do not coerce signatures, rename nominal types,
infer declarations, register symbols, or construct a proof.

## Accepted authority

Before model dispatch obtain accepted IR and certificate through existing
`export.verified_ir` evidence verification. Read exact IR, certificate and
certificate-referenced profile bytes with the existing bounded package reader;
check hashes, certificate identity, contract input root and toolchain, and exact
canonical equality with the original fixed context's IR/profile. The label
`accepted_profile` alone and projected/model-supplied context confer no authority.
Only the accepted `symbols` table supplies endpoint names. Preserve the original
fixed context for checker and prover paths.

Retain the complete authenticated IR, certificate and profile in an existing
bounded CAS checkpoint, with their original package paths/hashes/sizes and
normalizer implementation identity. Historical receipt restoration re-runs the
existing evidence verification and requires the same retained authority binding;
it recomputes mapping from retained exact profile bytes. It cannot silently
normalize against a newly accepted profile or an incompatible normalizer.
Storage/authority failures are explicit and prevent model/checker dispatch;
existing memory and package limits are unchanged.

## Exact mapping

Retain the exact model response first and canonical serialization of its decoded
raw relation separately, even if later protocol, source or mapping checks fail.
The raw JSON token whitespace is preserved only in the original response; the
`relation.raw.json` name does not claim that it is the original token slice.

Use unchanged `load_relation` to check the complete raw descriptor, exact
version/format/template, sorted distinct symbol strings and unique entries.
Authoring helper slots must be the existing `vscore-source` and `vscore-proof`.
For each submitted q define M(q) as the distinct accepted symbol IDs whose key
is exactly q or whose `lean_decl` string is exactly q. Require M(q)={s}; a direct
key match never wins over another alias. Require also M(s)={s}, so emitted
canonical relations are fixed points under this translation. Same-key and
same-declaration matches to one ID are one candidate, not two.

No trimming, case folding, basename/suffix match, namespace stripping, Unicode
normalization or Lean pretty-name parsing is permitted. Predicates, theorem,
record, enum, constructor and projection inventories are not aliases. Missing
or malformed symbol metadata fails closed; selected functions require an exact
accepted declaration, valid accepted argument/result sorts and an empty
`level_params` list. Actual unsupported polymorphism has a distinct diagnostic.
Synthetic ambiguous-table fixtures test metadata rules and do not assert those
tables are currently produced by native reification.

Replace only `binding.symbol`, retaining entries and all other descriptor fields.
Reject two raw spellings resolving to one ID. Sort completed rows by canonical
ID and re-run unchanged `load_relation`. Already canonical, unambiguous input
has identical canonical output bytes; every admitted output is idempotent.
Unknown names, ambiguity, collisions and malformed descriptors publish no
partial relation to any checker. Entry coverage, source signatures, exact nominal
layouts and refinement remain the unchanged checker's responsibility; a naming
receipt never asserts these checks passed or makes an invalid source valid.

## Artifacts and transaction

Each source attempt retains:

- `response.txt`: exact provider completion.
- `relation.raw.json`: canonical decoded relation, including invalid descriptors.
- `relation-normalization.json`: versioned receipt and immutable CAS snapshot
  reference; original response/raw/normalized hashes, sizes and relative paths;
  accepted authority snapshot and binding; exact per-row submitted name/entry,
  candidate IDs/declaration names, match modes, selected ID and canonical-ID
  candidates; original/final order, outcome and complete diagnostics.
- `relation.json`: only the complete normalized canonical relation used by native
  preview, proof prompts and final candidate delivery, published on naming success.

Checkpoint the full receipt and exact raw/normalized bytes before publishing the
immutable receipt and normalized relation. A persistence failure prevents preview
and never falls back to raw names. Re-entry with an existing receipt restores
and revalidates it against exact raw inputs and the same authority, without
rewriting it. A crash after receipt publication may complete a missing identical
normalized artifact only after this replay; conflicting bytes fail closed.

Preserve source text, canonical source bytes and optional submitted proof text.
Retain supplied proof text before source validation; never rewrite it during name
normalization. The raw relation is saved before envelope/source validation.
Malformed source still fails its ordinary path. Native diagnostics bind the
normalized relation hash only when that checker ran. Normalization rejection
explicitly identifies raw relation input and has no native-compilation label.
Retries retain the exact previous response and full diagnostics, including
submitted names, exact candidates and reason.

## Prompt and validation

Add only a compact pointer to the existing exact `accepted_profile.symbols`
table: canonical relation symbols are its keys; `lean_decl` is the accepted
native name; only exact unambiguous declaration spellings can be translated.
Do not duplicate the table or imply support for unregistered functions,
polymorphism or renamed types.

Test identity, alias mapping, same-ID dual matches, ordering, fixed-point
ambiguity, collision, spelling near misses, malformed metadata and unsupported
polymorphism; raw/source/proof preservation; authenticated binding and receipt
corruption; and real mocked-provider retry dispatch in both authoring modes.
Use an unrelated accepted Packet/Int fixture for actual native canonical/alias
controls, byte-identical goals/proposition hashes, and unchanged signature,
nominal-layout, missing-endpoint and false-refinement rejection. Direct checker
alias input and legacy VSCore 0.1 remain unchanged. No live models are part of
this qualification; context fit is a separate measured boundary.
