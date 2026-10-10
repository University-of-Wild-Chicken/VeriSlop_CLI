import Std

/-!
Normative native boundary fact model, v0.2. The host Python AST-to-fact mapping
is source-bound and TRUSTED at Tier 0. These theorems prove rules about the fact
model; they do not prove the parser, CPython, ownership analysis or arbitrary
future Python programs. Facts are computed by the registered source checker,
never supplied as observations by a candidate author.
-/
namespace VeriSlop.Native

inductive NativeRequirement where
  | entry (file qualname : String) (arity : Nat)
  | pureJson
  | standardRuntimeOnly
  | noExternalIO
  | inputPreserved
  | deterministic
  | noFloatingPoint
  deriving DecidableEq

structure Entry where
  file : String
  qualname : String
  arity : Nat
  deriving DecidableEq

structure ModuleFacts where
  entries : List Entry
  uniqueFunctions : Bool
  closedNames : Bool
  acyclicCalls : Bool
  pureJson : Bool
  standardRuntimeOnly : Bool
  noExternalIO : Bool
  inputPreserved : Bool
  deterministic : Bool
  noFloatingPoint : Bool

def checkRequirement (r : NativeRequirement) (m : ModuleFacts) : Bool :=
  match r with
  | .entry f n a => m.uniqueFunctions && decide (Entry.mk f n a ∈ m.entries)
  | .pureJson => m.closedNames && m.acyclicCalls && m.pureJson
  | .standardRuntimeOnly => m.standardRuntimeOnly
  | .noExternalIO => m.noExternalIO
  | .inputPreserved => m.inputPreserved
  | .deterministic => m.deterministic
  | .noFloatingPoint => m.noFloatingPoint

def HoldsRequirement (r : NativeRequirement) (m : ModuleFacts) : Prop :=
  match r with
  | .entry f n a => m.uniqueFunctions = true ∧ Entry.mk f n a ∈ m.entries
  | .pureJson => m.closedNames = true ∧ m.acyclicCalls = true ∧ m.pureJson = true
  | .standardRuntimeOnly => m.standardRuntimeOnly = true
  | .noExternalIO => m.noExternalIO = true
  | .inputPreserved => m.inputPreserved = true
  | .deterministic => m.deterministic = true
  | .noFloatingPoint => m.noFloatingPoint = true

def checkBoundary (rs : List NativeRequirement) (m : ModuleFacts) : Bool :=
  rs.all (fun r => checkRequirement r m)

def HoldsBoundary (rs : List NativeRequirement) (m : ModuleFacts) : Prop :=
  ∀ r ∈ rs, HoldsRequirement r m

def Transfer (rs : List NativeRequirement) : Prop :=
  ∀ m, checkBoundary rs m = true → HoldsBoundary rs m

def AdmissionInhabited (rs : List NativeRequirement) : Prop :=
  ∃ m, checkBoundary rs m = true

-- The endpoint is real closed Lean data containing the accepted function.
-- Its identity is reified and linked independently; the boundary theorem does
-- not establish functional equivalence to this reference implementation.
structure NativeDefinition (τ : Type) where
  endpoint : τ
  requirements : List NativeRequirement

def Contract {τ : Type} (d : NativeDefinition τ) : Prop :=
  Transfer d.requirements ∧ AdmissionInhabited d.requirements

theorem checkRequirement_sound (r : NativeRequirement) (m : ModuleFacts) :
    checkRequirement r m = true → HoldsRequirement r m := by
  cases r <;> simp [checkRequirement, HoldsRequirement, Bool.and_eq_true] <;> grind

theorem transfer_sound (rs : List NativeRequirement) : Transfer rs := by
  intro m h r hr
  exact checkRequirement_sound r m ((List.all_eq_true.mp h) r hr)

def witnessEntries : List NativeRequirement → List Entry
  | [] => []
  | .entry f n a :: rs => Entry.mk f n a :: witnessEntries rs
  | _ :: rs => witnessEntries rs

def modelWitness (rs : List NativeRequirement) : ModuleFacts :=
  ⟨witnessEntries rs, true, true, true, true, true, true, true, true, true⟩

theorem entry_in_witness (f n : String) (a : Nat) (rs : List NativeRequirement)
    (h : NativeRequirement.entry f n a ∈ rs) : Entry.mk f n a ∈ witnessEntries rs := by
  induction rs with
  | nil => simp at h
  | cons r rs ih => cases r <;> simp_all [witnessEntries] <;> grind

theorem admission_inhabited (rs : List NativeRequirement) : AdmissionInhabited rs := by
  refine ⟨modelWitness rs, List.all_eq_true.mpr ?_⟩
  intro r hr
  cases r with
  | entry f n a =>
    simp [checkRequirement, modelWitness, entry_in_witness f n a rs hr]
  | pureJson => rfl
  | standardRuntimeOnly => rfl
  | noExternalIO => rfl
  | inputPreserved => rfl
  | deterministic => rfl
  | noFloatingPoint => rfl

theorem contract_sound {τ : Type} (d : NativeDefinition τ) : Contract d :=
  ⟨transfer_sound d.requirements, admission_inhabited d.requirements⟩

end VeriSlop.Native
