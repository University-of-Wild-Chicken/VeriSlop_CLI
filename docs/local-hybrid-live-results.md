# Local hybrid evaluation, 2026-10-13–14

**Completed result:** fresh natural-language trial
`local-hybrid-live-20261014-005` passed the full strict Tier 0 pipeline on
P03 Unicode labels. Six guarantees reached TESTED with 32 effective cases each;
the independent checker passed 160 cases twice. Formal-contract review, release
review and final verification all passed. This establishes one completed task,
not broad corpus coverage or END_TO_END_VERIFIED.

The requested first target is strict Tier 0 TESTED Python. The route assigns Qwen
to interpretation, formalization, implementation and concrete review; unresolved
proofs use Pythagoras up to three times, Qwen refinement up to three times, then
the configured Sol proof budget. The initial trials confined Sol fallback to proofs;
the October 14 continuation explicitly adds autonomous critic protocol fallback.
See the [workflow specification](local-hybrid-workflow.md).

Qwen and Pythagoras run through native Ollama with pinned model digests. Sol, if
needed, uses the recorded fresh-agent collaboration simulation because this shell
has no OpenAI API credential. Its provider identity and token usage are unattested.
No supplied draft, contract, proof or implementation enters the full pipeline trial.

## Runtime tuning

The initial 65,536-token Qwen context used a 4 GiB F16 attention cache and placed
50 of 66 layers on GPU. The runner used roughly 15 CPU cores, while GPU utilization
was around 21%. Actual workflow generation was approximately 16 tokens/second.

A separate Ollama instance on port 11436 leaves the existing 11435 service
configuration unchanged. With a 32,768-token context, `q8_0` cache, Flash Attention,
one loaded model and one request, all 66 layers fit on GPU. Neutral probes measured
approximately 54 tokens/second. Restricting the evaluated llama.cpp backend to four
CPU threads retained that speed; a warm probe averaged 2.46 CPU cores. These short
runtime probes are not task-quality comparisons. Cache quantization changes
inference precision; the Lean and testing gates remain unchanged.

The trial freezes the official Qwen tokenizer and checks complete input plus an
8,192-token output allowance and 128-token margin before dispatch. Native counts
matched all nine completed calls in the first tuned full trial exactly. Oversized
input is blocked explicitly, never truncated.

## Retained trials

- `local-hybrid-live-20261013-001`: stopped for CPU tuning after three completed
  native calls and one interrupted call. Evidence and a complete source archive
  remain local. A cancellation-reporting defect was subsequently fixed.
- `local-hybrid-live-20261013-002`: preparation only; no inference. The runtime
  receipt used JSON floats where canonical JSON requires decimal strings. A new
  receipt and fresh run directory preserve this setup failure.
- `local-hybrid-live-20261013-003`: nine native Qwen calls, 74,241 input and 14,560
  output tokens. The fourth formalization parsed and elaborated, but its critic
  input grew to 49,639 tokens and was blocked before dispatch. No Pythagoras, Sol,
  Python implementation or TESTED delivery occurred in this run.
- `local-hybrid-live-20261013-004`: fresh natural-language trial with compact critic
  input and the four-thread runtime. Seventeen native Qwen calls used 245,928
  input and 19,238 output tokens. The formerly oversized critic call completed;
  the final result was `BLOCKED / REVIEW_INCOMPLETE` at formalization. Critic
  replies either referenced no current diagnostic or omitted the required
  concrete functional probe. Native model call time totalled 465,335 ms. No
  Pythagoras, Sol, Python implementation or TESTED delivery occurred in this run.
- `hybrid-proof-diagnostic-20261013-002`: a separate public proof-free natural-number
  AST diagnostic passed Qwen criticism, one Pythagoras proposal, Lean acceptance
  and accepted-IR reconstruction. Two native calls used 5,114 input and 292 output
  tokens. Built-in proof tactics were disabled. This is proof-only evidence;
  it is not a natural-language software result and did not exercise escalation.
- `hybrid-proof-diagnostic-20261013-003`: the second and final adaptive proof-only
  diagnostic used a public proof-free list-fold AST. All three Pythagoras
  proposals were rejected for unavailable tactics. Qwen's first refinement left
  the concrete goal `1 + l.length = l.length + 1`; its second refinement passed.
  Lean acceptance and reconstructed IR passed with unchanged statement hashes.
  Seven native calls comprised three Pythagoras proposals, two Qwen refinements
  and two Qwen critic calls, using 21,415 input and 925 output tokens. Sol was not
  called. This exercises live failed-proof handoff, not TESTED Python generation.

