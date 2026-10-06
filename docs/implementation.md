# VeriSlop CLI v0.1 — implementation notes

This document describes how the `verislop` CLI realises [the specification](specification.md), and where it deliberately stops. It is descriptive. The normative documents remain the specification, [contract-ir.md](contract-ir.md), [obligation-states.md](obligation-states.md) and [providers-and-review.md](providers-and-review.md).

## 1. Principles carried through the code

- **Proposals vs decisions.** LLM agents, humans and existing code only produce candidates. Every lifecycle outcome is derived from an evidence record written by a registered verifier (`verislop/verifiers.py`). Each verifier's hash covers the exact source bytes it runs, so editing a verifier makes its earlier evidence `STALE`.
- **Evidence binds to roots.** Each record (`evidence/ev-*.json`, write-once, read-only) names a claim, an input root, and the verifier hash. Its ID is derived from its content, which makes tampering detectable. `obligation-view.json` is recomputed from evidence and current roots, never from candidate fields.
- **Fail closed.** These all produce diagnostics rather than approximations: unknown schema keywords, unsupported Lean constructs, non-constructive witnesses, a missing toolchain or required filesystem/network isolation, and unparseable agent output.
- **No silent downgrade.** An unsupported tier, endpoint or capability is a stable `UNSUPPORTED_CAPABILITY` diagnostic.

## 2. Run package and roots

```text
<package>/
  package.json            run identity, artifact index, stage history (bookkeeping only)
  request/                prompt.txt (exact bytes), request.json, routing.json
  draft.json              interpretation proposal (never downstream authority)
  interpretation.json     clause dispositions, assumption suppliers, ambiguity decisions
  claims.json             frozen contract-phase claim inventory (frozen by formalize)
  contract/candidate/     last formalization attempt and its statement-check report
  contract/challenge/     FROZEN: Contract.lean (+registry), formalization, profile, statements,
                          policy, lean-toolchain, verifier hashes, challenge.json (manifest + root)
  contract/proofs/        proof workspace: candidate.lean, attempts/, attempts.jsonl
  accepted/               content-addressed source/olean/environment/profile/statements,
                          certificates/, acceptance.json (current), expressions/, accepted-ir.json
  implementation/         exact candidate sources
  bridges/                bindings.json (proposal), link.json (validated), tier1/ monitors,
                          <bridge-id>/ frozen bridge preparation bundles, with
                          <bridge-id>/semantic/edge-*/ registered-checker acceptances
  tests/                  campaign.json (frozen), results.json
  closure/                implementation-claims.json (frozen by generate), review-config.json
  reviews/<campaign>/     packet, campaign, ballots, transcripts, consensus certificate
  evidence/               immutable records + raw results
  obligation-view.json    derived overlay       report.json   authoritative decision
```

| Root | Covers | Binds |
|---|---|---|
| interpretation root | prompt bytes, draft, ledger | INTERPRETED |
| contract input root | `claims.json` + every frozen challenge file (incl. verifier hashes) | FORMALIZED, TYPECHECKED, PROVED |
| implementation root | `implementation/` tree | IMPLEMENTED |
| link root | accepted IR, implementation root, binding proposal, implementation claims | LINKED |
| test root | link root + frozen campaign configuration | TESTED |
| implementation closure input root | certificate, IR, claims, implementation, bindings, monitors, campaign, verifier registry, schema hashes | closure claims, END_TO_END_VERIFIED |

Manifests (`fsutil.py`) use sorted relative POSIX paths and exact bytes. Symlinks, escaping or non-NFC paths, non-UTF-8 names and case collisions are rejected. Certificates, reports and evidence are outputs and are never part of their own inputs.

## 3. Interpretation (§3)

- `classify.py` is a deterministic lexical router. It returns `SOFTWARE`, `NON_SOFTWARE` or `UNCERTAIN` with supporting spans.
  - `NON_SOFTWARE` routes to `NOT_APPLICABLE`, which is a blocked run, never a verification success.
  - `UNCERTAIN` becomes an interpretation ambiguity, resolved by `--mode software` or `--resolve routing=…`.
