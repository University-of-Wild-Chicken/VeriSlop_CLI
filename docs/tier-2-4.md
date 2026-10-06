# VeriSlop Tiers 2–4: specification and implementation outline

Status: specification of proposed extensions, with partial implementation. This document specifies release gates. Implemented so far: the shared certificate infrastructure (Phase A) and the Tier 2 semantic-edge checker for `vscore/0.1`, i.e. Phase B except pipeline dispatch and end-to-end closure (see Phase B). Tiers 3 and 4 are not implemented, and no backend yet yields `END_TO_END_VERIFIED`. The existing [specification](specification.md), [obligation states](obligation-states.md), and [implementation notes](implementation.md) remain the baseline.

The recommended sequence is **Tier 2 restricted source → Tier 3 certified bytecode lowering → Tier 4 exact machine-code regions → whole native executables**. Tiers identify bridge strategies and endpoints. A larger tier number does not automatically establish more properties.

The next concrete milestone is [Tier 2 pipeline and restricted-source closure](tier-2-closure-milestone.md). That specification fixes backend dispatch, complete claims and roots, lifecycle applicability, two full semantic rebuilds, optional-test policy, review ordering, compatibility and finite release tests. It is specification-only: finish those gates before enabling Tier 2 E2E or beginning Tier 3.

## 1. Shared verification contract

### 1.1 Authority and semantic boundaries

The accepted Lean environment and its reconstructed `accepted-ir.json` remain the authority for obligations. Implementation generation MUST consume that IR, its acceptance certificate, and the frozen semantic profile. Candidate JSON, ASTs, theorem names, hashes, and reviewer votes are proposals.

Every backend MUST declare:

- Language, format, semantic-model and adapter versions, with exact dependency hashes.
- The requested endpoint, artifact bytes, entry points, input domain, representations, and observables.
- Supported obligation kinds and the precise properties each preservation theorem transports.
- Required correspondence edges, proof goals, witnesses, assumptions and registered verifiers.
- Trusted logic/checkers/environment and excluded execution surfaces.

An identity check establishes which artifact was examined. A semantic theorem establishes what that artifact means. Both are required; neither substitutes for the other. Disclosing an unproved required translation as trusted MUST NOT make it eligible for `END_TO_END_VERIFIED`.

The dependency graph must distinguish artifact identity, typing, semantic refinement, property transport and environmental premises. For each required obligation, closure must connect its **exact accepted proposition** to its **requested endpoint** through current evidence for every required edge. Matching names or merely finding a path through arbitrary theorem statements is insufficient: registered relation templates and mechanically checked composition rules determine valid paths.

### 1.2 Correctness and progress

For a deterministic, total function the initial proof target can be extensional equality:

```text
for every input x satisfying the accepted assumptions:
  decodeOutput(evalImplementation(program, encodeInput(x))) = reference(x)
```

The representation bridge must separately prove input coverage and round trips:

```text
∀ x, AcceptedPre(x) → ∃ tx, InputRepresents(tx, x)
∀ x, AcceptedPre(x) → InputRepresents(encodeInput(x), x)
∀ tx x, InputRepresents(tx, x) → decodeInput(tx) = some(x)
```

The selected encoder, not just some hypothetical representation, must satisfy these laws. Also cover every target input admitted by the frozen interface: it must correspond to an input in the claimed domain, or have the explicit invalid-input behavior required by the contract. Restricting the claim to canonical encodings is allowed only when that restriction is part of the accepted boundary; an agent cannot omit inconvenient target inputs during proof generation.

For nondeterministic/effectful profiles, replace function equality with an appropriate relation over all permitted target executions. Safety, termination, divergence, fairness, trace observations, errors, costs and noninterference need property-specific transport rules. An implication about executions that happen to return is not a termination proof. Fuel exhaustion is an incomplete check, not a successful execution or a source-level error unless the accepted contract explicitly defines it that way.

Representability is a release condition. A finite machine-word encoding cannot cover an unrestricted `Nat` domain. Adding a new bound in an implementation theorem silently weakens the accepted contract and MUST block. Accept a separately revised bounded contract or provide a faithful arbitrary-precision representation and its implementation proof.

### 1.3 Obligation states

Keep the existing eight symbols and their applicability rules:

