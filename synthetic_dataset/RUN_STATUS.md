# Stopped head-to-head experiments

**Both experiments are USER_STOPPED and incomplete.** No completed 100-task benchmark result is claimed. Completed scores remain unchanged; unfinished CLI arms receive no invented score.

The sealed [failure diagnosis](diagnostics/stopped-experiments-003-002/DIAGNOSIS.md), [machine-readable diagnosis](diagnostics/stopped-experiments-003-002/DIAGNOSIS.json), [stopped comparison](diagnostics/stopped-experiments-003-002/comparison.json), and [offline four-arm viewer](diagnostics/stopped-experiments-003-002/viewer.html) replace the live experiment view. Its [snapshot manifest](diagnostics/stopped-experiments-003-002/snapshot-manifest.json) binds these diagnostic artifacts and both stopped run manifests.

- Native Qwen `qwen-local-003`: 42 completed pairs, raw 34/42 successful paired tasks, strict CLI 0/42. All 85 completed arm records remain; D12 raw is the additional completed arm, D12 CLI is unscored. [Termination](runs/qwen-local-003/termination.json) and [stopped evidence manifest](runs/qwen-local-003/run-manifest.json).
- Luna simulation `luna-agents-002`: 18 completed pairs, raw 17/18 successful paired tasks, strict CLI 0/18. All 37 completed arm records remain; G17 raw is the additional completed arm, G17 CLI is unscored. [Stopped summary](runs/luna-agents-002/summary.json) and [stopped evidence manifest](runs/luna-agents-002/run-manifest.json).

On the same 18 completed pairs across models, Qwen raw passes 15/18 tasks and 154/167 hidden cases; Luna raw passes 17/18 tasks and 162/167 hidden cases. Both strict arms pass 0/18 tasks and generate no Python artifacts. The unequal transport, prompt and call budgets prevent equal-compute or causal conclusions. Luna model identity, sampling, tokens and tool-policy enforcement are not independently observable.

All 142 Qwen and 144 Luna measured source files matched current and captured versions at the stop boundary. Runtime fixes made afterward are audited separately against frozen historical source copies; no old score is rescored. The diagnosis found actual schema failures, Lean elaboration and domain failures, a generated-recursion kernel replay defect, prover retries with identical stale input, semantically weak accepted contracts, obsolete proof bodies in review packets and separately recorded provider failures. Exact evidence references are in the diagnosis.

The prior [supported-profile control](comparison-qwen-003-luna-002/SUPPORTED_CONTROL.md) remains separate from corpus metrics. Earlier stopped [Qwen run002](runs/qwen-local-002/termination.json), [Luna run001](runs/luna-agents-001/termination.json), and the earlier timed Qwen run001 remain preserved and excluded from this comparison.

A fresh [reservation proof of concept](diagnostics/strict-reservation-poc-20261008/SUMMARY.md)
completed the repaired strict pipeline at Tier 0 TESTED, including both reviews and two
clean builds. Its independent request oracle passed 400 cases twice. A separate wrong
equality-boundary implementation failed generated tests, had three reviewer proposals
confirmed by replay, and was blocked. This control is outside the corpus. No corpus
experiment was restarted and no historical score changed.
