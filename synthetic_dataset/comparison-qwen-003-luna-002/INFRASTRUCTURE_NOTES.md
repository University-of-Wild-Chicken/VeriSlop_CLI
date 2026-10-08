# Observed experiment infrastructure

These notes supplement the recorded run evidence. They do not change scores, votes, model responses or the frozen protocol.

## Native Qwen G03 strict CLI

The CLI accepted the interpretation after one schema correction, then requested a second formalization after the first Lean candidate failed elaboration. The local provider returned HTTP 500 for that correction request; the arm is recorded as `INFRASTRUCTURE_FAILURE`, with unknown generated-token usage for the disconnected call.

The host service journal at 2026-10-07 21:21:08–21:21:10 America/Chicago records `CUDA error: the launch timed out and was terminated`, followed by an aborted `llama-server` and HTTP 500 for `/api/chat`. This is an observed model-runner failure; no benchmark model-generation deadline was configured. The service automatically started a replacement runner for the next task. No service settings were changed during the experiment.

The selected journal excerpt is preserved in [qwen-local-003-gpu-error.txt](../../.verislop/qwen-local-003-gpu-error.txt). The authoritative CLI diagnostic is [G03 strict score](../runs/qwen-local-003/artifacts/G03/verislop/score.json).

## Native Qwen D21 strict CLI

D21 exercised the fresh-package recovery path after Lean candidate build failures. Its selected package is `package-repair-01`, and interpretation was mechanically revalidated without changing the requirements. A later formalization request again ended with HTTP 500. The service journal at 21:35:44–21:35:45 records a CUDA launch timeout, aborted runner and matching `/api/chat` 500. The score follows the returned repaired package and records `INFRASTRUCTURE_FAILURE`, seven calls and one call with unknown generated usage. Neither the failed parent nor the child produced an implementation artifact.

Evidence: [selected journal excerpt](../../.verislop/qwen-local-003-d21-gpu-error.txt), [D21 strict score](../runs/qwen-local-003/artifacts/D21/verislop/score.json). This repeated runner failure affects the interpretation of native CLI results; it is not attributed to Lean or treated as a formal counterexample.

## Luna simulation scheduling

The first fresh responder could not spawn while all four collaboration slots were occupied, including an orphaned responder from the previously stopped experiment. The first new request waited about 420 seconds before spawn. The historical responder was never used. Scheduling observations are recorded separately in `.verislop/luna-agents-002-controller-events.jsonl`.

Luna's recorded arm elapsed time includes collaboration scheduling and controller overhead. It must not be compared with native Qwen elapsed time as an inference-speed measurement. Requested model identity, sampling controls, token usage and instruction-based tool restrictions are not independently attested by the simulation transport.
