# Structured data contracts and the Python test bridge

The Tier 0 executable contract surface now includes signed integers, Unicode scalar strings,
typed lists and fixed-field records. It supports ordinary filtering, mapping, projection,
concatenation, reversal, totals and counts. The strict pipeline still interprets a request,
checks its Lean statement, proves and accepts the contract, reconstructs the accepted IR,
generates an independent Python implementation, links it and runs a campaign. Unsupported
statements require correction or remain blocked; there is no artifact-first bypass.

## Versioned sorts and carriers

`verislop.contract-dsl/0.1` and `python-v0_1` retain their existing Nat/Bool/Unit/enum/Except
surface. New accepted profiles select `verislop.contract-dsl/0.2` and `python-v0_2`. A binding
proposal must name exactly the profile selected from the accepted artifact. Accepting both
names in the proposal schema does not permit a caller to choose different semantics.

The extension has these sorts:

```text
Sort ::= Nat | Int | Bool | Unit | String
       | {enum: EnumId}
       | {result: {error: Sort, ok: Sort}}
       | {list: Sort}
       | {record: RecordId}
```

Int uses exact signed arithmetic; Nat subtraction is still truncated. String contains
Unicode scalar values, without normalization or trimming. Lists preserve order and
multiplicity. A record has an ordered list of named, typed fields, read from its accepted
Lean constructor. Records are monomorphic and nonrecursive; proof and dependent fields
are unsupported. Record projection declarations must have the exact corresponding Lean
projection AST. The constructor, type and projections are bound by declaration hashes.

Explicit public declarations may use underscore-prefixed names. The reifier retains
exact names decoded from checked obligation bindings, and discovers their nested
carriers from accepted type ASTs. Unbound auxiliaries, private declarations and reserved
`_vs_` names remain excluded; a proposed JSON name alone cannot register a declaration.

The evaluator uses immutable tuples for lists and tagged immutable tuples for records,
so oracle caching keys preserve the entire typed value. Python receives actual lists and
dicts with exactly the accepted keys. A function with one record argument keeps one
Python argument. Missing/extra fields, Boolean values passed as integers, surrogate
code points, and tuple/list substitutions fail decoding.

```json
{"dict":{"values":{"list":[{"int":"-2"},{"int":"3"}]},"minimum":{"int":"0"}}}
```

Canonical decimal wire integers have no leading zeros or negative zero. Closed tagged
syntax, sorts and finite transport budgets are checked separately. Exceeding a work
budget yields unsupported/indeterminate evidence, never a fabricated counterexample
or a passing test.

## Expressions and acceptance

The new term constructors cover Int arithmetic/negation, exact Nat-to-Int conversion,
String literals/append/length/isEmpty, record
construction/fields, list literals/cons/append/reverse/length/map/filter/sum/foldl, Boolean
connectives/equality and `decide` of quantifier-free supported formulas. Map/filter bodies
have a typed local binder. Foldl has typed accumulator and element binders, visits values
in order, and returns its initial accumulator for an empty list. Function calls still
refer to accepted profile symbols.

The JSON is reconstructed from the replayed Lean environment. For each executable
statement, the reifier constructs a Lean denotation of the JSON formula and requires
kernel definitional equality with the exact accepted theorem type. Builtin operations
use fixed pinned standard instances. A user-defined instance cannot silently change
the meaning of an arithmetic, ordering or equality node. Opaque expressions do not
become executable merely because their Lean statements typecheck.

The implementation prompt carries a lossless table of accepted formula packages,
keyed by their canonical hashes. Each obligation retains its metadata and a
`formula_package_ref` to its entire package. Identical packages are shared; no
obligation, hypothesis, binder or branch is dropped. Strict response parsing reports
malformed outer objects and duplicate keys directly, rather than selecting a nested
fragment as a replacement proposal.

For Python Tier 0 TESTED requests, the formalizer can propose
`verislop.formalizer-ast/0.1`: ordered record fields, typed total definition bodies,
closed theorem formulas and explicit bindings to the interpreted IDs. A generic
[frontend](../verislop/formal_frontend.py) renders quoted, typed Lean syntax. It does
not infer a task's answers, add requirements or repair formulas. It rejects unknown
fields, wrong sorts, missing IDs and cyclic dependencies. Raw Lean proposals remain
supported through the same gates.

A rejected typed response supplies its actual parse/type diagnostic to the next
formalizer attempt. The exact transport placeholder is not treated as a legacy
binding manifest with missing fields. This changes repair feedback only: malformed
source, supplied candidate directories and exhausted attempts keep their rejection
gates, and no placeholder can freeze a contract.

Before freezing, Lean checks the original typed proposal's denotations against the
emitted definitions, predicates and theorem statements. This compiler-fidelity check
does not prove a theorem containing a proof hole. Proof search, axiom and witness
audits still have to succeed. The downstream IR is reconstructed from the accepted
Lean environment; the proposed AST never becomes accepted IR by promotion.
Structurally tautological guarantees such as `solve(x) = solve(x)` are rejected for
an automatic test campaign. A complete equation against fixed primitives can still
be proved by reflexivity after unfolding its model definition.

The untrusted deterministic proof portfolio now constructs typed existential
witnesses for these carriers, including nested records, enums and explicit results.
It handles conjunction branches separately and uses fully qualified quoted Lean
names. Search is bounded by four binders per branch, 256 candidate tuples, 4,096
carrier nodes and depth 32. Exhaustion leaves a proof hole; it does not establish
satisfiability or permit acceptance. The ordinary kernel and witness audits remain
the authorities.

Record projections are operations, rather than independent implementation functions.
Separately defined reference helpers can remain implementation symbols; an inline
primitive expression or local `let` expresses the independent observable requirement
without equating two unconstrained implementation functions.

