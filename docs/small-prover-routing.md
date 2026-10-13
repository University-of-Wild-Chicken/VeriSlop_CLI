# Optional small-model proof routing

This specification precedes implementation and live evaluation. The initial model
under evaluation is `Pythagoras-LM/Pythagoras-Prover-4B`, imported into a local
Ollama server as F16 GGUF converted from pinned BF16 weights. The bounded live
evaluation accepted **three of six contracts**, including one unresolved by the
built-in tactics; the full VSCore bridge prompt exceeded its context capacity.
See the [live results](small-prover-live-results.md) and
[evaluation protocol](small-prover-evaluation.md) for scope and failures.
The route remains disabled by default. These results do not establish token
savings or change a historical qualification.

The first live compatibility cohort evaluated six complete-file workflow
jobs: the model solved zero jobs, while the deterministic portfolio solved
five. Several responses supplied only a theorem and omitted required frozen
definitions; the integer response also used unavailable Mathlib tactics. These
results remain unchanged. The following optional fragment protocol is a separately
specified adaptation to evaluate, not a retroactive repair of those submissions.

## Configuration and scope

Routing is optional. An absent `proof_routing` field or `enabled: false` preserves
the existing configured prover, prompts and attempt limits. Enabling the route
requires an explicit initial-agent name; it never downloads a model or starts a
server implicitly. Users select their own provider endpoint and model through the
existing provider and agent registry. Pythagoras is an evaluated example, not a
required model identifier.

The proposed configuration addition is:

```json
{
  "proof_routing": {
    "enabled": true,
    "initial_agent": "local-small-prover",
    "initial_attempts": 3
  }
}
```

When enabled, `initial_attempts` is exactly three for this milestone. The named
agent must exist, resolve to a usable provider and use `tool_profile:
"proof_sandbox"`. The initial agent and its provider count as used configuration
entries; their missing endpoint, credentials or model configuration cannot remain
an unused-provider warning. The fallback is always the ordinary `roles.prover`;
there is no independently guessed model or provider. Disabled routing does not
make an otherwise unused initial agent or provider mandatory.

For example, an additional agent in an existing Ollama configuration can be:

```json
{
  "local-small-prover": {
    "provider": "local",
    "model_ref": "env:VERISLOP_SMALL_PROVER_MODEL",
    "tool_profile": "proof_sandbox",
    "proof_response_format": "theorem_fragment",
    "max_output_tokens": 4096,
    "context_window_tokens": 16384
  }
}
```

The output and context limits in that example are user choices, not validated
recommendations for this model. Evaluation must record the actual imported model
digest, effective limits and runtime. The existing model-identity pin can bind an
Ollama digest. The ordinary prover and all other role assignments remain explicit.

Each agent may optionally set `proof_response_format` to `complete_file` (the
default) or `theorem_fragment`. The field controls only proof subprocess responses;
it cannot change an interpreter, formalizer or implementation response protocol.
Fragment-mode prompts request one or more raw Lean theorem commands, restate the
exact frozen theorem headers and explain the Std-only environment. Unknown tactics
are ordinary concrete Lean failures; no tactic whitelist or automatic replacement
of their proof bodies is introduced.

Fragment assembly is deterministic and conservative. Lex comments (including
nested comments), strings, character literals and quoted identifiers before
identifying declaration boundaries. Accept only expected named theorem commands
whose header tokens, including every binder and the result proposition, equal
the frozen declaration's tokens. Whitespace and comments between header tokens
are harmless; changed names, types, universes, attributes or goals are rejected.
Unknown and duplicate theorem names, imports, definitions, namespace commands or
other extra commands are rejected. Unsupported source syntax is rejected rather
than guessed with a regular expression.

Only proof-body bytes from the response are inserted. All frozen scaffold,
imports, definitions, namespace boundaries, declarations, headers and registry
bytes stay exact. For a multi-theorem contract, a partial response leaves other
proof holes intact. Previously proposed bodies may be retained only when their
complete scaffold and every theorem header match the frozen source. Assembly
never authors a proof body, adds a lemma or changes an expected theorem. The
ordinary Lean/semantic acceptance paths remain final authority.