- The interpreter agent returns **quotes**. VeriSlop locates them in the exact request bytes, so byte spans and hashes are never taken from a model.
- `draft.py` validates the draft (schema, hashes, spans, unique IDs, role/kind pairs). A candidate claiming any milestone beyond INTERPRETED, or a `state` such as `"PROVED"`, is rejected with `STALE_OR_UNBOUND_EVIDENCE`.
- The ledger check validates clause dispositions and assumption suppliers. Coverage is mechanical (`segment.py`): every request segment needs a disposition, otherwise `UNCOVERED_SOURCE_CLAUSE`.
- An unresolved ambiguity with a blocking impact blocks only the guarantees it affects. An agent default may settle only `routine` ambiguities. Users resolve with `--resolve ID=ALT` or interactively.

## 4. Formal contract, acceptance and export (§§5–7)

**Challenge.** `formalize` composes the candidate Lean file with a generated `VeriSlop.Registry` module (typed metadata: ID, revision, kind, role, statement, provenance, scope, dependencies, criteria, Lean bindings). Registry entries are an index, never evidence, and contain no status fields. The challenge is then:
1. elaborated in the sandbox as module `VeriSlopContract`;
2. replayed through the kernel and exported by the trusted tool;
3. checked: registry against claims, binding kinds, no module axioms, no `sorry` in definitions;
4. given a mechanically derived semantic profile, then reified and kernel-defeq-checked.

Derived non-vacuity obligations come from the registered rule `verislop.non-vacuity/0.1` and carry derived provenance.

**Compiled artifacts.** Legacy Lean files retain their raw `.olean` artifact. Lean 4.34.1 `module` files store a deterministic `verislop.lean-module/1` bundle containing `.olean`, `.olean.server` and `.olean.private`, with exact member names and per-member hashes. The certificate's existing `olean` slot binds the complete bundle bytes, even when its stored filename ends in `.olean`. Staging validates the complete envelope, sizes, digests and canonical encoding before writing any member. Public sections and private declarations are supported; third-party imports remain rejected.

