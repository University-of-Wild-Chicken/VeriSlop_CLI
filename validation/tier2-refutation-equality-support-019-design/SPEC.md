# Equality support 019: frozen design before implementation

Status: DESIGN_FROZEN_NOT_IMPLEMENTED. This document prescribes a generic repair and future actual-Lean qualification. No production source was changed, no Lean compilation or test was executed, no model was called, and no native task, candidate, proof, benchmark, or old answer content was read in this design pass. Qualification results do not yet exist.

## Scope and observed mechanism

The repair concerns only `verislop/contract_refutation.py::_derivations` and its call in `_proof`. The structured frontend already renders each finite enum with `deriving _root_.DecidableEq`; records do not receive a frontend equality derivation. `_derivations(profile)` currently emits an unconditional `deriving instance DecidableEq for Carrier` for every admitted enum, followed by records in bottom-up dependency order.

Lean 4.34.1's primary local implementation, `Lean/Elab/Deriving/DecEq.lean`, explains the duplicate-helper failure without using a retained task artifact. `mkDecEqInstance` dispatches enum carriers to `mkDecEqEnum`; that calls `mkEnumOfNat` and `mkEnumOfNatThm`, which add constants named exactly `Carrier.ofNat` and `Carrier.ofNat_ctorIdx`. These names remain in the carrier namespace even if the second deriving command sits in a fresh refutation namespace. Re-deriving a previously derived enum therefore attempts to add the same helper declarations. An elaboration failure correctly remains UNKNOWN today; it prevents an otherwise available concrete kernel proof.

The existing separate kernel tool replays the complete root-module declaration inventory, exports declarations from the replayed kernel environment, and retains full private module-system declarations. `contract.Env` contains the resulting declaration ASTs and hashes. It does not expose a typeclass-instance registry. Its inventory includes equality definitions even when those definitions are not reachable from statement roots and therefore lack `decidable_eq` profile metadata. Source spelling, guessed `instDecidableEq...` names, instance attributes, profile metadata, and host execution results are therefore unsuitable authorities for deciding whether a second derivation is needed.

Here, a dependent record carrier means an admitted record whose field sorts depend on other admitted record/enum carriers through records, lists, options, or results. Genuinely dependent Lean field types and indexed/recursive inductives remain outside the existing admitted profile and are not added by this repair.

## Required behavior

1. Already derived structured enums support concrete equality proofs without generating their enum helpers again.
2. Raw Lean enums with no equality declaration still receive a proof-producing derivation when Lean supports it.
3. Records with a usable preexisting equality definition reuse it. Records lacking equality still derive it bottom-up, including records containing enums or nested record/list/option/result carriers.
4. Equality discovery consults only the exact fresh, independently replayed base `Env` supplied to `_proof`; candidate metadata and host truth do not grant proof authority.
5. All original declarations retain their exact exported hashes in the proof module. The final theorem remains the exact requested expression, closed, safe, monomorphic, replayed, policy-clean, and free of sorry dependencies.
6. A generated derivation or alias that does not elaborate, an unsupported carrier, an unusable existing equality definition, or a failed kernel check cannot create a receipt. Existing UNKNOWN/error behavior remains in force.
7. Reference probes still certify only the exact candidate output. Their critic expectations remain untrusted annotations. Correct universal guarantees still receive no PROVED/TESTED/release authority from finite sampling.

## Proposed minimal production change

Change `_derivations(profile)` to `_derivations(profile, expected_env)` and pass the existing replayed `expected_env` from `_proof`. Preserve the current carrier dependency walk: enums first, then every record after its nested record dependencies. Preserve quoting through `_qualified`.

For each carrier `C`, inspect `expected_env.decls` for declarations whose actual exported type AST is exactly:

```
app(const("DecidableEq", [1]), const(C))
```

These are the existing profile's monomorphic `Type` carriers; the universe choice is the same nominal equality shape the current enum audit accepts. Sort candidate declaration names for deterministic output. A matching name is reusable only if the existing equality declaration audit accepts it against `expected_env.decls` and `expected_env.hashes`.

The current `reify._enum_equality_declaration(name, carrier, decls, hashes)` is structurally carrier-generic: it checks the exact nominal `DecidableEq` type, a safe monomorphic computable definition with a body, and its semantic closure/hash identity; it does not inspect enum constructors. It can audit an equality definition for an admitted record without changing the accepted profile or the global proof policy. Reuse this existing audit from the refutation helper; avoid a duplicated, weaker validation path. A later helper rename is unnecessary for this fix.

For the first usable equality definition `D`, emit one deterministically named local alias in the fresh proof namespace:

```lean
local instance _vr_eq_0 : _root_.DecidableEq _root_.«Carrier» := _root_.«ExistingEqualityDefinition»
```

