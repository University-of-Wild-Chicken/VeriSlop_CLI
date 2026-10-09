# Bootstrap contract: capability reports and exact rejected proposals

This specification precedes its implementation. It fixes the formalizer/critic
handoff without changing Lean acceptance, executable readiness, release review,
TESTED evidence or any historical experiment. Models remain untrusted authors.

## Capability-report language

A formalizer may return either an existing complete contract proposal or this
strict JSON envelope:

```json
{
  "encoding": "verislop.formalizer-capability-gap/0.1",
  "obligation_ids": ["D1", "O1"],
  "gaps": [{
    "obligation_ids": ["O1"],
    "feature": "requested observable operation",
    "reason": "specific missing sort or registered semantics",
    "attempted_representations": ["faithful alternate representation considered"]
  }]
}
```

All keys are mandatory; extra keys are invalid. `obligation_ids` contains each
active frozen obligation exactly once. Each gap names a nonempty subset of those
IDs, a bounded feature/reason, and 1–8 bounded descriptions of faithful alternative
representations considered. Reports cannot create assumptions, remove requirements,
change IDs, accept a contract, supply implementation artifacts or assign milestones.
Descriptions are model claims, not proof that a domain is impossible.

A valid report produces `UNSUPPORTED_CAPABILITY` with the report bound in diagnostic
details, rather than a missing `lean_source` error. It does not enter Lean or freeze
any challenge. Within the existing configured formalization-attempt bound, a critic
and subsequent author receive the exact report and the registered language. They
must seek a changed faithful representation using supported operations, retaining
all obligations. The first report is not a terminal failure when attempts remain.
When those attempts are exhausted, the last unresolved report explicitly blocks the
formalization. It does not consume fresh outer repair packages merely to repeat
an unchanged declared language gap. Malformed reports still get bounded protocol
correction as `INVALID_CANDIDATE`. A successful alternate contract must pass every
ordinary strict gate; an opaque term cannot satisfy a TESTED request.

## Byte-exact rejected-response handoff

Every actual formalizer response already has an immutable memory snapshot. The
current attempt now includes its exact UTF-8 text and pinned response snapshot
reference in both the critic packet and the retained candidate context. The helper
restores that snapshot and compares exact bytes before passing it to another role.
A snapshot mismatch, missing blob, stale head or tampering blocks before inference.
Legacy authored callable fixtures without a recorded response remain supported,
but they have no asserted raw-response provenance.

A fresh local author restores the rejected candidate and response references from
the retained `formalize/attempt` checkpoint. An outer recovery seed restores that
same checkpoint, preserving raw malformed JSON or typed-AST text in addition to
placeholder Lean and diagnostics. Creating a child package first verifies the
parent memory, then checkpoints those exact response bytes in the child's own
memory store and updates only the local context reference. The child stores the
original parent reference separately as provenance. Its existing lineage binds
parent snapshot, copied interpretation and complete recovery-context hash. Fresh
roles restore the child reference; no unchecked path traversal into siblings is
needed. Context is search feedback and has no formal artifact authority.

Critics see `raw_formalizer_response`, `raw_response_snapshot`, and
`capability_report` alongside actual diagnostics. They must address the actual
proposal or report; placeholders alone are insufficient repair context.

## Finite regression obligations

1. A valid gap followed by a supported complete proposal executes the actual Lean
   checker and can freeze only the latter proposal.
2. Repeated valid gaps exhaust local attempts without Lean invocation, challenge
   freeze or acceptance; their IDs survive in diagnostics.
3. Unknown/missing IDs, extra keys and malformed gap fields are protocol errors.
4. Critics receive byte-exact malformed and capability responses plus validated
   memory references, with no invented implementation counterexample.
5. Recovery seeds and fresh child prompts preserve exact rejected raw responses;
   changing a retained blob blocks before the next provider call.
6. Historical run inputs remain untouched. Coverage extensions are described in
   their separate prior specification and added to prompts only after their
   executable/compiler semantics exist.
