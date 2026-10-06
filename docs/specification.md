# VeriSlop CLI specification

Version: 0.1 design candidate · 2026-10-05

Product name: **VeriSlop CLI**, expanded as **Verify the Slop CLI**. Proposed executable: `verislop`.

This document specifies a system to build. MUST and MUST NOT describe requirements for that future system. Examples are designs, not evidence of a completed VeriSlop run. The accompanying Lean fixture checks a small formal model only.

## 1. Product contract

Given a software-development prompt, VeriSlop MUST first produce an explicit, structured obligation draft. It then constructs and proves a formal contract in Lean 4. Only after acceptance does it reconstruct an authoritative obligation IR from the checked formal artifact. Implementation agents consume that IR and generate or adapt code using a selected bridge tier.

The core rule is:

> The original LLM JSON is a proposal. The checked formal artifact determines the accepted semantics. Bound verifier evidence determines what has been established about those semantics and about each implementation.

Three separate questions MUST remain visible:

1. Does the chosen formalization represent the intended request? This is an interpretation boundary, with provenance and recorded decisions; Lean does not prove natural-language intent.
2. Does the formal theorem hold? This requires an admissible proof of the exact frozen statement.
3. Does the delivered implementation satisfy it? This requires tier-specific evidence and, for a formal implementation claim, semantic correspondence.

Every obligation MUST expose `INTERPRETED`, `FORMALIZED`, `TYPECHECKED`, `PROVED`, `IMPLEMENTED`, `LINKED`, `TESTED`, and `END_TO_END_VERIFIED`. Their normative meanings are in [obligation-states.md](obligation-states.md).

Users MUST be able to supply their own API credentials and configure provider/model assignments and agent counts at every adversarial review tier. Review proceeds from lower tiers to higher tiers only after the configured acceptance consensus; all configured tiers must accept the same candidate revision. This independent review hierarchy is specified in [providers-and-review.md](providers-and-review.md). It cannot substitute for proof acceptance or bridge verification.

## 2. Scope and non-goals

The system supports new software, changes to existing software, and verification of existing artifacts. It may create a pure reference model before the target implementation. The reference model is part of the specification boundary and is not automatically the delivered application.

The initial product SHOULD support deterministic, terminating, sequential functions over natural numbers with explicit range constraints, Booleans, finite enumerations, and result/error types. Lists, richer algebraic data, and native numeric profiles are subsequent registered extensions. It SHOULD begin with one target language and one fixed serialization profile. Tier 0 is the default when the caller does not specify a tier; the output MUST identify it as test evidence. Requested tiers MUST NOT be silently downgraded.

The following are not implicit promises: completeness of prompt classification; recovery of all unstated requirements; automatic resolution of contradictory intent; proof discovery for every theorem; decidability of arbitrary Lean propositions; arbitrary-language verification; unbounded liveness from finite tests; physical timing or memory guarantees from abstract costs; machine-code correctness from source proofs; hardware correctness; or correctness of future revisions.

Tier 4 is a separate integration capability, not a checkbox enabled by successful Lean compilation. A release MUST publish its supported tier/language/property combinations.

## 3. Prompt routing and interpretation

### 3.1 Classifier behavior

The ingress API accepts text, immutable attachments, repository revision, target language/runtime, requested tier, and a verification policy. The classifier returns `SOFTWARE`, `NON_SOFTWARE`, or `UNCERTAIN`, with a short reason and spans supporting the decision. Confidence may assist routing but MUST NOT count as proof evidence.

`verislop run --mode software` bypasses classification. `--mode auto` routes prompts requesting implementation, debugging, refactoring, APIs, tests, build changes, or behavior-changing configuration through the obligation pipeline. Mixed prompts isolate software parts and record their boundaries. A confident non-software classification produces a `NOT_APPLICABLE` routing result, not an empty verification success. An uncertain result creates an interpretation ambiguity; it MUST NOT silently bypass verification.

The first generated deliverable for software work MUST be a draft with all ten arrays:

```json
{
  "entities": [],
  "preconditions": [],
  "postconditions": [],
  "invariants": [],
  "safety_properties": [],
  "liveness_properties": [],
  "resource_constraints": [],
  "error_semantics": [],
  "explicit_non_goals": [],
  "ambiguities": []
}
```

Empty arrays mean no proposed entries in that category; they MUST NOT mean that a category was proved irrelevant. A `category_review` ledger records reviewed omissions and their rationale. Drafts MUST be emitted before target implementation generation, including in unattended operation.

### 3.2 Obligation records

Each record has a stable unique ID, revision, kind, role, statement, source references, interpretation decision, required flag, scope, dependency edges, acceptance criteria, and the complete lifecycle map. Stable IDs survive wording changes; a semantic change increments the revision and changes its content hash. IDs MUST NOT be reassigned to unrelated requirements.

Roles distinguish `guarantee`, `assumption`, `declaration`, `exclusion`, and `open_question`. Entities are normally declarations; preconditions are normally assumptions; non-goals are exclusions; ambiguities are open questions. Representing every entry uniformly does not make every entry a proposition to be proved.

