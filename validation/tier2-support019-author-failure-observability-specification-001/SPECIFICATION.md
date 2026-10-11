# Author failure observability specification, version001

This is a specification-only proposal written before any implementation change. It authorizes no model, author, VIEW, Lean, task, generator, source repair, installation or qualification run. Q003 and its exact failed literal remain immutable. A separate actual protocol probe and root authorization are prerequisites to any later source candidate. No probe result is assumed here.

## Concrete observed gap

Q003's one author returned exactly these119 UTF-8 bytes, without a trailing newline:

```json
{"markers":[],"field_roots":{},"field_eof":{"/system":true,"/user":false},"field_chars":{"/system":892,"/user":429112}}
```

The literal SHA is `sha256:d067c463cad2b80855acd615881e7152cc3cd76a1bf6b2896cc5b96756f3e0c0`. It exposes incomplete user EOF and absent roots. It does not identify a failed operation, chunk, cursor, error or reproduction. Those omissions prevent locating where progress stopped from the delivered literal alone. They do not establish that any reader, CONFIRM, HASH, transport, model or context mechanism caused the outcome. Hidden model/tool traces and model internal reasons remain unavailable. The root reported Q003 terminal BLOCKED with report SHA `sha256:0d739f111e1ffc1ceb5502e04ac51804889087d4cfe4196604299d8854cff7e7`; this specification does not reproduce or replace that verdict.

Current source provides concrete error values at several boundaries: the inline reader emits error records and numeric nonzero completion; the fixed author observer forwards ACTUAL_RESULT and stages own pending data; the fixed pure checkpoint validator throws named errors; HASH requires complete confirmed fields and throws on violations. The current exact4-key success response carries none of those diagnostics. Their existence in source is not evidence that Q003 encountered one.

## Frozen success boundary

Let `SuccessKeys = {markers, field_roots, field_eof, field_chars}`. The successful FINAL remains the current exact object over those four keys, with the current marker order/domain, strict original-field SHA hashes, original Unicode point totals and both explicit EOFs. The existing independently reconstructed whole-message, raw singleton canonical task_name, exactlyone requested Sol/forknone actor, no resampling, literal FINAL preservation, contamination, current-root/input/source binding and all27 claim predicates remain required. In particular the full user field must still exceed400000 decoded characters in the gate fixture; a small diagnostic reproduction never replaces that fixture or its coverage.

Define `AcceptedSuccess(r)` as the existing current success acceptance predicate, unchanged. Failure reporting does not create an alternative acceptance route:

```text
Final ::= ExistingSuccess | DiagnosticFailure
keys(ExistingSuccess) = SuccessKeys
keys(DiagnosticFailure) = SuccessKeys union {failure}
AcceptedSuccess(DiagnosticFailure) = false
DiagnosticFailure => original success obligation remains BLOCKED
```

There is no success discriminator, success metadata, warning-only failure, partial PASS, status conversion or removal of current required fields. Existing incomplete4-key responses remain preserved failures even if no diagnostic can be recovered. The proposed5-key branch is future explicit failure evidence, never a successful response. Its syntax validity is not proof of its contents or cause.

## Minimal closed failure branch

The four ordinary fields contain only the author's actual available partial result under the unchanged field types; unavailable roots remain absent from the partial map rather than invented. Add exactly one `failure` object with exactly these keys:

