# Superseded timed experiment

The user replaced the 60-second generation deadline before this experiment completed. These partial scores are preserved as a separate timed experiment and will not be pooled with the new deadline-free run. Original execution sources are saved in `execution-source/`; any unscored pending arm is excluded.

# Bounded local Qwen software-engineering benchmark

Dataset: 100 locally authored tasks; 11 complete pairs.

Model: `aix-qwen3.8:27b-ud-q3_k_xl`; digest `283945d2cfdbd2646a4cfa392a55f7ba6c64c69661464f145a321fcbe976a036`.

The raw arm uses one native coding call. The VeriSlop arm invokes the full strict Tier 0 CLI workflow; its existing prompts, validators, Lean gates and configured review gates are retained. A successful task passes both public and held-out cases and, for VeriSlop, the CLI workflow. Blocked stages and timeouts count as unsuccessful tasks. A missing artifact fails every held-out case.

- **Raw Qwen:** 10/11 successful tasks; 99/102 held-out cases passed (97.1%); 11 artifacts; 11 model calls; 139.0 generation seconds.
- **Full VeriSlop:** 0/12 successful tasks; 0/112 held-out cases passed (0.0%); 0 artifacts; 13 model calls; 720.6 generation seconds.

## Fixed limits and interpretation

Per arm: 60 seconds (up to two seconds shutdown grace), 4096 generated tokens per call, 8192 generated tokens total; raw one call, VeriSlop at most 6. Candidate cases have a 1 second limit and 512 MiB memory limit.

Arm order alternates within a fixed shuffled task order. Temperature is zero, thinking is disabled and JSON mode is used by both arms. Tasks and tests were frozen before benchmark calls. Only two public examples enter each task prompt; reference implementations and held-out expected outputs are excluded from prompts and candidate execution mounts. Scores are calculated outside candidate execution.

This is a single-model, single-run feasibility comparison on synthetic bounded Python functions. Difficulty is author assigned. The full CLI currently supports narrower formal domains than general JSON/Python tasks. Its blocked runs may measure that representation boundary or contract-generation overhead rather than coding ability. Wall budgets are matched; prompt size, model-call count and verification work differ, so this is not an equal-token causal estimate of verification benefits. No passing score establishes universal correctness or a Lean implementation proof.

Token totals cover received native responses only; timeout/disconnection usage is unknown and counted separately. Requested output capacity is reserved before calls, including calls with unknown usage. The global deadline is checked between pairs; a pair already admitted may complete both bounded arms and their bounded graders.

## Evidence

`protocol.json` freezes model, limits, execution order and verifier identities. `results.jsonl` and `summary.json` are authoritative benchmark scores. Each artifact directory preserves request prompts, native response bodies (including rejected/truncated responses), broker transcripts, generated code or CLI package, CLI output and per-case observations. `manifest.json` binds the dataset; `run-manifest.json` binds final evidence bytes.

## Workflow outcomes

- raw: ARTIFACT=11
- verislop: TIMEOUT=12

## Concrete recorded failures

- G03: `INTERRUPTED` — the run was cancelled; required checks remain unresolved. Evidence: `artifacts/G03/verislop/score.json`.
- G13: `INTERRUPTED` — the run was cancelled; required checks remain unresolved. Evidence: `artifacts/G13/verislop/score.json`.
- D21: `INTERRUPTED` — the run was cancelled; required checks remain unresolved. Evidence: `artifacts/D21/verislop/score.json`.
- D19: `INTERRUPTED` — the run was cancelled; required checks remain unresolved. Evidence: `artifacts/D19/verislop/score.json`.
- D16: `INTERRUPTED` — the run was cancelled; required checks remain unresolved. Evidence: `artifacts/D16/verislop/score.json`.
