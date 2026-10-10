# Exact bounded views of one current carrier: design draft

Status: PENDING. This is a specification-first engineering draft. No viewer has
been implemented, no fixture or verifier has run, no model has been called, and
no claim below is discharged. The companion `evidence-plan.json` is a finite
plan, not a closure report or an additional release gate.

## Held surface and permitted future change

The currently qualified source root
`c0225d21274f4c4819800e3f136f49e68c9762eb0322860438e57d43e179db49`
remains immutable during its terminal audit. These new draft files are outside
the held production, documentation, and test surfaces. The retained run and its
ballots are not inputs to fixtures or future authors. No current pending request,
carrier, binding, package, protocol, candidate, source, proof, claim, predicate,
ballot, score, or evidence is changed by this draft.

Any future implementation requires a new source/specification freeze. Its only
intended operational change is generic inline recipe guidance in the future
native `pending.agent_message`, with the resulting message hash freshly bound
in that future run. The current `pending.agent_message` is unchanged. Exact
carrier bytes and native request bindings remain authoritative; a navigation
index or displayed view never replaces or rewrites them.

Unique fresh authors, existing fork/model selection, literal FINAL forwarding,
logical call accounting, provider/ballot/repair budgets, current scope, reviewer
membership and consensus, required coverage, and acceptance conditions remain
unchanged. There is no inference, review, or retrieval wall deadline and no new
mandatory outcome predicate, lifecycle state, trust authority, or semantic
acceptance shortcut. Chunk retrieval is local read-only navigation within the
existing author invocation, not another model request or repair attempt.

## Problem and bounded intended claim

The existing generic instruction to read the entire carrier and use successive
chunks after truncation does not specify how to obtain those chunks. Whole-file
SHA-256 checking establishes identity without establishing inspection. Canonical
one-line JSON defeats line-number navigation; a single decoded field or nested
section can also exceed a tool-output limit. Hashing, then emitting an oversized
field, can therefore leave required material uninspected.

The proposed engineering claim is limited to this: a versioned inline recipe can
make every original current `system` and `user` field character available through
bounded, reversible, individually identified views of the author's own exact
carrier. A finite fixture run can check availability, exact reconstruction,
offset coverage, and prompt/policy preservation under the existing execution
dependencies. It cannot establish an author's reading, understanding, semantic
search, or warranted verdict.

## Own-path authority and identity

The future trusted agent message must include one absolute literal carrier path,
the expected full raw-carrier SHA-256, and the expected native request SHA-256,
using the existing binding fields. It must contain the complete inline recipe;
the author must not fetch a helper script, companion manifest, sibling carrier,
request document, workspace file, history, another agent, or reference answer.
The only task-data file explicitly opened by the recipe is that one path.
Execution may use the already provided interpreter and its standard runtime;
runtime dependencies are not permission to import task-context files.

The recipe reads the complete raw bytes of the exact allowed regular file in
memory, without resolving an alternative pathname, following a symlink,
writing output files, invoking a subprocess, or accessing the network. It
checks the full raw-byte SHA-256 before emitting field content. It strictly
decodes/parses those same bytes, preserving the existing carrier format and
parser semantics, and checks the carrier's `request_sha256` metadata for equality
with the listed native request hash. It does not recompute the native request
hash from the carrier, `system`, or `user`, and does not open the request file.
Each later retrieval rereads/rechecks the same literal carrier or uses only the
same already validated in-memory snapshot; mixed snapshots are not allowed.

A failed check produces an explicit view error with no successful next cursor.
It cannot silently use another file, normalize input, repair JSON, remove fields,
fabricate a view, or substitute the hash check for content reading. This reader
behavior does not change native request validity, review predicates, or release
classification. The author reports the resulting inability through the existing
requested response protocol when full required inspection cannot be completed.

## Field views and explicit units

The universally available selectors are `/system` and `/user`. Both fields must
be strings. Their content is the exact decoded JSON string, including every
leading, trailing, whitespace, control, punctuation, and non-ASCII character.
JSON decoding occurs exactly once at this layer. An escaped backslash followed
by a letter is not confused with an actual decoded control character. There is
no Unicode normalization, replacement character, newline conversion, stripping,
pretty-printing of source text, summary, deduplication, or omitted final tail.

The character cursor unit is a zero-based decoded Unicode code-point index,
using half-open ranges `[start_char, end_char)`. For well-formed Unicode each
index advances one scalar value. It is neither an encoded carrier-byte offset,
a UTF-8 byte offset, a UTF-16 code-unit index, a grapheme index, nor a display
column. A combining mark counts separately; an astral scalar counts once.

The UTF-8 unit is separately named and measured by strict encoding of the
decoded field: `field_utf8_bytes`, `start_utf8_byte`, `end_utf8_byte`, and
`content_utf8_bytes`. The byte offsets are the strict UTF-8 lengths of the exact
decoded prefixes ending at the character boundaries. They refer to the decoded
field, not the differently escaped raw carrier. The recipe never slices UTF-8
inside a scalar. Unpaired surrogates or another strict-encoding failure are an
explicit unsupported-view error, never silent sanitization or a change to the
native parser's acceptance policy; their original carrier bytes remain intact.