```text
failure = {
  format: "verislop.author-observed-failure/0.1",
  trust: "UNATTESTED",
  stage: Stage,
  operation: OwnOperation | null,
  observation: Observation,
  reproduction: Reproduction,
  self_critique: SelfCritique
}
Stage ::= "FIRST_INVENTORY" | "NEXT_SYSTEM" | "NEXT_USER"
        | "CONFIRM" | "HASH" | "FINAL_ASSEMBLY" | "UNKNOWN"
OwnOperation = {
  chunk_id: nonempty string | null,
  selector: "/system" | "/user" | null,
  start_char: exact nonnegative safe integer | null,
  output_cap_bytes: exact integer in current allowed bounds | null,
  metadata_reserve_bytes: exact integer in current allowed bounds | null
}
Observation ::= {kind:"literal", source:ObservedSource,
                 text:exact string, scope:"complete"|"visible_fragment"}
              | {kind:"reference", source:ObservedSource,
                 reference:AlreadyExposedReference, scope:"complete"|"visible_fragment"}
              | {kind:"unavailable", reason:"NOT_EXPOSED"|"NOT_RETAINED"}
ObservedSource ::= "NESTED_ACTUAL_RESULT" | "OUTER_ACTUAL_RESPONSE"
                 | "PURE_EXCEPTION_RESPONSE" | "OWN_VISIBLE_PROTOCOL_STATE"
Reproduction = {
  template: "FIRST" | "NEXT" | "CONFIRM" | "HASH" | "FINAL_SCHEMA" | "UNAVAILABLE",
  view: current closed VIEW | null,
  confirmation: current closed CONFIRM | null,
  own_input_literal: exact string | null,
  expected_observed_error_literal: exact string | null,
  availability: "PROVIDED" | "UNAVAILABLE"
}
SelfCritique = {
  violated_check: exact observed error/check string | null,
  own_attempted_retry: current closed VIEW or CONFIRM | null,
  observed_retry_error_literal: exact string | null,
  recovery: "RECOVERABLE_ALLOWED_VALUES" | "FIXED_SOURCE_BLOCKED" | "UNAVAILABLE"
}
```

Every displayed shape is closed: extra/missing keys, booleans used as integers, unsupported stages, invalid selectors and unsafe integers are rejected by a future diagnostic parser. OwnOperation describes the last **reported attempt**, not an attested execution. Stage UNKNOWN and null values are mandatory when the author lacks a concrete observation; `/user` EOF false alone must not be converted into NEXT_USER or a guessed cursor. Cursor units remain decoded Unicode points. The current closed VIEW/CONFIRM schemas and bound/reserve relationships remain authoritative when such objects are provided.

The literal form is the default. AlreadyExposedReference may name only an existing exposed actual chunk/result or a raw reference already present in the author's own visible input; it cannot name a file the author did not create or observe, an imagined future controller sidecar, another actor's state or a hidden native identifier. The controller may add independent file/hash wrappers after delivery, preserving the author's literal unchanged. No extra file-writing permission or raw-trace retrieval capability is granted to the author.

Observation.text copies the exact visible error/output or smallest sufficient exact observed fragment. It does not normalize, strip a prefix, manufacture an error name, replace a truncation marker, or mark a fragment complete. The full original delivered response remains independently retained whenever actually exposed. A reference never substitutes a promised future output hash. An unavailable observation is a truthful diagnostic limitation, not an actionable counterexample or proof of failure cause.

Reproduction records the smallest available concrete operation/input that could expose the reported check, using only already observed own data and the fixed template. It is a candidate minimal reproduction, not a claim of globally minimality or prior execution. The template's registered source hash is supplied by the future frozen root, not asserted by the author. The author may provide an exact owned observed input excerpt where that is sufficient; if an exact necessary input or checkpoint is unavailable, reproduction.availability is UNAVAILABLE. No invented synthetic checkpoint, evaluator marker answer, field-root oracle, hidden helper or source modification is permitted. A fresh independent reproducer may later use a small unrelated fixture to test a mechanism, but must distinguish that from reproducing the actual author's episode.

## Same-actor autonomous critique and recovery

Before reporting a recoverable failure, the same sole author must identify the exact observed violated check and compare its attempted closed parameters with the unchanged protocol. It must construct a concrete own observed error case, then retry only values already permitted by the fixed templates. This introduces no second author, reviewer model, helper, retrospective root cleanup, source patch, hard deadline or new retry-count/cost bound. Existing model/compiler/output budgets remain unchanged.

Nested or outer truncation, malformed/inconsistent output, missing/nonzero/noninteger completion, or a reader failure never permits accepted cursor advancement or CONFIRM. Retry the same explicit selector/start with4096cap/2048reserve, then further reduction only with a viable existing reserve. FIRST/NEXT still execute exactlyone VIEW and forward one full actual result per call. Inventory, complete system EOF, complete user EOF and own HASH prerequisites remain in order. No loop over VIEW calls, automatic cursor, skipped gap/tail or arbitrary prefix loading is allowed.