The oversized critic input contained six repeated symbol-hash maps. A generic,
deterministic projection now retains their complete hash-bound CAS artifact while
keeping every formula, source, diagnostic and probe in the prompt. Replaying the
recorded failing input through this projection reduced it to 23,238 tokens, or
31,558 including output allowance and margin. Checker inputs remain complete.

Large traces stay in ignored `validation/` directories. The append-only checkpoint
ledger starts at `validation/local-hybrid-ledger-20261013/ledger-0001.json`.
Its initial-series final checkpoint is `ledger-0002.json`, which verifies both current source
bindings and all three archived source snapshots. The completed trial models were
unloaded from the task endpoint to release GPU memory.
No result here establishes END_TO_END_VERIFIED.

## October 14 continuation

An optional explicit Sol critic route now handles exhausted invalid autonomous
critic replies. It preserves the actual fallback identity, concrete-defect vetoes,
consensus slot count and ordinary Qwen checkpoint/release membership. Consumed
attempts and exact responses survive restarts. Independent routing/probe/projection
tests passed 29 cases and the harness passed 25 cases. An authored regression
passed real Lean, implementation, linking, test and closure gates; it is not a live
model success. Each new trial saves a hash-bound complete source archive.

`local-hybrid-live-20261014-001` completed with zero TESTED deliveries. Twenty
native Qwen calls used 183,191 input and 26,331 output tokens. Two interpretation
calls passed, followed by nine rejected formalizations across three packages.
Each failed with `typing: invalid sort 'Input'`. Qwen's critic returned valid
indexed corrections but incorrectly described nested record support. No
Pythagoras, Sol or implementation call occurred. This is a separate authoring
failure; critic fallback cannot override a valid diagnostic correction.

The next iteration improves generic grammar guidance: errors for bare registered
record/enum names show their required structured sort syntax, and critics see the
registered grammar when formalization fails without usable analysis. It does not
rewrite a model response or supply a task solution. The closed run and its source
archive are recorded in `ledger-0003.json`.

`local-hybrid-live-20261014-002` passed interpretation, formalization, proof,
acceptance, accepted-IR reconstruction, formal-contract review, implementation,
linking and testing. All six functional obligations reached TESTED with 32
effective cases each. The independent checker passed 160 cases twice (320
observations), with unchanged input bytes. Release review could not dispatch:
its complete input was 36,192 tokens, exceeding the 32K context even before the
8K output allowance. Consequently the overall trial remains an infrastructure
failure, not a completed strict delivery. Thirteen native Qwen calls used 173,920
input and 13,130 output tokens. Pythagoras's 13,379-token proof prompt also exceeded
its former 16K context plus reserved output; the explicit predispatch route
advanced to Qwen, whose first refinement passed Lean. Sol was not called.
`ledger-0004.json` binds these outcomes and the verified source archive.

The next configuration changes Qwen review to 40,960 context / 2,048 output
tokens and Pythagoras to 32,768 context / 8,192 output tokens. A neutral four-thread
Qwen probe retained all 66 GPU layers at 40K, measuring 53.75 tokens/second.
A 48K probe offloaded part of the model and measured 36.56 tokens/second, so the
smaller setting was selected. No task artifacts or checker cases are supplied to
fresh generation; the changes reserve capacity for complete existing prompts.

`local-hybrid-live-20261014-003` exercised the full local proof handoff: three
Pythagoras proposals were rejected, then Qwen's first refinement passed Lean.
All six guarantees reached TESTED and the independent checker again passed
160 cases twice. Nineteen native calls (including three Pythagoras calls) used
326,917 input and 17,038 output tokens; Sol was not called. The first release
ballot added forbidden `note` fields to its probes. Its protocol-repair request
duplicated the entire checkpoint guidance, growing to 42,855 input tokens and
exceeding 40K. The overall result remains an infrastructure failure, recorded in
`ledger-0005.json`.

The retry builder now omits only that redundant guidance copy. The original
complete guidance and packet, rejected ballot and diagnostics are preserved.
Exact frozen-tokenizer reconstruction removes 5,902 duplicate tokens, reducing
this retry to 36,953 input + 2,048 output + 128 margin = 39,129 tokens. Eleven
review protocol regressions passed, including unchanged-packet, bounded retry,
abstention and concrete-defect checks. This change enables correction rather
than accepting or silently repairing a malformed ballot.

`local-hybrid-live-20261014-004` confirms that the retry context fix works. All
three release-review calls completed, but Qwen returned the same malformed
ballot each time: seven `target_case` probes included an unsupported `note`
field. The strict result remains `BLOCKED / REVIEW_INCOMPLETE`. All six
obligations reached TESTED, and the independent checker passed 160 cases twice.
Twenty-one native calls, including three rejected Pythagoras proposals followed
by an accepted Qwen refinement, used 401,168 input and 19,026 output tokens.
Sol was not called. `ledger-0006.json` records this outcome and its verified
source archive. The next repair clarifies the difference between an invalid
probe kind and extra fields on a valid probe; model replies still face the
unchanged closed-schema validator.

