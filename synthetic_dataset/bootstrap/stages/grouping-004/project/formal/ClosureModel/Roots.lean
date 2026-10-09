/-!
# Roots, the closure plan and the closure manifest

Milestone §6. `H` is SHA-256 over exact bytes and `J` SHA-256 over canonical JSON; both are
modelled as abstract functions, and injectivity is assumed only where a theorem says so.

* `implementation_root` binds the selection, the frozen claim inventory, the delivered source
  and the backend descriptor; the materialization inventory is its output.
* `link_root` binds the implementation root, the bindings and the materialization inventory,
  never the link record it produces.
* `closure_root` binds the closure ID, plan, manifest and the registry/TCB snapshots. The
  manifest enumerates closure inputs only, so build logs, new evidence, results, reviews and
  package indices cannot change it, and the plan contains no hash of itself or the manifest.

Python mirror: `verislop/closure_plan.py`.
-/

namespace ClosureModel

inductive ArtifactRole where
  | input | output
  deriving DecidableEq, Repr

structure Artifact where
  path : String
  role : ArtifactRole
  digest : Nat
  deriving DecidableEq, Repr

def inputs (as : List Artifact) : List Artifact := as.filter (·.role == .input)

/-- Manifest entries of the closure inputs (the Python manifest also sorts and records sizes). -/
def manifest (as : List Artifact) : List (String × Nat) := (inputs as).map fun a => (a.path, a.digest)

structure Snapshots where
  verifierRegistry : Nat
  schemaRegistry : Nat
  tcb : Nat
  deriving DecidableEq, Repr

structure ClosureRootInputs where
  closureId : String
  planHash : Nat
  manifestHash : Nat
  snapshots : Snapshots
  deriving DecidableEq, Repr

/-- The plan lists outputs by producer and expected format, never by future digest. -/
structure OutputSlot where
  path : String
  producer : String
  format : String
  deriving DecidableEq, Repr

structure Plan where
  closureId : String
  claimIds : List String
  outputs : List OutputSlot
  deriving DecidableEq, Repr

def closureRoot (J : ClosureRootInputs → Nat) (Hp : Plan → Nat) (Hm : List (String × Nat) → Nat)
    (plan : Plan) (as : List Artifact) (s : Snapshots) : Nat :=
  J ⟨plan.closureId, Hp plan, Hm (manifest as), s⟩

/-- Outputs are not inputs: changing or adding output artifacts never changes the root. -/
theorem outputs_do_not_affect_root (J Hp Hm plan s) (as bs : List Artifact) (h : inputs as = inputs bs) :
    closureRoot J Hp Hm plan as s = closureRoot J Hp Hm plan bs s := by
  simp [closureRoot, manifest, h]

theorem adding_output_keeps_root (J Hp Hm plan s) (as : List Artifact) (a : Artifact)
    (ha : a.role = .output) : closureRoot J Hp Hm plan (a :: as) s = closureRoot J Hp Hm plan as s := by
  apply outputs_do_not_affect_root
  simp [inputs, ha]

/-- With injective hashes, changing a manifest member, the plan or any snapshot changes the root. -/
theorem input_change_changes_root (J Hp Hm) (hJ : ∀ a b, J a = J b → a = b)
    (hM : ∀ a b, Hm a = Hm b → a = b) (plan s) (as bs : List Artifact)
    (h : manifest as ≠ manifest bs) : closureRoot J Hp Hm plan as s ≠ closureRoot J Hp Hm plan bs s := by
  intro heq
  have := hJ _ _ heq
  simp only [ClosureRootInputs.mk.injEq] at this
  exact h (hM _ _ this.2.2.1)

theorem snapshot_change_changes_root (J Hp Hm) (hJ : ∀ a b, J a = J b → a = b) (plan as)
    (s t : Snapshots) (h : s ≠ t) : closureRoot J Hp Hm plan as s ≠ closureRoot J Hp Hm plan as t := by
  intro heq
  have := hJ _ _ heq
  simp only [ClosureRootInputs.mk.injEq] at this
  exact h this.2.2.2

/-! ## Implementation and link roots -/

structure ImplementationRootInputs where
  selectionHash : Nat
  implementationClaimsHash : Nat
  deliveredSourceHash : Nat
  backendDescriptorHash : Nat
  deriving DecidableEq, Repr

def implementationRoot (J : ImplementationRootInputs → Nat) (i : ImplementationRootInputs) : Nat := J i

structure LinkRootInputs where
  implementationRoot : Nat
  bindingsHash : Nat
  materializationInventoryHash : Nat
  deriving DecidableEq, Repr

def linkRoot (J : LinkRootInputs → Nat) (i : LinkRootInputs) : Nat := J i

/-- The phase records: the materialization inventory is produced under the implementation root
and consumed by the link root; the link record is produced under the link root. -/
structure Phases where
  implementation : ImplementationRootInputs
  bindingsHash : Nat
  inventoryHash : Nat
  linkRecordHash : Nat
  deriving DecidableEq, Repr

def Phases.link (Ji : ImplementationRootInputs → Nat) (Jl : LinkRootInputs → Nat) (p : Phases) : Nat :=
  linkRoot Jl ⟨implementationRoot Ji p.implementation, p.bindingsHash, p.inventoryHash⟩

/-- The link record is not an input to its own link root. -/
theorem link_root_ignores_link_record (Ji Jl) (p : Phases) (r : Nat) :
    Phases.link Ji Jl { p with linkRecordHash := r } = Phases.link Ji Jl p := rfl

/-- Changing the delivered source changes every downstream root (injective hashes). -/
theorem source_change_changes_link_root (Ji Jl) (hi : ∀ a b, Ji a = Ji b → a = b)
    (hl : ∀ a b, Jl a = Jl b → a = b) (p q : Phases)
    (h : p.implementation.deliveredSourceHash ≠ q.implementation.deliveredSourceHash) :
    Phases.link Ji Jl p ≠ Phases.link Ji Jl q := by
  intro heq
  have h1 := hl _ _ heq
  simp only [LinkRootInputs.mk.injEq] at h1
  have h2 := hi _ _ h1.1
  exact h (congrArg ImplementationRootInputs.deliveredSourceHash h2)

end ClosureModel