CONFIRM and HASH remain the fixed explicit zero-VIEW pure exceptions. An author may retry a demonstrably incorrect closed CONFIRM chunk_id only with the actual matching intact own result; it may not turn outer_output_intact true without the existing visible-intact condition. It must not call HASH before complete confirmed EOF. A deterministic fixed-source exception that cannot be corrected by permitted closed values must be reported with its actual error and reproduction; source changes and weakened validation are forbidden. Repeated identical retries without new allowed values are not evidence of correction. Missing observations remain unavailable; the requirement to criticize does not authorize fictional diagnostics or an infinite identical retry to conceal a fixed-source block.

SelfCritique's values are author reports only. They are not new authoritative explanations, semantic review, test success or proof. The independent reviewer must demand a concrete reproduction rather than accepting speculative reliability claims.

## Exporting errors without another call

An already visible nested result or outer pure-exception response can be copied directly into a failed FINAL without another VIEW, pure call, file write or helper. Even when CONFIRM/HASH throws before producing a summary, the author may report an exact exception literal if that literal was actually exposed by functions.exec. The current fixed source must not be wrapped, caught or edited merely to obtain a diagnostic. If the runtime exposes no error text/chunk or the actor did not retain it, use Observation.unavailable and null operation values; do not invent a stack trace, native status, PID, token count or internal reasoning trace.

This proposal does not guarantee recovery of hidden model internal traces, every inner tool result or every error. Own memory availability is limited to the previously authorized own checkpoint/pending/draft data; no controller tool-state extraction, retrospective hidden-trace read or other-agent access is introduced. The author may compose failure JSON and perform the existing permitted syntax validation on its own draft. A syntax check creates no success or lifecycle authority.

## Independent reconstruction and later evidence

Keep legacy reader source, legacy FIRST/NEXT and current author FIRST/NEXT/CONFIRM/HASH exact bytes and ASTs separate from a future versioned failure instruction literal. The minimal first implementation should change only prompt/response diagnostic policy and its registered independent reconstruction/profile. Any eventual code change requires a separate source-before-change specification and a new source candidate. Do not silently alter legacy reader/validator/hash templates while labeling the change diagnostic-only.

The independent reconstruction must authenticate the new exact diagnostic instruction bytes and append/insertion location from accepted source literals/ASTs, reconstruct the complete future message without invoking producer agent_message/template APIs, and reject unregistered additions or self-described message hashes. The successful four-key FINAL and the existing semantic acceptance predicates stay exact. The failure branch parser only records UNATTESTED failure evidence and cannot resolve Q019-07 or any of27 success claims.

For a later failure report f and an independently registered reproduction witness w:

```text
Reported(f) = literal failure branch exposed by the one actual author
SchemaChecked(f) != CauseConfirmed(f)
ReproducedCheck(f,w) = current registered fixed source/input/process
                       independently exhibits f's concrete reported check
ReproducedGenericMechanism(f,w) != ReproducedAuthorEpisode(f,w)
ReproducedCheck(f,w) does not imply AcceptedSuccess(f)
```

Bind any independent reproduction to its actual fresh source/input root, fixed template, raw result/status, environment and declared forwarding/runtime trust. Do not infer Q003's cause from a successful small protocol probe. Keep unavailable channels explicit. No generic probe PASS or old qualification outcome may be reused as a fresh author or whole-root success.

## Minimal future handoff and stop

The root first reviews this specification and the independent actual small-fixture probe. If authorized later, prepare a new diagnostic prompt/profile/source candidate outside all sealed/Q003 artifacts; preserve exact legacy template identities and all27 claim objects; implement the closed failure parser as evidence-only; register concrete negative controls for fabricated/missing/extra fields, wrong cursors, booleans, invented refs, partial-output completeness claims and accidental success acceptance. These are future obligations, not tests authorized by this document.

A later fresh complete root, exact new literal author message and exactlyone new requested Sol/forknone author are required for a new qualification. Do not resume the completed Q003 author. The400000-character floor, full EOF/hash/marker success predicate, oneauthor rule, no hidden helpers/oracle, and all model/compiler/output constraints remain unchanged.

Stop after this specification and its actual source/hash references. Await probe results and root authority; no implementation, source edit, generator, test, VIEW, Lean, model or runtime qualification is performed in this task.
