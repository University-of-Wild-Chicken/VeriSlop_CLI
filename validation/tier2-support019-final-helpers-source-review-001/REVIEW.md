# Bounded helper source review

Source-only review completed. No control, verifier, build, compiler, model, probe,
channel, qualification or task API executed, and no task artifact or actual
qualification result was read. This record grants no closure or activation
authority. SOURCES.json binds inspected current source bytes.

The review covers repaired plan002 admission/evidence handling; equality004
observation and finite ledgers followed by final equality005; core002 witness
production/schema; orchestration001's eight registered process identities,
wrapper child receipt and output index; finalized recorder001's observable result,
VIEW and exact submitted recipe retention. Unfinished adapters, live tool-result
authenticity, actual registration/materialization and runtime evidence are outside
this inspection. Collector authenticity remains the explicitly declared tool
forwarding/orchestration TCB.

## Finding H001: equality004 grouped source mutation fails unconditionally

Affected claims: Q019-01 and Q019-02. In equality-producers004/test_candidate_019.py
lines534-560, binding_and_wires obtains structured_source via
harness.prepare('structured', 'wrongToken'), then tries replacing the raw Lean
match-text string. structured_source constructs an ite DSL term; the qualified
frontend emits @_root_.cond at verislop/formal_frontend.py lines318-320. Thus the
searched match bytes are absent and changed_source == source. The assertion at
line560 fails before the changed-source negative runs, the grouped case is FAIL,
the original-main process is nonzero, and verify_equality's accepted predicate
returns2 instead of0. This is a concrete source witness, not an executed result.

Prospectively closed in005: test_candidate_019.py lines183-186 retain the default
DSL term and add identity_swap=True; lines558-565 regenerate a different source
through the same frontend and preserve exact diagnostic/zero-attempt/zero-receipt
assertions. The other five source/support files compared004-to005 are byte
identical. The sealed004 candidate was not changed or rescored. Runtime success
of005 is not asserted.

## Acknowledged schema discrepancy S001

Affected interface: Q019-03 raw carrier witness decoding. WITNESS_SCHEMA.json
line125 describes raw bytes as keyword.raw or positional slot3, while the bound
CandidateTests.carrier signature at implementation002/test_candidate.py line94
is (system, user, raw=None, name='own.json'). verify_carrier_controls.py line92
serializes the bound method's actual args, so a call carrier('s','u',raw_bytes,
'own.json') retains raw bytes at zero-based index2 and the name at index3. The
schema also uses zero-based indices0,1 for read immediately below. A consumer
using index3 as raw would obtain the filename. This is the already acknowledged
metadata discrepancy; the parent reported a separate prospective clarification.
No unfinished consumer was inspected, and no producer-code false acceptance is
claimed from this sentence alone. The exact frozen schema is preserved.

## Final finite source disposition

No additional concrete counterexample was found in the current inspected
plan002, final equality005, core002 observer code, orchestration001 or finalized
recorder001 within these boundaries. The prior authenticated-byte, canonical
output and typed author JSON defects are repaired at audit_actual.py lines99-100,
25-33 and36-50; first-read metadata is retained and rehashed at lines71-78 and
106-117. These are source findings only. Full27-claim evaluation, live raw process
evidence, compiler outcomes, adapter integrations, actual calls and the one fresh
author remain outside this review. FINAL/STOP.
