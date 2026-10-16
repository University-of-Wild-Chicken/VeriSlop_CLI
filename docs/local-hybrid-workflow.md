# Local hybrid workflow: specification before the trial

This opt-in workflow assigns interpretation, formalization, implementation,
implementation repair and concrete adversarial review to a user-selected Qwen
model. Built-in proof tactics remain enabled. Unresolved frozen proof jobs use
up to three Pythagoras proposals, followed by up to three checked Qwen proof
refinements, followed by the ordinary configured Sol prover budget. Every later
phase receives the exact latest rejected proposal and concrete checker diagnostics.
An accepted proof ends the job immediately.

The optional additions to `proof_routing` are `refinement_agent` and
`refinement_attempts` (one through three, both supplied together). With neither
field, the existing three-attempt initial-model route is unchanged. An absent or
disabled route preserves the normal prover. The refinement agent must use the
proof sandbox profile. Sol remains `roles.prover`, never an inferred model.

For an immutable proof job and ordinary fallback budget B, retain:

```text
0 <= initial_used <= 3
0 <= refinement_used <= configured refinement_attempts <= 3
0 <= fallback_used <= B
initial -> refinement -> fallback
```

Persist allocation before inference. Interrupted attempts remain consumed across
resume; no phase can return to an earlier phase. Duplicate failed local proposals
cannot stop the search before the later configured phases get a chance. Model
service failures may trigger an explicitly recorded next-phase transition.
Configuration, model binding, global budget and verifier failures retain their
ordinary terminal classification. Deterministic tactics consume no model slots.

Refinement changes proof terms only. Imports, definitions, theorem propositions,
registry, source implementation and refinement relation stay frozen. All proof
proposals use normal Lean compilation, acceptance and accepted-IR reconstruction.
A defective contract needs the existing separately recorded fresh-package contract
repair; neither Qwen nor Sol may weaken the current frozen job. Reviewers must
construct concrete probes and respond to actual diagnostics. Their opinions cannot
assign proof, testing or implementation milestones.

Retain the latest rejected raw response, submitted candidate and diagnostics in
content-addressed feedback evidence bound to the job. Keep compact routing state
with hashes and counters, not cumulative copies of all past contexts. The next
phase and resumed jobs reconstruct this feedback from bound evidence. JSON, Lean,
model submissions and checker results remain available after chat compression.

## First live trial

The user selected Tier 0 TESTED Python for this trial. Start from fresh natural
language requests in the existing public data-pipeline cohort, without supplying
an interpretation, formal contract, proof, solution or successful reference
candidate. Execute the ordinary strict CLI with required tests and concrete review.
Tier 0 cannot establish END_TO_END_VERIFIED. Existing Tier 2 jobs and historical
bootstrapping evidence remain unchanged.

Freeze selected requests, model identities, configuration, source and finite call
budgets before inference. Native Ollama calls use the installed Qwen and Pythagoras
models with no request wall deadline. Verifier resource limits remain enabled.
Check the complete Pythagoras prompt against its configured context before any
call; a context failure is an explicit transition or block, never silent truncation.

Sol fallback uses GPT-6.1 Sol. When no API credential is available, the trial may
use the existing fresh-agent collaboration transport, forwarding exact SYSTEM/USER
messages and retaining request/response hashes. That transport must be explicitly
reported as a simulation: actual provider model identity, tokens, cost and enforced
read restrictions are unattested. Native local calls remain native. No supervisor
may edit a fallback response or supply proof/implementation hints to obtain success.

Report reached stages, native model calls/tokens, simulated calls separately,
fallback reasons, exact failures and resulting artifacts. Blocked runs remain
unsuccessful; no skipped formal or review stage can be counted as TESTED delivery.

## Optional configuration

[`examples/local-hybrid-config.json`](../examples/local-hybrid-config.json) selects
this route explicitly. Set `VERISLOP_QWEN_MODEL` and `VERISLOP_PYTHAGORAS_MODEL` to
your installed Ollama model names and `OPENAI_API_KEY` for the Sol API fallback.
The supplied local endpoint profile uses Ollama on port 11434; select your own
profile when the server runs elsewhere. This example gives Sol the proof fallback
role and explicitly enables the autonomous critic protocol fallback described
below. Qwen failures in interpretation, implementation or ordinary checkpoint/
release review remain explicit blocks; this configuration does not silently
replace those agents.