- `INTERPRETED`: the recorded interpretation has passed its existing checks.
- `FORMALIZED`: the formal statement and semantic dependencies are frozen.
- `TYPECHECKED`: the applicable Lean declarations were accepted.
- `PROVED`: the exact formal obligation has an accepted proof under its declared hypotheses.
- `IMPLEMENTED`: the backend has materialized the exact well-formed implementation artifact.
- `LINKED`: its entry points and objects have unique, mechanically checked structural bindings.
- `TESTED`: the recorded campaign actually passed, when applicable; proof acceptance does not assign this state.
- `END_TO_END_VERIFIED`: the required endpoint correspondence, property transport and mechanical closure checks passed for this obligation and artifact revision.

Bridge typing, refinement, encoding and preservation are internal claims, not additional lifecycle symbols. Assumptions, declarations, exclusions and unresolved questions retain their existing applicability rules; a higher tier does not fabricate proof milestones for them.

Always qualify the final milestone, for example:

```text
END_TO_END_VERIFIED [restricted_source; vscore/0.1]
END_TO_END_VERIFIED [extracted_language; vsstack/0.1]
END_TO_END_VERIFIED [machine_code_region; rv64i-leaf/0.1]
END_TO_END_VERIFIED [native_binary; <pinned platform profile>]
```

Run closure still has the separate terminal states `VERIFIED`, `BLOCKED`, and `INFRASTRUCTURE_FAILURE`. Required tests remain an independent policy choice. Required adversarial review is a workflow gate: rejection can block release while a current mechanical proof remains valid.

## 2. Tier 2: restricted implementation semantics in Lean

### 2.1 Initial capability

Introduce a distinct implementation language, **`vscore/0.1`**, with target `vscore` and endpoint `restricted_source`.

The first profile supports `Nat`, `Bool`, `Unit`, the contract's finite enumerations, and `Result(Error, Value)`. Expressions include variables, literals, explicitly defined natural arithmetic/comparison, Boolean operations, `if`, `let`, constructors and exhaustive result matching. A program contains a finite set of typed entry points. Initially, entries cannot call one another.

Reject recursion, loops, mutable state, sequences, I/O, FFI, concurrency, reflection, dynamic loading, exceptions outside explicit `Result`, and unknown primitives. Add each feature only with syntax, static rules, semantics, preservation lemmas, proof support and negative tests.

Do not reuse the contract formula DSL as executable syntax: it contains quantifiers and predicates that need not be computable. Reuse its accepted type/enum registry through an explicit checked adapter.

The delivered source is canonical JSON with a closed schema, fixed field names and explicit type tags. Encode unbounded natural literals as canonical decimal strings, avoiding the existing canonical JSON integer range limit. Specify variable indices, entry IDs and enum identity/order. Reject duplicate keys, unknown fields, noncanonical representations, invalid indices and malformed encodings. Freeze resource budgets for parsing/proof checking; exceeding a budget cannot count as acceptance.

The first fixture is the existing bounded-increment function:

```text
increment(limit, input) =
  if input < limit then ok(input + 1) else error(limitReached)
```

This profile uses mathematical natural numbers, including truncated subtraction. It does not imply that an ordinary host interpreter has unlimited memory.

### 2.2 Formal library and exact source binding

Add a verifier-owned Lean library with the following interfaces. The declarations below are the design interface. The implemented library (`verislop/lean/VSCore/`) provides them as `VSCore.parseSource : List Nat → Except String Program`, `VSCore.checkProgram : Profile → Program → Except String (List EntrySig)` and `VSCore.evalEntry : Program → String → List Value → Except EvalError Value`. It proves type soundness (`checkProgram_sound`) and determinism, and its representation adapters carry their laws:

```text
parseSource  : Bytes → Except ParseError RawProgram
checkProgram : AcceptedProfile → RawProgram → Except TypeError CheckedProgram
evalEntry    : CheckedProgram → EntryId → TypedArguments → TypedResult
```

Define a typed expression AST and a structurally recursive evaluator. Establish static preservation, determinism and evaluation totality for the supported fragment. A step-count semantics is optional and must name its units; it does not establish wall-clock time, arithmetic bit complexity or physical memory bounds.