Before insertion, a small trusted helper uses the pinned Lean syntax parser to
parse every extracted proof body as exactly one term through end-of-input. It
does not elaborate or execute the submitted source. This independently rejects
extra command forms (including indented commands after a same-line tactic), rather
than relying on an exhaustive keyword list. The helper runs under the existing
bounded sandbox and its infrastructure failures remain explicit. The lexical
protocol admits only sole `by sorry` or `sorry` frozen holes; unsupported frozen
metaprogramming or ambiguous command layouts are rejected. Trailing frozen comments
and whitespace stay outside replaced body spans. An invalid previous scaffold is
retained as feedback but assembly starts from the exact frozen baseline.

The parser helper initializes only its fixed trusted Lean/Std imports; it never
imports a candidate module or executes its initializers. It uses a 30-second
syntax-check limit and a 2048 MB Lean heap limit plus the existing virtual-address
headroom. These are verifier subprocess limits, not model request timeouts.

The route applies to two existing proof subprocesses:

1. Contract proof search proposes complete Lean files for a frozen challenge.
2. VSCore implementation proof search proposes proofs of the exact generated
   refinement goal for a fixed program and relation.

Interpretation, formalization, implementation generation, autonomous criticism,
adversarial review and verifier execution retain their configured roles. In
particular, a cloud critic may run before the first local proof proposal. A proof
route cannot by itself establish a reduction in total workflow cloud tokens.

[`examples/small-prover-routing-config.json`](../examples/small-prover-routing-config.json)
is a complete disabled-by-default example combining a user-selected Ollama model
with a configured OpenAI prover. Set the listed model environment variables and
change `proof_routing.enabled` to `true` to opt in. Provider request deadlines in
that example are disabled; the ordinary proof-search wall budget remains a separate
CLI option. Fragment-mode Ollama proof calls omit JSON output enforcement; other
roles and default complete-file calls retain their existing transport protocol.

For the evaluated installation on this machine, set
`VERISLOP_SMALL_PROVER_MODEL=verislop-pythagoras:4b-f16` and use
[`examples/aix-ollama-endpoint-profiles.json`](../examples/aix-ollama-endpoint-profiles.json)
to select `http://127.0.0.1:11435`. The ordinary server default remains port 11434.
Merge the optional agent and routing fields into your existing configuration,
preserving your normal prover and other model choices. Set `proof_routing.enabled`
to `true` to opt in. The live evaluation used an 8192-token output budget and
16384-token context; the example's 4096-token output budget is a user choice.
Use `--budget-seconds 0` when proof search should have no wall deadline. Lean
verifier resource limits and model attempt/token budgets still apply.

## Immutable jobs and attempt budgets

A contract proof job is bound to the frozen challenge and its formalization,
statements, semantic profile, toolchain and policy hashes. A VSCore proof job is
bound to the program, relation, generated goal, backend version, accepted contract
references, verifier-library identity and toolchain hashes. These bindings name
the exact proof task; changing its source or statement requires a different job.
The job also binds the routing configuration and initial/fallback model identities.
Its routing binding includes the router, assembler, role prompts and parser-helper
source hashes; resuming across an implementation change requires a fresh job.
Changing routing configuration while resuming existing work is a binding error,
not an implicit reset of the local budget.

For each job, let `s` be allocated initial-agent attempts, `f` allocated fallback
attempts, and `B` the existing configured prover attempt budget. Maintain:

```text
0 <= s <= 3
0 <= f <= B
total model proposals <= 3 + B
```

The initial model supplies the first three model proposals unless it succeeds or
an explicitly recorded local-provider failure triggers early escalation. Once
fallback begins, the job cannot return to the initial model. Proof success stops
both routes. Exhaustion leaves the ordinary unresolved-proof result.

