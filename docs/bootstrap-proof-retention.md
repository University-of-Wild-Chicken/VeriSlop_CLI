# Bounded proof-body retention

This specification precedes implementation and follows the reviewed
`incremental-retention-specification.json` from the trial004 feedback audit.
This increment constructs search state only. It grants no proof, acceptance,
TESTED, or Tier 2 authority. Trial004 and its frozen sources remain unchanged.

## Scope and opt-in

Add optional disabled-by-default contract proof retention. It applies only to
the existing conservative theorem-fragment grammar and exact original sole
proof holes. VSCore implementation and bridge proof paths are unchanged.
No model call, task-specific proof, tactic edit, witness, semantic repair or
subset search belongs to this optimization.

Require a successful native baseline compiled in the current process under the
exact frozen source, toolchain and policy. Resume recompiles retained baselines.
Native sorry warnings, uniquely mapped under Lean's literal-LF and Unicode
character position rules, determine unresolved names U. Lexical sorry branches
do not authorize edits. The selected set S is a subset of U, and every
unselected body, header and nonbody byte must match the baseline/frozen scaffold.
Every proposed body must parse as exactly one term through the existing native
syntax helper. Unsupported shapes or boundaries are ineligible, never repaired.

## Structured native observation

Retain original native severity-error messages and file positions together with
source hash, policy hash, toolchain identity, compiler outcome and completeness.
Never derive authoritative positions by parsing formatted errors. Every failed
evaluation error must correspond exactly to an original error from the submitted
module. Missing/malformed positions, nonmodule filenames, synthetic errors,
timeout/process failure, missing artifacts and inconsistent inventories make
retention ineligible. Preserve existing formatted errors and raw results.

## Bounded algorithm

Keep original model response, decoded proposal C and failed native result exact.
Begin W=C and reverted set R empty. Map every native error uniquely inside an
edited proof-body span belonging to S minus R. Header/outside/ambiguous positions
are ineligible. The union E must be nonempty. Replace exactly those complete
body slices with baseline B slices, retaining every other W byte unchanged.
Record old/new source hashes, byte spans and each copied slice hash.

Persist counters before every whole-file native recheck. Use unchanged native
resource/isolation limits and the remaining proof-job deadline. Rechecks never
call a model. A failed recheck may expose another error: revert only additional
uniquely mapped edited bodies, never undo a reversion. Stop after at most two
rechecks per original model proposal and four per frozen proof job, including
interrupted dispatches and across provider escalation/resume.

A successful recheck may become a search baseline only when its newly mapped
native unresolved set is a proper subset of U, all names remain original holes,
and all frozen/unselected bytes still match. Failure, ineligibility, exhausted
caps or no progress retains B. Genuine infrastructure/storage failures keep
their ordinary explicit treatment. An optimization miss is not contract falsity
or a new user-task failure.

Bodies referring to unresolved declarations may elaborate while their transitive
axiom closure still contains sorryAx. Retained/elaborating bodies are never
independently called PROVED. With zero native sorry warnings, the resulting file
still follows ordinary statement-preservation, native replay, forbidden-axiom,
acceptance and export checks without relaxation.

## State, receipts and handoff

Bind caps and eligibility implementation to the frozen proof-job/search identity.
Use existing bounded CAS memory and single-writer run locking. Restore counters,
input references and receipts exactly; interrupted rechecks remain consumed.
Tampered sources, native observations, selected sets, slice metadata, counters
or bindings must not create a baseline or refund budget.

Retain raw provider response, exact decoded proposal and failure, successful
baseline/observation, each mechanical source/result, and frozen source/toolchain/
policy/implementation bindings. Receipts contain version, authority, job hash,
original/baseline refs, selected names, round input/output hashes, result refs,
reverted declarations and slice hashes/spans, persistent ordinal/caps, old/new
unresolved names and final status (promoted, ineligible, no_progress,
budget_exhausted or infrastructure_failure).

The next proposal sees the mechanical current baseline separately from the exact
latest model rejection and its actual diagnostics. Include a compact retention
receipt. Never relabel a mechanical build as a provider success or replace the
latest failed response/evaluation with a synthetic success.

## Qualification

Use unrelated native fixtures for independent successful edits beside failure;
transitive sorry dependencies and false propositions; cascading errors; changed
frozen or solved bytes; outside/stale/malformed/incomplete positions; Unicode
LF accounting; unused lexical sorry branches; no progress and persistent caps;
real recorded-call failure-to-baseline prompt handoff; and restoration/tampering.
Tests must establish actual whole-module results and final axiom rejection,
not infer correctness from missing diagnostics. No live models or hand-repaired
project candidates are part of this increment. A future live qualification
requires a new frozen trial from the original natural-language request.

## Registered interfaces and diagnostic decoder prerequisite

The optional agent field `proof_retention` is a boolean, default false, read from
the configured contract prover role. Direct `prove.run` callers may explicitly
set the same boolean; other proof/implementation paths ignore this capability.
The fixed bounds are two native rechecks per proposal and four per frozen job;
they are not user-expandable. Native JSON output is split only at literal LF,
and an unresolved warning requires both severity `warning` and kind `hasSorry`.
Information or error text containing the word `sorry` cannot establish U.
The full native observation is separate from the existing focus descriptor.

## Prompt references for added native telemetry

Exact new native observations (including base64 stdout/stderr, argv and process
limits) remain in bounded CAS as `latest-native-diagnostics.json` and the original
result in each retention receipt. The next proposer retains the entire previous
candidate, exact provider response and every existing formatted native error.
Its previous-result field adds `native_result_ref` with an integrity-bound memory
blob path, SHA-256 and byte count; the summary separately pins the receipt
snapshot. These references explicitly identify additional retained telemetry;
they do not duplicate raw compiler streams inline or omit any existing error
content. Resume restores the complete native observation from CAS and verifies
its reference before using it for historical feedback. A fresh native build is
still mandatory before using any retained source as a baseline.

The promoted receipt commits the exact mechanical source before the general proof
attempt checkpoint. If execution stops between those commits, resume recovers the
newest authenticated promoted source from retention history and recompiles it in
the current process before comparing it to the saved best baseline. It keeps the
raw original failed proposal/response and never refunds or repeats the consumed
substitution dispatch. Unfinished pending dispatches remain consumed and cannot
supply a successful source. The trusted append-only CAS journal is the persistence
boundary; a wholesale coherent rewrite of that trusted store is outside its hash
integrity guarantee, as in the existing memory implementation.

Persistent retention history is reconciled against every exact-stage snapshot
reference in the authenticated memory journal. A receipt cannot discard spent
counters by replacing its own `previous` pointer with a shorter chain. The
read-only `agent_memory.snapshot_refs` API returns journal-order references
without hydrating all large artifacts. If the deadline expires while the pending
checkpoint is being committed, the reserved counter stays consumed but no native
process is launched; its explicit budget-exhausted receipt has no native result.

Legacy proof snapshots without full native telemetry retain that absence; the
feature must not invent a null native result or a historical raw response. A
present native-result reference and retained artifact must agree in presence,
hash and size. Opting in still performs a fresh baseline compilation before any
retention attempt, including when previous feedback predates the feature.
