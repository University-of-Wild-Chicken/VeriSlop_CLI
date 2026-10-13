# Small prover evaluation protocol

This is a finite evaluation of local Lean proof generation in VeriSlop. It does
not resume bootstrapping, evaluate natural language interpretation, or establish
a general model capability claim. Interpretation and formalization use a
published, proof-free synthetic cohort. Only the proof-generation role calls a
model. Generated software, TESTED status, and final release are outside scope.

The cohort contains six fresh contracts: natural arithmetic, signed arithmetic,
list map, list filter, list fold, and nominal records with an enumeration. Their
natural-language requests, obligation records, and typed formalizer ASTs are
published together. No theorem proof or successful candidate is part of the
cohort. The harness compiles these ASTs with the existing formal frontend, runs
the ordinary interpretation and statement-checking stages, and freezes every
challenge before any inference. A setup failure is an infrastructure or contract
setup result; it is not a model proof failure.

Each selected challenge receives two independent arms with identical frozen
challenge bytes: the ordinary deterministic tactic portfolio, and a local model
with the portfolio disabled and at most three proof proposals. Model generation
has no imposed wall deadline. The existing Lean build resource policy remains
in force. An external stop ends execution without a success claim. The published
configuration and source/cohort hashes are bound before the first model call.
The first three attempts refer to proof proposals, not transport retries or
deterministic tactic attempts.

The model receives the existing prover prompt, the exact complete frozen file,
and actual previous candidate diagnostics. No expected proof is supplied. Raw
responses and submitted candidates are retained separately. A candidate counts
as accepted only after the existing `accept` and `export` stages succeed and the
accepted required obligation inventory and statement hashes match the frozen
contract. Compiling a file, completing a candidate, or returning `prove` PASS
alone does not count. False statements are not inferred from failed search.

The initial complete-file interface measurement is retained unchanged. A fresh
second measurement may select `--proof-response-format theorem_fragment` after
that interface is implemented in the ordinary prover agent. This is an explicit
input/output interface change, not a repair of earlier results: the model emits
theorem declarations; the agent checks their exact frozen names and statements
and assembles their unchanged proof terms into the original frozen scaffold.
The harness does not supply proof expressions, edit model proof terms, copy
portfolio proofs, or strengthen success labels. `complete_file` remains the
default. Each new run freezes its selected interface and reports it. Comparison
with an earlier run requires identical cohort bytes, original obligation
inventories, statement hashes, and Lean challenge hashes; source implementation
hashes are expected to change when the explicit interface changes.

Failure classification follows observed evidence: transport/configuration and
build infrastructure failures are distinct from invalid response envelopes,
missing or changed frozen scaffolds, changed contract statements, actual Lean
elaboration/tactic failures, and elaborated candidates with remaining holes.
Raw responses and the original first-run summary are never rewritten to apply
the later interface. Failed Lean search does not constitute a counterexample.

Optional `--tokenizer DIR` uses a locally installed Transformers tokenizer with
network access and remote tokenizer code disabled. Before dispatch, the harness
renders exactly the submitted system/user messages with the frozen local chat
template, `add_generation_prompt=True`, and `enable_thinking=False`; it counts
that serialization and requires input tokens plus the declared output budget to
fit the explicitly configured context. It never shortens the prompt. The count
is exact for that local serialization; Ollama may render a different native
template. Record this basis and compare its count with the actual provider usage
after a response. A substantial disagreement or an observed native context
overrun is an infrastructure/context result, not a theorem failure. Tokenizer
files and runtime package identities are retained in the run freeze. Omitting
the tokenizer performs no token-fit assertion.

An optional Tier 2 refinement probe uses a fixed canonical implementation for
the cohort's nominal record/enum contract, only after the model arm has accepted
that contract. The supervisor derives and freezes the exact bridge goal,
proposition hash, accepted reference, source, relation, and readable selection
before bridge proof inference. Up to three generated proof modules are checked
against those inputs. Preview is advisory; an accepted bridge result requires
the existing preparation and two-build bridge checker. Contract-dependent skips
are reported explicitly and excluded from standalone bridge success rates.