Existing attempt limits remain fallback budgets. For example, contract proof
search with `max_attempts = 4` permits at most three initial attempts followed by
four ordinary-prover attempts. A VSCore source with `proof_attempts = 3` permits
at most three initial attempts followed by three ordinary-prover attempts. Simply
replacing the first three existing VSCore slots would eliminate fallback and is
outside this specification. With no fallback attempts allowed, the existing
zero-attempt setting disables proof-model search altogether.

One attempt is allocated immediately before one logical broker call. The broker's
bounded HTTP retries belong to that same attempt and are recorded separately.
Malformed envelopes, oversized responses, Lean rejection, incomplete proofs and
duplicate proposals consume attempts. An interrupted or failed allocated call
also consumes its slot; resumption cannot repeatedly reclaim an uncertain request.
If a reserved slot fails frozen-context protocol validation before inference,
record `call_dispatched: false`; no provider request or token use is fabricated.

The following are not initial-agent attempts: deterministic tactic-portfolio
evaluations; supplied candidate files; retained candidate rechecks; the initial
proof supplied with an implementer response; critic calls; and HTTP retries.
These operations retain their existing evidence and limits.

Both routes share the existing wall-clock and total provider-token budgets. The
local prelude cannot reset those budgets or reserve extra unconfigured wall time.
A disabled proof-search deadline remains disabled; verifier limits still apply.

## State and compact evidence

Persist the route state before every dispatch. Within a retained run package,
reopening the same immutable job restores its consumed slots. Re-evaluating an
existing candidate cannot reset those slots. VSCore can reset the proof budget
only for a genuinely different fixed source/relation/goal job; regenerating
identical bytes does not create a fresh local allowance.

The routing states are:

```text
INITIAL_READY -> INITIAL_DISPATCHED -> INITIAL_READY
INITIAL_READY -> FALLBACK_READY -> FALLBACK_DISPATCHED -> FALLBACK_READY
either route -> COMPLETE | EXHAUSTED | BLOCKED | INFRASTRUCTURE_FAILURE
```

A dispatch record is durable before the provider call. A completion record binds
the exact response and existing proposal/checker evidence. If the process stops
between these records, retain the dispatch as interrupted, consume its slot and
continue according to the remaining budget when the user resumes the workflow.
Missing or inconsistent state evidence blocks before another provider call.

Store immutable attempt records and content-addressed references, plus a compact
current-state checkpoint. Do not write a cumulative copy of prompts, responses,
frozen input maps or complete event history into every checkpoint. Each attempt
records the job and route-policy hashes, route phase, ordinal, agent, requested
and returned model identity, Ollama digest when available, prompt/response
references, provider retry count, and the outcome or failure reference. A
transition to fallback records its concrete reason.

All of this is search evidence. It cannot set `PROVED`, `LINKED`, `TESTED` or
`END_TO_END_VERIFIED`, and an exhausted search does not prove a theorem false.
No existing frozen qualification input or historical result is rewritten.

## Escalation and error semantics

After three rejected initial proposals, give the ordinary prover the exact latest
candidate and diagnostics, together with the best baseline where the existing
protocol provides it. Initial-model repetition cannot trigger the contract search's
existing `NO_PROGRESS` termination before fallback has been tried. Scope or reset
the consecutive-repetition stopping counter at the route transition while retaining
the earlier failure records. The ordinary prover retains its existing repetition
and exhaustion rules.

A terminal provider transport or model-service failure on the optional initial
route may trigger immediate fallback after its exact failure is retained. This is
an explicit configured transition, not silent substitution. Budget exhaustion,
invalid configuration, unavailable required credentials, stale model/job bindings,
and verifier infrastructure failures are not such transitions: they retain their
existing blocking or infrastructure classification. In particular, a missing Lean
toolchain or failed registered verifier cannot be repaired by calling another model.
Detected model-pin/catalog/returned-model mismatches carry an explicit binding-failure
marker and cannot be mistaken for an ordinary truncated service response. Required
route failures are retained as terminal; resuming the same job re-raises that
classification before inference. After resolving such a failure, a fresh independently
frozen job/package is required, so repeated resumes cannot turn hard failures into
ordinary initial-attempt exhaustion and silent fallback.