The names above illustrate shape; actual carrier and definition names use complete `_qualified` output, and the index follows the ordered carrier list. The alias makes the typed definition available to Lean inference even when the original declaration had a nonstandard name, was an ordinary definition rather than an attributed instance, or had its instance attribute removed in the candidate. It adds a safe definition; it does not mutate the existing declaration or rely on the candidate's typeclass attribute registry. Do not use `noncomputable`, `classical`, `native_decide`, an axiom, `sorry`, or an unsafe helper.

If no usable exact-type equality definition exists, emit the existing proof-producing command for that carrier:

```lean
deriving instance _root_.DecidableEq for _root_.«Carrier»
```

Do not skip all enums. Do not infer absence from a missing profile binding. Do not suppress duplicate-declaration errors, delete helpers, overwrite original declarations, or alter the frontend rendering to work around refutation.

Reject a generated local alias name already present in `expected_env.decls`, using the same fail-closed approach as the existing `closed_check` root collision guard. Derivation may still fail for a raw Lean carrier whose helper names are independently occupied; such a case remains UNKNOWN with diagnostics rather than permitting replacement of existing constants.

This proposal requires no additional imports, Lean command metaprogram, second compile, kernel-tool changes, policy changes, semantic-denoter changes, or new timeout/deadline. The local primary APIs `Lean.Meta.synthInstance?`, `trySynthInstance`, and `Lean.Elab.Command.liftTermElabM` exist, but a generated metaprogram would broaden source composition and import concerns unnecessarily. Exact replayed declaration reuse plus a typed local alias solves the present admitted-carrier problem with the existing tools.

## Proof and trust boundary

The equality selection is preparation for proof elaboration, not evidence that a guarantee is true or false. Its output must feed the unchanged theorem:

```lean
theorem closed_check : <exact _expr_lean(expr)> := by decide +kernel
```

The existing export request must still request an actual replay and exact theorem-type definitional equality against the original expression. The proof receipt must still require: no `Env` diagnostics; unchanged hashes for every expected base declaration; the existing `_clean_root` predicate; exactly one defeq row with ID `closed_check`; exact result `{ok: true, typechecks: true, defeq: true}`; zero refutation-root sorry dependencies; and the existing source/module/export/toolchain hashes. Candidate theorem holes can remain in the candidate, but a refutation root may not depend on them. Nothing in this repair loosens module imports, axioms, review requirements, semantic identity, or milestone authority.

The reuse audit must reject unsafe, partial, opaque, polymorphic, stale-hash, unresolved, sorry-dependent, Classical-choice-dependent, and wrong-nominal-type definitions. Rejection of a proposed equality definition is not automatically a failure of the case: the ordinary safe deriving fallback may still construct legitimate equality from the carrier. If fallback fails, the result remains UNKNOWN. A negative test must distinguish rejection of a bad helper from refusal of an independently valid safe theorem.

## Fresh actual-Lean fixture plan

Implement these fixtures only after this design seal and the separate production source freeze have been accepted. Use a new generic test module, for example `tests/test_contract_refutation_equality_support_019.py`. Fixtures are freshly authored; do not load any native tasks, benchmark answers, old proposals, or earlier task proof artifacts. Compile fixture bases through `leanbridge.compile_module`, derive their analysis through the actual kernel export and `contract.analyze`, run `cr.check`, and inspect receipt files only from those new temporary fixtures. Use the pinned toolchain and strict policy; do not mock Lean to establish positive behavior.

Use the namespace `RefutationEquality019` and fresh unrelated carriers:

```lean
inductive Token where | amber | violet
structure ZLeaf where
  token : Token
  amount : Nat
structure AParcel where
  leaf : ZLeaf
  spare : Option Token
  history : List ZLeaf
  outcome : Except Token ZLeaf

def swap (t : Token) : Token :=
  match t with | .amber => .violet | .violet => .amber

def carry (p : AParcel) : AParcel :=
  { p with leaf := { p.leaf with token := swap p.leaf.token } }

theorem wrongToken (t : Token) : swap t = t := by sorry
theorem rightToken (t : Token) : swap (swap t) = t := by
  cases t <;> rfl
theorem wrongParcel (p : AParcel) : carry p = p := by sorry
```

Add a correctly proved `rightParcel : carry (carry p) = p` by constructor cases and `rfl`. Deriving toggles and manually authored equality definitions are variants of this source; no field name or theorem name participates in production logic. `AParcel` deliberately sorts before `ZLeaf`, so successful absent-instance record proof must demonstrate dependency order rather than alphabetical declaration order. Include `List`, `Option`, and `Except` fields to exercise each existing nested-sort dependency route.

