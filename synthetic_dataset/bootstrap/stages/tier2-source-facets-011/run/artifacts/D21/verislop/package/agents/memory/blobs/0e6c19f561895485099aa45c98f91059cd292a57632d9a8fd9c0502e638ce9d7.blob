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
structure «Event» where
  «group» : _root_.String
  «time» : _root_.Int
  «value» : (_root_.Option _root_.Int)
structure «Input» where
  «events» : (_root_.List _root_.VeriSlopAST.«Event»)
  «start» : _root_.Int
  «end» : _root_.Int
  «width» : _root_.Int
  «fill» : _root_.String
structure «Output» where
  «group» : _root_.String
  «start» : _root_.Int
  «count» : _root_.Nat
  «value» : (_root_.Option _root_.Int)
structure «State» where
  «previous» : (_root_.Option _root_.Int)
  «rows» : (_root_.List _root_.VeriSlopAST.«Output»)
structure «Stats» where
  «count» : _root_.Nat
  «sum» : _root_.Int
def «bucket_count» («_v0» : _root_.VeriSlopAST.«Input») : _root_.Nat := (_root_.Int.toNat (_root_.Int.fdiv (_root_.Int.sub (_root_.Int.add (_root_.Int.sub (_root_.VeriSlopAST.«Input».«end» «_v0») (_root_.VeriSlopAST.«Input».«start» «_v0»)) (_root_.VeriSlopAST.«Input».«width» «_v0»)) (_root_.Int.ofNat 1)) (_root_.VeriSlopAST.«Input».«width» «_v0»)))
theorem «_vs_body_bucket_count» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«bucket_count» «_v0») = (_root_.Int.toNat (_root_.Int.fdiv (_root_.Int.sub (_root_.Int.add (_root_.Int.sub (_root_.VeriSlopAST.«Input».«end» «_v0») (_root_.VeriSlopAST.«Input».«start» «_v0»)) (_root_.VeriSlopAST.«Input».«width» «_v0»)) (_root_.Int.ofNat 1)) (_root_.VeriSlopAST.«Input».«width» «_v0»))))) := by intros; rfl
def «stats» («_v0» : _root_.VeriSlopAST.«Input») («_v1» : _root_.String) («_v2» : _root_.Nat) : _root_.VeriSlopAST.«Stats» := (@_root_.List.foldl _root_.VeriSlopAST.«Stats» _root_.VeriSlopAST.«Event» (fun («_v3» : _root_.VeriSlopAST.«Stats») («_v4» : _root_.VeriSlopAST.«Event») => (@_root_.cond _root_.VeriSlopAST.«Stats» (_root_.Decidable.decide (((_root_.VeriSlopAST.«Event».«group» «_v4») = «_v1») ∧ (((_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v2») (_root_.VeriSlopAST.«Input».«width» «_v0»))) ≤ (_root_.VeriSlopAST.«Event».«time» «_v4»)) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v4») < (_root_.Int.add (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v2») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Input».«width» «_v0»))) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v4») < (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ ((@_root_.Option.isSome _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v4»)) = _root_.Bool.true)))))) (_root_.VeriSlopAST.«Stats».«mk» (_root_.Nat.add (_root_.VeriSlopAST.«Stats».«count» «_v3») (1 : _root_.Nat)) (_root_.Int.add (_root_.VeriSlopAST.«Stats».«sum» «_v3») (@_root_.Option.getD _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v4») (_root_.Int.ofNat 0)))) «_v3»)) (_root_.VeriSlopAST.«Stats».«mk» (0 : _root_.Nat) (_root_.Int.ofNat 0)) (_root_.VeriSlopAST.«Input».«events» «_v0»))
theorem «_vs_body_stats» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), (∀ («_v1» : _root_.String), (∀ («_v2» : _root_.Nat), ((_root_.VeriSlopAST.«stats» «_v0» «_v1» «_v2») = (@_root_.List.foldl _root_.VeriSlopAST.«Stats» _root_.VeriSlopAST.«Event» (fun («_v3» : _root_.VeriSlopAST.«Stats») («_v4» : _root_.VeriSlopAST.«Event») => (@_root_.cond _root_.VeriSlopAST.«Stats» (_root_.Decidable.decide (((_root_.VeriSlopAST.«Event».«group» «_v4») = «_v1») ∧ (((_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v2») (_root_.VeriSlopAST.«Input».«width» «_v0»))) ≤ (_root_.VeriSlopAST.«Event».«time» «_v4»)) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v4») < (_root_.Int.add (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v2») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Input».«width» «_v0»))) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v4») < (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ ((@_root_.Option.isSome _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v4»)) = _root_.Bool.true)))))) (_root_.VeriSlopAST.«Stats».«mk» (_root_.Nat.add (_root_.VeriSlopAST.«Stats».«count» «_v3») (1 : _root_.Nat)) (_root_.Int.add (_root_.VeriSlopAST.«Stats».«sum» «_v3») (@_root_.Option.getD _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v4») (_root_.Int.ofNat 0)))) «_v3»)) (_root_.VeriSlopAST.«Stats».«mk» (0 : _root_.Nat) (_root_.Int.ofNat 0)) (_root_.VeriSlopAST.«Input».«events» «_v0»)))))) := by intros; rfl
def «step» («_v0» : _root_.VeriSlopAST.«Input») («_v1» : _root_.String) («_v2» : _root_.Nat) («_v3» : _root_.VeriSlopAST.«State») : _root_.VeriSlopAST.«State» := (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.VeriSlopAST.«Stats» (fun («_v4» : _root_.VeriSlopAST.«State») («_v5» : _root_.VeriSlopAST.«Stats») => (_root_.VeriSlopAST.«State».«mk» (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v5»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v5»)) (_root_.VeriSlopAST.«State».«previous» «_v4»)) (@_root_.List.append _root_.VeriSlopAST.«Output» (_root_.VeriSlopAST.«State».«rows» «_v4») ([(_root_.VeriSlopAST.«Output».«mk» «_v1» (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v2») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Stats».«count» «_v5») (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v5»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v5»)) (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")) (_root_.VeriSlopAST.«State».«previous» «_v4») (@_root_.Option.none _root_.Int))))] : (_root_.List _root_.VeriSlopAST.«Output»))))) «_v3» ([(_root_.VeriSlopAST.«stats» «_v0» «_v1» «_v2»)] : (_root_.List _root_.VeriSlopAST.«Stats»)))
theorem «_vs_body_step» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), (∀ («_v1» : _root_.String), (∀ («_v2» : _root_.Nat), (∀ («_v3» : _root_.VeriSlopAST.«State»), ((_root_.VeriSlopAST.«step» «_v0» «_v1» «_v2» «_v3») = (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.VeriSlopAST.«Stats» (fun («_v4» : _root_.VeriSlopAST.«State») («_v5» : _root_.VeriSlopAST.«Stats») => (_root_.VeriSlopAST.«State».«mk» (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v5»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v5»)) (_root_.VeriSlopAST.«State».«previous» «_v4»)) (@_root_.List.append _root_.VeriSlopAST.«Output» (_root_.VeriSlopAST.«State».«rows» «_v4») ([(_root_.VeriSlopAST.«Output».«mk» «_v1» (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v2») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Stats».«count» «_v5») (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v5»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v5»)) (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")) (_root_.VeriSlopAST.«State».«previous» «_v4») (@_root_.Option.none _root_.Int))))] : (_root_.List _root_.VeriSlopAST.«Output»))))) «_v3» ([(_root_.VeriSlopAST.«stats» «_v0» «_v1» «_v2»)] : (_root_.List _root_.VeriSlopAST.«Stats»)))))))) := by intros; rfl
def «group_rows» («_v0» : _root_.VeriSlopAST.«Input») («_v1» : _root_.String) : (_root_.List _root_.VeriSlopAST.«Output») := (_root_.VeriSlopAST.«State».«rows» (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.Nat (fun («_v2» : _root_.VeriSlopAST.«State») («_v3» : _root_.Nat) => (_root_.VeriSlopAST.«step» «_v0» «_v1» «_v3» «_v2»)) (_root_.VeriSlopAST.«State».«mk» (@_root_.Option.none _root_.Int) ([] : (_root_.List _root_.VeriSlopAST.«Output»))) (_root_.List.range (_root_.VeriSlopAST.«bucket_count» «_v0»))))
theorem «_vs_body_group_rows» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), (∀ («_v1» : _root_.String), ((_root_.VeriSlopAST.«group_rows» «_v0» «_v1») = (_root_.VeriSlopAST.«State».«rows» (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.Nat (fun («_v2» : _root_.VeriSlopAST.«State») («_v3» : _root_.Nat) => (_root_.VeriSlopAST.«step» «_v0» «_v1» «_v3» «_v2»)) (_root_.VeriSlopAST.«State».«mk» (@_root_.Option.none _root_.Int) ([] : (_root_.List _root_.VeriSlopAST.«Output»))) (_root_.List.range (_root_.VeriSlopAST.«bucket_count» «_v0»))))))) := by intros; rfl
def «groups» («_v0» : _root_.VeriSlopAST.«Input») : (_root_.List _root_.String) := (@_root_.List.mergeSort _root_.String (@_root_.List.eraseDups _root_.String (@_root_.instBEqOfDecidableEq _root_.String _root_.instDecidableEqString) (@_root_.List.map _root_.VeriSlopAST.«Event» _root_.String (fun («_v1» : _root_.VeriSlopAST.«Event») => (_root_.VeriSlopAST.«Event».«group» «_v1»)) (_root_.VeriSlopAST.«Input».«events» «_v0»))) (fun (_vs_left _vs_right : _root_.String) => _root_.Decidable.decide (_vs_left ≤ _vs_right)))
theorem «_vs_body_groups» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«groups» «_v0») = (@_root_.List.mergeSort _root_.String (@_root_.List.eraseDups _root_.String (@_root_.instBEqOfDecidableEq _root_.String _root_.instDecidableEqString) (@_root_.List.map _root_.VeriSlopAST.«Event» _root_.String (fun («_v1» : _root_.VeriSlopAST.«Event») => (_root_.VeriSlopAST.«Event».«group» «_v1»)) (_root_.VeriSlopAST.«Input».«events» «_v0»))) (fun (_vs_left _vs_right : _root_.String) => _root_.Decidable.decide (_vs_left ≤ _vs_right))))) := by intros; rfl
def «solve» («_v0» : _root_.VeriSlopAST.«Input») : (_root_.List _root_.VeriSlopAST.«Output») := (@_root_.List.foldl (_root_.List _root_.VeriSlopAST.«Output») _root_.String (fun («_v1» : (_root_.List _root_.VeriSlopAST.«Output»)) («_v2» : _root_.String) => (@_root_.List.append _root_.VeriSlopAST.«Output» «_v1» (_root_.VeriSlopAST.«group_rows» «_v0» «_v2»))) ([] : (_root_.List _root_.VeriSlopAST.«Output»)) (_root_.VeriSlopAST.«groups» «_v0»))
theorem «_vs_body_solve» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«solve» «_v0») = (@_root_.List.foldl (_root_.List _root_.VeriSlopAST.«Output») _root_.String (fun («_v1» : (_root_.List _root_.VeriSlopAST.«Output»)) («_v2» : _root_.String) => (@_root_.List.append _root_.VeriSlopAST.«Output» «_v1» (_root_.VeriSlopAST.«group_rows» «_v0» «_v2»))) ([] : (_root_.List _root_.VeriSlopAST.«Output»)) (_root_.VeriSlopAST.«groups» «_v0»)))) := by intros; rfl
@[reducible] def «valid_input» («_v0» : _root_.VeriSlopAST.«Input») : Prop := (((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«width» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«start» «_v0») ≤ (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«fill» «_v0») = "none") ∨ ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous"))))
theorem «_vs_predicate_valid_input» («_v0» : _root_.VeriSlopAST.«Input») : ((_root_.VeriSlopAST.«valid_input» «_v0») ↔ (((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«width» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«start» «_v0») ≤ (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«fill» «_v0») = "none") ∨ ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous"))))) := by rfl
def «SolveSource» : _root_.VeriSlop.Source.SourceDefinition (_root_.VeriSlopAST.«Input» → (_root_.List _root_.VeriSlopAST.«Output»)) := ⟨_root_.VeriSlopAST.«solve», [(_root_.VeriSlop.Source.SourceRequirement.entry "program.vscore.json" "solve" 1), _root_.VeriSlop.Source.SourceRequirement.typedTotal, _root_.VeriSlop.Source.SourceRequirement.deterministic, _root_.VeriSlop.Source.SourceRequirement.inputPreserved, _root_.VeriSlop.Source.SourceRequirement.noExternalIO, _root_.VeriSlop.Source.SourceRequirement.noFloatingPoint, _root_.VeriSlop.Source.SourceRequirement.pureData, _root_.VeriSlop.Source.SourceRequirement.restrictedRuntimeOnly]⟩
theorem «complete_aggregation» : ((∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«valid_input» «_v0») → ((_root_.VeriSlopAST.«solve» «_v0») = (@_root_.List.foldl (_root_.List _root_.VeriSlopAST.«Output») _root_.String (fun («_v1» : (_root_.List _root_.VeriSlopAST.«Output»)) («_v2» : _root_.String) => (@_root_.List.append _root_.VeriSlopAST.«Output» «_v1» (_root_.VeriSlopAST.«State».«rows» (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.Nat (fun («_v3» : _root_.VeriSlopAST.«State») («_v4» : _root_.Nat) => (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.VeriSlopAST.«Stats» (fun («_v5» : _root_.VeriSlopAST.«State») («_v6» : _root_.VeriSlopAST.«Stats») => (_root_.VeriSlopAST.«State».«mk» (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (_root_.VeriSlopAST.«State».«previous» «_v5»)) (@_root_.List.append _root_.VeriSlopAST.«Output» (_root_.VeriSlopAST.«State».«rows» «_v5») ([(_root_.VeriSlopAST.«Output».«mk» «_v2» (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Stats».«count» «_v6») (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")) (_root_.VeriSlopAST.«State».«previous» «_v5») (@_root_.Option.none _root_.Int))))] : (_root_.List _root_.VeriSlopAST.«Output»))))) «_v3» ([(@_root_.List.foldl _root_.VeriSlopAST.«Stats» _root_.VeriSlopAST.«Event» (fun («_v5» : _root_.VeriSlopAST.«Stats») («_v6» : _root_.VeriSlopAST.«Event») => (@_root_.cond _root_.VeriSlopAST.«Stats» (_root_.Decidable.decide (((_root_.VeriSlopAST.«Event».«group» «_v6») = «_v2») ∧ (((_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) ≤ (_root_.VeriSlopAST.«Event».«time» «_v6»)) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.Int.add (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Input».«width» «_v0»))) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ ((@_root_.Option.isSome _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6»)) = _root_.Bool.true)))))) (_root_.VeriSlopAST.«Stats».«mk» (_root_.Nat.add (_root_.VeriSlopAST.«Stats».«count» «_v5») (1 : _root_.Nat)) (_root_.Int.add (_root_.VeriSlopAST.«Stats».«sum» «_v5») (@_root_.Option.getD _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6») (_root_.Int.ofNat 0)))) «_v5»)) (_root_.VeriSlopAST.«Stats».«mk» (0 : _root_.Nat) (_root_.Int.ofNat 0)) (_root_.VeriSlopAST.«Input».«events» «_v0»))] : (_root_.List _root_.VeriSlopAST.«Stats»)))) (_root_.VeriSlopAST.«State».«mk» (@_root_.Option.none _root_.Int) ([] : (_root_.List _root_.VeriSlopAST.«Output»))) (_root_.List.range (_root_.Int.toNat (_root_.Int.fdiv (_root_.Int.sub (_root_.Int.add (_root_.Int.sub (_root_.VeriSlopAST.«Input».«end» «_v0») (_root_.VeriSlopAST.«Input».«start» «_v0»)) (_root_.VeriSlopAST.«Input».«width» «_v0»)) (_root_.Int.ofNat 1)) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) ([] : (_root_.List _root_.VeriSlopAST.«Output»)) (@_root_.List.mergeSort _root_.String (@_root_.List.eraseDups _root_.String (@_root_.instBEqOfDecidableEq _root_.String _root_.instDecidableEqString) (@_root_.List.map _root_.VeriSlopAST.«Event» _root_.String (fun («_v1» : _root_.VeriSlopAST.«Event») => (_root_.VeriSlopAST.«Event».«group» «_v1»)) (_root_.VeriSlopAST.«Input».«events» «_v0»))) (fun (_vs_left _vs_right : _root_.String) => _root_.Decidable.decide (_vs_left ≤ _vs_right))))))) ∧ (_root_.VeriSlop.Source.Contract _root_.VeriSlopAST.«SolveSource»)) := by sorry
theorem «_vs_value_complete_aggregation» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«valid_input» «_v0») → ((_root_.VeriSlopAST.«solve» «_v0») = (@_root_.List.foldl (_root_.List _root_.VeriSlopAST.«Output») _root_.String (fun («_v1» : (_root_.List _root_.VeriSlopAST.«Output»)) («_v2» : _root_.String) => (@_root_.List.append _root_.VeriSlopAST.«Output» «_v1» (_root_.VeriSlopAST.«State».«rows» (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.Nat (fun («_v3» : _root_.VeriSlopAST.«State») («_v4» : _root_.Nat) => (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.VeriSlopAST.«Stats» (fun («_v5» : _root_.VeriSlopAST.«State») («_v6» : _root_.VeriSlopAST.«Stats») => (_root_.VeriSlopAST.«State».«mk» (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (_root_.VeriSlopAST.«State».«previous» «_v5»)) (@_root_.List.append _root_.VeriSlopAST.«Output» (_root_.VeriSlopAST.«State».«rows» «_v5») ([(_root_.VeriSlopAST.«Output».«mk» «_v2» (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Stats».«count» «_v6») (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")) (_root_.VeriSlopAST.«State».«previous» «_v5») (@_root_.Option.none _root_.Int))))] : (_root_.List _root_.VeriSlopAST.«Output»))))) «_v3» ([(@_root_.List.foldl _root_.VeriSlopAST.«Stats» _root_.VeriSlopAST.«Event» (fun («_v5» : _root_.VeriSlopAST.«Stats») («_v6» : _root_.VeriSlopAST.«Event») => (@_root_.cond _root_.VeriSlopAST.«Stats» (_root_.Decidable.decide (((_root_.VeriSlopAST.«Event».«group» «_v6») = «_v2») ∧ (((_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) ≤ (_root_.VeriSlopAST.«Event».«time» «_v6»)) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.Int.add (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Input».«width» «_v0»))) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ ((@_root_.Option.isSome _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6»)) = _root_.Bool.true)))))) (_root_.VeriSlopAST.«Stats».«mk» (_root_.Nat.add (_root_.VeriSlopAST.«Stats».«count» «_v5») (1 : _root_.Nat)) (_root_.Int.add (_root_.VeriSlopAST.«Stats».«sum» «_v5») (@_root_.Option.getD _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6») (_root_.Int.ofNat 0)))) «_v5»)) (_root_.VeriSlopAST.«Stats».«mk» (0 : _root_.Nat) (_root_.Int.ofNat 0)) (_root_.VeriSlopAST.«Input».«events» «_v0»))] : (_root_.List _root_.VeriSlopAST.«Stats»)))) (_root_.VeriSlopAST.«State».«mk» (@_root_.Option.none _root_.Int) ([] : (_root_.List _root_.VeriSlopAST.«Output»))) (_root_.List.range (_root_.Int.toNat (_root_.Int.fdiv (_root_.Int.sub (_root_.Int.add (_root_.Int.sub (_root_.VeriSlopAST.«Input».«end» «_v0») (_root_.VeriSlopAST.«Input».«start» «_v0»)) (_root_.VeriSlopAST.«Input».«width» «_v0»)) (_root_.Int.ofNat 1)) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) ([] : (_root_.List _root_.VeriSlopAST.«Output»)) (@_root_.List.mergeSort _root_.String (@_root_.List.eraseDups _root_.String (@_root_.instBEqOfDecidableEq _root_.String _root_.instDecidableEqString) (@_root_.List.map _root_.VeriSlopAST.«Event» _root_.String (fun («_v1» : _root_.VeriSlopAST.«Event») => (_root_.VeriSlopAST.«Event».«group» «_v1»)) (_root_.VeriSlopAST.«Input».«events» «_v0»))) (fun (_vs_left _vs_right : _root_.String) => _root_.Decidable.decide (_vs_left ≤ _vs_right))))))) := by exact _root_.VeriSlopAST.«complete_aggregation».1
theorem «input_inhabited» : (∃ («_v0» : _root_.VeriSlopAST.«Input»), (_root_.VeriSlopAST.«valid_input» «_v0»)) := by sorry
theorem «source_properties» : (_root_.VeriSlop.Source.Contract _root_.VeriSlopAST.«SolveSource») := by sorry
end VeriSlopAST