The Lean parser is the normative interpretation of source bytes. The supervisor independently reads the frozen artifact and constructs its byte literal. Acceptance requires a kernel-checked equation of the following shape:

```text
parseSource exactSourceBytes = Except.ok rawProgram
checkProgram acceptedProfile rawProgram = Except.ok checkedProgram
```

A host parser can propose `rawProgram` and accelerate diagnostics, but cannot discharge these equations. If a canonical-renderer design is used instead, its injectivity and round-trip properties must first be established. A Python parse/serialize comparison alone is insufficient.

After acceptance, reconstruct `implementation-ir.json` from the accepted `checkedProgram` declaration using bounded constructor reification. Bind this IR to the compiled proof artifact, source digest, profile and semantics version. Discard the candidate AST as an authority, just as the contract pipeline discards candidate obligation JSON as an authority.

### 2.3 Implementation and obligation proofs

For the first release, require equality with the accepted reference functions for every symbol needed by an obligation. The verifier constructs the expected theorem type from the accepted environment, exact checked program, argument/result adapters and frozen binding plan:

```text
∀ limit input,
  evalEntry checkedProgram incrementEntry (encodeArgs limit input)
    = encodeResult (AcceptedReference.increment limit input)
```

The agent supplies a proof of this frozen target. It cannot replace the evaluator, reference function, representation, predicate, scope or premises. Check the complete declaration dependency closure, exact theorem type, axiom policy, constructive witnesses and statement identity using the existing kernel-replay machinery.

Mechanically derive and check a transfer theorem for each exact accepted obligation. Its implementation interpretation must mention the accepted program/evaluator. Repeating a theorem about the reference model does not establish implementation correctness. If an obligation uses several implementation symbols, all necessary symbol relations must be present.

Opaque contract terms are not automatically executable. They may receive a formal implementation proof only if a supported transfer rule or an exact, independently checked direct theorem covers them. Otherwise the bridge reports `UNSUPPORTED_CAPABILITY`; it never generates a fabricated test oracle.

### 2.4 Release gate

Tier 2 can first support functional postconditions, explicit result/error semantics, pure value invariants and termination under the declared source semantics. General reactive liveness, state invariants, machine overflow and physical resources remain unsupported until separately modeled.

The bounded-increment source must pass exact parsing/typing, reference correspondence, obligation transfer, existing non-vacuity checks, and two isolated reproducible builds. Its state is scoped to the delivered VSCore source. Executing a Python VSCore interpreter or compiling Lean normally adds an execution boundary that this certificate does not close.

## 3. Tier 3: proof-producing lowering and verified extraction

### 3.1 Initial target

Build a concrete lowering from `vscore/0.1` to **`vsstack/0.1`**, with endpoint `extracted_language`.

VSStack is a small, versioned stack bytecode language. Start with typed argument/local access, constants, arithmetic/comparison, stack operations, conditional and unconditional forward branches, result construction/matching and return. Require a finite, acyclic control-flow graph, valid branch targets, compatible stack types at joins, initialized locals and exactly specified returns. Reject backward branches, external calls, allocation primitives and unknown opcodes in the initial profile.

Its value semantics initially reuse mathematical VSCore values. Its decoder and small-step semantics are defined in Lean. Prove progress, absence of stuck well-formed executions, and termination for accepted acyclic programs. A host VM can aid testing, but is outside the formal endpoint until its own implementation correspondence is checked.

### 3.2 Route A: per-artifact proof production

An untrusted lowerer emits bytecode plus a Lean proof candidate relating it to the accepted VSCore program. It may be handwritten, agent-generated, or an ordinary compiler. Acceptance independently binds the exact bytecode bytes to the decoded program and checks a theorem equivalent to:

```text
decodeBytecode exactBytecodeBytes = Except.ok targetProgram

∀ x, AcceptedPre(x) →
  all maximal executions from init(targetProgram, encodeInput(x))
  terminate without a VM fault, returning encodeResult(evalCore(sourceProgram, x))
```

For deterministic VSStack this can be implemented as termination plus unique-result theorems. A bounded runner may support the proof, but the theorem must establish a sufficient bound; “if execution finishes within fuel” is insufficient.

