# Tier 2 collection transport and exact obligation identity

This specification precedes implementation. Stage016 is sealed BLOCKED at
bridge acceptance. Its accepted Lean contract and admitted source do not establish
source refinement. The independent finite audit and matching frozen verification
completed before the source hold was released. Earlier run results remain immutable.

The clean, unrelated generated fixture in
`validation/isolated-collection-bridge-20261010-gcb` demonstrated actual adapter
normalization failures and universal kernel-checked positive controls. It reached
proof preview and structural preparation, without semantic bridge acceptance or
closure. This milestone promotes only its five source-independent laws and fixes
an independently observed declaration-identity bug. It supplies no task program,
task theorem, reference definition, or accepted guarantee.

## Universal proof support

Add exactly five theorems to `VSCore3.ProofSupport` in the existing
`VSCore3.Transport` module, after the adapters they reference. Keep the existing
six catalog entries. The new entries and their exact signatures are part of the
explicit authoring catalog, hashed against current module source. None becomes a
global simp rule. For `a : Adapter t α`, `b : Adapter u β`, with the existing
`α β : Type` carriers, the laws are:

* `to_eq_iff`: `a.to x = a.to y ↔ x = y` for every `x y : α`.
* `decide_to_eq`: `decide (a.to x = a.to y) = decide (x = y)`, retaining both
  supplied lawful DecidableEq instances for the intrinsic and native carriers.
* `map_transport`: if `∀ x, g (a.to x) = b.to (f x)`, then
  `(listAdapter b).inv (List.map g ((listAdapter a).to xs)) = List.map f xs`.
* `filter_transport`: if `∀ x, q (a.to x) = p x`, then
  `(listAdapter a).inv (List.filter q ((listAdapter a).to xs)) = List.filter p xs`.
* `foldl_transport`: if `∀ z x, g (b.to z) (a.to x) = b.to (f z x)`, then
  `b.inv (List.foldl g (b.to z) ((listAdapter a).to xs)) = List.foldl f z xs`.

Map and fold permit different element/result or accumulator carriers. Every law
quantifies over all lists, and fold over every initial and intermediate
accumulator. Pointwise agreement remains a candidate proof obligation; the laws
cannot infer it from passing examples. Equality transport follows from adapter
inverse laws and cannot replace nominal registry identities or fixed decisions.

Do not add helper/environment, append, Option or other normalization laws without
a separate actual generated failure, universal positive control and specification.
Authoring prompts may explain these catalog premises and existing local
`with_unfolding_all` normalization. They must not contain fixture or task proofs.

## Exact declaration identity

Allowed obligation IDs contain hyphens, dots and colons. A generated leaf such as
`transfer_G-map` or `transfer_G.map` is one Lean Name string component under
`VeriSlopBridgeGoal`; a dot in the ID does not create a namespace. Resolve transfer
theorems in both bridge checking and concrete review replay using the exact
generated component array and canonical exported spelling. Compare accepted
theorem dependencies by parsed Lean Name components. Missing declarations,
different namespace structure, wrong kind, or a missing accepted-theorem
dependency must still block. Do not sanitize IDs, use suffix matching, or retry
with a guessed spelling.

Certificate `transfer`, `transfer_theorem`, and `statement_identity` fields use
the same exact identity as the actual replayed declarations. Preserve the existing
distinction between ordinary one-component generated leaves and the reserved
`Readable` nested namespace. Existing exact statement/type/body comparison and
accepted-AST program re-export remain mandatory. Plain identifiers retain their
current serialization. This repair applies to VSCore 0.3; older protocol roots
are not rewritten or rescored.

## Preserved assurance boundary

No DSL or source grammar, renderer, semantic goal, input domain, assumption,
import, axiom policy, resource policy, inference deadline, proof size or native
repair budget changes. Compiler/proof/closure failure evidence remains durable.
The catalog itself assigns no lifecycle state. PROVED still requires actual
kernel acceptance; Tier 2 still requires every frozen universal refinement,
raw-input coverage and per-obligation transfer. Optional TESTED remains separate.

The endpoint is `restricted_source` under `vscore-semantics/0.3`, with the user's
explicit revised VSCore delivery contract. This adds no Python, extraction,
compiler-chain, machine-code or physical resource guarantee. Declared kernel,
toolchain, controller, host, hash and hardware trust remains explicit.

## Frozen qualification before fresh task generation

Extend real-kernel catalog checks to the exact eleven names, independent signature
elaboration, safe declarations, actual axiom/dependency inventories, two clean
builds and deterministic module identities. New-law expected axiom closures are
empty for `to_eq_iff` and `propext` for the other four. Reject a false universal
claim and a materially false collection agreement using actual Lean diagnostics.
Include unrelated instantiations with different map/fold carriers and arbitrary
lists and accumulators.

Test hyphen, dot and colon obligation IDs together against actual generated goals
and kernel exports; exercise bridge checking, certificate identity and concrete
review replay. Include missing/near-name/wrong-dependency/wrong-kind and exact
statement mismatch negatives. No mocked acceptance is sufficient for qualification.

Create one new unrelated package with Shade(light/dark/neutral), Parcel(shade,n)
and Envelope(parcel,active), covering all alternatives and unbounded Nat values.
Freeze its natural-language specification and candidate fixtures before running:

1. Map envelopes using a captured Nat increment and a helper-to-helper call with
   heterogeneous declared-order arguments; preserve shade and active.
2. Filter by exact captured Parcel equality, preserving order and duplicates;
   the accepted DSL uses supported enum/Nat field decisions and the source uses
   intrinsic record equality. Prove their universal predicate agreement.
3. Fold matching shades from an arbitrary Nat accumulator, with a helper and a
   captured shade; prove agreement at every step and accumulator.
4. Compare two shades by their exact fixed equality decisions.
5. Bind a distinct source-only entry alongside at least one Mixed value/source
   obligation. This tests source-only and Mixed transfer, without adding arbitrary
   reference-body equality to a solely operational endpoint.

Use actual frontend compilation, Lean denotation audits, contract proof/witness
acceptance and AST reconstruction. Require actual compiled source, CHECKED readable
selection covering helpers/captures, original Refines/EdgeProp, and dependencies on
all five production laws. Preserve an actual failed direct-conversion baseline.
A semantically wrong but type-correct source must not obtain semantic acceptance;
selection tampering must block through existing checks.

Freeze every current production/spec/schema/transport input, fixture, test and
driver before final qualification. Run the registered workflow through bridge
acceptance and closure, actual isolated builds A/B and deterministic comparison,
concrete release probe, retained validation after original temporary-root removal,
and a second probe on the retained package. Retain complete logs/exports/failed
attempts and exact artifact hashes. The expensive full fixture uses
`VERISLOP_COLLECTION_QUALIFICATION_FREEZE`; unset skips are never qualification.

Root reconstructs the engineering record from the actual current package and
registered results. An independent generic audit must bind the new frozen root,
plan, exports, inventories, builds and release evidence. Only then can a new
strict natural-language task run use that source root, with unique fresh role
authors and literal final-response transport. No retained task solution, proof,
candidate, hidden case or generic fixture answer enters those role contexts.
Fresh model identity remains explicitly unattested when using collaboration
simulation. No earlier VERIFIED root grants assurance to a changed implementation.