## Campaign and concrete review

Campaigns sample signed/extreme integers, Unicode and empty strings, empty/duplicate
lists and recursively typed records. Only an exact successful evaluation counts as an
effective passing case. Sampled exhaustion of an infinite residual quantifier cannot
discharge that quantifier. An exact counterexample or existential witness still has its
ordinary three-valued evaluator meaning.

Concrete reviewer proposals can carry nested list/dict wire values. Replay checks the
accepted binder sorts and invokes the actual hash-bound generated implementation in
the isolated harness. The v0.2 pure Python admission includes list comprehensions,
dicts/subscripts, local loops and the positional builtins `len`, `sum`, `list`, `range`,
plus one-argument local-list `append`. Legacy admission is unchanged. Imports,
reflection, arbitrary attribute calls, classes and nested functions remain unsupported.

After acceptance, review packets carry only the hash-checked accepted proof source;
the duplicate pre-proof template is omitted. Before acceptance, the frozen template
is shown instead. A stale or mutated accepted source blocks review rather than
falling back to the template. Request text, obligations, interpretation, acceptance
inventory and concrete probe requirements remain in the packet.

Tier 1 structured monitors and the Tier 2 VSCore 0.1 transfer rule are explicitly
unsupported for this new encoding. Tier 0 can reach TESTED, with two isolated clean
builds and the configured review gates. It cannot reach END_TO_END_VERIFIED.

## Native proof-of-concept protocol

[Preregistered prompts and execution rules](../examples/proof-of-concept/data-pipelines/PROTOCOL.json)
fix three tasks before model generation. Their 160 distinct request-oracle cases per
task include signed boundary equality, negative/zero factors, large integers, nested
records, duplicate preservation and exact Unicode text. Expectations come from an
independent imperative request oracle, rather than the Lean model.

The [supervisor](../synthetic_dataset/tools/run_data_pipeline_poc.py) freezes its runtime
and verifier sources, starts the ordinary native CLI without candidate flags, retains
all automatic repair packages and records exact provider transcripts. The final Python
source must match a complete native implementation response byte for byte. Withheld
cases are evaluated after model generation in two fresh isolated harnesses; their
results never become repair feedback. Failed tasks stay in the denominator. A runtime
change requires a new full cohort and a new source root.

Typed proposals retain a compilation receipt binding the exact captured response,
proposal, interpreted records, compiler bytes, Lean source and binding manifest.
The origin audit recompiles that response and reconstructs its registry and frozen
challenge. It also checks every proof attempt against a captured proof response or
the unchanged deterministic tactic portfolio. Neither handwritten test fixtures nor
negative mutants count as native positive results.

Run a new cohort using the provided pinned local Ollama example:

```bash
python -m synthetic_dataset.tools.run_data_pipeline_poc \
  --cohort .verislop/data-pipeline-poc/cohort-001
```

Each cohort emits source-freeze, invocation, origin-audit, native report, independent
oracle and result receipts. The native report is the authority for CLI milestones.
Independent request observations add finite evidence of prompt fidelity and cannot
award a milestone. The recorded origin checks assume the host operator, hashing,
sandbox and local provider transcript fidelity; they do not prove resistance to a
privileged operator fabricating every input and receipt.

For an installed Ollama model with a larger supported context, pass
`--ollama-context-tokens 32768` to the supervisor. The effective configuration,
its hash and the departure from the base configuration are frozen before calls.
Each agent's optional `context_window_tokens` becomes the documented
[`options.num_ctx`](https://github.com/ollama/ollama/blob/main/docs/api.md) parameter.
Other provider families reject this option. Omission preserves the installed model
setting. Transcripts record the configured request value; that is not attestation
of the provider's actual context allocation. No model-generation deadline is added.

An optional [three-task Luna supplement](../synthetic_dataset/tools/luna_data_pipeline_poc.py)
uses the same natural-language tasks and withheld cases through fresh collaboration
agents. It declares its separate protocol before generation and leaves the strict
mechanical/review gates in place. This is a simulation transport: the requested model
is `gpt-6-luna`, but actual provider snapshot, token usage, sampling and tool-policy
enforcement are unattested. Its results must be reported separately from native
Ollama/Qwen results and cannot support an equal-compute comparison.

For large requests, preregister `prepare --relay-mode file`. Each fresh agent may
read only its exact current carrier file, whose bytes contain the original SYSTEM
and USER strings. Carrier, request, spawn-message, task and protocol hashes are
checked again at submission and audit. This tool-policy departure is declared
before generation, and reading/tool enforcement remain unattested. Inline mode
remains the default. Transport failure requires a new whole cohort; earlier
responses are never carried into it.

An exact empty agent final is retained as a hash-bound `EMPTY_AGENT_FINAL`
transport failure, with zero output bytes and the actual fresh agent ID. It never
becomes a completion or candidate. The native task fails explicitly and the
supervisor continues the remaining fixed tasks. Error receipts and counters are
audited separately from normal responses.

This coverage does not yet include arbitrary dynamic JSON, dependent/recursive records,
general text parsers, sorting or graph algorithms. These three tasks are a proof of
concept for a larger data domain, not a rerun or estimate of the 100-task benchmark.

The [retained results](../synthetic_dataset/diagnostics/data-pipeline-poc-20261008/OVERALL.md)
separate native CLI milestones from experiment accounting. Latest native cohort005
has one CLI PASS through TESTED out of three tasks, including 160 independent cases
passing twice. Its original supervisor reports 0/3 because it compared the emitted
tier object to integer zero. The checker now consumes the exact Tier0 Python TESTED
scope and keeps all build, review and campaign gates. That fix was applied after the
cohort sealed; no historical result is rescored, and a newly measured qualification
would require another complete frozen cohort. Luna003 produced no implementations.
