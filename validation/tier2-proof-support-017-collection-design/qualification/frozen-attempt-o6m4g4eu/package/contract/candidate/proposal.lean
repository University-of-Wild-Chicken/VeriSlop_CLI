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
inductive «Shade» where
  | «light»
  | «dark»
  | «neutral»
  deriving _root_.DecidableEq
structure «Parcel» where
  «shade» : _root_.VeriSlopAST.«Shade»
  «n» : _root_.Nat
structure «Envelope» where
  «parcel» : _root_.VeriSlopAST.«Parcel»
  «active» : _root_.Bool
@[reducible] def «envelope_domain» («_v0» : _root_.VeriSlopAST.«Envelope») : Prop := ((_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v0»)) = (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v0»)))
theorem «_vs_predicate_envelope_domain» («_v0» : _root_.VeriSlopAST.«Envelope») : ((_root_.VeriSlopAST.«envelope_domain» «_v0») ↔ ((_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v0»)) = (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v0»)))) := by rfl
def «inspectEnvelope» («_v0» : _root_.VeriSlopAST.«Envelope») : _root_.Nat := (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v0»))
theorem «_vs_body_inspectEnvelope» : (∀ («_v0» : _root_.VeriSlopAST.«Envelope»), ((_root_.VeriSlopAST.«inspectEnvelope» «_v0») = (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v0»)))) := by intros; rfl
def «keepParcel» («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)) («_v1» : _root_.VeriSlopAST.«Parcel») : (_root_.List _root_.VeriSlopAST.«Envelope») := (@_root_.List.filter _root_.VeriSlopAST.«Envelope» (fun («_v2» : _root_.VeriSlopAST.«Envelope») => (_root_.Bool.and (@_root_.Decidable.decide ((_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) = (_root_.VeriSlopAST.«Parcel».«shade» «_v1»)) (_root_.VeriSlopAST.«instDecidableEqShade» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) (_root_.VeriSlopAST.«Parcel».«shade» «_v1»))) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) = (_root_.VeriSlopAST.«Parcel».«n» «_v1»))))) «_v0»)
theorem «_vs_body_keepParcel» : (∀ («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)), (∀ («_v1» : _root_.VeriSlopAST.«Parcel»), ((_root_.VeriSlopAST.«keepParcel» «_v0» «_v1») = (@_root_.List.filter _root_.VeriSlopAST.«Envelope» (fun («_v2» : _root_.VeriSlopAST.«Envelope») => (_root_.Bool.and (@_root_.Decidable.decide ((_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) = (_root_.VeriSlopAST.«Parcel».«shade» «_v1»)) (_root_.VeriSlopAST.«instDecidableEqShade» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) (_root_.VeriSlopAST.«Parcel».«shade» «_v1»))) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) = (_root_.VeriSlopAST.«Parcel».«n» «_v1»))))) «_v0»)))) := by intros; rfl
def «sameShade» («_v0» : _root_.VeriSlopAST.«Shade») («_v1» : _root_.VeriSlopAST.«Shade») : _root_.Bool := (@_root_.Decidable.decide («_v0» = «_v1») (_root_.VeriSlopAST.«instDecidableEqShade» «_v0» «_v1»))
theorem «_vs_body_sameShade» : (∀ («_v0» : _root_.VeriSlopAST.«Shade»), (∀ («_v1» : _root_.VeriSlopAST.«Shade»), ((_root_.VeriSlopAST.«sameShade» «_v0» «_v1») = (@_root_.Decidable.decide («_v0» = «_v1») (_root_.VeriSlopAST.«instDecidableEqShade» «_v0» «_v1»))))) := by intros; rfl
def «shadeTotal» («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)) («_v1» : _root_.Nat) («_v2» : _root_.VeriSlopAST.«Shade») : _root_.Nat := (@_root_.List.foldl _root_.Nat _root_.VeriSlopAST.«Envelope» (fun («_v3» : _root_.Nat) («_v4» : _root_.VeriSlopAST.«Envelope») => (@_root_.cond _root_.Nat (@_root_.Decidable.decide ((_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v4»)) = «_v2») (_root_.VeriSlopAST.«instDecidableEqShade» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v4»)) «_v2»)) (_root_.Nat.add «_v3» (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v4»))) «_v3»)) «_v1» «_v0»)
theorem «_vs_body_shadeTotal» : (∀ («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)), (∀ («_v1» : _root_.Nat), (∀ («_v2» : _root_.VeriSlopAST.«Shade»), ((_root_.VeriSlopAST.«shadeTotal» «_v0» «_v1» «_v2») = (@_root_.List.foldl _root_.Nat _root_.VeriSlopAST.«Envelope» (fun («_v3» : _root_.Nat) («_v4» : _root_.VeriSlopAST.«Envelope») => (@_root_.cond _root_.Nat (@_root_.Decidable.decide ((_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v4»)) = «_v2») (_root_.VeriSlopAST.«instDecidableEqShade» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v4»)) «_v2»)) (_root_.Nat.add «_v3» (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v4»))) «_v3»)) «_v1» «_v0»))))) := by intros; rfl
def «shiftEnvelopes» («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)) («_v1» : _root_.Nat) : (_root_.List _root_.VeriSlopAST.«Envelope») := (@_root_.List.map _root_.VeriSlopAST.«Envelope» _root_.VeriSlopAST.«Envelope» (fun («_v2» : _root_.VeriSlopAST.«Envelope») => (_root_.VeriSlopAST.«Envelope».«mk» (_root_.VeriSlopAST.«Parcel».«mk» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) (_root_.Nat.add (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) «_v1»)) (_root_.VeriSlopAST.«Envelope».«active» «_v2»))) «_v0»)
theorem «_vs_body_shiftEnvelopes» : (∀ («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)), (∀ («_v1» : _root_.Nat), ((_root_.VeriSlopAST.«shiftEnvelopes» «_v0» «_v1») = (@_root_.List.map _root_.VeriSlopAST.«Envelope» _root_.VeriSlopAST.«Envelope» (fun («_v2» : _root_.VeriSlopAST.«Envelope») => (_root_.VeriSlopAST.«Envelope».«mk» (_root_.VeriSlopAST.«Parcel».«mk» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) (_root_.Nat.add (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) «_v1»)) (_root_.VeriSlopAST.«Envelope».«active» «_v2»))) «_v0»)))) := by intros; rfl
def «InspectDelivery» : _root_.VeriSlop.Source.SourceDefinition (_root_.VeriSlopAST.«Envelope» → _root_.Nat) := ⟨_root_.VeriSlopAST.«inspectEnvelope», [(_root_.VeriSlop.Source.SourceRequirement.entry "program.vscore.json" "inspectEnvelope" 1), _root_.VeriSlop.Source.SourceRequirement.typedTotal, _root_.VeriSlop.Source.SourceRequirement.deterministic, _root_.VeriSlop.Source.SourceRequirement.inputPreserved, _root_.VeriSlop.Source.SourceRequirement.noExternalIO, _root_.VeriSlop.Source.SourceRequirement.noFloatingPoint, _root_.VeriSlop.Source.SourceRequirement.pureData, _root_.VeriSlop.Source.SourceRequirement.restrictedRuntimeOnly]⟩
def «MapDelivery» : _root_.VeriSlop.Source.SourceDefinition ((_root_.List _root_.VeriSlopAST.«Envelope») → _root_.Nat → (_root_.List _root_.VeriSlopAST.«Envelope»)) := ⟨_root_.VeriSlopAST.«shiftEnvelopes», [(_root_.VeriSlop.Source.SourceRequirement.entry "program.vscore.json" "shiftEnvelopes" 2), _root_.VeriSlop.Source.SourceRequirement.typedTotal, _root_.VeriSlop.Source.SourceRequirement.deterministic, _root_.VeriSlop.Source.SourceRequirement.inputPreserved, _root_.VeriSlop.Source.SourceRequirement.noExternalIO, _root_.VeriSlop.Source.SourceRequirement.noFloatingPoint, _root_.VeriSlop.Source.SourceRequirement.pureData, _root_.VeriSlop.Source.SourceRequirement.restrictedRuntimeOnly]⟩
theorem «inhabited_domain» : (∃ («_v0» : _root_.VeriSlopAST.«Envelope»), (_root_.VeriSlopAST.«envelope_domain» «_v0»)) := by sorry
theorem «law_equality» : (∀ («_v0» : _root_.VeriSlopAST.«Shade»), (∀ («_v1» : _root_.VeriSlopAST.«Shade»), ((_root_.VeriSlopAST.«sameShade» «_v0» «_v1») = (@_root_.Decidable.decide («_v0» = «_v1») (_root_.VeriSlopAST.«instDecidableEqShade» «_v0» «_v1»))))) := by sorry
theorem «law_filter» : (∀ («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)), (∀ («_v1» : _root_.VeriSlopAST.«Parcel»), ((_root_.VeriSlopAST.«keepParcel» «_v0» «_v1») = (@_root_.List.filter _root_.VeriSlopAST.«Envelope» (fun («_v2» : _root_.VeriSlopAST.«Envelope») => (_root_.Bool.and (@_root_.Decidable.decide ((_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) = (_root_.VeriSlopAST.«Parcel».«shade» «_v1»)) (_root_.VeriSlopAST.«instDecidableEqShade» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) (_root_.VeriSlopAST.«Parcel».«shade» «_v1»))) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) = (_root_.VeriSlopAST.«Parcel».«n» «_v1»))))) «_v0»)))) := by sorry
theorem «law_fold» : (∀ («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)), (∀ («_v1» : _root_.Nat), (∀ («_v2» : _root_.VeriSlopAST.«Shade»), ((_root_.VeriSlopAST.«shadeTotal» «_v0» «_v1» «_v2») = (@_root_.List.foldl _root_.Nat _root_.VeriSlopAST.«Envelope» (fun («_v3» : _root_.Nat) («_v4» : _root_.VeriSlopAST.«Envelope») => (@_root_.cond _root_.Nat (@_root_.Decidable.decide ((_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v4»)) = «_v2») (_root_.VeriSlopAST.«instDecidableEqShade» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v4»)) «_v2»)) (_root_.Nat.add «_v3» (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v4»))) «_v3»)) «_v1» «_v0»))))) := by sorry
theorem «law_shift» : ((∀ («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)), (∀ («_v1» : _root_.Nat), ((_root_.VeriSlopAST.«shiftEnvelopes» «_v0» «_v1») = (@_root_.List.map _root_.VeriSlopAST.«Envelope» _root_.VeriSlopAST.«Envelope» (fun («_v2» : _root_.VeriSlopAST.«Envelope») => (_root_.VeriSlopAST.«Envelope».«mk» (_root_.VeriSlopAST.«Parcel».«mk» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) (_root_.Nat.add (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) «_v1»)) (_root_.VeriSlopAST.«Envelope».«active» «_v2»))) «_v0»)))) ∧ (_root_.VeriSlop.Source.Contract _root_.VeriSlopAST.«MapDelivery»)) := by sorry
theorem «_vs_value_law_shift» : (∀ («_v0» : (_root_.List _root_.VeriSlopAST.«Envelope»)), (∀ («_v1» : _root_.Nat), ((_root_.VeriSlopAST.«shiftEnvelopes» «_v0» «_v1») = (@_root_.List.map _root_.VeriSlopAST.«Envelope» _root_.VeriSlopAST.«Envelope» (fun («_v2» : _root_.VeriSlopAST.«Envelope») => (_root_.VeriSlopAST.«Envelope».«mk» (_root_.VeriSlopAST.«Parcel».«mk» (_root_.VeriSlopAST.«Parcel».«shade» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) (_root_.Nat.add (_root_.VeriSlopAST.«Parcel».«n» (_root_.VeriSlopAST.«Envelope».«parcel» «_v2»)) «_v1»)) (_root_.VeriSlopAST.«Envelope».«active» «_v2»))) «_v0»)))) := by exact _root_.VeriSlopAST.«law_shift».1
theorem «source_delivery» : (_root_.VeriSlop.Source.Contract _root_.VeriSlopAST.«InspectDelivery») := by sorry
end VeriSlopAST