Compiler certificates can contain block invariants, stack-shape witnesses, variable maps and local simulation lemmas. Each proposed item must be checked against the exact instruction addresses and source/target programs. The final theorem is composed from accepted obligations through VSCore correspondence and this lowering theorem.

### 3.3 Route B: verified extraction

After Route A works, implement a pure Lean compiler and prove a general theorem:

```text
compile sourceProgram = Except.ok targetProgram
  → PreservesRequiredSemantics sourceProgram targetProgram
```

For every artifact, also kernel-check the concrete compilation equation and the exact emitted-byte decoder equation. Running a compiled compiler and trusting its output because the compiler's source has a theorem is not enough; the concrete equation or an independently sound certificate checker must bind that run's result.

Every optimization, proof erasure, representation change, helper routine and error translation adds a preservation obligation. Initially use tagged values so result constructors remain distinct. Introduce unboxed words, big-integer runtimes or memory layouts only with their own proofs. Cost or trace properties require theorems stating the appropriate relations rather than inheriting functional equality automatically.

The alternative `proof_bearing_source` endpoint may package VSCore source together with a complete accepted proof certificate. This is another delivery strategy, not stronger semantic assurance than Tier 2 proving the same source and properties.

### 3.4 Release gate and compilation boundary

The release must reject a changed opcode, branch target, constant, stack layout, error tag or adapter even if the original proof still checks for its original program. Exact target bytes, correspondence inventory and proof identities must reproduce in two isolated builds.

Ordinary Lean compilation is not this extraction path: Lean separates kernel checking from executable compilation, and its native compilation passes through generated C. The design therefore requires a specific semantic-preservation chain rather than treating `lean --run` or a successful native build as an extraction certificate. See the [Lean compilation reference](https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/).

## 4. Tier 4: exact machine semantics

### 4.1 First endpoint: a machine-code region

Introduce an explicit endpoint **`machine_code_region`** and a narrowly published profile **`rv64i-leaf/0.1`**. This is an extension to the endpoint vocabulary; it cannot satisfy the existing `native_binary` endpoint implicitly.

The initial artifact is a flat byte sequence for a leaf routine, with a fixed entry offset and declared code region. Specify 64-bit registers, endianness, instruction alignment, code placement, argument/result registers, result tags, allowed clobbers and an aligned return target. Start with the actual encodings of a few RV64I instructions, such as `ADDI`, `ADD`, `SUB`, unsigned comparisons/branches and `JALR` for return. Admit only the selected subset and forward control flow, with no calls, stack/heap data access, syscalls, interrupts, concurrency or self-modification in the execution profile.

