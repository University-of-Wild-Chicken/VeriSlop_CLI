# Patch integration and functional audit — 2026-10-16

Applied `verislop-token-budget.patch` and `agent-effect-dsl-prototype.patch` to
the existing working tree on `267719bbb`. The incoming documents' historical
test reports were treated as claims to distinguish from this local validation.

The token patch applied cleanly. The DSL patch's `review.py` hunk conflicted
with the newer ballot-repair path; its dispatch was integrated while retaining
the complete packet, exact retry feedback, final schema reminder and existing
Ollama schema handling. The other DSL hunks applied cleanly. A pre-application
backup and patch/file digests are retained locally in
`validation/patch-functional-audit-20261016-001/`. All 24 preexisting changed or
untracked files outside the four intended integration files remain byte-identical.

## Findings resolved

1. A supplied DSL configuration could replace the actual Broker configuration,
   including disabling an enabled checker or substituting an agent profile.
   Lowering now rejects a differing configuration before dispatch.
2. DSL resource checks could use configured defaults while a custom Broker
   Budget requested different retries or allowed fewer output tokens. Lowering
   now checks the actual Budget's call/token limits and retry allowance without
   mutating the stored configuration.
3. A valid enabled configuration with an undersized token budget raised an
   uncaught `EffectError` in the review worker. It now records an
   `effect_check_failed` attempt and an incomplete consensus certificate with
   the reviewer still missing; no request or accepting ballot is fabricated.

The reservation wrapper retained the existing strict model/schema paths.
Concrete regressions cover shared concurrent admission, logical-call caps,
provider/credential/identity/logging failures, cancellation, unavailable usage,
and the combined enabled DSL → reservation → native Ollama adapter path.

## Local validation

109 distinct targeted tests passed across these modules (some were run in
separate batches while the new regression cases were added):

```bash
PYTHONPATH=tests:. /usr/bin/python3.12 -B -m unittest \
  test_broker_budget test_budget_patch_audit \
  test_ollama_review_schema test_ollama_context_window \
  test_provider_conformance test_provider_unbounded_timeout \
  test_agent_effects test_effect_patch_audit test_review_protocol_repair
```

These include local HTTP fixtures and actual CLI review/counterexample replay.
Another 54 existing regressions passed in 131.256 seconds across
`test_autonomous_correction`, `test_critic_routing`, `test_hybrid_proof_routing`
and `test_local_hybrid`. They include real Lean acceptance, accepted-IR export,
Python implementation/linking/TESTED gates and hybrid route/configuration checks.
The combined total is **163 distinct passing tests**, with no external model
inference or historical benchmark regeneration. Full-suite success is not claimed.
Test IDs and changed-file digests are retained in the local audit's `result.json`.

## Functional limits

The token policy is a soft estimate shared by one in-memory Budget, not a strict
token or monetary ceiling or a cross-process ledger. Missing usage and failed
or retried requests still prevent complete billing accounting. Existing
collaboration-simulation transports that bypass Broker do not acquire native
Broker reservations.

The Effect DSL remains optional (`"agent_effect_dsl":{"enabled":true}`). Its
generic checker supports four operation signatures, but only ordinary review
dispatch is integrated. It checks host-authored structure and allocations;
artifact declarations are not provenance evidence, and the prototype establishes
no new Lean proof, OS isolation or END_TO_END_VERIFIED assurance.
