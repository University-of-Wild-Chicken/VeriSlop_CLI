# Bounded local Qwen software-engineering benchmark

Dataset: 100 locally authored tasks; 27 complete pairs.

Model: `aix-qwen3.8:27b-ud-q3_k_xl`; digest `283945d2cfdbd2646a4cfa392a55f7ba6c64c69661464f145a321fcbe976a036`.

The raw arm uses one native coding call. The VeriSlop arm invokes the full strict Tier 0 CLI workflow; its existing prompts, validators, Lean gates and configured review gates are retained. A successful task passes both public and held-out cases and, for VeriSlop, the CLI workflow. Blocked stages and timeouts count as unsuccessful tasks. A missing artifact fails every held-out case.

- **Raw Qwen:** 22/27 successful tasks; 217/248 held-out cases passed (87.5%); 27 artifacts; 27 model calls; 439.9 generation seconds.
- **Full VeriSlop:** 0/27 successful tasks; 0/248 held-out cases passed (0.0%); 0 artifacts; 100 model calls; 7194.0 generation seconds.

## Fixed limits and interpretation

Per arm: no generation wall-clock deadline, 8192 generated tokens per call, 262144 generated tokens total; raw one call, VeriSlop at most 32. Candidate cases have a 1 second limit and 512 MiB memory limit.

Arm order alternates within a fixed shuffled task order. Temperature is zero, thinking is disabled and JSON mode is used by both arms. Tasks and tests were frozen before benchmark calls. Only two public examples enter each task prompt; reference implementations and held-out expected outputs are excluded from prompts and candidate execution mounts. Scores are calculated outside candidate execution.

This is a single-model, single-run feasibility comparison on synthetic bounded Python functions. Difficulty is author assigned. The full CLI currently supports narrower formal domains than general JSON/Python tasks. Its blocked runs may measure that representation boundary or contract-generation overhead rather than coding ability. Both arms have the same wall-clock policy; prompt size, model-call count and verification work differ, so this is not an equal-token causal estimate of verification benefits. No passing score establishes universal correctness or a Lean implementation proof.

Token totals cover received native responses only; timeout/disconnection usage is unknown and counted separately. Requested output capacity is reserved before calls, including calls with unknown usage. A nonzero global deadline is checked between pairs; zero disables it. The experiment remains bounded by the task count, call/token budgets and finite candidate evaluation limits.

## Evidence

`protocol.json` freezes model, limits, execution order and verifier identities. `results.jsonl` and `summary.json` are authoritative benchmark scores. Each artifact directory preserves request prompts, native response bodies (including rejected/truncated responses), broker transcripts, generated code or CLI package, CLI output and per-case observations. `manifest.json` binds the dataset; `run-manifest.json` binds final evidence bytes.

## Workflow outcomes

- raw: ARTIFACT=26, ERROR=1
- verislop: BLOCKED=27

## Concrete recorded failures

- G03: `CANDIDATE_BUILD_FAILURE` — the challenge does not elaborate: 201:26: unexpected token 'end'; expected ')', ',' or ':'; 202:5: Missing name after `end`: Expected the current scope name `Contract`

Hint: To end the current scope `Contract`, specify its name:
  end ̲C̲o̲n̲t̲r̲a̲c̲t̲; 202:8: unexpected token ')'; expected command; 206:44: Missing name after `end`: Expected the current scope name `Contract`

Hint: To end the current scope `Contract`, specify its name:
  end ̲C̲o̲n̲t̲r̲a̲c̲t̲; 206:47: unexpected token ')'; expe. Evidence: `artifacts/G03/verislop/score.json`.
- G13: `INVALID_CANDIDATE` — clause 0: unknown obligation O1. Evidence: `artifacts/G13/verislop/score.json`.
- D21: `CANDIDATE_BUILD_FAILURE` — the challenge does not elaborate: 485:16: unexpected token 'end'; expected ')'; 485:17: Invalid name after `end`: Expected `BucketAgg`, but found `width`

Hint: Use current scope name `BucketAgg`:
  e̵n̵d̵ ̵w̵i̵d̵t̵h̵e̲n̲d̲ ̲B̲u̲c̲k̲e̲t̲A̲g̲g̲; 485:27: unexpected token ':'; expected command; 486:10: Missing name after `end`: Expected the current scope name `BucketAgg`

Hint: To end the current scope `BucketAgg`, specify its name:
  end ̲B̲u̲c̲k̲e̲t̲A̲g̲g̲; 486:14: unexpected token '∧'; expected . Evidence: `artifacts/D21/verislop/score.json`.
- D19: `CANDIDATE_BUILD_FAILURE` — the challenge does not elaborate: 445:55: Unknown constant `JoinContract.Json.hash`; 445:78: Unknown constant `JoinContract.Json.hash`; 446:55: Unknown constant `JoinContract.Json.hash`; 446:78: Unknown constant `JoinContract.Json.hash`; 448:0: Missing name after `end`: Expected the current scope name `JoinContract`

Hint: To end the current scope `JoinContract`, specify its name:
  end ̲J̲o̲i̲n̲C̲o̲n̲t̲r̲a̲c̲t̲. Evidence: `artifacts/D19/verislop/score.json`.
- D16: `UNCOVERED_SOURCE_CLAUSE` — request clause [0, 87) has no disposition: 'Software engineering task D16: Recursive schema defaults with deterministic diag'. Evidence: `artifacts/D16/verislop/score.json`.
