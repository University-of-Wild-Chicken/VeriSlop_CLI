# Independent offline G04 semantics diagnostic

Base: `2c63b2b20bb804d30f3573c17639452f9e53a304`.
Request: `examples/project-bootstrap/G04-release-manifest.txt`, SHA-256
`128aeea6d95a4df6fc679c5101e58e5178033d3e82da9eb978be48f57e4e6298`.

This is a separate finite post-hoc diagnostic, not a qualification mechanism.
It does not assign TESTED, prove the request universally, establish
END_TO_END_VERIFIED, accept release review, or change strict Tier 2 gates.
No historical trial is reclassified. It makes no claim that G04 has qualified.

## Independent expected semantics

`synthetic_dataset/tools/g04_oracle.py` implements an imperative reading of the
natural-language request, without importing candidate implementations, accepted
formulas, Lean evaluators, model providers, or review code. Eighteen fixed cases
cover scalar length, combining marks, supplementary-plane characters, NUL,
order, duplicate occurrences, empty/disabled paths, empty input/prefix,
zero bytes, exact concatenation, and arbitrary-precision sums (through 10^100).
The suite is finite: these are tested examples, not bounds on the request domain.
Surrogates, negative sizes, floats and Bool-as-Nat are rejected, never coerced.
The report encodes all natural numbers as tagged decimal strings.

The first case has prefix U+1F511 U+0000 and two enabled paths U+0065 U+0301,
plus an empty-path and a disabled asset. The expected lengths are 4, the total
is 6 and the count is 2. Its UTF-16 length is 5 and UTF-8 length is 8.

No caller in generation, proving, review, or `run_local_hybrid.py` imports these
modules. `tier2-project --independent-check` remains rejected. Only the separate
command below discloses diagnostic cases after generation. Do not attach its
case output, report, test fixtures or oracle files to author/prover/reviewer
prompts, nor use failures to repair the same frozen trial. Once this suite is
published it is a disclosed regression suite, not a permanently secret holdout;
a later benchmark needs separately reserved cases.

## Existing interface and read-only adapter

The existing `target_case` path in `verislop/review_counterexamples.py` binds
assignments to accepted functional guarantees. Replaying that predicate alone
cannot detect an incorrect natural-language formalization. It also is not a
general source-output extraction API.

The new `check_g04_offline.py` instead reuses:

* `vscore3_checker.load_context` and `derive_goal` for frozen bundle binding,
  exact source typing, accepted nominal record layout, and native goal derivation;
* `vscore3_replay.literal` and `check` for concrete accepted-carrier literals and
  pinned-kernel replay of a new closed equality: `source_fn_solve(input) = expected`.

Expected outputs come only from the independent oracle. Accepted formulas are
not used as expected results. The native replay's existing dependency audit
rejects reliance on accepted guarantee, refinement, or transfer theorems.
Reports retain the native equality decision and its proof/dependency evidence;
there is no fabricated actual-output dump. A false equality means a mismatch,
not an explanation of which field differed.

Supply a frozen `bridges/<bridge-id>` directory, exact edge ID and source digest.
The adapter uses descriptor-relative reads, checks all manifest sizes/hashes,
rejects links/traversal, and rechecks the snapshot after loading and after replay.
It does not write to the bundle or run package. Native scratch builds are handled
by the existing temporary-directory/sandbox machinery. No candidate Python,
model inference, package update, evidence publication or toolchain download runs.

This checks only the explicitly pinned bundle source. It does not authenticate
that source as the latest delivered program of a live run, establish request
provenance for an entire historical trial, or rebuild its final closure. The
caller must select the intended frozen bundle; the report binds plan, manifest,
source, profile, request, suite, checker sources and native replay identities.
A valid bundle is required even if its final refinement/release was unsuccessful.
Only exact G04 field names/sorts and a one-argument `solve` entry are admitted;
opaque record IDs and field order are handled from the accepted profile.

## Commands

Run from the repository root. Python needs no additional packages.

```sh
python -m unittest tests.test_g04_offline tests.test_local_hybrid_tier2 -v
python synthetic_dataset/tools/check_g04_offline.py --cases
```

With the bundle's pinned Lean toolchain already installed (currently 4.34.1 for
the base repository), run the native engineering tests without any model calls:

```sh
VERISLOP_G04_NATIVE_TESTS=1 python -m unittest tests.test_g04_offline.NativeReplayTests -v
```

These use a handwritten VSCore positive and a deliberately wrong-length source
against a vacuous accepted contract. They are not historical model outputs.
Opt-in without the required toolchain fails; the default suite explicitly skips
them. Set `VERISLOP_LEAN_PREFIX` only to an existing matching installation.

For a historical frozen bundle, read its edge ID from `plan.json` and obtain the
source hash from its source slot in `artifacts.json`. Replace the placeholders:

```sh
python synthetic_dataset/tools/check_g04_offline.py \
  --bundle /absolute/frozen/run/bridges/BRIDGE_ID \
  --bridge-id BRIDGE_ID --edge-id EDGE_ID \
  --source-sha256 sha256:SOURCE_HEX --seconds-per-case 60 \
  > /absolute/new-diagnostics/g04-report.json
```

Keep redirected output outside the frozen run. Stdout is a standalone JSON
report. Exit 0 means every case passed (or suite export with `NOT_RUN`); exit 1
means at least one kernel-confirmed mismatch; exit 2 means unresolved admission,
toolchain, budget, mutation or execution failure without a confirmed mismatch.
When cases mix mismatches and unresolved results, the report is FAIL but retains
all unresolved rows. Time limits bound the checker, not the component semantics.

## Validation boundary at delivery

Python regressions and existing Tier 2 gating tests were executed offline.
They include an independent positive implementation using UTF-32 counting,
18 deliberately faulty implementation variants, real VSCore source parsing and
goal construction, nominal carrier conversion, report status tests, and real
snapshot/hash/link checks with mocked native execution. Those mocks establish
adapter behavior, not kernel assurance. See the accompanying test log for counts.

The delivery environment lacks the pinned Lean toolchain. The opt-in native
regression is supplied but was not executed, and no historical G04 bundle was
available or replayed. Native end-to-end execution remains unvalidated here;
no G04 implementation defect or strict Tier 2 success is asserted.

## Local validation after application (2026-10-17)

The pinned Lean 4.34.1 installation is available in the receiving checkout.
The first native test exposed a syntax error in the handwritten contract fixture:
`prefix` is a reserved Lean keyword. The fixture now quotes that field as
`«prefix»` and encodes its source as UTF-8 bytes. No checker or acceptance rule
was changed.

After rebuilding the fixture and native modules in fresh temporary directories,
the native regression passed: all 18 correct-source cases passed, the wrong-length
variant produced a confirmed mismatch, and all 36 replays resolved without an
`UNRESOLVED` case. The 24 offline regressions also passed; the native test skipped
by the default suite was executed separately with the opt-in flag.

Local logs are retained under the ignored directory
`validation/g04-offline-application-20261017-001/`, including the initial Lean
failure, a Python encoding correction during repair, and the successful rebuild.
This validates the engineering fixtures and adapter. No historical G04 bundle or
live model experiment was run, and bootstrapping remains paused.
