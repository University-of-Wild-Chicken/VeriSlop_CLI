# Prospective qualification plan

Overall status: PENDING. Every item below is PENDING and NOT RUN. No subprocess
fixture, Lean build, model call, test, or qualification claim was executed for
this design. Read/hash/file-writing commands used to draft it are not compiler
qualification evidence.

Use newly authored unrelated generic fixtures after the current audit/source
hold becomes terminal. Do not read/reuse any native D21/A23 candidate, proof,
reference payload, prior answer, or sealed run to author the fixtures. Freeze
the implementation, specifications, unrelated fixture inputs, receipt policies,
normalization rules, verifier identities and planned checks before execution.
Run within the existing compiler/kernel/whole-build limits and call budgets.
Store commands, actual process receipts and terminal results; do not count a
mocked result as an actual compiler execution.

## Actual execution checks — all PENDING

1. **PENDING: unrelated successful compiler execution.** A small fresh generic
   Lean module succeeds through the real pinned isolated compiler. Assert its
   observed launcher argv/cwd and numeric returncode, measured timeout flag,
   byte-exact stdout/stderr sizes/hashes/blobs and source/setup binding. If the
   real sandbox uses a wrapper, explicitly identify its compiler-launcher role
   and mark an unobserved child boundary unavailable; launcher success cannot
   establish a separate child's status.
2. **PENDING: unrelated rejected compiler execution.** A different fresh generic
   module has an ordinary elaboration/type error. Retain actual nonzero measured
   returncode when supplied, both raw channels and parsed errors, then preserve
   existing blocking outcome and severity. No artificial OOM event is required.
3. **PENDING: bounded actual timeout execution.** Use an unrelated deterministic
   fixture chosen to exceed its already-authorized frozen timeout without
   exhausting host resources. Retain actual timeout observation, numeric
   returncode only if observed, exact captured streams and explicit partial
   capture when applicable. Assert failure retains completed preceding receipts.
   Preflight fixture suitability in the later qualification scope; no fixture is
   run or claimed suitable here.
4. **PENDING: two complete unrelated clean-source builds.** Exercise fresh
   contract acceptance and the full generic semantic path using a new unrelated
   Tier 2 source fixture. Retain every actual process in separate outer A/B
   inventories. Bind source/setup/dependency and output identities, retain
   nested raw evidence without treating semantic aliases as fresh compiles, and
   preserve unchanged mechanical/semantic outcomes and reproducible outputs.
5. **PENDING: selected optional phases.** Use an unrelated fixture for each
   actually supported frozen BASE/SELECTED path. Check phase membership and
   ordinals against the predeclared plan; do not merge repeated module names.
6. **PENDING: later failure/interruption.** A controlled unrelated failure after
   successful compiler completion retains completed receipts; a whole-build
   interruption preserves available partial records and explicit unavailability
   without prolonging the deadline or changing the original diagnostic.

## Byte, binding and normalization controls — all PENDING

These may use pure receipt fixtures or targeted runner fixtures. They supplement
the actual executions above and cannot replace them.

- **PENDING:** binary/non-UTF-8 stdout/stderr round-trip, exact empty streams,
  separate retained-prefix/full-stream hashes, cap-at/cap-over limits, aggregate
  allocation order, and interrupted capture. No dropped byte is silently full.
- **PENDING:** pre-launch failure, unmeasured child status, missing timeout flag,
  synthetic/legacy `CompileResult`, and unavailable stream use explicit null and
  reasons. Boolean returncodes, invented zero exits and copied prior receipts
  fail receipt validation.
- **PENDING:** remove, duplicate, reorder, relabel or substitute one receipt;
  alter its source/setup/dependency hash, stdout/stderr byte, byte count or blob
  digest; omit a expected compile step or add a unplanned step. The receipt
  validator exposes each inconsistency without granting proof authority.
- **PENDING:** known temporary root differences normalize only at declared path
  locations or recorded stream offsets. Raw A/B observations remain retained.
- **PENDING:** unknown temporary path, toolchain path, non-path argv option,
  source location, error/warning text, changed returncode/timeout flag, output
  hash, unlisted time-like text, stream timestamp or one non-path byte remains
  different. No catch-all numeric/path/hex regular expression may hide it.
- **PENDING:** path prefix without the specified boundary, overlapping roots,
  malformed role mapping and an unregistered argv path form are rejected or
  remain exact. The replacement ledger recomputes the projection from raw data.
- **PENDING:** launcher equality cannot become `AGREE` with partial/missing
  required launcher measurements; unmeasured child scope remains unavailable;
  receipt provenance telemetry remains separate from existing closure proof and
  deterministic-output predicates.
- **PENDING:** independent A/B receipts do not share process invocation IDs;
  temporary semantic A/B aliases of one build do not multiply actual executions.
- **PENDING:** existing base failures, optional-support behavior, acceptance
  semantics, policy/axiom/TCB inventories, proof milestones and reproducible
  slots remain identical for equivalent fixture inputs. No rerun fills old
  evidence, extends a timeout or spends additional model/compiler call budget.

## Completion rule

Every claim above remains PENDING until an exact retained result from its
predeclared check is available. Record PASS/FAIL/UNAVAILABLE only from those
observations, including fixture/input/implementation hashes. An unobserved
inner-child boundary remains unavailable, and must not be inferred from
launcher success or become a new trust component. A mock-only success or
agreement of build metadata cannot close actual launcher-process qualification.

This plan does not authorize implementing or executing during the current
terminal audit/source hold. Existing sealed receipt presence/sufficiency remains
UNDETERMINED here; a confirmed retained inventory may make production repair
unnecessary. Its deliverable is this prospective draft only.
