# Specification: bounded reference preflight and fail-stop target channels

Written before these changes. The first live A23 arithmetic gate accepted and
proved its contract and generated Python, then exposed a native campaign defect:
the reference list range was unbounded in the theorem despite the caller bounds,
and target execution preceded the reference's finite evaluation budget. A timed-out
target remained active; subsequent requests reused its stream. Preserve that run
as interrupted evidence, not a TESTED result or a logical counterexample.

## Case preflight

Structured campaigns gain an explicit frozen opt-in reference-preflight policy:
200,000 evaluation steps and 4,096 range elements per assignment. Reconstruct
reference calls only by reifying definition values from the accepted environment
AST, checking its hash and each profile symbol's declaration hash. The existing
accepted profile records signatures, not definition bodies. Standalone engineering
fixtures may supply explicit typed bodies; native accepted runs must use the
environment bound by the accepted IR. All reachable bodies must exist, be acyclic
and type-check. Use one fresh evaluator for the accepted reference
formula with those pure bodies, with no Python callback. Its result is a feasibility
check, never a test pass. An exhausted budget or unavailable reference body gives
an explicit indeterminate reason, zero target calls and zero effective cases for
that assignment. False reference behavior cannot turn a candidate test into PASS.
Unknown or false preflight results remain indeterminate. A false exact caller
antecedent remains a discard only if it contains no target calls. A target-dependent
false reference antecedent is indeterminate: the candidate could change it. Always
restart target evaluation at the original formula, including its antecedents.
Preflight and sampling hints never invoke Python, and invalid reference graphs
cannot be entered by hint evaluation. New campaigns bypass the target result cache
so every effective assignment actually executes its target calls.
Register the accepted-body reifier, environment/declaration hashing and its helper
modules in the campaign verifier's source inventory; evidence must become stale if
any of these newly executed translations changes.

After feasible preflight, run the unchanged accepted formula against the exact
linked Python artifact with a separate fresh evaluator and the same per-case
budget. Count success only after actual target execution and an exact true result.
Keep minimum effective cases, discard limits, failure semantics, target execution
limits, adversarial probes and closure gates unchanged. Record preflight skips and
their reasons. Old frozen campaigns without the opt-in retain their original
sampling/evaluation behavior. This bounds the finite test surface, not the
universal domain or the user's caller assumptions.

## Channel failure

Each target call has a monotone request ID. Require its response to contain that
exact ID. A timeout, EOF, malformed response, wrong ID or failed send irrevocably
closes and terminates that harness. No later call may reuse its stream or consume
an old response. Closure must not enqueue further work on the failed channel.
Native campaigns stop after timeout/channel failure, record TEST_INCOMPLETE and
never shrink that failure into an alleged functional counterexample. A genuine
functional mismatch still uses normal shrinking. Coverage retrieval after closure
is empty rather than another wait. Reviewer replay continues to classify timeouts
as infrastructure failure, never a confirmed mathematical counterexample.

## Finite checks and new live gates

Run real process regressions demonstrating bounded termination on a slow call,
no later callback or stale-response attribution, response-ID rejection, and no
target call for an oversized accepted reference. Demonstrate fresh case budgets,
old-config preservation, actual target success and a concrete wrong-output failure.
The timed-out source/root and exact six Sol responses remain untouched. Freeze
new source/configuration roots and rerun original A23 through every strict gate.
Then run D21 from its original prompt with grouping/literal sampling enabled.
Never inject manually repaired positive contracts/code or external case answers.
