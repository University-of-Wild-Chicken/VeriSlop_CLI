# Lean compiler process evidence

This milestone records the concrete subprocess observations behind a Lean
compilation result. It does not change proof acceptance, compiler limits, source
semantics, or the severity of existing base-verifier failures.

The motivating observation is the immutable stage013 resource audit:
`validation/tier2-proof-resource-audit-013/resource-audit-attempt-1c8_u0xv/audit.json`.
Two rejected bridge proposals retain both a Lean unification error and stderr
reporting `INTERNAL PANIC: out of memory`. The existing result omits the process
return code and invocation, preventing more precise attribution.

For every completed compiler invocation, retain a closed, versioned process
record with the requested argv, working directory, actual return code, actual
timeout flag, requested resource limits, elapsed time when actually measured,
and exact stdout/stderr byte counts and SHA-256 digests. Distinguish requested
argv from any sandbox wrapper argv. Retain existing full output and sandbox
profile evidence. Never report inferred peak memory, a host OOM kill, a signal,
or a particular failed memory boundary without the corresponding observation.

An explicit stderr memory-panic report is a reported compiler panic. It may
coexist with parsed Lean errors; preserve both channels. A negative return code
may identify a termination signal only when the subprocess API supplies that
code. A timeout is established only by the subprocess result's timeout flag.
Do not replace a parsed Lean error with a speculative cause or conclude that
more memory would establish a proof.

The record belongs to the exact current compile attempt. Bind it to the input
module/proof hashes and retained output artifacts wherever the existing bridge
diagnostic record is produced. Schema/protocol failures before invocation must
not inherit a prior attempt's process record. Missing process telemetry is
explicitly unavailable, never synthesized.

The process record format is `verislop.lean-compile-process/1`. It binds the
module source and, for named modules, the exact setup bytes. Full stdout/stderr
are retained losslessly as base64 together with their byte counts and hashes;
durations are decimal strings, or null when unavailable. Requested Lean heap,
sandbox address-space, CPU, file-size, core and wall-time boundaries remain
distinct from actual subprocess observations. The launcher return code belongs
to the recorded launcher argv, including a wrapper when one was used.

Successful bridge builds retain a defaulted `Build.process_evidence` inventory
keyed by compiled module. Acceptance stores the A/B inventories in the
hash-bound EvidenceStore raw result as additive observational fields. They are
excluded from deterministic build observations, certificate descriptors and
fresh-build equality comparisons. Preview returns the same inventory in its
advisory info for its caller to persist. Existing callers and stored semantic
evidence without this optional inventory remain compatible. This telemetry is
not an additional proof-acceptance predicate.
The advisory CLI retains that inventory in `compile-process-evidence.json` and
reports its path/hash; agent preview check records retain the same inventory.
These advisory artifacts do not become semantic proof evidence.

Rejected bridge compiles retain the current process record and the preceding
completed compiler inventory in the existing diagnostic. When a compiler
invocation completes but stage or compiled-artifact validation subsequently
raises an infrastructure diagnostic, attach its captured process record while
preserving the exception, diagnostic code and severity. Failures before an
invocation have no current process record.
Later bridge kernel/audit diagnostics also retain the completed compiler
inventory; they do not turn compiler telemetry into a kernel-process record.

Keep existing `CompileResult` fields and existing callers compatible. Additive
telemetry does not permit accepting a failed compile, modifying a theorem,
extending an axiom policy, or fabricating model or kernel evidence. Optional
readable-view support can separately classify its own unavailable status from
these observations under its specified policy; base-verifier behavior stays
unchanged.

Validation must exercise successful and failed process results, parsed error
plus memory-panic coexistence, timeout observations, exact output digests,
attempt-local binding, and compatibility of existing compile-result consumers.
Tests must assert observable records and existing acceptance behavior, rather
than cause an artificial out-of-memory event or claim an unmeasured limit.