All outputs go to a new local validation directory. A run never overwrites an
earlier run, never reads private evaluator cases or session/controller records,
and stores a compact source freeze, stage records, exact agent transcripts,
proof artifacts, and summary. Report observed successes, attempt counts, elapsed
time, and provider-reported input/output tokens. Missing usage is unknown; no
token-price or savings figure is invented. Failure summaries distinguish setup,
transport, malformed response, Lean build/unsolved proof, immutable-contract
rejection, external stop, and acceptance/export failures. The fixed cohort is a
smoke evaluation, not an estimate of full-corpus performance.

Example usage after preparing an Ollama model:

```sh
python synthetic_dataset/tools/evaluate_small_prover.py --prepare-only --out validation/small-prover-example
python synthetic_dataset/tools/evaluate_small_prover.py --model verislop-pythagoras:4b-f16 --endpoint http://127.0.0.1:11435 --case nat --proof-response-format theorem_fragment --out validation/small-prover-live-example
```

`--case` may be repeated. `--config` supplies a normal VeriSlop provider config;
`--model` and `--endpoint` are optional local overrides. The harness disables any
cheap-proof routing configuration for its direct model arm so the measured model
is the configured prover itself. `--prepare-only` freezes setup and runs the
deterministic baseline without inference. `--compare-to` binds an earlier
published summary and checks the frozen contract identities before the new
inference arm. Results are limited to the completed live invocations reported in
their original run directories.

## Local model provenance and observed initial result

The evaluated local model is the official
`Pythagoras-LM/Pythagoras-Prover-4B` repository at revision
`aa05cf9a86cd1bc5af16935ab8f2190f4a1e62b8`. The thirteen downloaded weight and
tokenizer files were checked against publisher metadata. Official llama.cpp
revision `1b70350c92563449576bcbbf552994b1d1ed847d` converted those weights to
F16 GGUF; the GGUF blob SHA-256 is
`3a91f87fc7846514ed0e87353a51924a9a6ec8d3ba9c15a26e69412e9e3ea031`.
Ollama 0.34.0 serves the explicitly configured
`verislop-pythagoras:4b-f16` tag at `http://127.0.0.1:11435`, with aggregate
model digest
`4b6a8a6374d56cac7f7c9b289d35a8c7c99194ffeafb8cec54f143a263fc6695`.
The local GPU is an RTX 5080 with 16 GB VRAM. Native Safetensors import required
MLX, unavailable on this Linux runtime; the standard GGUF route worked. Those
setup failures count as infrastructure failures, not theorem failures.

The first completed six-contract measurement, using the complete-file
interface, accepted **0/6** model contracts and **5/6** deterministic portfolio
contracts. Its eighteen real provider calls reported 40,298 input tokens, 6,058
output tokens, and 73,565 ms of provider-call time. Some responses supplied
standalone theorem declarations without the frozen definitions and namespace;
other responses named tactics unavailable in the pinned Std-only environment.
These are observations of that interface and cohort, not estimates of future
success or monetary savings. The original raw results remain unchanged in local
ignored validation paths. Failed temporary import and orphan artifacts were
pruned through a hash ledger; installed models and current measurements were
retained. Evaluation does not automatically download models, change user roles,
or restart bootstrapping.

The second measurement used the theorem-fragment interface on the same frozen
contracts and also accepted **0/6**, versus **5/6** for the portfolio. Its eighteen
provider calls reported 39,721 input tokens, 5,838 output tokens and 67,648 ms.
Inspection exposed an adapter defect: a global command-token check rejected
Lean's `@` explicit applications even in an exactly matching frozen theorem
header. Four jobs encountered that rejection; the other two encountered tactics
unavailable in Std. The original run remains unchanged. Its zero acceptance rate
therefore does not establish that all six proposed mathematical proofs failed.

A fresh retry corrects this generic parsing defect before inference. Exact header
matching, complete proof-term parsing through EOF, frozen scaffold preservation
and ordinary Lean acceptance remain required. Tokens inside matched headers and
parsed terms are not classified as top-level commands merely because the same
spelling can start a command elsewhere. Actual extra declarations and attributes
remain rejected. Neither proof bodies nor goals are supplied or corrected by the
harness. The optional bridge probe uses the same production proof-response
adapter as the contract arm, including its declared fragment response mode.
