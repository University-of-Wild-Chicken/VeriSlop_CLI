# Strict reservation proof of concept

This is a fresh supported-domain software task, separate from the stopped 100-task
corpus. It exercises successful subtraction, an explicit error, the equality and
zero boundaries, and a preservation invariant. It does not establish support for
the corpus's general JSON, graph, text or collection APIs.

The protocol is fixed before native generation: Qwen must produce the interpretation,
formalization and Python implementation through the strict CLI. Lean proofs may use
the CLI's checked tactic portfolio. Both configured review checkpoints must construct
concrete probes, replayed by the supervisor. Accepted IR must come from the accepted
Lean environment, and the implementation must be bound to those symbols. No supplied
draft, formalization, proof or implementation candidates are used for the positive run.

Use the existing CLI closure/evidence layout rather than a parallel verifier stack.
The claimed endpoint is Tier 0 `TESTED`, with the reference theorems `PROVED`:
finite tests and two clean builds do not establish `END_TO_END_VERIFIED`.
The independent finite oracle must check both branches, equality, zero and values
larger than 64 bits. A separate implementation with the wrong equality boundary
must fail the same generated contracts; it cannot contribute a positive result.
Source/configuration hashes and the final report identify each new run. Failed
attempts remain separate packages. The historical benchmark scores remain unchanged.

The example configuration points to the local Qwen server used in this workspace.
Replace its model name, digest and endpoint with your own local Ollama model if needed.
Model generation has no wall deadline; finite call/token/repair budgets and mechanical
verifier and test limits remain in effect.

```sh
VERISLOP_CONFIG_HOME="$PWD/examples/proof-of-concept/reservation" \
python -m verislop run \
  --prompt-file examples/proof-of-concept/reservation/request.txt \
  --request-ref examples/proof-of-concept/reservation/request.txt \
  --config examples/proof-of-concept/reservation/qwen-config.json \
  --mode software --tier 0 --target python --endpoint test_campaign \
  --require-state TESTED --require-tests --non-interactive \
  --budget-seconds 0 --repair-rounds 2 --seed 20261008 --cases 32 \
  --run-id reservation-poc --runs-dir .verislop/proof-of-concept/runs
```

Reproduction requires Lean `leanprover/lean4:v4.34.1`, the configured native model
server and the containment requirements reported by the CLI. The model transport,
request interpretation, Lean toolchain, kernel replay/export, Python runtime,
registered verifiers, host isolation and test generators remain trusted components.
