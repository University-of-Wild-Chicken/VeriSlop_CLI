# Source-only result

Three concrete defects were found in the frozen qualification-plan admission
helper. The carrier capture amendment002 closes the prior quoted-path finding.
No additional concrete defect was found in the inspected core/equality producer
surfaces or their actual report/ref contracts. Nothing reviewed was executed.

## PREQUAL019-001: interpreted evidence bytes are not the authenticated bytes

`validation/tier2-support-019-qualification-plan/audit_actual.py:60–63`
calls `self.evidence(record)`, discards its authenticated byte string, then calls
`load(regular(ROOT, record["path"]))` to read and interpret the path again.
`registration_lib.py:78–84` authenticated only the first read. `finish()` at
`audit_actual.py:331–334` rehashes the path at the end, not the bytes interpreted
by the second read.

Concrete unexecuted schedule: an evidence file contains registered JSON bytes A
when `evidence()` reads it; it contains different JSON bytes B when `load()` reads
it; it is restored to A before subsequent authenticated reads and `finish()`.
For example, A has a claim row with status BLOCKED and a nonempty blocking reason,
while B has VERIFIED and an empty reason list with the other fields unchanged.
The caller's hash and size checks and the final rehash accept A, while the
predicate checks consume B. The same gap applies to process, channel, author and
other documents read by `doc()`. It also permits falsely blocking authentic A
with hostile B. Parse the authenticated returned bytes rather than rereading.

This is a direct evidence-binding defect in the helper; it does not depend on a
hash collision. No file substitution or reader execution was performed here.

## PREQUAL019-002: lexical output validation permits source mutation after finish

`audit_actual.py:345–346` constructs `ROOT / args.output` and checks
`output.is_relative_to(ROOT / "validation")`. The check is lexical and neither
rejects `..` nor resolves the output path. `:377–378` creates the directory and
writes the report after `audit.finish()` and after the report is marked VERIFIED.

Concrete unexecuted invocation argument:

```text
--output validation/../policies/support019-audit-witness
```

Assume that directory is absent and the other audit inputs are valid. The lexical
validation-prefix check passes. The successful path first checks the frozen
inventory, then creates `policies/support019-audit-witness/report.json` and returns
VERIFIED/0 with the previous source root. The registered source recipe includes
every `policies/**/*.json`, so the helper itself has invalidated its current
source-root check before returning. The `source_names` registration and actual
`bootstrap_tier2.source_inventory` implementation both include this new file.

This finding concerns the helper's own report and output boundary. A separate
outer guard could subsequently reject the mutation; its existence does not make
the helper's VERIFIED/0 result or validation-only output check correct. No output
path was created or invocation performed in this review.

## PREQUAL019-003: the author comparison equates numbers with EOF booleans

`audit_actual.py:294–297` parses the literal final response and the evaluator's
expected JSON, then uses Python `==`. JSON booleans become Python booleans, which
compare equal to integers 1 and 0.

The generic prepared fixture explicitly requests EOF booleans in
`validation/tier2-carrier-context-support-019-implementation-002/prepare_unrelated_fixture.py:24–29`
and creates expectations containing `/system: true` and `/user: true` at
`:85–88`. A literal final response identical to those new expectations except
for the following field passes `Audit.author()`:

```json
"field_eof": {"/system": 1, "/user": 1}
```

It does not contain the requested observed explicit EOF booleans. Hashing and
retaining the exact literal bytes do not fix this comparison. Use type-aware JSON
equality or validate the exact response schema. This is a false-PASS in the
helper's author predicate. The separately required predicate adapters were not
reviewed, so this report does not claim that they would also admit the malformed
response or that whole-root qualification has passed. No final response or
expected output artifact was read or generated; the witness follows from the
generic fixture construction source.

## Reviewed finite surfaces without additional findings

- Capture amendment002 uses equality on complete LF-delimited lines for both the
  forwarding statement and the complete ACTUAL_RESULT fault statement. Quoted
  path data, including escaped literal newlines, cannot become matching source
  lines. The fifteen control sources cover the two original collisions, combined
  escaping/Unicode, exact observer-only differences, missing/duplicate source
  targets, fixed own keys, actual mocked object forwarding/storage and budgets.
  No control was run or prior PASS reused by this reviewer. The schema/registration
  continue to mark hidden native outer envelopes, separate streams and PID
  UNAVAILABLE, with explicit observable-tool-runtime trust and no model-consumption
  authority. The plain author message remains delegated unchanged to candidate002.
- The core gate differs from its generic Q002 source template only in the explicit
  new qualification root and current external-bindings preregistration contract.
  Its exact ordered suite IDs, mandatory module floor, no-skip/xfail/xpass and
  source/test/input entry/exit checks remain present. The final materializer emits
  the manifest/spec/freeze fields and external keys consumed by this gate.
- The carrier pure-control observer collects fifteen candidate tests and fifteen
  capture tests from frozen source, records ordered per-test outcomes and rejects
  skipped/adverse/subtest outcomes. It binds installed carrier source to the
  candidate hash and emits observations without qualification authority.
- The equality observer imports installed production through the primary harness,
  removes inherited partial-control selectors and selects absolute new output
  directories for all three child sources. The supplementary control source is
  byte-identical to its generic template; the primary source differs only in its
  production import and the private/binding source only in the output environment
  override. The original44/new11 labels, grouped semantic-Analysis mismatch
  assertions, actual compiler/kernel calls, proof/prefix/axiom/hash assertions and
  raw process/artifact retention remain in those source files. Reports have the
  `cases`, `label`, `status`, and integer `failed` fields consumed by the helper.
- Registration library relative file/ref checks reject indirect files and enforce
  raw hash and byte count. Its source-map recipe matches current bootstrap source
  inventory and its map-root serialization uses the registered UTF16 member
  ordering. Materialization binds the current complete source/test maps, creates
  the new freeze/spec before its manifest/preregistration, and requires the
  separately reviewed raw-predicate adapter paths. No adapter implementation,
  actual final configuration/preflight, actual fixtures, receipts, model output,
  or qualification evidence was reviewed.

These are limited source findings, not a qualification, activation approval or
reassurance about uninspected runtime evidence. Production and every preexisting
frozen file were left unchanged by this reviewer. Exact hashes are in the sealed
review manifest. FINAL/STOP.
