# Explicit autonomous-critic capacity fallback

This specification precedes implementation. Trial004's release-manifest recovery
could not dispatch its local critic: the exact request plus reserved output was
44,334 tokens against a 40,960-token context. Its configured protocol fallback did
not handle this pre-dispatch resource condition. The historical trial stays closed
and unsuccessful.

An enabled `critic_routing` may opt in with `on_context_limit: true` (default
false). Only a structured, local, pre-dispatch `context_budget_exceeded` provider
diagnostic may advance a primary autonomous critic to its already configured
fallback. Require `call_dispatched` to be exactly false and a consistent failed
preflight with integer input/output/window counts whose sum exceeds the window.
Do not infer capacity exhaustion from error text. Mixed diagnostics, malformed
counts, provider failures after dispatch, transport failures, global call/token
budget exhaustion and checker failures remain terminal. The fallback must still
fit its own limits; its failure cannot recurse into another route.

Record the failed primary allocation and exact diagnostic before routing. Skip
another primary dispatch with the same oversized context. Preserve the complete
semantic packet and any earlier raw primary response, probe checks and diagnostics;
add an explicit capacity-routing reason. Do not truncate, summarize, increase
context/output budgets, or manufacture a successful primary response. Existing
route attempt caps, configuration/model binding, durable allocation and cached
response revalidation apply unchanged across resume. A resumed failed primary
allocation may trigger the same route without a new dispatch; it cannot reset
budgets or silently change routing policy.

The primary capacity failure is a non-voting route observation. Only a valid
fallback response occupies the configured critic slot. Valid primary dispositions
and concretely replayed defects never escalate or disappear. Every fallback probe
must pass the existing concrete-input validation and native refutation replay;
neither fallback nor consensus supplies proof or release authority.

Regression coverage must exercise opt-in versus legacy behavior, exact packet and
diagnostic retention, effective reviewer identity, durable resume, primary failure
after a malformed first response, unchanged counterexample veto, fallback capacity
failure, dispatched/ambiguous/malformed errors, and global budget/checker errors.
Use an unrelated native replay fixture to show that the capacity route reaches the
ordinary strict verification gates. A live-model result requires a fresh frozen
trial; engineering fixtures cannot change trial004's outcome.

The local hybrid harness currently supplies the complete tokenizer preflight
diagnostic required by this route. Ordinary remote provider errors do not prove
that no call was dispatched, and therefore do not qualify. This option does not
add tokenizer preflight to the standard provider broker or promise fallback for
HTTP context-length errors.
