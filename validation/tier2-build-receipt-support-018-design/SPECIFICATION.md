# Clean-source-build compiler receipts, prospective specification

Status: DRAFT ONLY; every qualification claim is PENDING. Applies only to a new
run frozen after implementation and qualification. Historical receipts remain
unavailable when their measurements were not retained. Current sealed AUD-17
receipt presence/sufficiency is UNDETERMINED here; the auditor resolves it. This
draft does not assert that existing capture or serialization is absent. A
confirmed current inventory may make production retention repair unnecessary.

## 1. Observational boundary

Each actual compiler-launcher subprocess issued during one clean source build
gets one receipt with an explicit process role, collected at the observed
process boundary and handed upward before its
temporary stage is removed. This covers fresh contract acceptance compilation
and every executed generic-library/goal/proof phase. The freeze records an
ordered expected step inventory for the selected path, including fresh
contract compilation and optional phases; it must be obtained from the actual
generic execution path, not inferred from successful output files. No new
compilation, replay, model call, or dependency lookup is authorized by retention.

An outer build index contains `build_label`, `closure_root`, frozen source,
verifier and toolchain identities, ordered invocation ordinals, phase/module
identities, exact receipt/blob path-size-hash references, expected-step inventory
hash, and `inventory_completeness`. Each expected step is `observed`,
`not_started`, or `observation_unavailable`, with a stable reason and any actual
measurements. Unexpected, duplicate, reordered or missing steps are visible.
One actual invocation referenced by duplicated semantic A/B aliases remains one
outer receipt with one ordinal. The outer clean builds A and B remain distinct.

Publish at `builds/<label>/compile-process/index.json`, with receipts named
`receipts/<zero-padded-ordinal>.json` and raw blobs below `streams/`. These are
retained in the same atomic execution publication and exact execution inventory
as the existing build artifacts. Put a path/hash reference beside the outer
build's execution metadata, outside its existing `outputs` projection. A
dedicated receipt-completeness report is provenance telemetry; it does not
establish any theorem or change a closure/acceptance predicate.

## 2. Exact process fields and attribution

Use a closed versioned receipt envelope. Include:

- Invocation identity: outer build label, ordinal, phase, module, input source
  SHA-256, raw setup SHA-256 if any, sorted dependency module-part hashes,
  toolchain identity and binary SHA-256, producer verifier ID/hash.
- Requested payload: exact argv as a string array, resolved invocation cwd,
  source/module role, unchanged requested resource limits, and existing sandbox
  isolation observations. Hashes/paths bind inputs; these are not new payloads.
- Observed launcher: exact executed launcher argv/cwd where supplied by the
  runner, numeric integer returncode where observed, `timed_out` where observed,
  and the mechanism that measured each field. JSON booleans are not integers.
  A negative returncode retains the subprocess API's numeric convention; do not
  replace it with an inferred signal, memory cause, or compiler failure cause.
- Observed compiler payload: exact argv/cwd, numeric returncode and timeout
  observation only when the existing process supervisor actually observes that
  boundary. Attach its measurement mechanism and link to the launcher. When the
  compiler is the direct observed subprocess, explicitly identify that same
  process. When a wrapper is observed without child measurements, mark child
  fields unavailable. Requested payload argv and a wrapper exit are never
  copied into observed-child fields. If later implementation cannot collect
  child measurements within the frozen sandbox/TCB and limits, it must report
  that limitation. Complete launcher observation does not claim complete child
  measurement and does not require adding a trust component or changing the
  sandbox.
- Actual elapsed duration as decimal text, start/end timestamps only if
  measured, and availability/reason per unmeasured field. Do not derive process
  duration or returncode from the enclosing verifier, build `ok`, parsed errors,
  module existence, or certificate status.

Observation states are `available`, `partial`, `unavailable`, and `not_started`.
An available returncode is a measured integer; otherwise it is null with a
reason. An unavailable timeout flag is null, not false. A timeout may retain a
measured numeric returncode after reaping, or a null returncode if reaping was not
observed. Requested limits are separate from observations. A compiler timeout,
whole-build interruption, launch failure and telemetry write failure must stay
distinct. Pre-launch failure cannot inherit the previous invocation's receipt.
No receipt represents kernel replay, toolchain version queries, native runtime
behavior, or a verified compiler chain unless those separate events are
explicitly scoped and measured; they are outside this compiler-receipt design.

## 3. Byte retention, completeness and caps

For stdout and stderr separately retain exact binary bytes, not decoded or
filtered lines. Decoded diagnostics remain derivative views. Each stream records
`observed_byte_count`, `retained_byte_count`, SHA-256 of retained bytes, optional
SHA-256 of the complete observed stream, exact blob reference,
`capture_complete`, `retention_complete`, `cap_bytes`, and an explicit loss
reason. Empty observed streams have zero length and the hash of empty bytes;
unobserved streams use null counts/hashes, never invented empty blobs.

The prospective retention policy freezes a per-stream retained-prefix cap of
16,777,216 bytes and an aggregate retained-stream cap of 134,217,728 bytes per
outer build. These are storage caps only: they do not alter any existing
compiler/output/optional-support limit or determine proof acceptance. Retain the
prefix in process-ordinal order, stdout then stderr for each ordinal; allocate
the smaller remaining aggregate allowance. Record both requested cap and actual
allowance. The fixed ordering makes allocation independently checkable.

