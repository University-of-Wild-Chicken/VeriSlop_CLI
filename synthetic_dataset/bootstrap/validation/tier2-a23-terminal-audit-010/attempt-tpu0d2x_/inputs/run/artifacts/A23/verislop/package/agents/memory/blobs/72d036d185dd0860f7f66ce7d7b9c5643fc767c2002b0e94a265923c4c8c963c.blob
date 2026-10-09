import Std

/-!
Normative restricted-source boundary requirement model, v0.1. These rules prove
checking soundness and inhabitation of an abstract fact model. They do not assert
facts about a delivered program, its evaluator, or a host runtime. The source
bridge must derive every fact from the exact admitted source and semantic laws.
This algebra is independent of the Python NativeBoundary model.
-/
namespace VeriSlop.Source

inductive SourceRequirement where
  | entry (file id : String) (arity : Nat)
  | typedTotal
  | deterministic
  | inputPreserved
  | noExternalIO
  | noFloatingPoint
  | pureData
  | restrictedRuntimeOnly
  deriving DecidableEq

structure Entry where
  file : String
  id : String
  arity : Nat
  deriving DecidableEq

structure ModuleFacts where
  entries : List Entry
  uniqueEntries : Bool
  typedTotal : Bool
  deterministic : Bool
  inputPreserved : Bool
  noExternalIO : Bool
  noFloatingPoint : Bool
  pureData : Bool
  restrictedRuntimeOnly : Bool

def checkRequirement (r : SourceRequirement) (m : ModuleFacts) : Bool :=
  match r with
  | .entry f n a => m.uniqueEntries && decide (Entry.mk f n a ∈ m.entries)
  | .typedTotal => m.typedTotal
  | .deterministic => m.deterministic
  | .inputPreserved => m.inputPreserved
  | .noExternalIO => m.noExternalIO
  | .noFloatingPoint => m.noFloatingPoint
  | .pureData => m.pureData
  | .restrictedRuntimeOnly => m.restrictedRuntimeOnly

def HoldsRequirement (r : SourceRequirement) (m : ModuleFacts) : Prop :=
  match r with
  | .entry f n a => m.uniqueEntries = true ∧ Entry.mk f n a ∈ m.entries
  | .typedTotal => m.typedTotal = true
  | .deterministic => m.deterministic = true
  | .inputPreserved => m.inputPreserved = true
  | .noExternalIO => m.noExternalIO = true
  | .noFloatingPoint => m.noFloatingPoint = true
  | .pureData => m.pureData = true
  | .restrictedRuntimeOnly => m.restrictedRuntimeOnly = true

def checkBoundary (rs : List SourceRequirement) (m : ModuleFacts) : Bool :=
  rs.all (fun r => checkRequirement r m)

def HoldsBoundary (rs : List SourceRequirement) (m : ModuleFacts) : Prop :=
  ∀ r ∈ rs, HoldsRequirement r m

def Transfer (rs : List SourceRequirement) : Prop :=
  ∀ m, checkBoundary rs m = true → HoldsBoundary rs m

def AdmissionInhabited (rs : List SourceRequirement) : Prop :=
  ∃ m, checkBoundary rs m = true

/-- Closed accepted data identifies the endpoint; Contract supplies only abstract
checking rules and does not establish implementation refinement. -/
structure SourceDefinition (τ : Type) where
  endpoint : τ
  requirements : List SourceRequirement

def Contract {τ : Type} (d : SourceDefinition τ) : Prop :=
  Transfer d.requirements ∧ AdmissionInhabited d.requirements

theorem checkRequirement_sound (r : SourceRequirement) (m : ModuleFacts) :
    checkRequirement r m = true → HoldsRequirement r m := by
  cases r <;> simp [checkRequirement, HoldsRequirement, Bool.and_eq_true]

theorem transfer_sound (rs : List SourceRequirement) : Transfer rs := by
  intro m h r hr
  exact checkRequirement_sound r m ((List.all_eq_true.mp h) r hr)

def witnessEntries : List SourceRequirement → List Entry
  | [] => []
  | .entry f n a :: rs => Entry.mk f n a :: witnessEntries rs
  | _ :: rs => witnessEntries rs

def modelWitness (rs : List SourceRequirement) : ModuleFacts :=
  ⟨witnessEntries rs, true, true, true, true, true, true, true, true⟩

theorem entry_in_witness (f n : String) (a : Nat) (rs : List SourceRequirement)
    (h : SourceRequirement.entry f n a ∈ rs) : Entry.mk f n a ∈ witnessEntries rs := by
  induction rs with
  | nil => simp at h
  | cons r rs ih => cases r <;> simp_all [witnessEntries] <;> grind

theorem admission_inhabited (rs : List SourceRequirement) : AdmissionInhabited rs := by
  refine ⟨modelWitness rs, List.all_eq_true.mpr ?_⟩
  intro r hr
  cases r with
  | entry f n a =>
    simp [checkRequirement, modelWitness, entry_in_witness f n a rs hr]
  | typedTotal => rfl
  | deterministic => rfl
  | inputPreserved => rfl
  | noExternalIO => rfl
  | noFloatingPoint => rfl
  | pureData => rfl
  | restrictedRuntimeOnly => rfl

