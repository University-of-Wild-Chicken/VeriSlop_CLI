# Broker token budget audit (2026-10-16)

Base: `267719bbb39d8bfdce147823788604528bf56169` on `main`.
GitHub connector and local checkout agreed on broker blob
`3fb26135840f6ff3679527f4a215561d370ae08f`.
Scope: Broker admission, shared Budget accounting, concurrency and offline regressions.
No external inference, credentials, historical evidence changes or reviewer-policy changes.

This document retains the supplied patch's original audit report. The combined
application to the current working tree, additional regressions and Effect DSL
integration fixes are recorded in [the local integration audit](patch-integration-audit-20261016.md).

## Confirmed findings

Before patching, two offline tests exercised the actual Broker with a patched
`complete` adapter. Both passed their assertions of the defect:

- Budget 100; one admitted call reports 140: `used_tokens == 140`; the next call is blocked.
- Budget 100; two threads enter a provider-side Barrier before either completes;
  each reports 70: both calls succeed and `used_tokens == 140`.

The latter proves overlapping admission in Broker itself, rather than in an
independent reimplementation. Timeouts bound every synchronization wait.

## Minimal repair and settlement

`Budget.reserved_tokens` is shared under the existing budget lock. Each call
atomically tests `used_tokens + reserved_tokens + estimate <= max_total_tokens`
and reserves its estimate before dispatch. Estimate = system/user UTF-8 bytes +
configured `max_output_tokens`. This intentionally avoids introducing a tokenizer
or provider identity assumptions, but is only a heuristic admission quantity.
An estimate that does not fit is rejected without consuming a logical call slot.
Concurrent calls still run when their combined estimates fit.

The original transport, authentication, identity validation, retries, diagnostic
mapping and transcript path execute unchanged inside `_call_reserved`. Successful
responses add the original provider-reported input/output sum under the lock;
a `finally` block releases the reservation on all exits, including credential,
provider, unexpected exception and transcript errors. Actual usage is never clamped
to the configured budget. Between usage accounting and reservation release,
admissions conservatively see both amounts; this can temporarily reject work,
but cannot create an admission gap. Admission does not wait for budget to free up.

## Exact guarantees and limitations

| Quantity | Meaning and guarantee |
| --- | --- |
| `max_calls_per_instance` | Existing atomic cap on logical calls for one instance key within one Budget. Existing credential/prompt failures can consume a slot. |
| Transport attempts | At most `1 + max_retries` per logical call for retryable ProviderError; retry attempts do not consume separate logical call slots. |
| Admission estimate | Lock-atomic reservation test includes all in-flight estimates sharing the Budget, including independent Brokers explicitly sharing it. |
| `used_tokens` | Sum of available input/output usage on successfully returned, identity-validated completions; missing fields still contribute zero. This is reported usage accounting, not complete actual billing. |
| Strict actual-token or monetary cap | **Not guaranteed.** One response can exceed its estimate; missing usage, provider framing/hidden reasoning, failed requests, retries and post-completion identity failures prevent complete accounting. |
| Scope of “global” | One in-memory Budget object. Independent default Broker instances and other processes do not share this budget. |

UTF-8 bytes do not prove a provider-independent input-token upper bound; configured
output limits do not prove an upper bound on every provider's billed token category.
The reservation spans the retry loop, but does not reserve a proven total for all
attempts. Releasing a failed request's reservation says nothing about whether the
provider billed it. Missing usage can allow repeated admissions. This patch repairs
the unreserved concurrent admission defect, not those provider-accounting limitations.

A strict cap would require an enforced upper bound covering every billed token
category for each attempt, reliable usage/error settlement and shared accounting
across all intended callers/processes. None is established here. Larger prompt
estimates may reject calls earlier than the old threshold-only policy; this is an
intentional behavior change and can require a larger configured soft budget.

## Offline validation

`python -m unittest discover -s tests -p test_broker_budget.py -v`

10 tests cover the retained single-call overshoot limitation, deterministic
concurrent rejection (two Brokers sharing a Budget), preserved fitting concurrency,
exact-boundary admission, UTF-8 prompt estimates, oversized preflight rejection,
settlement/refund, provider/unexpected/credential exceptions, logical call limits,
retry accounting, and unavailable usage.

Provider conformance: 18 tests passed. Ollama suites: 38 tests passed.
Provider-pattern discovery: 49 tests passed, plus one class setup error in
`test_providers_review`; the same setup error reproduces on the unmodified base.
Full discovery initially ran 1,180 tests (including the then-seven new budget tests):
26 failures, 128 errors, 42 skips. The environment lacks the pinned Lean 4.34.1
installation and filesystem isolation support. Full-suite success is not claimed;
a baseline comparison is recorded below. No historical results were regenerated.

Unmodified-base full discovery: 1,173 tests, 26 failures, 128 errors, 42 skips.
The failure/error test labels are identical between baseline and patched runs;
the seven-test count difference was the initial budget suite. Three subsequent
budget cases were run in the final passing 10-test targeted run. This comparison
does not establish that every pre-existing failure is environmental.
