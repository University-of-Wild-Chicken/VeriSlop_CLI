# Live Qwen and GPT-6.1 Sol: direct versus strict VeriSlop

The three-task comparison completed on 2026-10-08. Both direct coding arms
succeeded on all three tasks. The full strict CLI succeeded on zero Qwen tasks
and two Sol tasks. Sol generated native Tier 0 TESTED implementations for all
three tasks; its row task remained unsuccessful because release review did not
accept it. There is no END_TO_END_VERIFIED claim.

The authoritative aggregation is [COMPARISON-SUMMARY.json](COMPARISON-SUMMARY.json),
recomputed from the original result rows, saved independent observations and
native reports. Original cohort scores were retained unchanged.

- **Qwen direct:** 3/3 successful tasks; 3 calls; 480/480 distinct task cases and
  960/960 observations passed.
- **Qwen strict:** 0/3 successful tasks; 41 calls; no implementations or native
  TESTED tasks; zero independent observations executed. The 480-case denominator
  remains present, but unexecuted cases are not reported as observed failures.
- **GPT-6.1 Sol direct:** 3/3 successful tasks; 3 calls; 480/480 task cases and
  960/960 observations passed.
- **GPT-6.1 Sol strict:** 2/3 successful tasks; 18 calls; native TESTED on all
  three tasks; 480/480 task cases and 960/960 observations passed. The blocked
  row release still counts as an unsuccessful task.

## What was measured

The fixed cohort consists of numeric filtering and multiplication, enabled-row
filtering and projection, and Unicode-label filtering and prefixing. These are
three selected data-pipeline tasks, not the original 100-task corpus or a broad
software-engineering evaluation. Every task used one direct attempt and one
full strict attempt per model. Arm order alternated: numeric direct then strict,
rows strict then direct, and Unicode direct then strict.

Direct generation received the natural-language request and the unchanged raw
coding prompt, with no repair. Strict generation ran the actual CLI through
interpretation, formalization, autonomous criticism, Lean proof acceptance,
implementation, linkage, generated tests, configured reviews and final closure.
All required strict gates remained in force. Independent cases were evaluated
only after each arm finished and were never supplied as repair feedback.

There were 160 frozen independent cases per task, evaluated in two fresh
isolated Python harnesses. Thus each model/arm had 480 distinct task cases and
960 planned observations. Repeated observations do not increase the number of
tasks or domains. Candidate calls had a one-second execution limit, a 512 MiB
memory limit and required filesystem/network isolation.

Generation, proof-search and review-tier wall deadlines were disabled. The
finite bounds remained one raw call or 128 strict calls per task, two outer
contract-repair rounds, 24 calls per agent instance, and 8,192 output tokens per
native call. The configured 524,288-token Broker budget is per Broker; repair
packages receive fresh Brokers. Sol token counts and output-token enforcement
are unavailable, so its 8,192-token setting is only a hint. One R0 critic/reviewer
used unanimous consensus at formal-contract and release checkpoints.

## Model and transport boundaries

Qwen used the native local Ollama endpoint and model
`aix-qwen3.8:27b-ud-q3_k_xl`, with a 32,768-token context setting. Its catalog
digest was pinned to
`283945d2cfdbd2646a4cfa392a55f7ba6c64c69661464f145a321fcbe976a036`
and checked around inference. The completed cohort made 44 calls and recorded
387,614 input tokens and 81,689 output tokens, including the length-terminated
critic response. Catalog honesty and the host remain trusted.

Sol used 21 fresh collaboration response agents, each explicitly requested with
`model="gpt-6.1-sol"` and `fork_turns="none"`. Agents were instructed to read only
their current hash-bound SYSTEM/USER carrier. Exact final text was copied without
editing code, proofs or reviews. This is the live collaboration-agent simulation
transport, not an OpenAI API benchmark: actual provider identity, immutable model
snapshot, sampling, token usage and enforcement of carrier-only access are
unattested. No API token was requested or used by this transport.

The arms use different prompts, call counts and formal work. Their scores do not
establish an equal-compute or causal effect of scaffolding, or a causal comparison
between providers.

## Concrete failure patterns

**Qwen numeric: valid candidate, invalid critic protocol.** Fifteen calls fixed
the record-sort and record-versus-list errors and produced an elaborated
candidate. Critics then invented diagnostic index 0 for permitted proof holes
when no diagnostic existed. Later ACCEPT responses omitted the required concrete
input probe. Both protocol retries repeated their invalid responses despite
explicit validation feedback. The terminal REVIEW_INCOMPLETE status did not
enter outer recovery, leaving one configured recovery round unused. No prover
or implementer was called. See the [numeric analysis](NATIVE-FAILURE-ANALYSIS.md)
and its [hash-bound evidence](NATIVE-FAILURE-ANALYSIS.json).

**Qwen rows: corrected structure, wrong predicate, truncated critic.** Seven
calls corrected the unsupported `and` tag and a constant-True output guarantee.
However, all formalizer proposals used `amount <= minimum`, reversing the request,
and the critic repeated that predicate in a suggested correction. An enabled row
with amount 1 and minimum 0 is a public-input analytical counterexample: the
request retains it and the candidate rejects it. This witness was not executed,
kernel replayed, supplied to models or counted as a test observation.