theorem contract_sound {τ : Type} (d : SourceDefinition τ) : Contract d :=
  ⟨transfer_sound d.requirements, admission_inhabited d.requirements⟩

end VeriSlop.Source

namespace VeriSlopAST
structure «Input» where
  «n» : _root_.Int
  «m» : _root_.Int
  «a» : _root_.Int
  «b» : _root_.Int
def «solve» («_v0» : _root_.VeriSlopAST.«Input») : _root_.Int := (_root_.List.sum (@_root_.List.map _root_.Nat _root_.Int (fun («_v1» : _root_.Nat) => (_root_.Int.fdiv (_root_.Int.add (_root_.Int.mul (_root_.VeriSlopAST.«Input».«a» «_v0») (_root_.Int.ofNat «_v1»)) (_root_.VeriSlopAST.«Input».«b» «_v0»)) (_root_.VeriSlopAST.«Input».«m» «_v0»))) (_root_.List.range (_root_.Int.toNat (_root_.VeriSlopAST.«Input».«n» «_v0»)))))
theorem «_vs_body_solve» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«solve» «_v0») = (_root_.List.sum (@_root_.List.map _root_.Nat _root_.Int (fun («_v1» : _root_.Nat) => (_root_.Int.fdiv (_root_.Int.add (_root_.Int.mul (_root_.VeriSlopAST.«Input».«a» «_v0») (_root_.Int.ofNat «_v1»)) (_root_.VeriSlopAST.«Input».«b» «_v0»)) (_root_.VeriSlopAST.«Input».«m» «_v0»))) (_root_.List.range (_root_.Int.toNat (_root_.VeriSlopAST.«Input».«n» «_v0»))))))) := by intros; rfl
@[reducible] def «valid_input» («_v0» : _root_.VeriSlopAST.«Input») : Prop := (((_root_.Int.ofNat 0) ≤ (_root_.VeriSlopAST.«Input».«n» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«n» «_v0») ≤ (_root_.Int.ofNat 500)) ∧ ((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«m» «_v0»))))
theorem «_vs_predicate_valid_input» («_v0» : _root_.VeriSlopAST.«Input») : ((_root_.VeriSlopAST.«valid_input» «_v0») ↔ (((_root_.Int.ofNat 0) ≤ (_root_.VeriSlopAST.«Input».«n» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«n» «_v0») ≤ (_root_.Int.ofNat 500)) ∧ ((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«m» «_v0»))))) := by rfl
def «SolveSource» : _root_.VeriSlop.Source.SourceDefinition (_root_.VeriSlopAST.«Input» → _root_.Int) := ⟨_root_.VeriSlopAST.«solve», [(_root_.VeriSlop.Source.SourceRequirement.entry "program.vscore.json" "solve" 1), _root_.VeriSlop.Source.SourceRequirement.typedTotal, _root_.VeriSlop.Source.SourceRequirement.deterministic, _root_.VeriSlop.Source.SourceRequirement.inputPreserved, _root_.VeriSlop.Source.SourceRequirement.noExternalIO, _root_.VeriSlop.Source.SourceRequirement.noFloatingPoint, _root_.VeriSlop.Source.SourceRequirement.pureData, _root_.VeriSlop.Source.SourceRequirement.restrictedRuntimeOnly]⟩
theorem «complete_behavior» : ((∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«valid_input» «_v0») → ((_root_.VeriSlopAST.«solve» «_v0») = (_root_.List.sum (@_root_.List.map _root_.Nat _root_.Int (fun («_v1» : _root_.Nat) => (_root_.Int.fdiv (_root_.Int.add (_root_.Int.mul (_root_.VeriSlopAST.«Input».«a» «_v0») (_root_.Int.ofNat «_v1»)) (_root_.VeriSlopAST.«Input».«b» «_v0»)) (_root_.VeriSlopAST.«Input».«m» «_v0»))) (_root_.List.range (_root_.Int.toNat (_root_.VeriSlopAST.«Input».«n» «_v0»)))))))) ∧ (_root_.VeriSlop.Source.Contract _root_.VeriSlopAST.«SolveSource»)) := by sorry
theorem «_vs_value_complete_behavior» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«valid_input» «_v0») → ((_root_.VeriSlopAST.«solve» «_v0») = (_root_.List.sum (@_root_.List.map _root_.Nat _root_.Int (fun («_v1» : _root_.Nat) => (_root_.Int.fdiv (_root_.Int.add (_root_.Int.mul (_root_.VeriSlopAST.«Input».«a» «_v0») (_root_.Int.ofNat «_v1»)) (_root_.VeriSlopAST.«Input».«b» «_v0»)) (_root_.VeriSlopAST.«Input».«m» «_v0»))) (_root_.List.range (_root_.Int.toNat (_root_.VeriSlopAST.«Input».«n» «_v0»)))))))) := by exact _root_.VeriSlopAST.«complete_behavior».1
theorem «operational_source» : (_root_.VeriSlop.Source.Contract _root_.VeriSlopAST.«SolveSource») := by sorry
theorem «valid_input_inhabited» : (∃ («_v0» : _root_.VeriSlopAST.«Input»), (_root_.VeriSlopAST.«valid_input» «_v0»)) := by sorry
end VeriSlopAST