Required positive matrix:

- Structured frontend v0.2 enum with its existing derivation: false enum guarantee yields REFUTED with a clean actual-kernel root; true enum guarantee remains UNKNOWN without guarantee-refutation receipts.
- Raw Lean with no enum or record equality: false enum and false nested-record guarantees yield REFUTED; correct guarantees remain UNKNOWN. The profile may legitimately lack enum decision metadata because these guarantees use propositional equality rather than a Boolean enum decision.
- Raw Lean enum equality already derived, record equality absent: enum proofs reuse its exact existing definition; records derive bottom-up; false nested-record guarantee yields REFUTED.
- Raw Lean enum plus ZLeaf equality already derived, AParcel equality absent: the inner definitions are reused and the outer definition derives successfully.
- Raw Lean equality already derived for all carriers: no repeated deriving command for any carrier; false enum and record guarantees still yield REFUTED.
- Raw Lean with a nonstandard safe equality definition name, including an ordinary typed definition or a removed instance attribute: a local alias makes the definition usable; successful concrete proofs do not require guessing its name or inspecting attributes.
- A preexisting equality definition outside the profile's reachable semantic roots is still found from the full replayed Env. The source inspection assertion must prove it was reused and not rederived.
- Reference probes for `swap` and `carry`: correct expectation produces REFERENCE_MATCH while aggregate status remains UNKNOWN; deliberately wrong expectation produces SEMANTIC_MISMATCH only after exact actual-output proof, with untrusted expectation authority and `guarantee_refuted == false`.

For each positive receipt verify the exact candidate source/formalization/records/analysis/proposals bindings, artifact hashes, original declaration hash preservation, exact theorem-type defeq result, root safety/monomorphism/closure, zero sorry dependencies, and receipt/proof hashes. Inspect fresh generated refutation source to assert no `deriving instance` is emitted for already-reused carriers and no enum helper is regenerated for those carriers. This source assertion complements actual successful elaboration; it cannot replace it.

Required negative matrix:

- Direct `_proof` request for `Not (rightToken amber)` and for the true concrete `rightParcel` equation: no receipt; actual Lean cannot prove a false closed proposition despite all equality support being available.
- A wrong-nominal-type equality declaration and a stale metadata binding do not select equality for a different carrier. Actual Env scanning, not profile metadata, determines the result.
- A safe-looking equality definition whose body contains `sorry`, a Classical-choice definition, and an unsafe/partial definition are never selected for reuse. If safe deriving fallback independently succeeds, its genuine proof is allowed; otherwise remain UNKNOWN. Assert that the bad definition is absent from the root dependency closure in any successful result.
- Equality/helper and generated-alias name collisions produce UNKNOWN and no receipt rather than changing any original declaration.
- Tamper fresh proof exports in separate boundary tests to alter the theorem defeq result, original base hash, theorem safety, level parameters, unresolved constants, or sorry/forbidden axiom closure: each case remains UNKNOWN without receipts. Retain the existing real-kernel negative tests in `tests/test_contract_refutation.py`.
- Changed candidate source, forged analysis/formula, malformed enum/record wires, extra proposal fields, and an unadmitted entry/clause remain rejected before authority is granted. Retain the existing canonical-wire and binding tests.
- Unsupported/genuinely dependent or recursive carriers remain outside the admitted profile; no widening of admission is part of this qualification.

## Qualification order and completion rule

1. Preserve this specification and seal unchanged. Root must finish sealing/auditing stage 018 before any implementation mutation.
2. Implement only the proposed refutation preparation and collision guard, plus fresh generic tests. Review the diff against this frozen specification.
3. Run focused actual-Lean refutation/equality/frontend tests and the existing trust-boundary tests. A fixture skip or absent Lean result does not establish the positive behavior.
4. Record exact source/toolchain/kernel-tool identities and actual commands/results under a new validation run, separate from this read-only design directory. Do not replace this design with implementation results.
5. Proceed to the separately authorized stage 019 freeze/qualification only when the generic positive/negative requirements pass. Do not run native task/model work, infer truth from host outputs, weaken review, alter kernel checks, or set inference deadlines as a shortcut.

This pass stops at the sealed design. It makes no claim that the proposed source changes or Lean fixtures have been implemented, compiled, or verified.

## Design-pass scope disclosure

An initial repository-wide filename inventory accidentally listed paths under `synthetic_dataset`, including artifact names, because its glob exclusions were too narrow. No artifact contents were opened and no prior answer was used. Inspection was immediately restricted to explicit production files, the generic tests named in the manifest, and local pinned Lean primary sources. This disclosure is retained to avoid presenting the pass as if the filename inventory had been perfectly scoped.
