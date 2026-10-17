# Exact VSCore implementation context

Status: specified before implementation; focused engineering checks now pass.
This is a model-context increment, not a live qualification result or a change to
any accepted contract.

## Retained failure and scope

The frozen G01 local-project trial 002 reached accepted contract export and formal
review, then its first implementation request was rejected before dispatch:
31,341 input tokens plus 8,192 reserved output tokens exceeded the configured
32,768-token Qwen context. The trial's 128-token safety margin remains unchanged.
The exact original request and failure remain retained under their original root.

The correction applies only to VSCore 0.3 implementation proposal prompts. It does
not change the fixed context used by checkers, source admission, proof generation,
proof routing identities, native replay, or release gates. Legacy VSCore 0.1
prompt behavior remains unchanged. There is no truncation, model-context increase,
output-budget reduction, semantic summary, or task-specific candidate generation.

## Lossless inline representation

1. Validate and retain the complete original context as strict canonical JSON.
   Count byte-identical canonical JSON values, including their types. Repeated
   values at least 20 bytes long may be shared through numeric definitions.
   Definitions used only once after parent sharing are inlined again. Object key
   order is not semantic; array order and every string byte are.
2. A closed envelope contains its format, original canonical SHA-256, shared
   definitions, encoded context and an exact string-block inventory. `{"$r":N}`
   refers to a definition keyed by the decimal string of N. `{"$text":N}` refers
   to the corresponding literal string block. An original object containing any
   reserved marker key is escaped by `{"$literal":object}`; decoding processes
   the escaped object's values without reinterpreting its original keys.
3. Unique strings at least 512 UTF-8 bytes long are displayed literally in
   length-framed blocks, avoiding JSON quote/newline escaping. Every block has an
   exact byte count and SHA-256. Framing is parsed by byte length, never by looking
   for a delimiter inside model-authored content. Embedded markers, NULs, empty
   strings, combining characters and astral Unicode retain their exact values.
4. Every value remains inline in the same request. References do not require a
   model to fetch a file. There are no semantic substitutions or omitted proof,
   requirement, grammar, declaration, formula, or diagnostic fields.
5. Restoration validates the closed envelope, contiguous numeric definition and
   block identities, reference types/bounds, absence of cycles, block sizes and
   hashes, absence of trailing bytes, and the restored original digest. Unknown,
   malformed, stale or corrupted inputs fail explicitly. Before dispatch the
   renderer must restore the exact original context successfully. Retain the
   original object and normalized prompt through the existing compact CAS memory.

## Source correction context

Every VSCore 0.3 source retry includes the exact previous implementation-model
response, the actual bound diagnostic inventory, and the complete saved diagnostic
record, including long error tails and diagnostic metadata. A failed bridge proof
may supply that record; it must not replace the previous implementation response
with the prover's response. The response is untrusted proposal data;
neither the supervisor nor the renderer repairs it. Its parsed program/relation
and raw response remain retained by the ordinary attempt artifacts. Normalization
may share exact duplicate values but must not omit a distinct failed response.

## Required checks

- Exact restoration for repeated/nested values, distinct scalar types, Unicode,
  reserved-marker collisions, embedded block delimiters and empty strings.
- Rejection of missing/unknown/cyclic/mistyped references, changed original or
  block digests, corrupt byte lengths, missing blocks and trailing bytes.
- Real implementation dispatch receives normalized 0.3 context, while the fixed
  object and ordinary checker/proof inputs remain unchanged; 0.1 stays compatible.
- A rejected source's complete raw response and actual diagnostics are present
  after retry restoration, including malformed JSON proposals.
- Recount the exact retained G01 request with the same frozen local tokenizer,
  8,192 output reservation and 128-token margin. Report initial and representative
  retry measurements separately. Larger future requests may still fail explicit
  capacity admission; fitting one request makes no universal capacity claim.

No live model calls are part of this engineering qualification. A later live run
must freeze the changed source and preserve the previous run as unfinished/blocked.

## Retained G01 capacity check

Re-rendering the exact retained trial-002 implementation context with the frozen
Qwen tokenizer produces 24,021 input tokens. The unchanged 8,192-token output
reservation and 128-token margin bring the total to 32,341, below 32,768 by 427.
Every original field restores exactly, including the complete accepted Lean
source, accepted IR, formula packages, profile, grammar, relation schema and
requirements. The message uses 76 shared definitions and two literal blocks.

There is no recorded live implementation response to measure on a retry: that
trial stopped before dispatch. Structural retry fixtures check exact rejected
response retention. The 427-token headroom does not establish that a later
response plus diagnostics will fit; capacity rejection remains explicit.