`review-protocol-diagnostic-20261014-001` tested that clarification with one
native Qwen call against the retained release packet and rejected ballot.
Despite explicit unexpected-key diagnostics and a final exact-field reminder,
Qwen returned the identical malformed response. The call used 37,381 input and
893 output tokens. It is recorded in `ledger-0007.json` as `INVALID_PROTOCOL`,
with no replay or TESTED delivery claim. The next iteration adds optional native
Ollama schema-constrained generation; strict ballot validation and concrete
counterexample replay remain authoritative.

`review-protocol-diagnostic-20261014-002` retained the exact previous diagnostic's
prompt and enabled the optional schema. Qwen stopped adding forbidden fields,
but declared eight attempted cases while returning one probe. The untouched
response was rejected. The call used 37,381 input and 487 output tokens, with
matching model pin and recorded schema binding; `ledger-0008.json` preserves
the result. The following schema revision expresses the existing equality
between attempted-case count and probe-array length, retaining every allowed
count from one through eight.

`review-protocol-diagnostic-20261014-003` passed strict protocol validation.
With the exact same prompt as diagnostic002, Qwen returned eight distinct probes,
reported eight attempted cases and used only permitted fields. The call used
37,381 input and 763 output tokens. Its schema, model pin and transcript bindings
were checked and retained in `ledger-0009.json`. It performed no replay and is
not a software delivery. A fresh full natural-language trial follows this
diagnostic; old failed trials retain their original outcomes.

`local-hybrid-live-20261014-005` completed successfully under the new optional
review schema. It began with the public natural-language P03 request; no supplied
draft, proof, code or expected checker outputs entered generation. Before the
first call, the harness froze configuration, tokenizers, runtime and an archive
of 241 source files. Two contract defects were corrected autonomously. All three
Pythagoras proposals were rejected, and Qwen's first proof refinement passed
Lean. Accepted-IR reconstruction, formal-contract review, Python generation,
linking, all six TESTED campaigns, release review and final verification passed.

The independent checker passed all 160 cases twice, with no failures, incomplete
cases or input mutation. Nineteen native calls used 325,593 input and 16,212 output
tokens, including three Pythagoras calls and no Sol calls. Native model call time
totalled 549,089 ms; recorded pipeline stages totalled 589 seconds. The corrected
review ballots passed on their initial attempts. The generated Python remains at
`validation/local-hybrid-live-20261014-005/tasks/P03-unicode-labels/runs/p03-unicode-labels/implementation/requested.py`;
the summary, report, intermediate contracts, proofs and transcripts remain beside
it in ignored local evidence. `ledger-0010.json` binds the final result.

The decisive release fix was optional schema-constrained generation, first for
closed probe fields and then for the existing count-equals-probe-length rule.
Prompt-only correction failed in a separately retained diagnostic. No malformed
response was rewritten into an accepted ballot, and no proof, test, replay,
consensus or release requirement was waived. Pythagoras did not solve this
task's theorem; this result validates the handoff to Qwen, not independent
Pythagoras proof success. Sol fallback remains unexercised by the successful run.

## Validation and remaining limit

Routing/provider suites passed 106 tests. One provider integration failure was
reproduced on clean HEAD before proof routing: its synthetic O17 critic expression
has no `Decidable` instance. The trial harness passed 21 tests; compact statement
projection passed six focused tests and 16 relevant autonomous regression cases.
Independent review checked concrete cancellation, context-boundary, tokenizer-file
mutation, retained-analysis restoration and probe-binding cases.

The initial pipeline bottleneck was the Qwen critic's inability to follow the concrete
probe protocol on the elaborated full contract. The initial configuration did
not give Sol an author/critic/reviewer fallback role. Proof fallback was implemented
and tested, but no live Sol call was required in these diagnostics, so this run
does not validate the Sol service or simulation response path in production use.

The task-scoped server was launched on this machine with:

```bash
AIX_OLLAMA_HOST=127.0.0.1:11436 AIX_CONTEXT_LENGTH=32768 \
OLLAMA_KV_CACHE_TYPE=q8_0 LLAMA_ARG_THREADS=4 \
/home/augustus/AIx/scripts/start-ollama.sh
```

This launcher is local to the evaluated machine. Other installations should use
their own Ollama model directory and endpoint. Ollama documents the cache precision
tradeoff in its [FAQ](https://docs.ollama.com/faq#how-can-i-set-the-quantization-type-for-the-kv-cache).