The final critic returned the wrong role envelope, `verislop.formalize/0.1`, and
generated a large formalization instead of the requested critique. Ollama ended
at 8,192 output tokens with `done_reason="length"`. The Broker rejected the
completion before critic protocol repair, and the CLI returned PROVIDER_FAILURE
with INFRASTRUCTURE_FAILURE. A native response exists; no network or tool outage
was demonstrated. No implementation was generated. See the
[row analysis](NATIVE-FAILURE-ANALYSIS-02.md) and
[evidence](NATIVE-FAILURE-ANALYSIS-02.json).

**Qwen Unicode: grammar correction never occurs.** Nineteen calls exhausted both
outer repair rounds. All nine formalizer attempts retained invalid bare record
sorts such as `"Input"`, rather than the admitted record-sort representation.
Critics cited the actual diagnostic, but the formalizer did not correct its
signature. No candidate elaborated and no implementation was generated. See the
[Unicode analysis](NATIVE-FAILURE-ANALYSIS-03.md) and
[evidence](NATIVE-FAILURE-ANALYSIS-03.json).

**Sol rows: requested-tier and review-lifecycle confusion.** The implementation
passed generated tests, both clean builds and all independent cases. Nevertheless,
its release reviewer abstained over missing endpoint closure evidence and
END_TO_END_VERIFIED PENDING. The packet omitted explicit requested tier/endpoint
fields while displaying that state; the final report correctly marked E2V
UNSUPPORTED for the requested Tier 0 TESTED endpoint. No concrete implementation
violation or mechanical veto was produced. Unanimity required ACCEPT, so review
remained INCOMPLETE and no correction call followed. The original task remains
BLOCKED. See [SOL-ANALYSIS.md](SOL-ANALYSIS.md) and
[SOL-ANALYSIS.json](SOL-ANALYSIS.json).

The present workflow therefore produces real TESTED software with Sol, but
does not resolve every review-protocol failure. Qwen's syntax repairs demonstrate
some correction, while its strict completion remains zero. Sol accepted all
first formalization candidates; its successful tasks do not demonstrate recovery
from rejected contracts or failed proof attempts.

The next fixes indicated by this evidence are precise grammar corrections,
critic responses constrained to the current signatures and actual diagnostics,
explicit requested-tier/review-stage metadata, and bounded recovery for malformed
or incomplete review/provider responses. These are follow-up changes, not changes
to the frozen measurement or a reason to waive strict gates.

## Frozen evidence and retention

Both completed cohorts used the same 172-file source root:
`sha256:e6f71ac5777e426936c0fdf551a05c69957e329bedbad7b13777ab926b28380e`.
The task preregistration root was
`sha256:d3f3a33c20cdfe745903da66b953f0ef5713ddf7236874c357a4792044c94c5f`.
Exact task inputs are archived under [task-inputs](task-inputs/PREREGISTRATION.json).

- [Comparison protocol](COMPARISON-PROTOCOL.json) and
  [preregistration](PREREGISTRATION.json).
- [Native Qwen summary](qwen/SUMMARY.json) and
  [evidence manifest](qwen/EVIDENCE-MANIFEST.json): all 1,145 entries rehashed.
- [Sol summary](../paired-002/sol/SUMMARY.json) and
  [evidence manifest](../paired-002/sol/EVIDENCE-MANIFEST.json): all 1,128 files
  rehashed, with 21 unique fresh response-agent chains.
- Exact drafts, JSON contracts, typed proposals, Lean candidates, proofs,
  refutations, model transcripts, failed packages and memory snapshots remain
  in their original cohort directories. All 119 native and 33 Sol snapshots
  restored correctly: 152 snapshots across nine package histories. See the
  [retention audit](RETENTION-AUDIT.json).
- The [final results manifest](RESULTS-MANIFEST.json) binds this report, the
  aggregation, diagnostic supplements and task-input archive, and references
  the completed Sol cohort and preserved infrastructure failures.

No hidden cases, task-specific oracle/reference implementation, hand-written
candidate code or hand-written proofs were supplied to generation. Successful Sol proofs came
from the unchanged registered tactic portfolio. The final aggregation reread
saved observations and reports; it did not rerun candidates or rescoring tools.
The two successful strict closures are VERIFIED only for their frozen finite
Tier 0 surface under the declared trusted components, not universal
implementation correctness or natural-language/formal equivalence.

## Infrastructure history and interpretation limits

An initial outer-protocol serialization failed before generation in
`paired-001`; its preparation failure is preserved. The first native controller
in `paired-002` subsequently lost its process during agent-slot cleanup, after
one successful raw numeric attempt and during the first strict call. The
[controller failure](../paired-002/qwen/CONTROLLER-FAILURE.json) and interrupted
evidence remain intact. The whole native cohort restarted in fresh `paired-003`
packages under root process control, before its replacement generation began.
Sol's already preregistered `paired-002` run continued unchanged. The
[recovery protocol](COMPARISON-PROTOCOL.json) binds both cohorts and discloses
the partial native attempt. It was not a timeout or a candidate repair, and its
outputs were not supplied to the restarted models. No completed model outcome
was selected from multiple completed native cohorts.

The preliminary aggregation counted native manifest metadata keys instead of
entries. Its pre-seal draft is retained as AGGREGATION-DRAFT-001.json; the final
aggregation records the corrected 1,145-entry count. Original scores and evidence
were not changed.

Earlier experiment archives and their scores remain untouched. This rerun is
descriptive evidence from three fixed tasks, not proof of improvement over a
historical source version, broader domain coverage, or END_TO_END_VERIFIED.