Pin both the formal model and the exact ISA edition. RV64I defines 64-bit integer registers; its specification builds on the RV32I base definitions, so the profile must account for both relevant sets of rules. See the [ratified RV64I specification](https://docs.riscv.org/reference/isa/v20260120/unpriv/rv64.html).

If the first backend uses a handwritten Lean subset model, identify that exact model as the declared machine semantics and expose its fidelity to the ISA specification as an explicit trust assumption. A stronger correspondence claim needs its own proof against an authoritative formal model. Instruction tests or successfully typechecking generated ISA code do not establish that correspondence.

The theorem's environment premises must explicitly cover installed code bytes, executable instruction fetch, disjoint/aligned layout, return conditions and absence of interference. A loader that installs arbitrary bytes does not satisfy those premises by assertion. At this endpoint, installation is an explicit model precondition rather than a claim about an OS loader.

### 4.2 Proof obligations

The verifier reads the actual bytes, checks decoding and control-flow bounds, and builds a frozen theorem goal over those bytes and the pinned machine semantics. A successful certificate establishes:

1. Input representability and correct argument decoding for the entire accepted input domain.
2. The exact code bytes and entry/layout correspond to the machine transition relation being proved.
3. Every permitted execution is free of modeled faults and terminates at the declared return boundary.
4. The returned registers encode the required result, including errors.
5. The frame condition holds: memory and all non-clobber registers are preserved as specified.
6. Every required obligation is transported from the accepted contract, directly or through the VSCore/VSStack proofs.

A theorem interface could be:

```text
∀ x machineState,
  AcceptedPre(x) → EntryRelation(exactBytes, layout, x, machineState) →
  TotalRegionCorrect(machineSemantics, exactBytes, machineState,
                     outputRelation(reference(x)), frameCondition)
```

`TotalRegionCorrect` is a verifier-owned definition including termination and all allowed executions, not an agent-chosen predicate. For the deterministic leaf profile, a sufficient instruction-step bound and a result/frame theorem provide an implementable starting point. ISA-step bounds do not establish cycle counts or wall-clock deadlines.

Require bridge-specific non-vacuity and entry-state coverage. For example, prove `AcceptedPre(x) → EntryRelation(exactBytes, layout, x, init(x))` for a checked initial-state constructor, and show that the frozen admitted entry-state class is covered by the relation. The correctness theorem quantifies over all those related states, not only one convenient initialization. Existing contract witnesses alone cannot rule out an always-false machine entry relation.

Compiler and assembler executables may remain untrusted producers when independent proof validation covers the final bytes directly. This is a valid direct-binary route; it does not claim that the producer is correct for every possible input program.

The first machine fixture must use an explicitly accepted bounded input contract. The existing unrestricted-natural reference cannot simply acquire a `limit < 2^64` hypothesis in the bridge. A big-integer route would require verified arithmetic and runtime support instead.

### 4.3 Later endpoint: native binary

To enable `native_binary`, close the remaining boundaries for one pinned deployment profile:

- Parse and bind the entire executable container, program headers, executable/data sections and entry point.
- Validate relocation, symbol resolution, linking, address layout and the relation between file bytes and the loaded memory image.
- Cover all reachable code, startup/exit stubs, static libraries, runtime helpers, allocators and applicable garbage collection.
- Specify the ABI, system calls, FFI, external inputs, error behavior and environmental assumptions; discharge the required interface contracts.
- Establish that the deployed bytes are the checked bytes, including all post-link transformations. A certificate for pre-strip/pre-patch output cannot be reused blindly.
- Prove resource sufficiency when successful completion is required. A preservation theorem that allows out-of-memory failure does not alone prove successful termination.

Start with a static, single-threaded executable and one platform profile. Dynamic linking, signals, threads, memory-mapped I/O, constant-time behavior and real-time deadlines require further models and theorem families. A functional machine proof does not automatically establish any of those properties.

### 4.4 External compiler ecosystems

Existing verified compilers are possible later integrations, with explicit proof boundaries:

- CompCert's principal preservation theorem relates CompCert C ASTs to Asm ASTs before assembling/linking. An integration still needs exact source interpretation and final-byte correspondence; merely invoking the executable compiler does not close those edges. See the [official CompCert manual](https://compcert.org/man/manual001.html).
- CakeML has a verified machine-code backend. Its compiler theorem has installation/configuration/FFI premises and allows resource-limit behavior, so a particular deployment needs the corresponding premises and any required resource-sufficiency proof. See [CakeML](https://cakeml.org/) and its [backend correctness paper, §10](https://cakeml.org/jfp19.pdf).

Neither route can be connected to a Lean contract by matching names, copying theorem text or trusting an LLM translation. A checked cross-logic interpretation and theorem transport, or another mechanically justified shared semantic interface, is required. Additional proof kernels belong in the declared TCB. The direct Lean machine-region backend avoids this cross-logic integration in the first Tier 4 release.

## 5. Artifacts, certificates and closure

### 5.1 Proposed package additions

```text
bridges/<bridge-id>/
  request.json                 frozen tier, endpoint, profile and obligation coverage
  inputs.manifest.json         artifact, semantics, representation and dependency inputs
  claims.json                  required binding/refinement/transport claims
  challenge.lean               verifier-generated theorem targets
  candidate/                   untrusted program/proof/certificate proposals
  accepted/                    content-addressed accepted proof modules and environment
  implementation-ir.json       reconstructed from accepted program declarations
  certificate.json             verifier-produced index of accepted facts and evidence
  builds/A.json, B.json         isolated build observations
```

Candidate search may precede freezing the final proof-input manifest. Freeze the requested scope, endpoint and expected theorem targets before proof acceptance; then freeze the complete candidate bytes, proof inputs and dependency closure before running the registered acceptance checks. Later changes create a new candidate/root and stale the affected evidence.

Certificates and final reports are outputs, not members of their own input manifests. Distinguish the input root, accepted proof artifact root and mechanical evidence snapshot. A review packet binds the completed mechanical snapshot. The release report references both that snapshot and the separate consensus certificate, preventing a circular hash through its own review outcome.

### 5.2 Certificate fields

Define new versioned schemas for a bridge request/plan, artifact manifest, semantic profile, typed semantic-edge record, endpoint certificate and release certificate. Do not reuse the name `endpoint-profiles`: the existing schema describes provider API endpoints. Each accepted edge records:

- Stable edge/claim ID and exactly affected obligation IDs/revisions.
- Source/target artifact references and hashes; language/model/profile identities.
- Relation template and property classes transported, plus the concrete checked theorem target.
- Proof-module digest, Lean declaration name, expected proposition digest and complete dependency closure.
- Input/output representation and entry-point binding references.
- Every premise and its discharge or authorized environmental-assumption evidence.
- Registered checker ID/hash, required input-root kind and current root, typed result/pass predicate, and immutable evidence reference.

The following is a schematic **verifier-produced descriptor**, not an existing schema or evidence of success. Placeholders denote supervisor-computed digests:

```json
{
  "format": "verislop.bridge-certificate/0.1",
  "tier": 3,
  "endpoint": "extracted_language",
  "profile": "vsstack/0.1",
  "input_root": "sha256:<frozen-inputs>",
  "accepted_contract": "sha256:<acceptance-certificate>",
  "accepted_ir": "sha256:<accepted-ir>",
  "implementation_artifact": "sha256:<exact-bytecode>",
  "edges": [{
    "claim_id": "BRIDGE:lowering:increment",
    "relation_template": "vsstack.total_refinement/0.1",
    "source": "sha256:<accepted-vscore-program>",
    "target": "sha256:<decoded-vsstack-program>",
    "theorem": {
      "module": "sha256:<accepted-proof-module>",
      "symbol": "VeriSlopBridge.increment_lowering",
      "expected_type": "sha256:<verifier-generated-goal>"
    },
    "premises": ["BRIDGE:input-representation", "BRIDGE:output-representation"],
    "evidence_ref": "evidence:<registered-verifier-record>"
  }],
  "coverage": {
    "O17": {
      "required_claims_ref": "sha256:<frozen-complete-claim-list>",
      "transport_theorem": "VeriSlopBridge.O17_target"
    }
  }
}
```

Coverage is recomputed against the frozen claim inventory. Omitting a required edge from this descriptor cannot make it optional. The descriptor itself assigns no lifecycle state; the evidence view independently validates its referenced records.

### 5.3 Required closure checks

Before an E2E milestone can pass, check all of the following:

1. Existing interpretation, formalization, proof, witness and binding prerequisites remain current and applicable.
2. Every required internal bridge claim passes its assigned registered verifier, including claims without a user obligation ID.
3. All semantic edges use the frozen relation templates, exact artifacts and exact accepted premises; their composition transports this obligation to the requested endpoint. Certificate/premise discharge dependencies must be acyclic: conditional theorems cannot establish each other's assumptions circularly. Program recursion, when supported, requires an accepted induction/fixpoint argument.
4. No required boundary is absent, merely tested, manually approved, assumed correct as a translation, or supported by stale evidence.
5. Two isolated builds reproduce the declared artifact bytes, decoded/program IR, proof inventory, correspondence and provenance metadata, and claim outcomes. Any permitted nondeterministic fields are declared before the run.
6. Provenance is complete, and there are no undefined-behavior dependencies or unaccounted dependencies outside the declared scope.

Only then publish mechanical E2E evidence. Apply the separate configured review/release gate afterward. A changed artifact or assumption invalidates the relevant proofs and votes; an unchanged proof does not become false merely because a reviewer rejects release.

Invalid proofs, missing edges, domain loss, wrong representations, stale evidence and unsupported semantics are blocking failures. Unavailable tooling, a crashed checker, or failed isolation is an infrastructure failure. A proof-search budget expiring without a certificate leaves the required claim unresolved and blocked. No failure permits a silent lower-tier result for the requested endpoint.

A compiled certificate checker returning `true` is not sufficient merely because its logical source has a soundness theorem. Acceptance also needs a kernel-checked instance of that checker result, a replayable proof term, or a separately justified execution path for the checker. The same rule applies to generated parsers, compilers and ISA evaluators; retain the pinned toolchain's native-evaluation/axiom audit.

## 6. Implementation plan against this repository

### Phase A: shared infrastructure before any E2E capability

The shared certificate workflow (#1) is implemented: strict proposal/plan/manifest/certificate schemas, `bridge prepare`, read-only `bridge check`, `bridge verify`, exact-byte artifact validation, actual accepted-contract replay, assigned-verifier evidence checks and run/resume/report integration. Preparation reconstructs the accepted IR and freezes a new bridge bundle before producing structural evidence and a preparation certificate. It establishes the accepted-contract import and structural preparation only. The semantic-checker registry is supervisor-owned and closed to package input. Its first entry is the Tier 2 VSCore checker (Phase B). Backend dispatch and endpoint closure below are still pending.

Introduce a backend registry and separate candidate production from registered checking. Its interface should cover capability discovery, source inventory, preparation of frozen bridge goals, materialization, structural linkage, proof acceptance, accepted-program export, optional tests, clean builds and endpoint assessment. A candidate cannot register its own verifier or relation template at runtime.

Refactor these current Python assumptions:

- `generate.py`, `materialize.py`, `link.py`, `testing.py`, `closure.py`: dispatch to registered backend operations instead of fixing Python files, profiles, verifier IDs and byte compilation.
- `schemas/implementation-bindings.schema.json`: replace Python-only constants and object shapes with a versioned, backend-discriminated format. Preserve old package semantics through an explicit reader/migration policy; do not reinterpret old evidence as the new format.
- `leanbridge.py`, the kernel tool and import policy: admit only frozen verifier-owned semantic libraries and explicitly bound accepted contract modules, with replay and hashed dependency closure. This does not require opening arbitrary Mathlib/candidate import paths.
- `verifiers.py`, `package.py`, `closure.py`: hash bridge artifacts, semantics, codecs, proofs, build recipe, dependency locks, relation/checker implementations and schemas into the appropriate roots.
- `closure.py`: replace the unconditional E2E block only behind a complete registered backend gate. Finalize E2E evidence after mechanical prerequisites to avoid circular provenance.
- `report.py`, `view.py`, `capabilities.py`, CLI and endpoint schemas: remove T0/T1-only rendering assumptions, display per-obligation endpoints and transport evidence, and add `machine_code_region` without aliasing `native_binary`.

The current accepted IR includes acceptance-certificate/environment identity. Proof-only changes therefore affect existing bindings even when the proposition is unchanged. Require a fresh closure initially; any later reuse needs a separate checked equivalence/import certificate.

Completed safeguards already enforce assigned evidence issuers, supervisor-selected input roots and typed result predicates. Required internal claims with no user-obligation ID are evaluated, with the four final closure claims handled separately. These checks remain prerequisites for future semantic backends.

### Phase B: Tier 2 MVP

Add `lean/VSCore/{Syntax,Decode,Typing,Semantics,Transport}.lean`, `targets/vscore_target.py`, a VSCore source schema, and registered binding/typing/refinement/transport verifiers.

Implement the exact-byte parser binding and typed-program exporter first. Then implement bounded increment, its representation proofs and obligation transfer. Enable only the published pure profile after its adversarial tests and two-build fixture pass. Next add a second error-producing example; sequences, parsers over byte arrays, state and bounded loops are separate extensions with new semantics versions.

Implementation status:

- **Done.** The library and the host modules `targets/vscore_source.py` and `targets/vscore_target.py` exist. The registered checker `verislop.vscore-checker` (`bridges/vscore_checker.py`) serves relation template `vscore.reference_refinement/0.1`. It checks one combined edge per bridge: binding, typing, refinement and transport are conjuncts of a single verifier-derived proposition.
- **Done.** Schemas exist for the source, relation, model/profile descriptors, implementation IR and edge certificate. The kernel tool replays several modules together.
- **Done.** The CLI provides `bridge accept`, the re-executing `bridge verify`, and the advisory `vscore parse` and `vscore goal`.
- **Done.** The bounded-increment fixture (`examples/vscore/`) passes two isolated builds. The rejection suite of §7 for Tier 2 is in `tests/test_vscore.py`.
- **Pending.** `generate`, `link`, `test` and closure do not dispatch to the VSCore backend, so `END_TO_END_VERIFIED [restricted_source; vscore/0.1]` is not assigned. `verislop capabilities` publishes Tier 2 as `partial`.
- **Pending.** A second error-producing example.

The remaining Phase B work is specified in [the Tier 2 closure milestone](tier-2-closure-milestone.md). Its endpoint is exact VSCore source under the normative Lean semantics. It permits mechanical E2E with optional `TESTED` still pending, adds no interpreter or test campaign, and keeps review release approval separate from mechanical proof. The milestone also requires an independent checked-subtraction fixture and preserves Tier 0/1 compatibility; capability enablement is the final step after its finite release suite.

### Phase C: Tier 3 MVP

Add `lean/VSStack/{Decode,Typing,Step,Simulation}.lean`, `targets/vsstack_target.py` and a lowerer that emits programs plus proof candidates. First accept per-program certificates for unoptimized lowering. Then add small proof-producing optimizations. A general verified compiler theorem and its concrete compilation-equation checker are a later improvement using the same endpoint/certificate architecture.

### Phase D: Tier 4 machine-region MVP

Add a pinned RV64I subset decoder and step model, representation/ABI relations, symbolic execution lemmas and an exact-byte proof checker under `lean/Machine/` and `targets/rv64i_target.py`. Begin with an explicitly bounded increment contract and direct machine-region proofs. Add a certificate-based compiler route only after its required per-pass or final-byte validation exists.

### Phase E: native executable integration

Choose one container, ISA, ABI and OS/environment profile. Add loaded-image correspondence, linker/relocation validation, runtime and system interface coverage, whole-entry-point closure and deployment-byte identity. Publish `native_binary` support only after a complete executable fixture and its corruption tests pass all these edges.

### Agent and adversarial-review workflow

The existing provider broker, user token references, agent selection/counts and review consensus configuration remain applicable. Assign optional roles for implementation synthesis, correspondence proof search, lowering proof search and machine proof search. All run within bounded candidate/proof workspaces; only registered verifiers publish acceptance evidence.

Review tiers remain user-configured and independent of bridge tiers. Useful checkpoints are frozen implementation goals, accepted source bridge, accepted lowering and final machine/release artifacts. Review agents should attack assumptions, domain coverage, decoder mismatches, hidden helpers, errors, termination and claim overreach. Lower-tier acceptance escalates according to the configured consensus; higher-tier rejection and candidate repair restart review on the new artifact root. Consensus cannot replace a missing mechanical edge.

## 7. Minimum acceptance and rejection suite

Positive release fixtures must exercise ordinary success, explicit error results, boundary inputs, multiple required obligations, re-export of the accepted implementation IR, and two clean builds. Retain the current Tier 0/1 regression suite.

All profiles must reject source/byte mutation with an unchanged supplied AST or hash; a theorem about another program with the same name; forged success metadata; a missing internal claim; circular premise discharge; evidence from the wrong registered verifier; an incorrect actual encoder despite an alternative valid encoding; stale semantics/adapter/proof roots; and source evidence offered for a native endpoint.

Tier 2 must additionally reject malformed/noncanonical source, false parse/typing certificates, wrong enum/argument/result mappings, unsupported constructs, unauthorized axioms and native-evaluation shortcuts, strengthened assumptions, omitted multi-symbol correspondence and a copied model theorem offered as implementation transfer.

Tier 3 must additionally reject changed opcodes/branch targets, stack underflow or type disagreement, an incorrect optimization, a missing helper proof, wrong error tags, unproved proof erasure, and a runner that proves only conditional return within arbitrary fuel.

Tier 4 must additionally reject signed/unsigned mismatches, overflow that disagrees with natural arithmetic, domain-narrowing bounds, false or incomplete entry relations, misaligned/escaping control flow, wrong byte order, callee-save violations, self-modifying code, unsupported instructions, unmodeled traps, stale post-link bytes and unaccounted runtime/FFI paths. A machine-region proof must not satisfy `native_binary`.

Keep liveness, constant-time behavior, physical-resource bounds and environment assumptions independently visible in reports. Enable each advertised tier/profile/property/endpoint combination only when its exact positive and negative release gates have passed.