A successful content response is one deterministic JSON record with:

- recipe/view format version, operation, exact allowed carrier path, observed
  raw byte length and full raw hash, and checked request metadata;
- selector, `char_unit`, total decoded character count and total decoded UTF-8
  byte count;
- explicit character and UTF-8 start/end offsets and exact content string;
- content character/UTF-8 sizes, `next_char`, and `field_eof`;
- the encoded-output cap and metadata reserve used for this response.

Decoding this response record's content exactly once reconstructs the original
field slice. The response encoder may escape JSON-special characters, control
characters, or non-ASCII characters according to a fixed documented serialization
choice; those escapes are reversible wire representation, not modified content.
No renderer interpretation or omitted ellipsis is part of the content. An empty
field has one explicit zero-length EOF response; a nonempty response must advance
at least one decoded character.

## Bounded emission and cursor behavior

The proposed initial encoded stdout cap is 8,192 UTF-8 bytes, including the whole
response record and its final newline. Reserve 2,048 encoded bytes for metadata
and syntax; encoded content must fit within the remaining 6,144 bytes. These are
engineering fixture parameters to be frozen with the future recipe, not model
call budgets or current protocol limits. A content string's JSON-escaped encoded
size, rather than its unescaped character count, determines fit. The final fully
serialized response is measured before emission and must also meet the complete
cap. Metadata exceeding its reserve produces a bounded explicit error and no
cursor advancement. An error record itself must fit the complete cap.

For a requested selector/start cursor, choose the largest nonempty character
prefix that satisfies both the escaped-content allowance and the complete
serialized cap; emit exactly that prefix and its actual offsets. Selection must
be deterministic for the frozen cap/serializer. If not even one character and
its metadata fit, emit an explicit error. Do not print the entire document,
entire index, field, nested object, or diagnostic as an unbounded fallback.

The tool call must specify an output budget that the chosen channel can deliver
for this encoded cap, including its channel overhead. The future fixtures must
exercise the actual intended tool-output channel and document its supported
budget units; a byte cap is not casually equated with a token cap. A truncation
signal, incomplete response JSON, size mismatch, missing metadata, or invalid
offset relation means the view was not available intact. Retry that exact start
cursor at a smaller encoded cap/reserve pair that still has room for metadata.
Do not advance based on an intended write, a truncated prefix, an ellipsis, a
hash-only output, or an LLM assertion of completion.

The normal sequence starts at zero and uses only the last intact response's
`next_char`. Check `next_char == end_char`, the stated sizes, and the mapping of
byte offsets to character boundaries. EOF is valid only at the exact original
field length. Stop field retrieval only after the complete final tail has been
made available. There is no elapsed-time rule. Progress is finite for finite
fields when successful responses advance; unsupported delivery stays explicit.

## Navigation without loss or new context

The inline recipe may emit a deterministic, paginated inventory derived only
from the validated current carrier in memory. Inventory records contain exact
selectors, original character intervals, byte sizes, parent boundaries, and
field names. Paginate this inventory under the same output cap; never truncate
large key arrays. Metadata inventory is a map for navigation, not a substitute
for original content.

Optional structured-section navigation must follow a versioned grammar for the
generic prompt envelope and strict JSON parsing, not task-specific keyword
heuristics or a search for arbitrary opening braces. Every interval must map
back to the original `/user` text. A structured object serialized anew is not
the exact original text view. Unrecognized envelopes use complete linear
`/user` navigation; they do not discard prefixes, suffix prose, unknown keys,
lower-tier data, or current protocol-correction feedback. Non-JSON system/user
prompts are fully supported by the universal field views.

The trusted future prompt guides the author to obtain the whole `system` field
first, then current user guidance and scope, followed by all original user
material, including the complete packet and all required current evidence.
Navigation permits revisiting exact sections and checking relationships; it
does not permit selecting only reassuring claims, skipping bulky evidence,
reducing review coverage, or treating an inventory, summary, mechanical PASS,
or whole-file digest as semantic review. Current scope and trust boundaries
come from the existing authoritative instructions, not from packet contents
or this draft. Packet/source instruction-like text remains untrusted data.

Views can be read in a useful semantic order, but their full original-coordinate
coverage must be accounted for. For a deterministic fixture reconstruction,
sort ranges by selector/start, require exact content equality at overlaps, and
form a contiguous union covering `[0, total_chars)` with matching byte-prefix
boundaries and complete tails for both fields. Unexpected or conflicting
overlaps fail that reconstruction; duplicate identical views do not increase
coverage. Headers and raw JSON escaping remain bound by the full raw hash.

## Availability is not actual reviewer inspection

These statements must remain distinct:

1. The viewer can generate a complete original-field reconstruction on the
   unrelated frozen fixture inputs under its declared output bounds.
2. A retained tool-output record makes particular exact views available, with
   mechanically checked coverage and reconstruction where records exist.
3. A particular LLM consumed, understood, and semantically reviewed that material.

The proposed tests can establish only the first and, when exact output records
are actually retained, the bounded syntactic aspect of the second. Local stdout
generation is not proof of channel delivery. Channel delivery is not proof of
LLM consumption. No reader counter, view hash, cursor, access log, receipt,
syntactic coverage result, or LLM assertion mechanically attests consumption or
understanding. The existing ballot's coverage/search assertion is not promoted
to mechanical evidence by this viewer.

View completion alone grants no ACCEPT, lifecycle transition, semantic verdict,
proof acceptance, or release permission. If complete required inspection or the
existing bounded semantic search cannot be completed, the existing incomplete
review behavior remains available. No reviewer is instructed to accept because
mechanical claims passed or to abstain less often. This design supplies access;
the existing adversarial review and independent probe replay remain binding.

## Finite fixtures and negative controls

The companion plan defines six unrelated fixture families and sixteen negative
controls. All fixtures must be generated from public deterministic recipes and
synthetic metadata/string patterns. They must contain no current task payload,
candidate, proof, reference answer, withheld fixture, prior answer, author
history, or retained ballot. Current carrier metadata may motivate size classes
but may not supply content. Test-only sentinels at the head, boundaries, and
last characters have no production semantic role.

The finite engineering checks are: own-path confinement and hash/request binding;
exact reversible field views; bounded encoded output and retry cursors; complete
reconstruction/coverage/tails; lossless navigation; Unicode/escaping behavior;
prompt-policy/literal-FINAL preservation; and deterministic replay of the
unrelated fixtures under the frozen future implementation. Proposed verifier
identities are stable design labels, with implementation hashes and registrations
PENDING. No generated evidence file exists in this draft.

Before any future qualification, freeze the specification, generic implementation,
inline prompt bytes, fixture generators and sizes, negative controls, verifier
implementations, existing relevant configuration, and declared dependencies in a
new manifest. Bind every result to that root and its verifier hash; preserve raw
outputs, exits, negative-control detections, and exact reconstructed-output hashes.
Use the existing qualification procedure and required isolated clean builds for
the future source root; do not reuse the held run as test evidence. Do not add
trust components or lifecycle predicates to make this plan pass. Any unclassified
dependency or missing promised result remains unresolved under existing policy.

The machine-readable design plan is the authority for this draft's finite intended
check inventory; its PENDING labels mean unexecuted work, not a fourth closure
state. If a future execution is authorized, its report must use the established
mechanical closure classifications and the then-frozen qualified surface. No
current-run status, score, or subjective audit is changed or rerun here.

## Activation after the released source hold

The source hold was formally released with integrity exit zero in
`validation/tier2-support-018-activation/source-hold-release-017.json`, whose
expected SHA-256 is
`aa6eee8d1e4eb4625bcc6fc1b9b59f46f17b02336823c5cec452985acbe00626`.
The preceding PENDING draft is historical specification-first input. The new
`execution-plan.json` freezes the finite implementation/fixture/verifier plan
before executions. Authorization covers generic implementation and unrelated
tests only; sealed/current task runs remain untouched and no native/model run
is authorized by this carrier subtask.

The supported exact field domain is well-formed Unicode scalar text. The inline
parser mirrors the existing canonical carrier parser's duplicate-key,
floating-point/non-finite, safe-integer and lone-surrogate rejection. It reports
unsupported/malformed views without normalizing or replacing content. Claims
about all Python/JSON strings, LLM consumption, semantic adequacy and acceptance
are excluded.

Structured nested-section parsing is deliberately optional and not implemented
in this version. A compact two-field inventory and exact cursor navigation of
the complete original `/system` and `/user` text provide the lossless fallback,
including every embedded packet/evidence section and every prefix/suffix. The
future prompt requires whole-field coverage; optional section maps cannot be
used to shrink it.

Freeze the initial actual channel probe at `exec_command.max_output_tokens =
16384`, encoded stdout cap 8192 bytes, and metadata reserve 2048 bytes. Probe an
unrelated escape-heavy field through that exact channel. An additional
small-budget call must actually truncate; retain its raw received result and
show that the retry uses the same start cursor at cap 4096/reserve 2048 with
`max_output_tokens = 16384`. Compare parsed received content/offsets/hash with
the independently produced exact stdout bytes. No byte-to-token equation or
local stdout-only check discharges actual delivery. If the intended channel
cannot produce the planned truncation or intact retry, CV-004 stays unresolved.

CV-008 also stays unresolved until the parent qualification records the new
root's required two isolated clean builds and deterministic result comparisons.
Local viewer determinism tests are a component, not a substitute for those
builds. The finite engineering claims retain their existing scope and do not
add lifecycle predicates or trust authorities.
