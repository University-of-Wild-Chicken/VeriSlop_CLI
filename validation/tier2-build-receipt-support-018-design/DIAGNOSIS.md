# Prospective clean-build receipt diagnosis

Status: DRAFT ONLY. Qualification: PENDING. No production implementation or test
execution accompanies this document.

The coordinator supplied the frozen AUD-17 finding: stage017's two registered
clean builds mechanically passed and agreed, while actual compiler process
argv, logs and numeric subprocess return codes were not retained. The terminal
`["verislop", "verify"]` invocation and its zero exit code describe the outer
verifier. This diagnosis records that finding as supplied; it has not read the
sealed run, its task candidate, proof, reference, or prior answers. It makes no
claim to reconstruct missing historical measurements. Current sealed-run
receipt presence and sufficiency are UNDETERMINED by this generic-code
diagnosis; the ongoing terminal auditor resolves them under its unchanged check.

The coordinator holds the production/docs/tests root
`c0225d21274f4c4819800e3f136f49e68c9762eb0322860438e57d43e179db49`
unchanged through the current terminal audit. That whole-root value was supplied,
not independently recomputed here. Only the seven generic files listed in
`READ_INPUTS.sha256` were read for content. Discovery read filenames, not native
payloads. All new files belong to this new design directory.

## Generic retention path

1. `verislop/leanbridge.py:243` defines `CompileResult.process_evidence` as
   optional, attempt-local telemetry. `_compile_process_evidence` at line 263
   binds source/setup hashes, requested argv, launcher argv, invocation cwd,
   launcher returncode, timeout flag, limits, measured elapsed time, isolation,
   and full stdout/stderr bytes encoded as base64 with sizes and hashes.
   `compile_module` and `compile_named_module` attach this after `sandbox.run`.
   The helper's explicit contract says that `SandboxResult.argv` and returncode
   belong to the launcher, which may be a wrapper. It does not establish an
   independently observed wrapped Lean child returncode. The permitted scope
   did not include the sandbox implementation.
2. `verislop/bridges/vscore3_checker.py:290` separates `Build.process_evidence`
   from deterministic `Build.observation`. `_run_build_once` collects compiler
   telemetry per module and propagates completed records into failure
   diagnostics. `run_build` may prefix two executed phases as `BASE::` and
   `SELECTED::`; these are actual distinct invocations and cannot be merged.
   `_audit` records only `ok/errors/sorries` compile summaries in its semantic
   observation, alongside checked module and replay identities. A summary is
   not a substitute for a process receipt.
3. `verislop/targets/vscore3_target.py:36` declares twelve generic library
   modules. The checker compiles those modules plus goal/proof as selected;
   it stages the contract module supplied by its context. Staging a contract
   module is not another compilation and must never acquire a invented process
   receipt. Optional BASE/SELECTED execution changes the invocation inventory,
   not the source semantics or compiler policy.
4. `verislop/bridges/vscore3_checker.py:695` constructs semantic build records
   and evidence. Its raw EvidenceStore result embeds A/B compiler inventories.
   Those inventories stay outside the semantic certificate descriptor and
   deterministic observation. The outer invocation is bridge acceptance,
   not an individual compiler invocation.
5. `verislop/backends/vscore3_closure.py:542` imports/replays the contract afresh
   and feeds that current compiled module into a fresh semantic build. It calls
   `checker.outputs(build, build)`: the two entries in this temporary semantic
   evidence are aliases of one closure-label execution, not two additional
   clean builds. The actual independent clean builds are the outer A and B.
   A correct receipt index must not count the alias twice.
6. `_clean_build` carries every generated semantic file in
   `BuildObservation.artifacts`. On success, `run` writes that bag under
   `builds/<A|B>/`, hashes each published file into `execution_inventory`, and
   atomically publishes the result. Thus the current generic code has a possible
   nested semantic raw-evidence retention route. That observation is relevant
   for the current auditor to inspect under its unchanged check; no old artifact
   or execution-source snapshot was inspected here.
7. Closure's primary A/B JSON contains build summaries and reproducible outputs;
   the terminal EvidenceStore invocation is `["verislop", "verify"]`. There is
   no explicit closure-level index guaranteeing every actual compiler process
   from fresh contract acceptance and semantic compilation, its measurement
   boundary, or stream completeness/caps. The permitted files show contract
   artifacts and a replay receipt crossing the import boundary, but not its
   compiler process inventory. Failed clean builds become plain dictionaries
   containing error messages; there is no successful artifact bag to publish.
   Some structured process diagnostics may survive, but that is not a closed
   per-build receipt inventory, especially when total-wall interruption occurs.

The exact current generic locator is:
`builds/<outer-label>/semantic/certificate.json` -> its `evidence.path` ->
that evidence record's `raw_result_ref` ->
`builds/<outer-label>/semantic/<raw_result_ref>`. The checker passes the following
key hierarchy as the EvidenceStore `result` argument (the surrounding raw
EvidenceStore envelope was not inspected):

`compile_process_evidence.builds.<A|B>.<module-or-phase-key>.record`

That record contains `requested_argv`, `launcher_argv`, `working_directory`,
`returncode`, `timed_out`, and `stdout`/`stderr` with `byte_count`, `sha256`,
`content_b64`. Its sibling `availability` distinguishes unavailable synthetic
or legacy results. The current generic serializer returns both evidence-record
and exact raw-result bytes, and closure's artifact bag carries both under the
`semantic/` prefix. This locator is supplied to the coordinator for the existing
auditor's unchanged check; it is not an inspection or reassessment of AUD-17.

## Conditional prospective receipt contract

The accompanying draft defines explicit, complete and discoverable receipts at
the clean-source-build boundary. It binds fresh contract compiler observations
and actual semantic phases to their outer build label, preserves completed and
interrupted observations on failure, and distinguishes launcher measurements
from payload measurements. A wrapper exit cannot be silently labeled as Lean's
exit. It does not propose actual code edits during the audit. A confirmed
existing retained inventory may make a production retention repair unnecessary;
whether any implementation is needed remains PENDING the auditor's resolution.

Do not add a proof predicate. Preserve the frozen compiler/kernel/whole-build
limits, deadlines, execution and model-call budgets, optional-support policy,
source semantics, proof obligations, axiom policy, TCB declaration, comparison
slots and acceptance criteria. No compiler/kernel/model rerun may be performed
merely to fill a receipt. Any implementation is deferred until the current audit
and source hold are terminal and a need is established. Upstream import/runner
coverage remains outside this read scope and is not an asserted source defect.