Source references include prompt/document hash and byte interval. Inferred requirements MUST be marked inferred and justified, never attributed to a nonexistent user span. Each meaningful source clause has a disposition: obligation IDs, explicit exclusion, unresolved ambiguity, or explanatory context. A mechanical coverage check can ensure that recorded spans are accounted for; it cannot prove semantic completeness of the interpretation.

An assumption MUST identify who supplies it and where it is discharged. For example, a callee's precondition becomes a caller obligation or an input-validation obligation. It MUST NOT be reported as an established environmental fact merely because a theorem uses it as a hypothesis.

### 3.3 Ambiguities and changes

Ambiguities include alternatives, affected obligations, impact, resolution, and resolution provenance. Block any dependent guarantee when alternatives change correctness, data-loss behavior, security, required failure behavior, target numeric semantics, or a requested formal boundary. Independent obligations may continue.

A policy may select routine defaults. Selected defaults MUST be explicit and visible in the interpretation ledger; an agent MUST NOT resolve ambiguity by quietly weakening a guarantee. Required input in noninteractive mode produces `BLOCKED` with `INTERPRETATION_UNRESOLVED` and machine-readable alternatives.

Before proof search, freeze the interpreted claim set and formal challenge. An agent may repair a proof or propose a new interpretation, but it MUST NOT change the theorem, precondition, non-goals, target boundary, or allowed axioms inside an active verification run. A changed statement starts a new candidate and preserves the old run.

## 4. System architecture

```text
prompt + repository snapshot + policy
                 |
        classifier / interpreter
                 |
        draft.json + interpretation ledger
                 |
     formalizer + formal statement checker
                 |
     frozen Lean contract / challenge
                 |
     bounded proof agents in sandbox
                 |
     isolated replay + axiom/statement audit
                 |
     accepted Lean environment + certificate
                 |
     deterministic reifier + export validator
                 |
     accepted-ir.json + bound state/evidence view
                 |
     selected bridge -> target implementation
                 |
     linker + tier verifier + closure verifier
                 |
     immutable artifact package + report.json
```

The interpreter, formalizer, prover, implementer, and repair agents are untrusted candidate generators. The supervisor alone controls immutable snapshots and launches registered verifiers. No agent may write its own PASS evidence into the authoritative evidence store.

A component API MUST identify its input roots, output artifacts, tool version, supported schema versions, diagnostics, and outcome. Standard components are `classify`, `interpret`, `formalize`, `prove`, `accept`, `reify`, `validate-export`, `generate`, `link`, `test`, `verify-bridge`, and `close`.

The proof workspace, target implementation workspace, and verifier/evidence workspace MUST be distinct. A proof agent cannot modify a trusted challenge, verifier, dependency lock, runtime policy, or accepted evidence. Candidate-generated tactics, elaborators, macros, plugins, build scripts, and native libraries are executable untrusted inputs and run without verifier credentials or access to the evidence store.

A provider broker owns API credentials and dispatches scoped tasks to interpreters, provers, implementers, and reviewers. A separate review coordinator owns tier membership, immutable review targets, ballots, finding disposition, consensus calculation, and escalation. Provider calls and reviewer text never write formal PASS evidence.

Parallel work is permitted across independent obligations. The scheduler respects dependency edges and uses bounded attempts, wall time, memory, and model-token budgets. Budget exhaustion preserves unresolved obligations as blocked; it does not manufacture a weaker contract or count as a disproof.

## 5. Formal contract design

### 5.1 What it means to prove a contract

Defining `Post : Input → Output → Prop` only specifies a property. A theorem of the form `∀ f, Satisfies f → Satisfies f` contributes no implementation correctness. The default strict acceptance profile requires a concrete reference model and proofs that it satisfies every required model guarantee:

```text
reference : Input → Result Error Output
reference_satisfies : ∀ x, Pre x → Post x (reference x)
pre_inhabited : ∃ x, Pre x
```

For stateful systems, use a state machine with explicit initialization, allowed transitions, observable traces, and exceptional outcomes. Prove initialization and preservation separately. For relational specifications, require a realizability witness, such as a concrete function `f` and a proof of `Satisfies f`. Existential claims MUST carry concrete checked witnesses rather than merely an axiom of existence.

Abstract interfaces MAY be typechecked without such a witness in a separately named exploratory mode. They remain `TYPECHECKED`; the default prove-before-generation gate MUST NOT label them accepted-and-proved.

Non-vacuity checks include concrete inputs for required preconditions, a reachable initial state, and witnesses for required success/error branches. These rule out specific empty-domain mistakes; they do not prove that a specification captures all intended behavior. When a branch is intentionally unreachable, a proof of unreachability and the recorded interpretation replace its witness. A satisfiable premise is not evidence that it holds for every deployment input.

### 5.2 Semantic profiles

A contract MUST fix the meanings of numbers, overflow, division, strings/Unicode, indexing, equality, maps/iteration order, aliasing, mutation, exceptions, I/O, concurrency, nondeterminism, and serialization wherever relevant.

