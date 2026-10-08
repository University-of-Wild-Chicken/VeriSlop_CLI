# GPT-6 Luna collaboration-agent experiment

**Consult the live summary and report for completion status.** This experiment
compares direct generation against the actual strict VeriSlop CLI workflow on
all 100 frozen tasks. Its evidence is kept separately in
`synthetic_dataset/runs/luna-agents-001`; partial scores are progress
observations, not a completed benchmark.

The [protocol](runs/luna-agents-001/protocol.json) records the selected tasks,
order, limits, execution sources and transport assumptions. The live
[summary](runs/luna-agents-001/summary.json) and
[arm records](runs/luna-agents-001/results.jsonl) describe completed arms.
The [report](runs/luna-agents-001/REPORT.md) updates as arms finish and is
finalized after the run's evidence audit.

## Corpus and paired workflow

The corpus is the same [frozen dataset](manifest.json) used by the local Qwen
experiment: 100 tasks, 1,157 cases, 200 public examples and 957 held-out cases.
Its root is
`sha256:00e1b28846431c379cf8460d57d84897c5d0575ce49fa1481d7fb1ebc000c04e`.
The task shuffle uses seed `20261007`. The first pair runs raw generation
first; subsequent pairs alternate which arm runs first, matching the Qwen
protocol. Each task prompt supplies exactly two public examples. Reference
implementations and held-out inputs or expected outputs are excluded from
generation prompts and are never sent back as repair feedback.

The raw arm makes one logical coding call with the existing benchmark's
system instruction and the frozen task prompt. It requires a JSON response
containing exactly `files.solution.py`, defining `solve(data)`. The source
is preserved without manual editing or a second coding attempt.

The VeriSlop arm runs `verislop run` with Tier 0, Python, the `test_campaign`
endpoint, strict policy, `--require-state TESTED`, `--require-tests` and
`--non-interactive`. It begins with the informal prompt, without prewritten
obligations, Lean contracts, proofs or implementations. Only the model
transport is replaced. The CLI's existing prompts, interpretation checks,
Lean gates, export, implementation, linking, testing and release checks remain
in the workflow. Configured review uses one adversarial critic at each of the
`formal_contract` and `release` checkpoints, retaining the requirement to
construct concrete counterexample probes and replay them.

Both arms use a fresh collaboration agent for every logical model request,
with `model="gpt-6-luna"` and `fork_turns="none"`. Reviewers receive fresh
contexts as well. Each agent receives the exact request's system and user
text, with an instruction to return response text only and use no tools,
files or delegation. The controller deposits the exact final text in the
mailbox; it does not correct malformed responses or candidate code.

## Limits and evaluation

The raw arm permits one logical model call and the full CLI permits at most
32. Every response is capped at **1 MiB of UTF-8 text**. There are no model
request, arm generation, proof-search, review-tier or global wall-clock
deadlines. Work remains finite in task count, logical calls, response size
and candidate evaluation limits. Mechanical verifier limits remain active.

The shared grader evaluates the exact selected Python artifact against the
same public and held-out cases. Candidate execution uses the existing
filesystem and network isolation, one second per case and a 512 MiB memory
limit. Expected outputs stay outside candidate execution. Missing or
ambiguous `solve(data)` artifacts fail every case. Exact JSON comparison
distinguishes values such as `false` and `0`; exceptions and case timeouts
are failures.

A successful task must pass every public and held-out case. The VeriSlop arm
must also finish its CLI workflow with `PASS`. A blocked stage counts as an
unsuccessful task, even if a partial artifact passes some external cases.
Recorded CLI diagnostics identify actual blockers; aggregate scores alone
do not establish their cause. Test success does not establish universal
correctness or an implementation proof in Lean.

## What is simulated

This run uses the collaboration-agent runtime, not an OpenAI API endpoint.
The runtime accepts the requested `gpt-6-luna` model override, but this
transport cannot independently attest a returned API model identity or
immutable model snapshot. Returned model identity and input/output token
counts are therefore **null**, and every call has unknown token usage.
Actual output bytes and logical calls are counted. The schema's
`max_output_tokens=8192` field is a requested role hint, not an enforced
collaboration-runtime token limit.

Temperature, thinking controls and native JSON sampling are unavailable to
this transport and are not claimed to match Qwen's native Ollama settings.
The compatible-provider entry and `https://collaboration.invalid/v1` profile
are schema scaffolding. The mailbox callback never contacts that endpoint
or resolves its placeholder credential reference; no user API token is
needed for this simulation.

Review freezes a **provider-alias** identity policy with
`require_fixed_model_snapshot=false`, preserving requested-model and agent
task provenance without fabricating attestation. The Qwen experiment instead
pins and checks an installed Ollama model digest. These identity and sampling
differences must accompany any comparison between the two experiments.

The no-tools rule for model agents is an instruction, not a capability-enforced
filesystem sandbox. Fresh contexts and observed request/response provenance
limit what is supplied to agents; they do not establish that undisclosed
runtime context is absent. This boundary differs from the mechanical
isolation used for candidate grading.

## Running and preserving evidence

The runner command is:

```bash
python -m synthetic_dataset.tools.luna_benchmark \
  --out synthetic_dataset/runs/luna-agents-001
```

**The command alone waits for responses.** An active autonomous collaboration
controller must service the mailboxes, spawning fresh GPT-6 Luna agents and
publishing their exact finals atomically. This is not a standalone cloud API
client. Do not reuse an existing output directory for a new experiment.

Each request records the exact system/user text, purpose, role and instance.
Each response envelope binds its request ID and the SHA-256 hash of the
exact request file, together with a unique canonical agent task ID. Response
receipts bind the request, envelope and final text hashes. The run preserves
broker transcripts, generated sources, CLI packages, stage diagnostics and
case observations alongside these records.

The final summary and evidence manifest must be assessed with their
`complete` and `valid` fields. The source inventory and dataset hashes must
remain unchanged; response identities, bindings, logical call counts and
case denominators must agree with the recorded evidence. This run's results
are never merged with the Qwen run or its superseded timed experiment.