```bash
python -m verislop run \
  --prompt-file examples/proof-of-concept/data-pipelines/P03-unicode-labels.txt \
  --runs-dir validation/my-hybrid-runs --run-id unicode-labels \
  --mode software --tier 0 --target python --endpoint test_campaign \
  --require-state TESTED --require-tests --policy strict --non-interactive \
  --config examples/local-hybrid-config.json --budget-seconds 0 \
  --repair-rounds 2 --seed 20261013 --cases 32
```

The bounded trial harness is `python -m synthetic_dataset.tools.run_local_hybrid`.
Its `prepare` command requires resolved model names, pinned local digests, explicit
endpoint profiles and the local Pythagoras tokenizer snapshot. Its `run` command
executes the frozen configuration; `pending` and `respond` expose the exact Sol
collaboration mailbox. This simulation path is for the recorded evaluation and is
separate from the API-backed example above.

## Local memory limits

The example selects a 32,768-token Qwen author/prover context and an 8,192-token
output budget. Its Qwen reviewer uses 40,960 context tokens and 2,048 output tokens;
Pythagoras uses 32,768 context tokens and 8,192 output tokens. Choose these explicitly
for your hardware and complete prompts. On the local
16 GB RTX 5080, a 65,536-token context with the default F16 attention cache left
16 of 66 layers on CPU. A separate Ollama instance with
`OLLAMA_KV_CACHE_TYPE=q8_0`, Flash Attention and a 32,768-token context loaded all
66 layers on GPU. Cache quantization changes inference precision; it is recorded
as a runtime change and does not change Lean or test acceptance criteria.

The trial harness can bind an additional official Qwen tokenizer snapshot using
`--qwen-tokenizer`. It checks the complete prompt plus output allowance and a
serialization margin before local Qwen dispatch. A context overflow remains an
explicit capability failure or registered proof-route transition; it is never
permission to truncate the specification or retained proof feedback. The normal
API example does not enable this evaluation-specific tokenizer check.

Runtime tuning uses a separate local endpoint, preserving the user's existing
Ollama service configuration. An interrupted trial remains unfinished with its
source snapshot and evidence retained; revised settings start a fresh trial.
The evaluated Ollama/llama.cpp backend also accepts `LLAMA_ARG_THREADS=4` on the
task server, limiting CPU generation and prompt workers while retaining GPU
inference. This backend-specific setting is recorded in the runtime manifest.
Use `--runtime-manifest` when preparing the trial to retain and hash-bind those
runtime settings and observations. This records the service configuration; it
does not independently attest the live service's memory placement.

The full release packet in the October 14 trial required 36,192 input tokens.
A separate neutral probe of the 40,960-token Qwen context retained all 66 GPU
layers with the four-thread, quantized-cache runtime. The reviewer's smaller output
allowance reserves capacity for the complete packet and protocol repair. The proof
prompt required 13,379 input tokens, so Pythagoras's former 16,384-token setting
could not reserve its 8,192-token output allowance. These per-role changes preserve
complete prompts and every acceptance gate; future larger packets can still fail
the explicit preflight. Output limits do not authorize incomplete JSON acceptance.

## Compact audit metadata in critic prompts

Critics retain the complete current request, obligations, Lean source, formulas,
native predicate packages, probe interface and concrete diagnostics. Audit-only
`semantic_closure` maps may be replaced in the prompt by their existing digest
and a hash-bound reference to the complete statement analysis retained in CAS.
This is a deterministic projection of audit metadata, not a model-written summary
or permission to omit propositions. Verifiers continue to consume the full
analysis. The projection must preserve all formula contents and the input
artifact unchanged, and make the retained full evidence discoverable after
resume or context compression.

## Explicit fallback for invalid autonomous critic responses

The optional `critic_routing` object declares `enabled`, `fallback_agent` and
`fallback_attempts` (one through three). The fallback agent must have the
`review_readonly` tool profile. This route applies to autonomous contract/proof
criticism only; ordinary checkpoint/release reviewer membership is unchanged.
Absent or disabled routing preserves the existing critic behavior.

Each configured critic slot first receives its existing two protocol attempts.
Only two invalid responses permit the declared fallback to search the same
candidate. A valid ACCEPT, ABSTAIN disposition, diagnostic correction or replayed
counterexample never triggers substitution. Provider, context, configuration,
model-binding, verifier and budget failures remain terminal. A concrete defect
still requires repair before any higher review tier can run.