Digest/count all bytes actually observed from spawn until observed EOF, even
after the storage cap, using bounded streaming storage within the existing
execution deadlines. No extra grace deadline or unbounded drain is introduced.
When EOF/drain is not observed before interruption, mark capture partial and
record only the observed-prefix count/hash. A full-stream hash is available only
when capture is complete. `capture_complete` means complete capture of that
observed process stream, including after timeout cleanup if actually completed;
it does not mean the compiler completed or describe hypothetical output after a
kill. `retention_complete` additionally requires all captured bytes be retained.
Any cap, short read, missing blob or failed write is explicit. A prefix hash is
never presented as a complete-stream hash. Partial/unavailable streams cannot
satisfy a full-retention qualification claim.

Preserve finalized receipts and streams when later module validation, kernel
replay, audit or whole-build processing fails. Preserve observed partial data
when interruption permits publication. If interruption prevents collection or
publication, report the unavailable step/measurement with that reason; do not
invent successful cleanup. Collection does not swallow or downgrade the
original error, diagnostic severity, timeout, or terminal state.

## 4. Predeclared deterministic receipt comparison

Existing reproducible-output slots and their equality remain unchanged. Add a
separate diagnostic comparison of a canonical receipt projection with results
`AGREE`, `DISAGREE`, or `UNAVAILABLE`. This comparison does not grant proof
authority, supply a missing proof, add an acceptance predicate, or redefine the
registered build/determinism claims. The comparison scope explicitly identifies
launcher observations and requested payload configuration; independently
observed child fields, when present, form a separate scope. Every difference
outside the following frozen rules is reported at an exact JSON pointer or byte
offset. Partial or unavailable required launcher measurements cannot become
`AGREE`; unmeasured child scope remains `UNAVAILABLE` even when launcher scope
agrees.

Freeze normalization rules, their version/hash, and path-role mappings before
the new run. For each actual invocation register exact supervisor-created
temporary roots with role IDs: `FROZEN_INPUT`, `CONTRACT_ACCEPTANCE`,
`SEMANTIC_BASE`, `SEMANTIC_SELECTED`, and `DEPENDENCY_STAGE` with ordinal suffix
when a role occurs more than once. Each root is one observed absolute byte
string, maps to one marker `@TMP[<role>]`, and is registered before spawn. Build
A and B receive the same role IDs for corresponding steps. Reject ambiguous,
overlapping role roots; paths outside registered roots stay exact.

Only these structured path fields may replace an exact registered root, either
as the whole string or as an absolute-path prefix followed by `/`: requested
and observed cwd; path-valued argv elements predeclared by argv index and form;
sandbox `read_only_paths`; and setup dependency part paths. For a structured
option containing a path, freeze its exact option prefix and value index before
spawn. Preserve relative suffixes, argv order, flags and every other byte. Keep
the original setup bytes/hash and also hash its canonical structured projection;
never normalize a setup hash directly.

Raw stream bytes remain unchanged and hash-bound. An optional normalized stream
view replaces only exact registered root byte strings followed by EOF, `/`, or
one of these ASCII delimiter bytes: TAB, LF, CR, SPACE, `"`, `'`, `:`, `)`, `]`,
`}`. Record the rule ID, every replacement offset, matched raw bytes and marker.
Process replacements left to right with no rescanning of inserted markers. Any
other path-looking substring remains exact. The recipe may operate on arbitrary
bytes and must not decode/re-encode them. No source location, error text, warning,
returncode, timeout flag, module/dependency hash, meaningful artifact byte,
non-path argv, or arbitrary hexadecimal/numeric text is excluded.

Exclude measured start/end timestamps and elapsed duration only at their exact
receipt JSON pointers. Compare a projection identified by logical outer-build
role and invocation ordinal; the raw build label remains recorded. Store a
comparison ledger listing every excluded pointer with its raw A/B values and
every normalization replacement. Do not strip timestamps from compiler output.
Do not normalize toolchain paths, unrelated host paths, unknown temporary paths,
evidence hashes, input/output hashes or arbitrary metadata. Any additional rule
requires a new pre-run freeze and qualification. Retain raw receipts, blobs and
their exact hashes even when normalized projections agree.

## 5. Historical and semantic compatibility

The supplied sealed AUD-17 run remains historical. If the auditor establishes
that any process measurements are missing, those are
`unavailable: not_retained_in_original_run`; no rerun may be presented as a
receipt for it. New source/schema/verifier/policy changes create
a new frozen root and require fresh evidence under existing rules. Existing
semantic evidence stays readable; absence of these additive historical
measurements does not retroactively manufacture a failure or a complete receipt.

This specification changes provenance retention only. Existing proof-state
behavior, source semantics, axioms, TCB declarations, acceptance predicates,
registered deterministic outputs, all budgets/deadlines and call budgets remain
in force. Implementation and actual positive/failed/timeout qualification are
deferred until the current terminal audit and production-source hold end, and
until the auditor's resolution establishes a need. No actual code edit is
proposed during the current hold.