**Trusted kernel tool** (`verislop/lean/VeriSlopKernel.lean`, run with `lean --run` in a separate process on a stage containing the candidate's complete compiled data):
- imports without executing initializers;
- imports at the private load level, checks a complete and consistent declaration inventory, and preserves hidden theorem/definition bodies;
- replays every module constant with `Lean.Kernel.Environment.replay` on top of the toolchain imports;
- exports canonical Expr JSON;
- walks transitive axioms itself on the replayed environment. Lean's `collectAxioms` is not used, because it trusts axiom data stored inside imported `.olean` files;
- extracts `Exists.intro` witnesses by bounded kernel head-normalisation;
- type-checks DSL denotations and decides kernel definitional equality.

**DSL v0.1.** `dsl.py` implements the exact node shapes, typing, limits, canonical encoding, the per-value round trip, and a three-valued evaluator. Reification (`reify.py`) is **Expr-level**: the trusted reifier reads the elaborated theorem type and reconstructs the DSL formula. Registered Prop-valued predicate definitions are the only reduction it performs (bounded delta/beta). Anything outside the fragment stays `lean_expr`. Each reified formula's denotation is re-checked by kernel defeq against the accepted theorem type.

This replaces the "closed `ContractExpr` data + `denote` theorem" encoding of contract-ir §6 with an equivalent check (denotation ≡ accepted type by the kernel). It needs no embedded DSL library in candidate files. The reifier never emits `forall_range`/`exists_range`; those are accepted as input and evaluated, but choosing them is a formalization decision, not a rewrite.

**Acceptance** (`accept.py`, policy `strict`):
1. Verify the frozen inputs, the policy, and that verifier hashes are unchanged since freeze.
2. Re-elaborate the challenge (determinism) and the proof candidate in isolated stages.
3. Replay the candidate through the kernel.
4. Require identical declaration hashes for the whole semantic closure of every statement, plus the registry. A candidate adding declarations to the reserved registry namespace is rejected.
5. Classify axioms per theorem: allowlist `propext`, `Classical.choice`, `Quot.sound`; `sorryAx` gives `PROOF_UNRESOLVED`; native-evaluation and unknown axioms give `INADMISSIBLE_AXIOM`.
6. Require constructive witnesses. A guarantee's assumption must be witnessed by an *accepted* non-vacuity obligation.
7. Write a content-addressed certificate plus TYPECHECKED/PROVED evidence.

**Export** (`export.py`) opens only the certificate's environment export, profile and `.olean`. It rejects raw drafts or unbound certificates, recomputes artifact hashes (mutation invalidates the certificate), re-reifies and re-checks defeq, and computes dependency edges mechanically (`assumes`, `uses_definition`, `uses_proof`, `requires_witness`). It writes canonical (RFC 8785) `accepted-ir.json`. Formula packages are content-addressed (`artifact:accepted-expressions/<ID>@sha256:…`), and opaque statements use `verislop.lean-export-ref/0.1` packages.

## 5. Implementation bridges (§8)

**`python-v0_1` profile:**

| DSL | Python |
|---|---|
| Nat | `int ≥ 0` (not `bool`) |
| Bool | `bool` |
| Unit | `None` |
| enumeration | constructor name as `str` |
| `Result(E, A)` | `("ok", a)` or `("error", e)` |

Python ints are arbitrary precision, so the profile has no overflow edge. Values outside the profile, and exceptions, are contract violations.

- **IMPLEMENTED:** every symbol in an obligation's accepted semantic closure has a proposed, existing top-level function, and the exact bytes byte-compile in the sandbox.
- **LINKED:** unique bindings. Competing bindings give `AMBIGUOUS_CORRESPONDENCE`; unbound public functions give `UNMAPPED_IMPLEMENTATION_OBJECT`; a candidate claiming coverage the accepted closure does not support gives `SCOPE_LEAK`.
- **TESTED (Tier 0):**
  - The harness (`targets/python_harness.py`) runs in an isolated interpreter (`-I -S -B`, no network, rlimits). It verifies the sha256 of every file before executing it and refuses to run with assertions disabled. Candidate sources and the harness are mounted read-only inside a writable scratch stage. Its JSONL receiver bounds response size and applies deadlines even to partial lines.
  - The campaign enumerates finite sorts and samples Nat with seeded, hint-guided generation (equality and bound hints from the formula, boundary values up to 2⁶⁴+1, a small grid).
  - Generation continues until the frozen number of *effective* cases is reached or a discard budget (20× that number) is spent, so the result does not hinge on a lucky seed.
  - Cases with false antecedents are discarded. Only exact counterexamples count, and they are shrunk (binary search).
  - Every input is re-called once to detect nondeterminism.
  - Fewer than 20 effective cases gives `EMPTY_TEST_CAMPAIGN`; any timeout gives `TEST_INCOMPLETE`.
  - Line coverage is recorded; branch coverage is not measured.
- **Tier 1:** `monitors.py` wraps bound entry points for obligations whose prefix is bound by one observed call. The self-contained runtime raises `ContractViolation` before returning. This is *detection*: effects are not rolled back, and the unwrapped module can be imported directly. Both facts are recorded in `bridges/tier1/placement.json` and the report.
- **Tier 2** (`vscore`, `restricted_source`) has a registered semantic-edge checker (below). The run pipeline does not dispatch to it yet, so `generate` still reports `UNSUPPORTED_CAPABILITY` and no `END_TO_END_VERIFIED` is assigned. **Tiers 3–4** are unsupported and return capability diagnostics.

### Shared bridge-certificate layer

`bridge prepare` consumes an accepted run and a proposal under the explicitly supplied candidate directory. The proposal lists nodes, artifact paths, relations and coverage; it cannot choose accepted obligation revisions, statement hashes, artifact digests, verifier assignments or lifecycle outcomes. The supervisor computes these values and imports the accepted contract through a fresh Lean acceptance and IR export in a private snapshot. Original artifacts and the newly rebuilt certificate, environment, compiled module and IR must agree exactly. Registered evidence is checked for the exact assigned issuer, current implementation hash, input root, claim and typed result. Persisted PASS metadata alone cannot authorize an import.

The importer copies only reproducible contract inputs, excluding unrelated package metadata, events and evidence history. Its stable receipt binds the source contract root, accepted IR and certificate hashes, current importer/acceptance/reifier hashes and checked artifact inventory. The receipt records a successful contract replay, with no implementation relation accepted.

Preparation constructs the plan and exact artifact manifest from those inputs and frozen candidate bytes, checks them, and writes a structural evidence record plus `preparation-certificate.json`. These outputs bind to the plan, manifest, accepted IR, acceptance certificate, import receipt and current preparation verifier. Evidence and the preparation certificate are excluded from their own input roots. Expected semantic proposition hashes remain candidate proposals and are explicitly marked as not semantically checked.

Each attempt publishes a new `bridges/<bridge-id>/` bundle through descriptor-relative writes and an atomic no-clobber rename. Existing attempts are never overwritten; changed inputs require a fresh ID. The bundle contains `plan.json`, `artifacts.json`, `proposal.json`, `import-receipt.json`, exact accepted inputs, `candidate-inputs/`, `evidence/` and `preparation-certificate.json`. All bundle references are relative to this directory. Reserved output paths cannot collide with imported inputs. Locks, publication paths and event files reject links and special files before writing.

`bridge verify --bridge-id ID` reconstructs the frozen bundle from its proposal, actual bytes and another fresh accepted-contract replay, then checks the receipt, evidence and certificate bindings. `run --bridge-proposal PATH --bridge-candidate-dir DIR` optionally prepares after export; `resume` checks preparations before skipping completed stages, and closure reports their checked structural status. Preparation failure prevents continuation through the optional stage.

`bridge check` remains a read-only envelope gate for future Tiers 2–4. It does not replay the source contract, call candidate code, create evidence, modify the package or assign a milestone. The five versioned schemas distinguish a proposal, prepared plan, concrete artifact manifest, structural preparation certificate and proposed semantic-edge certificate. Plan and manifest references hash exact file bytes; reformatting either file invalidates references to its previous digest.

`verislop/bridges/` checks unique identities and cross-references, accepted-obligation coverage, node/slot ownership, premise cycles and a contract-to-endpoint path for each required guarantee. Its bounded file reader rejects traversal, symlinks, hardlinked artifact files and special files, then checks sizes and hashes. Initial limits are 4 MiB per JSON file, 64 MiB per artifact, 256 MiB total, 512 entries per JSON collection, 32,768 JSON nodes and nesting depth 64. Observed mutations before completion are rejected; this read-only command does not make files immutable. Certificate checks bind the assigned verifier, required input root, current verifier implementation, relation and proposition identities, proof inventory and evidence reference.

The gate is explicitly `bridge structure and artifact integrity; no semantic acceptance`. A valid plan and manifest can pass this preparation gate without certificates. Candidate-supplied semantic-edge envelope certificates are never accepted, even for a relation whose template is registered; registered checkers publish their own outputs through `bridge accept`. Submitted metadata, theorem names and PASS records cannot create a semantic checker. Results of `bridge check` always expose `semantic_acceptance: false` and `assigns_end_to_end_verified: false`.

The shared claim evaluator also enforces issuer equality for existing lifecycle and closure claims. Expected roots come from the supervisor and frozen claims; raw verifier results cannot select their own root. Required internal claims are checked even when their user-obligation ID is null. The four supervisor-produced final closure claims are finalized separately.

### Tier 2: VSCore 0.1 restricted source

`vscore/0.1` is the first registered semantic bridge (docs/tier-2-4.md §2, Phase B). The verifier-owned Lean library `verislop/lean/VSCore/` has five modules plus the umbrella `VSCore.lean`. All of them are compiled from source in every build and replayed by the kernel tool:

| Module | Content |
|---|---|
| `Syntax` | types `nat | bool | unit | enum id | result error ok`; values; expressions (`var`, literals, `add/sub/mul/lt/le/eq/and/or`, `not`, `if`, `let`, `ok`, `error`, exhaustive `match_result`); entries and programs. De Bruijn variables; the last parameter is `var 0`. |
| `Decode` | `parseSource : List Nat → Except String Program`, the normative decoder of exact bytes. It accepts canonical JSON only: no whitespace, strictly sorted keys, printable-ASCII strings without escapes, integers ≤ 2^53−1, naturals as canonical decimal strings, and closed node schemas. It is fuel-bounded structural recursion, so the kernel evaluates it. `parseSource_of_check` turns a `decide +kernel` Boolean check into the equation. |
| `Typing` | `checkProgram` (language tag, nonempty unique entries, well-formed types against the accepted enumeration registry, exact body types), `checkProgram_of_check`, and the value typing relation `HasType`. |
| `Semantics` | Structural big-step `evalExpr` and `evalEntry` (arity and unknown-entry faults). It proves determinism, type soundness (`typeOf_sound`: well-typed expressions in typed environments evaluate without a fault to a value of their type) and `checkProgram_sound` for entries. |
| `Transport` | `Adapter p α τ` with `enc_typed`, `dec_enc`, `enc_dec` and `covers`; generic Nat/Bool/Unit/`Except` adapters; `enumAdapter`, whose laws are proved once from a constructor naming, an exhaustive list, injectivity and the registry entry; and `ArgsTypedIn`. |

The host side has three parts. `targets/vscore_source.py` mirrors the decoder and type checker; its output is only a proposal. `targets/vscore_target.py` derives the goal. `bridges/vscore_checker.py` is the registered checker `verislop.vscore-checker` for the relation template `vscore.reference_refinement/0.1`. During `bridge prepare`, the supervisor assigns this checker only when the frozen relation artifact names the template in its registered format. Every other relation stays with the unavailable verifier.

**Goal derivation.** The candidate supplies the source bytes, a relation that binds accepted symbols to program entries one-to-one, a proof module, and copies of the node model/profile descriptors. These copies must equal the descriptors derived from the library sources and the accepted profile registry. The supervisor generates `VeriSlopBridgeGoal` from the accepted IR, the accepted formula packages and the accepted profile:

- `sourceBytes` holds the exact bytes. `rawProgram` and `signatures` are host proposals; their only authority is the kernel-checked `source_parses` and `source_checks`.
- `profile` reuses the accepted enumeration registry. Adapters are derived per sort, and the enumeration names come from the accepted `lean_constructors ↔ constructors` mapping.
- For each bound symbol `f`, the implementation relation is `impl_f xs r := evalEntry rawProgram "e" [enc x…] = .ok (enc r)`. The target is `Refines_f := ∀ xs, impl_f xs (reference xs)`, together with `InputsCover_f`. Refinement is total: there is no domain restriction to weaken the contract. Generated equivalence helpers live in `VeriSlopBridgeGoal.Internal`, so accepted symbols such as `f` and `f_iff` cannot collide with helper declarations. Their proofs use adapter injectivity directly, including for Unit results.
- For each covered obligation `X`, `Transfer_X` is computed by the transfer rule. Each atomic formula containing calls is replaced by `∀ r, impl_f a… r → atom[r]` (innermost calls first). The goal uses `Internal.forall_impl_f` to eliminate complete call-result binders and prove equivalence to the explicit accepted DSL denotation. It then applies that equivalence to the accepted theorem through kernel conversion. This handles logical and Unit simplification as well as accepted theorem statements that still name registered predicate definitions.
- `EdgeProp` is the conjunction of the parse and typing equations, coverage, refinement and every transfer, with `edge_of_refines` as its proof. Obligations whose statement is not a contract-DSL formula, which mention no symbol, or which have calls inside range bounds are `UNSUPPORTED_CAPABILITY`. So are relations missing a used symbol (`UNMAPPED_IMPLEMENTATION_OBJECT`).
- `impl_*`, `Refines_*`, `InputsCover_*`, `Transfer_*` and `EdgeProp` are computed as kernel expressions and printed as fully explicit `@`-terms. After replay, their elaborated types and values must equal the computed expressions up to binder names (statement identity).

**Builds and checks.** Each of the two isolated builds runs these steps:

1. Compile the library in the sandbox with `lean --setup`, whose `importArts` bind every import to an exact artifact.
2. Stage the accepted contract module bytes from the acceptance certificate.
3. Compile the goal with read-only access to those artifacts.
4. Compile the candidate proof with read-only access to the library, contract and goal, then confirm that the dependency artifacts were unchanged.
5. Replay every non-toolchain constant of all modules together in the kernel tool, which gained a `replay_modules` mode on top of the toolchain-only imports of the set.

The audit then checks the following:

- every non-staged module resolves inside the pinned toolchain under the policy's import roots;
- the proof imports the goal;
- non-replayed declarations are only compiler `_unsafe_rec` auxiliaries;
- the proof declares no axioms or non-safe declarations, and only theorems in verifier-owned namespaces (Lean adds equation lemmas there on first use);
- `VeriSlopBridgeProof.edge` has exactly the type `VeriSlopBridgeGoal.EdgeProp`, and its transitively walked axioms are within the accepted policy (`sorryAx` gives `PROOF_UNRESOLVED`; native evaluation and unknown axioms give `INADMISSIBLE_AXIOM`);
- statement identity holds, and each `transfer_X` uses the accepted theorem;
- the proposition hash equals the hash frozen in the plan. This hash is the digest of the proposition and the declaration hashes of its semantic closure across the library, contract and goal.

`implementation-ir.json` is re-exported by bounded constructor reification of the replayed `sourceBytes`, `rawProgram`, `signatures` and `profile`. The only reduction is zeta, because long list literals elaborate to let-bound splits. The reified bytes must equal the frozen source, and the reified program must re-encode to exactly those bytes. Both builds must agree on the complete build observations, including all module parts, toolchain closure, replayed constants, export digest, proposition hash, axioms, compilation and isolation results, and IR; otherwise the result is `NONDETERMINISM`. Only the temporary build-directory prefix in isolation paths is normalized.

**Publication and rechecks.** `bridge accept --bridge-id ID` first re-verifies the preparation, including a fresh contract replay. It then checks each assigned edge and publishes `bridges/ID/semantic/edge-<hash>/` with a no-clobber rename. The folder holds the certificate (`vscore-edge-certificate`), the IR, the goal, every compiled part of the accepted goal and proof modules, `builds/A.json` and `builds/B.json`, and an evidence record. The evidence binds the semantic-edge root, the current checker hash and the complete deterministic certificate descriptor; only its time-dependent evidence reference is excluded to avoid a hash cycle. It satisfies the typed predicate `bridge-semantic-edge/0.1`, which only registered relation checkers can satisfy, and it must assert `semantic_acceptance: true` and `assigns_end_to_end_verified: false`. Acceptances are write-once. All rechecks independently derive obligation IDs, revisions, statement hashes, theorem and transfer names, symbol mappings, statement inventory, accepted references and toolchain identity. `bridge verify` additionally reruns the checker and requires the complete certificate descriptor and all published build artifacts to reproduce. `resume` and closure check certificate, evidence and byte bindings without rebuilding. The report then lists the accepted semantic certificates per bridge.

`vscore parse` (host proposal) and `vscore goal` are advisory helpers. `vscore goal` derives the goal, descriptors and proposition hash from an accepted run, optionally checks a proof in one build, and with `--bridge-id` writes a complete candidate directory. JSON numeric tokens are bounded by decimal length and lexical comparison before conversion to a host integer, so oversized tokens produce a stable source diagnostic. Frozen budgets: source ≤ 16 KiB and proof module ≤ 1 MiB; Lean time and memory limits come from the accepted policy. The next milestone is specified in [Tier 2 pipeline and endpoint closure](tier-2-closure-milestone.md).

## 6. Closure and report (§§9–10)

`verify` performs:
1. checks of the frozen inputs and of the certificate/IR import;
2. two isolated clean builds, each re-running Lean elaboration, kernel export, IR reconstruction, byte compilation and the frozen campaign. These are compared with each other and with the accepted and recorded values (`.olean`, environment export, IR bytes, `.pyc`, test outcomes). Declared nondeterministic fields are timestamps, durations and the staged candidate path;
3. the provenance check: every required claim must resolve to current, valid, registered evidence;
4. interpretation coverage, endpoint/require-state checks and the review gate;
5. closure evidence (`CLOSURE:clean-builds|determinism|provenance|endpoint`) and `report.json`.

Verifier crashes or unavailable toolchains give `INFRASTRUCTURE_FAILURE` (exit 3), with earlier evidence preserved. `run` orchestrates every stage, always writes a report, records cancellation as an incomplete run (exit 130), and `resume` re-verifies the frozen roots before continuing.

## 7. Providers and review

- **Configuration and auth.** `providers/config.py` checks role, agent, provider and endpoint profile consistency, capability support and quorum arithmetic. `auth.py` stores secrets in the OS keyring (`secret-tool`), in env or secret-manager references, or in an explicit 0600 file store (`secret-manager:verislop-file/<id>`).
- **Broker** (`providers/broker.py`): budgets per instance and total tokens; bounded retries honouring `retry-after`; refuses prompts containing the resolved secret; logs transcripts without secrets, recording requested and returned models.
- **Inference probe** (`providers/conformance.py`): `providers probe --config CONFIG --agent AGENT --live` explicitly opts into a potentially billable call. It preflights all selected models, credentials and endpoints, then makes one bounded JSON echo request per selected agent, without retries or saved response transcripts. It checks the challenge, model/usage metadata and requested output bound; differing returned model identifiers produce an alias warning, never assumed equivalence. Only selected agents need credentials or endpoints. Transport limits response bodies, validates response shapes and suppresses credential echoes and server-controlled error text. Local tests exercise all four protocols; no live-service conformance is claimed.
- **Review coordinator** (`review.py`):
  - Builds a checkpoint-scoped packet and a `review_target_root`. The root covers the candidate root, evidence package, claims, redacted config, agent profiles, resolved models, prompt template and adapter version. Credentials and ballots are excluded.
  - Runs each tier's slots in parallel. Ballots are validated (scope coverage for ACCEPT, no blocking findings on ACCEPT) and tallied deterministically, with mechanical-failure and blocking-finding vetoes.
  - Escalates tier by tier; bounded repair (implementation/release checkpoints) restarts at the first tier with a new root.
  - Writes a consensus certificate, which `review tally` and the release gate re-check from stored ballots.

## 8. Known limitations and deviations (v0.1)

- Tier 2 VSCore acceptance is a semantic-edge result only. `generate`, `link`, `test` and closure still dispatch to the Python target, so runs requesting Tier 2 stay blocked and `END_TO_END_VERIFIED [restricted_source; vscore/0.1]` is never assigned. VSCore has no recursion, loops, calls between entries, state, sequences or I/O. The certificate covers the source and its Lean semantics, not any interpreter or compiler that executes it.
- Only the bounded first-order fragment is reifiable. Universe-polymorphic statements remain outside the executable DSL; opaque accepted statements have no generated oracle or monitor. Non-toolchain imports (e.g. Mathlib) remain rejected.
- The toolchain's own compiled data is trusted as pinned, not replayed. Its imported closure hashes `.olean` and all loaded module/private/IR sidecars. Candidate modules are always replayed from their full private data.
- Bubblewrap confines reads and writes to the stage and explicitly mounted read-only runtimes/toolchain, with private PID/IPC/UTS namespaces, `/proc` and `/dev`, network isolation, rlimits and a scrubbed environment. It requires Linux, bubblewrap and usable namespaces, otherwise candidate execution fails closed. Cleanup never chmods candidate-created links; hostile directory permissions can instead cause a safe cleanup failure and leave a temporary stage for removal. Mounted runtime contents, bubblewrap and the kernel remain trusted; no seccomp filtering or aggregate cgroup limits are provided.
- Provider adapters and agent prompt templates remain untested against live services and models. The opt-in probe enables a narrow inference check with user credentials; automated tests use loopback mocks. Meta Muse and Qwen/DashScope still require user-supplied endpoint profiles.
- Author/reviewer separation and provider-diversity constraints are not configurable, because the configuration schema has no field for them. Review findings are recorded as `suspected`; they are not yet reproduced by a registered checker.
- Review supports the initial ballot round only. Reconciliation rounds (`round > 1`, `supersedes_ballot_ref`) are recorded fields but not yet driven. Per-provider data policies beyond "only the packet is sent" are not configurable, because the configuration schema has no field for them.
- The clean-build-failure branch of scenario 17 is exercised only through input-mutation paths in the automated tests.
- Lexical routing is a heuristic. It is advisory and can be overridden with `--mode software`.