Retain each invalid primary response and its actual agent identity. The fallback
uses its own agent and instance identity and explicitly resolves the original
configured slot; it does not impersonate the primary agent or add an extra vote.
The effective membership has exactly one voter per configured slot, with the
same tier consensus rule. Exhausted fallback leaves that slot incomplete.

Bind attempts to the complete candidate packet, configured slot, prompt source,
configuration, selected models and endpoint profiles. Allocate each attempt in
the package's content-addressed memory before dispatch. On resume, replay retained
responses through the current validators/checker without dispatching them again;
an allocated attempt lacking a retained response remains consumed and blocks that
same job. Do not reset attempts by reopening a package. Changed candidates are
separate jobs; changed routing for an existing job is a binding failure.

Both primary and fallback receive the complete current packet and exact protocol
errors. The prompt states current response requirements explicitly and labels old
criticism as history: only current diagnostics authorize diagnostic indices.
No generated software, expected output or successful probe is supplied by the
controller. Lean replay and the ordinary TESTED requirements remain authoritative.

## Grammar guidance for rejected formalizer proposals

When formalization has current diagnostics and no usable statement analysis, the
critic receives the complete registered authoring grammar as reference data. It
still returns the critic envelope; authoring instructions quoted in that grammar
do not change its role. Historical diagnostics alone do not enable this context,
and ordinary successful functional searches and proof repair keep their existing
packets. The complete prompt remains subject to the configured context bound.

Invalid bare names at sort positions receive exact diagnostic examples of the
registered record or enumeration reference. This is syntax feedback only: the
compiler never changes a submitted AST, supplies an implementation or selects a
different type. Acyclic nested records remain supported; recursive records remain
rejected. Record construction and projection terms retain their existing bare
record IDs, distinct from the structured objects required at sort positions.

## Bounded ballot correction context

Every checkpoint review attempt retains the complete original supervisor guidance
and current packet as an unchanged prefix. A protocol correction appends only the
exact previous ballot, validator diagnostics and the instruction to correct that
ballot for the same packet and scope. It does not append a second copy of the
guidance already present at the beginning. No policy, candidate evidence or probe
is removed, summarized or accepted by this prompt deduplication; review replay,
consensus rules, call bounds and context preflight remain unchanged.

Each initial ballot request and protocol retry ends with a compact reminder of
the exact keys admitted for each current probe kind. An unavailable probe kind
requires a newly constructed allowed probe. An allowed kind with extra metadata
requires the reviewer to remove those extra fields while retaining its concrete
inputs; explanations belong in the ballot's method or rationale. Missing fields
must be supplied from the actual packet and constructed probe, never invented
results. Validator errors identify unexpected and missing keys explicitly.

The reminder is derived from the same closed field sets used by the validator.
It supplies no candidate input, expected output or accepted ballot, and appears
after the unchanged packet and any exact rejected response/diagnostics. The
controller never edits a model response, relaxes the schema, or counts an invalid
ballot as acceptance. Repaired proposals still require independent replay.

## Optional Ollama review response schema

An Ollama agent may set `review_response_format` to `json_schema`. Omitting this
field preserves the existing response mode. The option applies only to the exact
ordinary review purposes `review:interpretation`, `review:formal_contract`,
`review:implementation` and `review:release`; autonomous criticism, authoring and
proof subprocesses retain their existing protocols. Selecting the option for a
non-Ollama family or a non-review agent profile is a configuration error.

The broker passes the self-contained `review-model-response.schema.json` object
as Ollama's `format`, as documented in [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
Its schema permits every existing verdict and search conclusion and all four
concrete probe kinds, with exact closed probe fields. It supplies no obligation
IDs, input assignments, expected values or decisions. Assignment payloads remain
subject to the existing typed wire validator and checkpoint restrictions.

The generation schema also encodes the existing count rule: exactly one of eight
search-object alternatives permits `attempted_cases = N` with exactly `N` probes,
for every `N` from one through eight. This constrains agreement between a claimed
count and the emitted array; it does not choose a count, probe kind, input or
verdict. The semantic validator independently rechecks this equality, probe
distinctness and the rest of the existing review protocol.

The exact schema and its canonical SHA-256 are retained in successful and failed
provider transcripts. Unsupported service/schema behavior remains an explicit
provider failure; the adapter never retries with a weaker response format.
Schema-constrained generation is syntax assistance, not a ballot acceptance
rule: exact response parsing, substantive scope checks, independent probe replay,
consensus and all formal/testing gates still run on the untouched model response.
The local example enables this optional setting for its Ollama reviewer.
