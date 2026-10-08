# Synthetic local software-engineering benchmark

Both corpus experiments are stopped. The [sealed failure diagnosis](diagnostics/stopped-experiments-003-002/DIAGNOSIS.md)
preserves every completed score and unfinished arm. A separate
[strict reservation proof of concept](diagnostics/strict-reservation-poc-20261008/SUMMARY.md)
now completes Tier 0 TESTED and rejects a concrete equality-boundary mutant;
it does not change corpus metrics or establish general JSON API support.

This directory contains 100 locally authored, bounded, informal Python software-engineering tasks. Each asks for `solution.py` with a pure deterministic `solve(data)` function, specifies exact JSON input/output, and provides two public examples. The held-out cases cover boundary conditions, ordering, tie-breaking, invalid inputs where specified, and seeded inputs. Difficulty is author assigned; this is not an established external benchmark or a set of real repository bug fixes.

The task groups cover graph algorithms and state/event simulations (`G01–G34`), parsing/codecs/text editing/data transformations (`D01–D33`), and exact arithmetic/optimization/intervals/dynamic programming (`A01–A33`). Reference implementations and independent hand-calculated anchors live in the three generator files. Model calls are not used to generate the dataset.

Generate and validate the dataset locally:

```bash
python -m synthetic_dataset.build_dataset
python -m unittest tests.test_synthetic_benchmark
```

`tasks.jsonl` indexes the tasks. Every `tasks/<ID>/` directory contains `prompt.txt` and `cases.json`. `manifest.json` binds the exact bytes of the prompts, cases, index and generators. Generation validates independent anchors, deterministic regeneration, unique inputs and reference outputs. Dataset changes require a new benchmark run.

The user selected the **full VeriSlop CLI pipeline** comparison. The raw arm makes one native coding call. The VeriSlop arm dispatches the actual `run` command with strict Tier 0, `TESTED`, required tests and configured adversarial review. It receives no prewritten draft, contract, proof or implementation. The benchmark does not replace the CLI with an obligations-only or review/repair prompt. All roles use the same pinned model. Blocked CLI stages count as unsuccessful tasks.

Run the bounded comparison with any installed model and local endpoint:

```bash
python -m synthetic_dataset.benchmark \
  --model 'aix-qwen3.8:27b-ud-q3_k_xl' \
  --base-url http://127.0.0.1:11435 \
  --arm-seconds 0 --per-call-output-tokens 8192 \
  --output-token-budget 262144 --harness-calls 32 \
  --global-seconds 0 --seed 20261007 \
  --out synthetic_dataset/runs/qwen-local-003
```

The example Qwen tag is specific to the provided AIx test service. The benchmark accepts `--model`, `OLLAMA_MODEL` and `--base-url`; it never pulls or substitutes models. Model catalog digests are pinned before dispatch and checked after inference.

The user requested Qwen be allowed to proceed without hard timeouts. In the current protocol, `--arm-seconds 0` disables the supervisor generation deadline, configures provider `request_timeout_seconds: null`, passes `--budget-seconds 0` for proof search, and configures review tier wall limits as zero. `--global-seconds 0` admits every selected task without an elapsed-time cutoff. Positive values still provide optional deadlines. No large finite timeout is used as a substitute for an unlimited wait.

Both arms use temperature zero, disabled thinking, native JSON mode, and an 8,192-token per-call output ceiling. The prover requests a JSON `lean_source` wrapper, consistent with the native transport, and all Lean acceptance checks remain intact. Raw Qwen gets one call. VeriSlop may spend up to 32 calls and 262,144 generated tokens, with at most two implementation/release repair rounds. Transport retries are disabled. Input-plus-output broker usage has a separate 1,000,000-token cap. These are finite work budgets; there is no wall-clock completion guarantee. Candidate tests and individual mechanical verifiers retain their execution/resource limits.

The benchmark reserves output capacity before calls; received usage is recorded and disconnected usage is marked unknown. Input tokens are measured, not equated between arms. Order alternates within a fixed shuffled task order. Calls run sequentially against the local model.

The same isolated evaluator scores both artifacts. Candidate execution receives the source and case inputs, with one second per case and 512 MiB memory; expected outputs and reference files remain outside the candidate environment. Exact JSON comparison distinguishes integers from booleans. Exceptions, invalid output, timeouts and missing artifacts fail cases. The primary case metric covers held-out cases. A successful task passes both public and held-out cases and, for VeriSlop, also completes its CLI workflow successfully. A blocked workflow can still have its existing artifact scored, but cannot count as a successful task.

The full CLI's formal domain is narrower than arbitrary JSON/Python interfaces. Representation failures and formalization overhead therefore affect this comparison. Results measure this exact workflow and its finite work budgets; they do not isolate the causal effect of verification or establish universal correctness. No failed formal gate is bypassed to produce code.

The earlier [60-second experiment](runs/qwen-local-001/REPORT.md) was superseded at the user's request after 11 complete pairs (23 recorded arms). Its scores, unscored pending evidence if any, original protocol, and execution source snapshot are preserved. Those results are excluded from the new experiment, which repeats both arms on all 100 tasks with its own source/configuration hashes.

Every run preserves its frozen `protocol.json`, `execution-source/` snapshot, `results.jsonl`, `summary.json`, `REPORT.md`, native response bodies, exact prompts, transcripts, artifacts, CLI packages, per-case observed/expected values and final evidence manifest. Rejected/truncated native responses are retained. Scores can be inspected without contacting the model. Use a new output directory for another run; existing evidence is never overwritten.

[Dataset validation](DATASET_VALIDATION.md) documents oracle checks and pre-freeze corrections. [The offline viewer](viewer.html) opens recorded summaries and result files without network access. [Concrete counterexamples](COUNTEREXAMPLES.md) link inputs and observed artifact failures; each example identifies its source experiment.

The [older final auditor](tools/finalize_qwen_002.py) belongs exclusively to the stopped `qwen-local-002` experiment. It remains stopped and must not publish the new runs as that experiment. To inspect that older run without changing documentation:

```bash
python synthetic_dataset/tools/finalize_qwen_002.py --check-now
```

The post-alignment comparison repeats all 100 tasks in `qwen-local-003` and `luna-agents-002`, with the same seed and alternating arm order. The Luna run uses fresh `gpt-6-luna` collaboration agents to simulate every requested CLI model role, preserving exact request and response text plus transport provenance. It does not call a Luna API or attest to model identity, sampling settings or token usage. Historical partial runs stay separate. See [current run status](RUN_STATUS.md).

```bash
python -m synthetic_dataset.tools.luna_benchmark \
  --out synthetic_dataset/runs/luna-agents-002 \
  --limit 100 --harness-calls 32 --case-seconds 1 \
  --concurrent-experiment qwen-local-003
```

The simulation driver requires an external collaboration controller to service its pending model requests. Starting it alone does not generate responses.

The [comparison auditor](tools/compare_runs.py) checks both runs independently without model calls or changing their evidence. It verifies source/corpus/configuration hashes, exact case grades, repaired package selection, strict gates and transport receipts. The [observer](tools/watch_comparison.py) refreshes a clearly labeled partial report as records arrive and publishes a final report only when both completed manifests pass the audit:

```bash
python -m synthetic_dataset.tools.watch_comparison \
  --out synthetic_dataset/comparison-qwen-003-luna-002
```

This observer does not impose generation deadlines or cancel experiments. It reports corpus task success separately from passing pipeline stages. The [infrastructure notes](comparison-qwen-003-luna-002/INFRASTRUCTURE_NOTES.md) distinguish recorded model-runner failures and simulation scheduling delays from formal-language or proof failures.
