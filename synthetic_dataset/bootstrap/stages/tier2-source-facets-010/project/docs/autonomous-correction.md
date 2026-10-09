# Autonomous correction and durable contract context

The agent-driven `run`, `formalize` and `prove` commands require autonomous
criticism of formalization candidates and unresolved proof attempts. They reuse
`review.review_tiers`, including each configured model, reviewer count, focus,
consensus mode and abstention bound. A lower tier with completed searches escalates
to the next tier. A concrete defect returns the candidate to its author before
escalation. These searches supplement the existing review checkpoints; they do
not replace release review or any mechanical gate.

## Correction protocol

Critics receive the recorded natural-language request, exact covered clauses,
current JSON bindings, exact Lean source, reconstructed formulas/signatures and
indexed machine diagnostics. They must construct concrete inputs or identify an
actual machine diagnostic and a specific correction. Speculation about reliability
cannot reject a candidate. Responses use this strict envelope:

```json
{
  "encoding": "verislop.autonomous-critique/0.1",
  "verdict": "REPAIR",
  "counterexamples": [
    {"obligation_id": "O1", "inputs": [{"int": "3"}]}
  ],
  "corrections": []
}
```

Universal cases instantiate the leading universal binders in declaration order.
Wire values use the same exact, sort-checked representation as the Python target:
`int`, `bool`, `none`, `str`, `list`, `dict` and admitted enum/result constructors.
Both formalization and proof-stage critic inputs are checked against the current
signatures. Unknown IDs, noncanonical values, wrong arity, wrong sorts, extra fields
and fabricated diagnostic indices receive bounded protocol correction. Each critic
gets at most two response attempts; the provider's call/token limits also apply.
Configured tier wall budgets are checked between calls, never used to interrupt
an inference. Zero disables that wall bound.

For a candidate that elaborates, a generic bounded scan searches primitive, list
and record inputs independently of task names. The checker freshly replays the
exact candidate and reconstructs its profile, registry, statements and denotations.
A host evaluation is only an untrusted search filter. A formal `REFUTED` result
requires a new closed Lean theorem proving the negation of the instantiated
guarantee, isolated compilation, kernel replay, exact theorem-type comparison,
unchanged original declarations and an admissible axiom closure without `sorry`.
The receipt binds the candidate, inputs, proposition, compiled module, kernel
export, toolchain and proof hashes. Candidate theorem holes do not taint a separate
refutation root whose closure has been checked clean.

A request/reference probe adds `entry_symbol`, `exact_clause_id` and `expected`:

```json
{
  "obligation_id": "O1",
  "entry_symbol": "bump",
  "exact_clause_id": "C1",
  "inputs": [{"dict": {"value": {"int": "0"}}}],
  "expected": {"int": "1"}
}
```

The clause ID is supervisor-assigned from the recorded coverage ledger, and must
cover the cited obligation. The checker proves the candidate's actual ground
output. A difference from the critic's expectation is `SEMANTIC_MISMATCH`, retained
with `natural_language_clause_verified: false` and `guarantee_refuted: false`.
The expectation is untrusted interpretation feedback. It cannot establish that
the natural-language request, the implementation or a universal property is proved.
The author must inspect the quoted requirement and propose a revised contract;
all strict checks run again. Removing obligations, adding caller assumptions or
changing a frozen contract in place remains forbidden.

Before freeze, concrete defects return to the formalizer with their full receipts
and the rejected proposal. Real parse/type errors return with indexed diagnostic
corrections. Advisory diagnostics do not trigger repair. After freeze, a prover may
change proofs only. Repeating an identical failed source and diagnostics twice
after the initial failure stops with `NO_PROGRESS`. Configured strict recovery can
then create a fresh sibling package with the same request and interpretation;
the failed package and every frozen artifact remain intact. No first-error
artifact-first fallback is introduced.

`UNKNOWN` is explicit when search or closed proof construction is unsupported,
inconclusive or bounded out. A completed finite search is not evidence for a
universal claim. Only the ordinary acceptance, implementation, linkage, testing
and closure verifiers can assign the corresponding obligation milestones.

## Retention and reload

Every role request is saved before the provider call, and every returned response
is saved byte-for-byte. Provider failures retain their input snapshot and error.
Formalization attempts additionally retain the draft, interpretation ledger,
binding JSON, typed proposal/compiler receipt when present, submitted and composed
Lean, reconstructed profile/statements, diagnostics and critique. Proof attempts
retain submitted and composed Lean, best/latest candidate context, frozen
signatures and diagnostics. Failed versions are never overwritten by later ones.
Recovery handoffs retain the concrete critique and parent snapshot reference.

The store lives under `agents/memory/`:

```text
blobs/<sha256>.blob
snapshots/<sequence>-<sha256>.json
indexes/<sequence>-<sha256>.json
journal.jsonl
```

Blobs and snapshot/index documents are immutable writes. Each index extends the
previous index; an append-only journal commits the current head. Reload checks
paths, sizes, hashes, file kinds and chain identities. Missing or stale heads,
tampered bytes and link replacements fail closed with
`STALE_OR_UNBOUND_EVIDENCE`. Readers never silently fall back to an older head.
The trusted host/filesystem must retain the journal: hashes do not authenticate a
wholesale, internally consistent rewrite or removal of the entire store.

A fresh formalizer automatically reloads the latest rejected proposal and feedback,
including the exact malformed raw response when needed. A fresh prover reloads
best/latest sources and recompiles them against the frozen challenge before use.
Current role prompts are assembled from these artifacts, rather than appending
all old conversations and causing repeated context inflation. Retained context
has no proof or milestone authority; downstream implementation contracts continue
to come from the accepted Lean environment and reconstructed IR.

Use the read-only CLI to recover context after conversation compression:

```bash
bin/verislop context --package runs/example --json --last 2 \
  --stage-prefix formalize/attempt
bin/verislop context --package runs/example --json --last 1 \
  --stage-prefix prove/attempt
```

Reloaded content includes exact UTF-8 bytes as text, or base64 for binary artifacts,
and bound snapshot/index references. Bounds are explicit: 64 artifacts, 2 MiB per
artifact, 8 MiB per checkpoint, 256 snapshots, 64 MiB total stored bytes and 2 MiB
per reloaded context. Exceeding a bound is `BUDGET_EXHAUSTED`, with no silent trimming.
Hydrated context cannot recursively be checkpointed as another context packet.

## Validation boundary

Authored mock-agent regressions correct a false theorem and a consistently proved
wrong reference through actual Lean acceptance, AST-derived IR, generated Python,
linkage, finite TESTED campaigns and clean builds. Other regressions cover quorum
escalation, malformed critic correction, proof stagnation, strict wire validation,
fresh-process recovery, corruption and preservation of rejected artifacts.
These checks establish regression behavior, not Qwen/Luna benchmark improvements
or end-to-end verification for the Python data bridge. Historical measured
packages and scores are unchanged.