For example, Lean `Nat` does not silently stand for a target `UInt64` or JavaScript `number`. A bridge must constrain ranges, supply checked encoders/decoders, and establish the chosen overflow behavior. Error semantics MUST define malformed inputs, invalid preconditions, normal domain errors, exceptions/panics, cancellation, timeout, and state after failure. Out-of-contract inputs must be explicitly excluded or covered by additional obligations.

Safety properties are predicates over states or trace prefixes. Liveness properties quantify over traces or executions and MUST state fairness, environment progress, scheduling, cancellation, and termination assumptions. Resource constraints MUST state a cost unit and model, input-size measure, bounds, and whether costs are exact, asymptotic, measured, or assumed. A proof about abstract steps is not a proof about elapsed milliseconds.

### 5.3 Lean representation

Use two supported representations:

1. **Reifiable contract language.** A versioned typed DSL embedded as closed Lean data, with Lean semantics `denote : ContractExpr → Prop` for closed expressions. Its [v0.1 core](contract-ir.md) covers typed binders, natural numbers, Booleans, unit, finite enumerations, explicit results, arithmetic/equality/order, connectives, general and bounded quantifiers, and references to pinned total specification functions. Products, general sums, sequences, state, traces, and cost models require registered extensions. Each obligation contains the typed DSL value and an attached theorem of its denotation.
2. **Opaque Lean expression.** Arbitrary supported Lean propositions can remain accepted formal terms, serialized losslessly with their dependency closure. The IR marks them `lean_expr`; test or monitor generation is unsupported unless a registered adapter proves an equivalent executable representation. The system MUST NOT paraphrase an opaque proposition into weaker JSON to make bridging possible.

Typed metadata binds ID, revision, kind, source references, scope, and proposition to the formal artifact. Definitions/types and metadata are typechecked; only proposition inhabitants are proof candidates. An attribute or record tag is an index, not evidence. A metadata field named `proved`, `state`, or `status` MUST have no authority to assign lifecycle outcomes.

The exporter reads elaborated `Expr` values and declarations in the checked `Environment`, not the parser's source `Syntax`, tactic transcript, pretty-printed theorem alone, or original draft JSON. Lean's elaboration and kernel-checking stages are distinct from source syntax. [Lean elaboration reference](https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/)

## 6. Lean acceptance boundary

Successful process exit from a candidate `lake build` is insufficient for strict acceptance of generated proofs. The acceptance service MUST:

1. Pin the Lean toolchain, dependency commits/lockfiles, formal library, statement checker, exporter, axiom policy, and verifier implementations.
2. Build candidates in isolation with resource limits; stage exact inputs and disallow mutable dependency downloads during verification.
3. Replay the exported declarations/proof terms with a trusted kernel process outside the candidate's control, using a pinned comparator or equivalent checker pipeline supported by the selected toolchain.
4. Match theorem types AND referenced definitions, typeclass instances, and semantics against the frozen challenge. A theorem with the same spelling but changed definitions is a different claim.
5. Audit transitive axiom dependencies and local hypotheses. Reject `sorryAx`, unresolved metavariables, unauthorized axioms, and native-evaluation proof axioms outside policy. Reject mismatched, incomplete, or uninspectable dependency closures.
6. Check required witnesses, obligation coverage, interpretation decisions, trust declarations, and exact claim IDs/revisions.
7. Produce an immutable acceptance certificate binding claims, proof inventory, environment export hash, source root, checker hashes, policy, toolchain, and the observed results.

