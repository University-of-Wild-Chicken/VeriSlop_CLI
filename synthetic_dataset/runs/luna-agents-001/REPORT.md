# GPT-6 Luna collaboration-agent experiment

Status: **USER_STOPPED**; 5/100 complete pairs.

Frozen dataset: `sha256:00e1b28846431c379cf8460d57d84897c5d0575ce49fa1481d7fb1ebc000c04e`.

Each call requests a fresh `gpt-6-luna` collaboration agent with `fork_turns=none`. This is an agent simulation, not a native API benchmark. Token usage, returned model snapshot, sampling settings and tool disabling cannot be independently attested by this transport.

Direct generation uses one coding call. The other arm runs the actual strict Tier 0 VeriSlop CLI with TESTED required, its existing Lean gates and counterexample review checkpoints. All public and hidden cases must pass; a blocked CLI task is unsuccessful.

- **Direct Luna:** 5/5 successful tasks; 46/46 hidden cases and 10/10 public cases passed; 5 model calls. Tokens unavailable.
- **Full VeriSlop with Luna:** 0/5 successful tasks; 0/46 hidden cases and 0/10 public cases passed; 19 model calls. Tokens unavailable.

Raw: one call; full CLI: at most 32 calls. Each response is limited to 1 MiB UTF-8. There are no model generation, proof search, review or overall experiment deadlines. Candidate execution retains the same one-second case and 512 MiB memory limits as Qwen.

The task shuffle and alternating arm order use seed 20261007. Model agents see only the exact system/user request; hidden cases and reference code are excluded. The no-tools instruction is a controller policy, not an enforced model sandbox. Candidate code is graded in the existing filesystem/network sandbox.

The collaboration transport uses provider-alias review identity, because no immutable provider snapshot is exposed. The Qwen experiment pins an Ollama digest and enforces sampling/token controls unavailable here. Qwen runs concurrently, so timing also includes local resource contention. These separate single-run experiments do not establish a causal benefit of verification or universal implementation correctness.

Authoritative live scores: `summary.json`, `results.jsonl`; frozen protocol: `protocol.json`. `execution-source/` captures measured sources. Each artifact directory retains exact prompts, captured agent finals, hash-bound receipts, transcripts, CLI diagnostics, generated code and case observations. The final `run-manifest.json` binds final evidence bytes.

## Recorded workflow failures

- G03: `MISSING_WITNESS` — challenge: non-vacuity theorem VeriSlop.non_vacuity must be a DSL conjunction of existentials (type VeriSlop.Result is outside the DSL v0.1 sorts). See `artifacts/G03/verislop/score.json`.
- G13: `INVALID_CANDIDATE` — W1 witnesses D1, which is not an assumption record. See `artifacts/G13/verislop/score.json`.
- D21: `INVALID_CANDIDATE` — draft schema: $.preconditions[0].source_refs: fewer than 1 items. See `artifacts/D21/verislop/score.json`.
- D19: `INVALID_CANDIDATE` — draft schema: $.preconditions[0].source_refs: fewer than 1 items. See `artifacts/D19/verislop/score.json`.
- D16: `INVALID_CANDIDATE` — clause 2: N1 must use the exclusion disposition. See `artifacts/D16/verislop/score.json`.

Stopped at the user's request. Partial scores are preserved; unfinished arms are unscored. See termination.json.