A successful ordinary prover after a local failure does not erase that failure.
The final search report separates initial attempts, ordinary-prover attempts,
provider retries, local failures, escalation reason and the checked best candidate.

## Unchanged verification boundary

The model remains an untrusted proof author. Use the existing contract response
decoder and the existing VSCore proof decoder, then compile and check the proposal
through their ordinary paths. Preserve exact frozen theorem statements,
definitions, imports, registries and implementation relations. All existing proof
size limits, prohibited constructions, axiom audits, witness checks, isolated Lean
replay, accepted-IR reconstruction and bridge certificate checks continue to apply.

Search success means only that an ordinary checked proof candidate exists. Contract
acceptance still decides `PROVED`; the bridge checker still decides the exact
refinement claim. A route cannot weaken either boundary or authorize a stronger
software-delivery milestone.

## Evaluation before rollout

Keep default routing disabled during evaluation. Freeze the evaluation selection,
model/runtime identity, proof jobs, prompt templates, budgets and success criteria
before inference. Run only separately designated evaluation packages; do not restart
an unfinished bootstrap qualification merely to evaluate a new model.

Use public or independently selected representative VeriSlop proof jobs covering
both contract and VSCore bridge paths. Include straightforward kernel proofs,
quantified reasoning, concrete structured witnesses, and supported refinement
goals. Evaluate actual workflow prompts and decoders rather than substituting a
different benchmark protocol. Retain every raw model submission and actual Lean
diagnostic. Do not supply a reference proof, private expected answer, or a
supervisor-written corrected proof to turn a failed model submission into success.

Report per-job success within three proposals, proposals used, elapsed time,
prompt/output token counts when available, protocol failures, Lean rejection and
context-limit failures. When a model/server omits token counts, report them as
unavailable rather than zero. Include complete route outcomes and distinguish
kernel acceptance from mere compilation with proof holes. Compare ordinary-prover
calls avoided and total cloud calls/tokens where both measurements are available;
do not infer savings from a local success alone.

The complete-file and full VSCore-library contexts may be substantially larger
than a small prover's advertised theorem benchmark inputs. Any later proof-state
adapter beyond the fragment protocol above requires its own prior specification
and independent evaluation. This milestone does not silently omit context,
truncate goals, alter statements or claim that an adapted protocol is the original
workflow.

## Required regression cases

1. Absent and disabled routing preserve existing behavior and configuration usage.
2. Enabled routing rejects unknown agents, invalid tool profiles, unresolved used
   providers and stale model/job bindings before inference.
3. Initial success prevents fallback; three rejected proposals trigger it with
   exact latest candidate and diagnostics.
4. Three identical initial failures still permit fallback. Builtin tactics,
   retained/candidate-file checks and implementer-supplied proofs consume no local
   slots.
5. Broker retries consume one logical slot; interrupted dispatches remain consumed
   across a resume. Changing a retained state blob blocks before dispatch.
6. Identical fixed jobs retain counters; a different VSCore source/relation/goal
   gets a separate bounded job.
7. Local service failure is recorded before escalation. Configuration, global
   budget and verifier failures are not swallowed or reclassified.
8. Contract and VSCore routes still reject changed statements, invalid envelopes,
   oversized proofs, unresolved `sorry` and prohibited constructions through the
   existing verifier paths.
9. Enabled routing preserves every fallback slot while respecting the unchanged
   total token and wall-clock limits. A zero fallback-attempt budget makes no
   proof-model calls.
10. Evidence grows with immutable events and referenced blobs rather than repeated
    complete history. No frozen bootstrap evidence is modified.
11. Fragment assembly compiles actual generated proofs in Lean while preserving
    frozen bytes. Negative fixtures reject changed headers, duplicate/unknown
    names, injected commands and misleading comment/string tokens before assembly.
    Such authored unit fixtures are not counted as live model successes.