The baseline logical axiom allowlist is `propext`, `Classical.choice`, and `Quot.sound`, with actual usage reported per theorem; stricter projects may choose a smaller list. Domain assumptions SHOULD be explicit hypotheses, not fresh axioms. Unknown axioms are blocked even if their names look harmless. Native evaluation has version-specific trust behavior, so source-text searches for `sorry` or a single historical axiom name are insufficient. [Lean axioms reference](https://lean-lang.org/doc/reference/latest/Axioms/)

Lean's current validation guidance describes sandboxed proof construction, exported proof replay, comparison with a trusted challenge, and independent checkers. VeriSlop SHOULD use that architecture; availability and invocation MUST be checked for the pinned toolchain. If an independent checker is required by policy, its absence blocks that profile rather than silently falling back. The checker/exporter/sandbox plumbing remains explicitly trusted unless separately verified. [Lean proof-validation guidance](https://lean-lang.org/doc/reference/latest/ValidatingProofs/)

The agentic proving loop may propose lemmas, use proof-producing tactics, search counterexamples, and repair proof terms. Required obligations missing proofs leave the contract gate blocked. Counterexamples are diagnostics until checked by an appropriate verifier. LLM judgments never discharge an obligation.

## 7. Reconstructing the authoritative obligation IR

### 7.1 Trust rule

The accepted IR contains two visibly distinct sources:

- **Formal content:** IDs, kinds, scopes, statements, binders, hypotheses, referenced definitions, formulas, and dependencies reconstructed from accepted declarations/typed metadata.
- **Evidence view:** lifecycle states, acceptance records, bridge results, test outcomes, and closure status joined from registered evidence, all bound to the same contract and relevant artifact roots.

The formal artifact cannot itself establish that external tests ran or that a target binary was built. Consequently the final JSON is artifact-derived, but its operational milestones are evidence-derived. Neither part uses the draft as semantic authority.

The original prompt and draft are retained only for provenance, interpretation review, and change analysis. Implementation agents receive accepted IR, formal artifact references, and the evidence view. Draft prose may be provided separately as non-authoritative context; it cannot override the IR.

Persist these as separate artifacts: `accepted-ir.json` is the immutable semantic payload; `obligation-view.json` is a derived join with the current lifecycle/evidence overlay. A downstream response may embed both under distinct keys. Updating TESTED or END_TO_END_VERIFIED changes the view, never the semantic IR already hashed into a closure input root. Internal obligations such as `non_vacuity` may be added by registered formalization rules and carry derived provenance; they do not silently introduce an eleventh user-draft category.

### 7.2 Export algorithm

1. Open only the acceptance certificate's checked environment export and verified declaration set. Do not load arbitrary candidate plugins in the trusted exporter.
2. Enumerate the accepted typed obligation registry; reject duplicate IDs, missing required entries, changed revisions, multiple unresolved semantic bindings, or unknown kinds.
3. Resolve every referenced symbol and verify its declaration and statement identity against the certificate and frozen challenge.
4. Extract binder order, universes, types, hypotheses, conclusion, and proof-constant dependencies. Preserve implicit/typeclass arguments and the meaning of referenced definitions.
5. For reifiable DSL terms, reconstruct syntax by safe structural reduction of closed data. Check `decode(encode(expr))` preserves the DSL term and that the exported denotation is definitionally equal or provably equivalent to the accepted theorem target.
6. For arbitrary Lean terms, serialize a versioned core expression graph and its referenced declaration closure. Retain its opaque status and explicit adapter limitations.
7. Compute dependency and axiom closures mechanically. Classify edges by `assumes`, `uses_definition`, `uses_proof`, `requires_witness`, `refines`, and `requires_bridge`; do not merge hypotheses and proved lemmas into one undifferentiated list.
8. Canonicalize, hash, independently validate, and write the IR. Join states only through checked evidence references.

Pretty-printed statements are optional display fields. Hashes are computed from the canonical core/DSL representation with schema version, toolchain/semantics profile, and referenced-definition hashes. Universe parameters and binder structure are preserved. Alpha-renaming may be normalized using de Bruijn indices. Unrestricted reduction or semantic equivalence checking is not promised: export is bounded and an unsupported term fails closed. Hash equality establishes identity of the chosen representation, not general mathematical equivalence.

The schema's human-readable `statement` is accepted provenance/display metadata. Code, test, monitor, and proof generators MUST use the formal expression identified by `formula_ref`, not reinterpret that prose as a replacement contract. Source wording can be preserved in accepted metadata without becoming the semantic authority.

JSON canonicalization SHOULD use RFC 8785 with sorted set-like arrays defined by the schema. Large integers and rationals MUST use decimal strings or tagged exact structures; they MUST NOT round through binary floating-point. Duplicate keys, non-finite numbers, invalid Unicode, and unknown mandatory tags are rejected. [JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785)

### 7.3 Shape of a downstream record

This is abbreviated **illustrative interface notation**, not an output from a run:

```json
{
  "O17": {
    "id": "O17",
    "revision": 1,
    "kind": "postcondition",
    "role": "guarantee",
    "state": "PROVED",
    "lean_symbol": "Contract.parse_preserves_identity",
    "dependencies": [
      { "id": "A3", "relation": "assumes" },
      { "id": "I2", "relation": "uses_proof" }
    ],
    "formal": {
      "representation": "contract_dsl",
      "formula_ref": "artifact:accepted-expressions/O17",
      "statement_hash": "sha256:<computed>",
      "hypotheses": ["A3"],
      "axioms": []
    },
    "lifecycle": {
      "INTERPRETED": { "outcome": "PASS", "evidence_refs": ["interpretation:O17"] },
      "FORMALIZED": { "outcome": "PASS", "evidence_refs": ["formalization:O17"] },
      "TYPECHECKED": { "outcome": "PASS", "evidence_refs": ["acceptance:O17:type"] },
      "PROVED": { "outcome": "PASS", "evidence_refs": ["acceptance:O17:proof"] },
      "IMPLEMENTED": { "outcome": "PENDING", "evidence_refs": [] },
      "LINKED": { "outcome": "PENDING", "evidence_refs": [] },
      "TESTED": { "outcome": "PENDING", "evidence_refs": [] },
      "END_TO_END_VERIFIED": { "outcome": "PENDING", "evidence_refs": [] }
    }
  }
}
```

Real envelopes also include contract/source/environment roots, schema version, profile, acceptance certificate, exporter identity, complete lifecycle reasons/scopes, all referenced records, and bridge boundaries. `state` is a derived display projection, not a replacement for the lifecycle map. `A3` remains an assumption unless separately discharged; `PROVED` refers to the exact conditional theorem.

## 8. Implementation bridges

### 8.1 Shared bridge interface

Every adapter publishes capabilities by language version, semantic profile, obligation kind, expression fragment, and tier. Given accepted IR and immutable implementation inputs it returns exact code/object hashes, an entry-point inventory, structural bindings, semantic correspondence evidence where applicable, generated checks, unsupported obligations, and a trust delta.

Bindings associate each implementation object with one unambiguous binding record. A binding record may intentionally cover several obligation IDs, and one obligation may constrain several objects; many-to-many coverage is permitted when explicitly represented. Missing or competing unresolved bindings block the corresponding claims.

An implementation proof needs a relation such as:

```text
decodeInput(targetInput) = some modelInput
targetBehavior ∈ semantics(targetArtifact, targetInput)
  ⇒ corresponding model behavior and required observable property
```

For nondeterministic implementations, universal safety needs all allowed implementation behaviors covered. Liveness needs a progress/divergence-sensitive relation and its environment assumptions; ordinary trace inclusion may not preserve eventuality. Error behavior, serialization, termination, resources, and concurrency MUST each have preservation evidence appropriate to their claim.

The user selects a requested tier and required endpoint. The system reports achieved evidence per obligation. No application-wide maximum tier may hide lower-tier required obligations. A mixed-tier report lists each boundary and identifies the weakest required bridge for each public claim.

### 8.2 Tier 0 — generated property tests

Generate test inputs, shrinkers, executable oracles, and adversarial/error cases from the accepted contract's executable fragment. A decidable or otherwise justified executable oracle is required. An oracle's equivalence to the Lean predicate SHOULD be proved or checked by a registered adapter; otherwise its translation is explicitly trusted, limiting the claim to that oracle's behavior.

Tests run the exact target artifact, not only a Lean reference function. Record seeds, generator version, cases, accepted/rejected inputs, branch and obligation coverage, minimized counterexamples, runtime, and oracle hash. Empty effective test sets, all-discarded inputs, disabled assertions, skipped required tests, or unverifiable harness invocation MUST NOT yield `TESTED: PASS`.

Outcome: `TESTED` for the recorded campaign. `PROVED` may independently hold for the reference contract. Ordinary finite property tests cannot establish `END_TO_END_VERIFIED` for an unbounded implementation claim. A formally justified exhaustive finite-state checker is a separate proof/certificate capability, not a silent relabeling of random tests.

### 8.3 Tier 1 — runtime assertions and contracts

Generate wrappers or instrumentation for preconditions, postconditions, state invariants, explicit errors, and decidable bounded resource checks. Freeze the instrumentation configuration and prove or declare trust in monitor-predicate correspondence. Verify instrumentation placement, build flags, entry-point coverage, snapshots of pre-state, and whether checks can be disabled or bypassed.

The contract MUST state whether violations reject input, abort, throw, roll back, or emit an event. A postcondition checked after an irreversible effect only detects a violation; prevention requires checks before commit or a separately justified transactional wrapper. Asynchronous state and concurrent writes require an observation/atomicity model.

Outcome: an artifact with identified runtime enforcement or detection plus any executed tests. Tier 1 does not prove all executions correct. General liveness cannot be established by waiting for a finite period; a deadline monitor enforces or observes the specified deadline/error rule only.

Tier 1 MUST NOT by itself assign `END_TO_END_VERIFIED`. Its structural bindings may assign `LINKED`; monitor installation alone does not assign `TESTED`.

### 8.4 Tier 2 — restricted implementation language in Lean

Accept a precisely versioned language fragment with a grammar, static checker, explicit operational/denotational semantics, errors, numeric model, and cost model where needed. Parse the exact delivered source into the formal program or use a checked translation with per-artifact validation. Prove the program satisfies each obligation under those semantics.

The bridge MUST establish correspondence between the actual source/AST and the Lean program. Proving a separately written model with similar names does not satisfy this requirement. Reject unsupported recursion, FFI, concurrency, undefined behavior, or other constructs unless their semantics and translation are explicitly covered.

Outcome: `END_TO_END_VERIFIED` may be assigned only for the declared restricted-source semantics endpoint after the correspondence and correctness proof chain closes. Output MUST say `END_TO_END_VERIFIED [restricted-source semantics]` and identify unverified compiler/runtime components. If the requested endpoint is a native executable, a source proof alone is insufficient.

### 8.5 Tier 3 — proof-producing implementation or verified extraction

Two paths are allowed:

- A proof-producing compiler/generator emits a concrete implementation and a proof that its formal semantics satisfies the accepted contract.
- A verified extraction/translation route starts with a proved program and establishes semantics preservation to the exact extracted artifact.

Either path requires an artifact-specific binding, proof acceptance, semantic preservation, and coverage of adapters, encoders, decoders, errors, libraries, and entry points. The generator itself may be untrusted when a small trusted checker validates its complete certificates.

Outcome: `END_TO_END_VERIFIED` for the exact proof-bearing source or extracted-language endpoint covered by the chain. Compiling a proved Lean definition through ordinary compilation does not by itself prove the resulting executable's machine behavior. Record compiler/runtime/FFI trust and the endpoint. Extraction that lacks a preservation proof is a trusted translation, not the strict verified-extraction path.

### 8.6 Tier 4 — machine-code semantics and compiler-chain verification

Start with the actual delivered byte sequence and an explicit ISA, ABI, memory, environment, and concurrency model. Establish the contract by either direct machine-code proof or a complete chain of proved/validated transformations through compiler, assembler, linker, loader-relevant configuration, and required runtime/library code.

Bind exact compiler versions/flags, source/IR/object/binary hashes, link inputs, address/relocation assumptions, and deployment model. Every relevant unverified edge blocks a strict machine-endpoint claim. A verified compiler alone does not automatically verify the assembler, linker, operating system, libraries, dynamic loader, or FFI.

Outcome: `END_TO_END_VERIFIED [declared machine semantics]` for the covered bytes and assumptions. Hardware conformance to the model remains an explicit trust assumption unless separately established. Functional refinement does not automatically preserve constant-time behavior, timing, memory peaks, or every liveness property; those require separate theorems.

### 8.7 Tier policy

Tiers describe bridge strategies, not a total order of every property. Tier 3 need not run Tier 1 instrumentation, and a machine-level functional proof need not establish a source-level asymptotic cost bound. `TESTED` is independent from proof and is required only when the selected release policy requires tests.

The default CLI MUST show the tier, obligation state, proof boundary, and remaining trust together. A Tier 0 closure may establish that the frozen test campaign passed; it MUST NOT present that as implementation proof.

## 9. Lifecycle and release decision

All lifecycle entries use `PASS`, `PENDING`, `FAIL`, `STALE`, `UNSUPPORTED`, or `NOT_APPLICABLE`. All except `PENDING` require an explanation; PASS requires bound evidence and scope. Only appropriate verifiers or provenance recorders can establish each milestone. `NOT_APPLICABLE` cannot substitute for a required claim.

Run status is separate and has exactly three terminal values: `VERIFIED`, `BLOCKED`, `INFRASTRUCTURE_FAILURE`. Working stages such as proving/running are progress events, not terminal statuses.

Review workflow decisions such as `TIER_ACCEPTED` and `REVIEW_ACCEPTED` are separate from these verification results and from the eight obligation symbols. Configured review acceptance is an additional release gate. Consensus can authorize escalation or completion of review, but cannot make a false theorem true or promote TESTED to END_TO_END_VERIFIED.

`VERIFIED` means every required frozen check passed under the declared trust boundary. At Tier 0 this can mean contract proofs plus the required test campaign, with implementation assurance still `TESTED`. The UI MUST qualify the result, for example `VERIFIED closure; implementation assurance: TESTED (Tier 0)`. It MUST NOT display an unqualified application-correctness badge.

`BLOCKED` covers unresolved or failed required claims, proof-budget exhaustion, unsupported required semantics, missing mappings, inadmissible axioms, stale inputs, failed builds, failing tests, unexplained nondeterminism, and incomplete provenance. A registered verifier crash, unavailable checker, filesystem failure, or unusable execution service is `INFRASTRUCTURE_FAILURE` when it prevents the run from completing independently of claim truth. Preserve any observed claim failures in either report; do not hide them behind an infrastructure incident.

## 10. Frozen closure package and trust

### 10.1 Two roots

The **contract input root** covers the frozen interpretation/claim inventory, formal sources and challenge, dependencies/toolchain identities, semantic definitions, schema, acceptance policy, and acceptance/export verifier hashes. Certificates and generated accepted IR are outputs of that root, not inputs to their own hashes.

The **implementation closure input root** covers the accepted contract certificate/environment/IR, target implementation, bridge mappings, tests/monitors/proof artifacts, build configuration, fixtures, schemas, dependencies, and registered closure verifiers. Reports/evidence are outputs and excluded from their own input manifest. The manifest defines sorted paths and bytes; hash fields never contain their own final value.

Here, IR means the immutable semantic payload, not the live obligation-state view. When adversarial review is required, freeze the mechanical checkpoint evidence as inputs to a review campaign, then freeze its ballots/consensus certificate as inputs to a final release decision. The final decision checks those sub-certificates and roots; it does not create a cycle in which reviewers vote on a report containing their own not-yet-created votes.

A proof certificate from the contract phase is an explicit input to the implementation phase. A registered import verifier checks its original root and bindings and emits new evidence for the current closure root. Copying an old PASS record and changing its root is forbidden. Mutable external URLs alone are not dependency identities.

### 10.2 Closure sequence

Before a run: enumerate finite public claims; decompose them into registered checks; fix pass/block predicates and severity; freeze inputs; register verifiers and hashes; classify every semantic/execution dependency as verified or trusted. Then validate correspondence and witnesses, run required verifiers, store immutable evidence, perform at least two isolated clean builds, compare declared reproducible outputs, bind provenance, check semantic boundary coverage, and emit the terminal report.

Fresh builds use isolated directories and frozen dependencies. Compare accepted proof inventory, IR, correspondence, provenance, claim outcomes, and all artifacts declared reproducible. Timestamps, execution duration, and other permitted nondeterministic fields must be identified before the run and excluded only where appropriate. Do not strip meaningful implementation bytes merely to make hashes match.

An input, claim, policy, toolchain, schema, or verifier change creates a new run/root. Previous evidence remains historical. A dependent milestone becomes `STALE` until rechecked. Immutable unchanged sub-certificates may be imported only through a verifier that validates their complete bindings; a new root never inherits a bare VERIFIED flag.

### 10.3 Evidence and provenance

Each PASS evidence record includes schema version, closure ID, claim ID, input root, verifier ID/hash, environment/toolchain, command or structured invocation, raw result/artifact hashes, exit code, and scope. Public claims must resolve through:

```text
public claim → claim ID → evidence → registered verifier
             → frozen inputs → declared assumptions and trust
```

The TCB normally includes logic assumptions, Lean/checker implementations, replay/export/IR validation, canonicalization/hash implementation, orchestration and sandboxing, OS/hardware, and any unverified bridge/compiler/runtime parts relevant to the claim. Declare a component trusted rather than pretending the system proves itself. NL interpretation remains a separately identified semantic assumption.

An LLM MAY propose verifiers, but generated verifiers are not trusted automatically. They need a prior registered policy, reviewed/validated semantics or a proved checker, and frozen hashes. Repeated agreement among agents is not verification evidence.

### 10.4 Report

`report.json` is authoritative; terminal summaries and rendered views derive from it. It includes terminal state, roots, claim and lifecycle counts, required/achieved tier by obligation, endpoint, mappings, witnesses, both builds, determinism, provenance, axioms/hypotheses, verified/trusted/excluded surfaces, blocking reasons, infrastructure errors, and artifact locations.

Errors have stable codes and affected claim IDs. Required baseline codes include `INTERPRETATION_UNRESOLVED`, `INPUT_MUTATION`, `CLAIM_MUTATION`, `STATEMENT_MISMATCH`, `INADMISSIBLE_AXIOM`, `PROOF_UNRESOLVED`, `MISSING_WITNESS`, `WITNESS_INVALID`, `IR_REIFICATION_MISMATCH`, `UNSUPPORTED_SEMANTICS`, `UNDECLARED_DEPENDENCY`, `VERIFIER_FAILURE`, `VERIFIER_NOT_RUN`, `STALE_OR_UNBOUND_EVIDENCE`, `UNMAPPED_IMPLEMENTATION_OBJECT`, `AMBIGUOUS_CORRESPONDENCE`, `NON_MECHANICAL_CORRESPONDENCE`, `TEST_FAILURE`, `EMPTY_TEST_CAMPAIGN`, `CLEAN_BUILD_FAILURE`, `NONDETERMINISM`, `ORPHAN_CLAIM`, `UNDEFINED_BEHAVIOR_DEPENDENCY`, and `SCOPE_LEAK`.

There is no force-pass, manual conversion from BLOCK to PASS, or confidence threshold that discharges a formal obligation. Changing the scope or trust policy creates a new visibly different candidate.

## 11. Proposed CLI

These commands are a proposed interface; no executable is supplied in this design repository.

```bash
verislop run --prompt-file request.txt --mode auto --tier 0 --target python
verislop interpret --prompt-file request.txt --out draft.json
verislop formalize --draft draft.json --out contract/
verislop prove --contract contract/ --policy strict --budget-seconds 600
verislop accept --contract contract/ --policy strict
verislop export --accepted contract/acceptance.json --out accepted-ir.json
verislop generate --ir accepted-ir.json --tier 2 --target restricted-v1
verislop link --ir accepted-ir.json --implementation generated/
verislop test --package run-package/
verislop verify --package run-package/ --endpoint restricted-source
verislop inspect obligation O17 --package run-package/ --json
verislop explain-block --package run-package/ --json
verislop diff --from previous-package/ --to run-package/
verislop resume --run-id run-123
verislop auth add --provider anthropic --credential-id claude-review
verislop providers check --config verislop.json
verislop review --package run-package/ --config verislop.json
```

Commands reject raw draft JSON where an accepted artifact is required. `generate` verifies acceptance, IR reconstruction bindings, and policy before handing work to an agent. Existing code is ingested as a candidate implementation, not silently treated as linked.

`--json` writes machine-readable results to stdout and progress to stderr. An optional `--events` stream uses schema-versioned JSON Lines with run ID, sequence number, phase, obligation ID, milestone, outcome, and evidence reference; candidate proposals and verifier decisions use distinct event types. Resume checks the complete frozen root. Concurrent writers cannot update the same run.

Proposed exit codes: `0` command completed and its requested gate passed; `2` blocked; `3` infrastructure failure; `64` invalid invocation. Non-verification commands returning `0` do not assert closure VERIFIED. Cancellation is recorded as an interrupted/incomplete run with unresolved required checks and no verification success; signal handling may preserve the platform signal exit code, documented by the runner.

`--require-state END_TO_END_VERIFIED --endpoint native-binary` requires the endpoint and complete correspondence chain, not just selection of Tier 4. `--tier 4` on an unsupported backend returns a capability diagnostic. Changing tier or endpoint after freeze starts a new candidate.

## 12. Proposed package layout

```text
.verislop/runs/<run-id>/
  request/                  prompt, source snapshots, routing decision
  draft.json                proposal; never downstream authority
  interpretation.json       spans, assumptions, ambiguity decisions
  claims.json               frozen finite verifier claims
  contract/                 Lean sources, DSL, challenge, lockfiles
  accepted/                 environment export, certificate, accepted IR
  implementation/           exact candidate source / build inputs
  bridges/                  bindings and preservation certificates
  tests/                    generators, oracles, seeds, fixtures
  closure/                  policy, manifest, TCB, verifier registry
  evidence/                 immutable results, logs, build attestations
  report.json               authoritative decision
```

Store candidate edits outside frozen run directories. Use atomic writes and content-addressed artifacts to avoid races between verification and generation. Hash the bytes actually executed or checked. Cross-platform path, symlink, case, and newline rules must be fixed in the manifest format; reject ambiguous or escaping paths.

## 13. Acceptance scenarios for the implementation

The future system is not conformant until these have executable checks:

1. A software prompt emits all ten draft categories before generating target code; forced software mode bypasses a false-negative classifier.
2. An ambiguity affecting error behavior blocks dependent guarantees while independent proof work continues.
3. A theorem about a weakened statement or changed definition is rejected even if candidate compilation succeeds.
4. `sorry`, hidden imported unauthorized axioms, and an unauthorized native-evaluation axiom fail acceptance.
5. A false precondition cannot give a useful-success contract an accepted non-vacuity witness.
6. Mutating or deleting the original draft after acceptance cannot change a re-exported accepted formula. Mutating the accepted artifact invalidates its certificate.
7. Re-export from identical accepted inputs is byte-identical under the canonicalization profile; DSL round-tripping preserves denotation.
8. An opaque proposition remains opaque and cannot acquire a fabricated executable oracle.
9. A string `"state": "PROVED"` in candidate metadata cannot elevate a lifecycle milestone.
10. A changed target function invalidates implementation, linkage, test, and end-to-end evidence while an unchanged model proof remains valid for its own contract root.
11. Zero effective property tests, skipped checks, or tests run only on the reference function fail a required target test campaign.
12. A Tier 1 post-effect assertion is reported as detection unless preventive/rollback semantics are established.
13. An embedded Lean program without correspondence to the delivered source cannot earn end-to-end verification.
14. A source-level proof cannot satisfy a requested native-binary endpoint.
15. Overflow, serialization, cancellation, and error-state mismatches are caught by profile/correspondence checks.
16. An unbounded liveness claim cannot be discharged by finite monitoring, and a step-count bound cannot satisfy an undeclared wall-time claim.
17. Stale evidence, a required clean-build failure, unexplained nondeterminism, or orphan public claims block closure.
18. A crashed checker reports infrastructure failure and preserves earlier valid evidence without a success badge.
19. Declarations, non-goals, assumptions, and unresolved ambiguities never get fabricated theorem-proof milestones.
20. An E2E report includes the exact endpoint, artifact root, assumptions, trust, and claim coverage; ordinary Tier 0/1 campaigns are ineligible.

These scenarios are the implementation acceptance plan, not a claim that the current repository runs them.

## 14. Delivery plan

**Milestone A — contract-first foundation.** Implement routing, structured obligations, all eight lifecycle milestones, immutable roots, a small contract DSL, sandboxed proof construction and isolated acceptance, deterministic reification, axiom/statement checks, and the bounded-function Lean fixtures. Complete artifact-to-IR anti-tampering and vacuity scenarios before implementation generation.

The foundation also includes the provider broker and configurable adversarial review coordinator: user-owned secret references, per-role model assignments, parallel reviewer counts, ordered consensus escalation, bounded repairs, and distinct review/mechanical decisions. Ship adapter capabilities explicitly; a provider name in configuration alone is not an implemented integration.

**Milestone B — useful Tier 0/1 workflow.** Add one target language, exact data adapters, executable predicates, generated property campaigns, runtime wrappers, evidence/reporting, two-build closure, and resumable bounded agent orchestration. Label tested/enforced behavior precisely.

**Milestone C — narrow Tier 2.** Specify a small language semantics, checked front end, translation/correspondence certificates, and per-program correctness proofs. Demonstrate source-endpoint E2E on the bounded-increment fixture plus an error-producing parser or stateful transition example.

**Milestone D — Tier 3 backend.** Integrate a concrete proof-producing or verified extraction path with explicit target-language preservation and artifact binding. Require negative tests for changed extracted output and adapters.

**Milestone E — Tier 4 integration.** Choose one existing verified compiler/ISA ecosystem or a narrowly scoped direct binary verifier. Close all remaining toolchain edges for a specified target and deployment model. Do not advertise this tier until actual certificates exist for delivered bytes.

Initial engineering choices still to fix before implementation: target language, implementation of the specified DSL v0.1 core, proof export/checker compatibility for the pinned Lean release, contract library, runtime isolation mechanism, concrete provider-adapter transport details, and supported endpoint profiles. These are product decisions, not missing evidence to be papered over by the specification.
