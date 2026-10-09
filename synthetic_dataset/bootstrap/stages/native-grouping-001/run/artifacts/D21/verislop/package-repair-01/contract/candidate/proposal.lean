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
structure «Row» where
  «group» : _root_.String
  «start» : _root_.Int
  «count» : _root_.Nat
  «value» : (_root_.Option _root_.Int)
structure «State» where
  «previous» : (_root_.Option _root_.Int)
  «rows» : (_root_.List _root_.VeriSlopAST.«Row»)
structure «Stats» where
  «count» : _root_.Nat
  «sum» : _root_.Int
def «solve» («_v0» : _root_.VeriSlopAST.«Input») : (_root_.List _root_.VeriSlopAST.«Row») := (@_root_.List.foldl (_root_.List _root_.VeriSlopAST.«Row») _root_.String (fun («_v1» : (_root_.List _root_.VeriSlopAST.«Row»)) («_v2» : _root_.String) => (@_root_.List.append _root_.VeriSlopAST.«Row» «_v1» (_root_.VeriSlopAST.«State».«rows» (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.Nat (fun («_v3» : _root_.VeriSlopAST.«State») («_v4» : _root_.Nat) => (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.VeriSlopAST.«Stats» (fun («_v5» : _root_.VeriSlopAST.«State») («_v6» : _root_.VeriSlopAST.«Stats») => (_root_.VeriSlopAST.«State».«mk» (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (_root_.VeriSlopAST.«State».«previous» «_v3»)) (@_root_.List.append _root_.VeriSlopAST.«Row» (_root_.VeriSlopAST.«State».«rows» «_v3») ([(_root_.VeriSlopAST.«Row».«mk» «_v2» (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Stats».«count» «_v6») (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")) (_root_.VeriSlopAST.«State».«previous» «_v3») (@_root_.Option.none _root_.Int))))] : (_root_.List _root_.VeriSlopAST.«Row»))))) «_v3» ([(@_root_.List.foldl _root_.VeriSlopAST.«Stats» _root_.VeriSlopAST.«Event» (fun («_v5» : _root_.VeriSlopAST.«Stats») («_v6» : _root_.VeriSlopAST.«Event») => (@_root_.cond _root_.VeriSlopAST.«Stats» (_root_.Decidable.decide (((_root_.VeriSlopAST.«Event».«group» «_v6») = «_v2») ∧ (((@_root_.Option.isSome _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6»)) = _root_.Bool.true) ∧ (((_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) ≤ (_root_.VeriSlopAST.«Event».«time» «_v6»)) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ ((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.Int.add (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) (_root_.VeriSlopAST.«Stats».«mk» (_root_.Nat.add (_root_.VeriSlopAST.«Stats».«count» «_v5») (1 : _root_.Nat)) (_root_.Int.add (_root_.VeriSlopAST.«Stats».«sum» «_v5») (@_root_.Option.getD _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6») (_root_.Int.ofNat 0)))) «_v5»)) (_root_.VeriSlopAST.«Stats».«mk» (0 : _root_.Nat) (_root_.Int.ofNat 0)) (_root_.VeriSlopAST.«Input».«events» «_v0»))] : (_root_.List _root_.VeriSlopAST.«Stats»)))) (_root_.VeriSlopAST.«State».«mk» (@_root_.Option.none _root_.Int) ([] : (_root_.List _root_.VeriSlopAST.«Row»))) (_root_.List.range (_root_.Int.toNat (_root_.Int.fdiv (_root_.Int.sub (_root_.Int.add (_root_.Int.sub (_root_.VeriSlopAST.«Input».«end» «_v0») (_root_.VeriSlopAST.«Input».«start» «_v0»)) (_root_.VeriSlopAST.«Input».«width» «_v0»)) (_root_.Int.ofNat 1)) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) ([] : (_root_.List _root_.VeriSlopAST.«Row»)) (@_root_.List.mergeSort _root_.String (@_root_.List.eraseDups _root_.String (@_root_.instBEqOfDecidableEq _root_.String _root_.instDecidableEqString) (@_root_.List.map _root_.VeriSlopAST.«Event» _root_.String (fun («_v1» : _root_.VeriSlopAST.«Event») => (_root_.VeriSlopAST.«Event».«group» «_v1»)) (_root_.VeriSlopAST.«Input».«events» «_v0»))) (fun (_vs_left _vs_right : _root_.String) => _root_.Decidable.decide (_vs_left ≤ _vs_right))))
theorem «_vs_body_solve» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«solve» «_v0») = (@_root_.List.foldl (_root_.List _root_.VeriSlopAST.«Row») _root_.String (fun («_v1» : (_root_.List _root_.VeriSlopAST.«Row»)) («_v2» : _root_.String) => (@_root_.List.append _root_.VeriSlopAST.«Row» «_v1» (_root_.VeriSlopAST.«State».«rows» (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.Nat (fun («_v3» : _root_.VeriSlopAST.«State») («_v4» : _root_.Nat) => (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.VeriSlopAST.«Stats» (fun («_v5» : _root_.VeriSlopAST.«State») («_v6» : _root_.VeriSlopAST.«Stats») => (_root_.VeriSlopAST.«State».«mk» (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (_root_.VeriSlopAST.«State».«previous» «_v3»)) (@_root_.List.append _root_.VeriSlopAST.«Row» (_root_.VeriSlopAST.«State».«rows» «_v3») ([(_root_.VeriSlopAST.«Row».«mk» «_v2» (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Stats».«count» «_v6») (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")) (_root_.VeriSlopAST.«State».«previous» «_v3») (@_root_.Option.none _root_.Int))))] : (_root_.List _root_.VeriSlopAST.«Row»))))) «_v3» ([(@_root_.List.foldl _root_.VeriSlopAST.«Stats» _root_.VeriSlopAST.«Event» (fun («_v5» : _root_.VeriSlopAST.«Stats») («_v6» : _root_.VeriSlopAST.«Event») => (@_root_.cond _root_.VeriSlopAST.«Stats» (_root_.Decidable.decide (((_root_.VeriSlopAST.«Event».«group» «_v6») = «_v2») ∧ (((@_root_.Option.isSome _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6»)) = _root_.Bool.true) ∧ (((_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) ≤ (_root_.VeriSlopAST.«Event».«time» «_v6»)) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ ((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.Int.add (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) (_root_.VeriSlopAST.«Stats».«mk» (_root_.Nat.add (_root_.VeriSlopAST.«Stats».«count» «_v5») (1 : _root_.Nat)) (_root_.Int.add (_root_.VeriSlopAST.«Stats».«sum» «_v5») (@_root_.Option.getD _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6») (_root_.Int.ofNat 0)))) «_v5»)) (_root_.VeriSlopAST.«Stats».«mk» (0 : _root_.Nat) (_root_.Int.ofNat 0)) (_root_.VeriSlopAST.«Input».«events» «_v0»))] : (_root_.List _root_.VeriSlopAST.«Stats»)))) (_root_.VeriSlopAST.«State».«mk» (@_root_.Option.none _root_.Int) ([] : (_root_.List _root_.VeriSlopAST.«Row»))) (_root_.List.range (_root_.Int.toNat (_root_.Int.fdiv (_root_.Int.sub (_root_.Int.add (_root_.Int.sub (_root_.VeriSlopAST.«Input».«end» «_v0») (_root_.VeriSlopAST.«Input».«start» «_v0»)) (_root_.VeriSlopAST.«Input».«width» «_v0»)) (_root_.Int.ofNat 1)) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) ([] : (_root_.List _root_.VeriSlopAST.«Row»)) (@_root_.List.mergeSort _root_.String (@_root_.List.eraseDups _root_.String (@_root_.instBEqOfDecidableEq _root_.String _root_.instDecidableEqString) (@_root_.List.map _root_.VeriSlopAST.«Event» _root_.String (fun («_v1» : _root_.VeriSlopAST.«Event») => (_root_.VeriSlopAST.«Event».«group» «_v1»)) (_root_.VeriSlopAST.«Input».«events» «_v0»))) (fun (_vs_left _vs_right : _root_.String) => _root_.Decidable.decide (_vs_left ≤ _vs_right)))))) := by intros; rfl
@[reducible] def «valid_input» («_v0» : _root_.VeriSlopAST.«Input») : Prop := (((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«width» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«start» «_v0») ≤ (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«fill» «_v0») = "none") ∨ ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous"))))
theorem «_vs_predicate_valid_input» («_v0» : _root_.VeriSlopAST.«Input») : ((_root_.VeriSlopAST.«valid_input» «_v0») ↔ (((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«width» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«start» «_v0») ≤ (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«fill» «_v0») = "none") ∨ ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous"))))) := by rfl
def «python_boundary» : _root_.VeriSlop.Native.NativeDefinition (_root_.VeriSlopAST.«Input» → (_root_.List _root_.VeriSlopAST.«Row»)) := ⟨_root_.VeriSlopAST.«solve», [(_root_.VeriSlop.Native.NativeRequirement.entry "solution.py" "solve" 1), _root_.VeriSlop.Native.NativeRequirement.pureJson, _root_.VeriSlop.Native.NativeRequirement.standardRuntimeOnly, _root_.VeriSlop.Native.NativeRequirement.noExternalIO, _root_.VeriSlop.Native.NativeRequirement.deterministic, _root_.VeriSlop.Native.NativeRequirement.inputPreserved]⟩
theorem «aggregation_contract» : ((∀ («_v0» : _root_.VeriSlopAST.«Input»), ((((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«width» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«start» «_v0») ≤ (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«fill» «_v0») = "none") ∨ ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")))) → ((_root_.VeriSlopAST.«solve» «_v0») = (@_root_.List.foldl (_root_.List _root_.VeriSlopAST.«Row») _root_.String (fun («_v1» : (_root_.List _root_.VeriSlopAST.«Row»)) («_v2» : _root_.String) => (@_root_.List.append _root_.VeriSlopAST.«Row» «_v1» (_root_.VeriSlopAST.«State».«rows» (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.Nat (fun («_v3» : _root_.VeriSlopAST.«State») («_v4» : _root_.Nat) => (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.VeriSlopAST.«Stats» (fun («_v5» : _root_.VeriSlopAST.«State») («_v6» : _root_.VeriSlopAST.«Stats») => (_root_.VeriSlopAST.«State».«mk» (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (_root_.VeriSlopAST.«State».«previous» «_v3»)) (@_root_.List.append _root_.VeriSlopAST.«Row» (_root_.VeriSlopAST.«State».«rows» «_v3») ([(_root_.VeriSlopAST.«Row».«mk» «_v2» (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Stats».«count» «_v6») (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")) (_root_.VeriSlopAST.«State».«previous» «_v3») (@_root_.Option.none _root_.Int))))] : (_root_.List _root_.VeriSlopAST.«Row»))))) «_v3» ([(@_root_.List.foldl _root_.VeriSlopAST.«Stats» _root_.VeriSlopAST.«Event» (fun («_v5» : _root_.VeriSlopAST.«Stats») («_v6» : _root_.VeriSlopAST.«Event») => (@_root_.cond _root_.VeriSlopAST.«Stats» (_root_.Decidable.decide (((_root_.VeriSlopAST.«Event».«group» «_v6») = «_v2») ∧ (((@_root_.Option.isSome _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6»)) = _root_.Bool.true) ∧ (((_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) ≤ (_root_.VeriSlopAST.«Event».«time» «_v6»)) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ ((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.Int.add (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) (_root_.VeriSlopAST.«Stats».«mk» (_root_.Nat.add (_root_.VeriSlopAST.«Stats».«count» «_v5») (1 : _root_.Nat)) (_root_.Int.add (_root_.VeriSlopAST.«Stats».«sum» «_v5») (@_root_.Option.getD _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6») (_root_.Int.ofNat 0)))) «_v5»)) (_root_.VeriSlopAST.«Stats».«mk» (0 : _root_.Nat) (_root_.Int.ofNat 0)) (_root_.VeriSlopAST.«Input».«events» «_v0»))] : (_root_.List _root_.VeriSlopAST.«Stats»)))) (_root_.VeriSlopAST.«State».«mk» (@_root_.Option.none _root_.Int) ([] : (_root_.List _root_.VeriSlopAST.«Row»))) (_root_.List.range (_root_.Int.toNat (_root_.Int.fdiv (_root_.Int.sub (_root_.Int.add (_root_.Int.sub (_root_.VeriSlopAST.«Input».«end» «_v0») (_root_.VeriSlopAST.«Input».«start» «_v0»)) (_root_.VeriSlopAST.«Input».«width» «_v0»)) (_root_.Int.ofNat 1)) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) ([] : (_root_.List _root_.VeriSlopAST.«Row»)) (@_root_.List.mergeSort _root_.String (@_root_.List.eraseDups _root_.String (@_root_.instBEqOfDecidableEq _root_.String _root_.instDecidableEqString) (@_root_.List.map _root_.VeriSlopAST.«Event» _root_.String (fun («_v1» : _root_.VeriSlopAST.«Event») => (_root_.VeriSlopAST.«Event».«group» «_v1»)) (_root_.VeriSlopAST.«Input».«events» «_v0»))) (fun (_vs_left _vs_right : _root_.String) => _root_.Decidable.decide (_vs_left ≤ _vs_right))))))) ∧ (_root_.VeriSlop.Native.Contract _root_.VeriSlopAST.«python_boundary»)) := by sorry
theorem «_vs_value_aggregation_contract» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«width» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«start» «_v0») ≤ (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«fill» «_v0») = "none") ∨ ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")))) → ((_root_.VeriSlopAST.«solve» «_v0») = (@_root_.List.foldl (_root_.List _root_.VeriSlopAST.«Row») _root_.String (fun («_v1» : (_root_.List _root_.VeriSlopAST.«Row»)) («_v2» : _root_.String) => (@_root_.List.append _root_.VeriSlopAST.«Row» «_v1» (_root_.VeriSlopAST.«State».«rows» (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.Nat (fun («_v3» : _root_.VeriSlopAST.«State») («_v4» : _root_.Nat) => (@_root_.List.foldl _root_.VeriSlopAST.«State» _root_.VeriSlopAST.«Stats» (fun («_v5» : _root_.VeriSlopAST.«State») («_v6» : _root_.VeriSlopAST.«Stats») => (_root_.VeriSlopAST.«State».«mk» (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (_root_.VeriSlopAST.«State».«previous» «_v3»)) (@_root_.List.append _root_.VeriSlopAST.«Row» (_root_.VeriSlopAST.«State».«rows» «_v3») ([(_root_.VeriSlopAST.«Row».«mk» «_v2» (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Stats».«count» «_v6») (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((0 : _root_.Nat) < (_root_.VeriSlopAST.«Stats».«count» «_v6»))) (@_root_.Option.some _root_.Int (_root_.VeriSlopAST.«Stats».«sum» «_v6»)) (@_root_.cond (_root_.Option _root_.Int) (_root_.Decidable.decide ((_root_.VeriSlopAST.«Input».«fill» «_v0») = "previous")) (_root_.VeriSlopAST.«State».«previous» «_v3») (@_root_.Option.none _root_.Int))))] : (_root_.List _root_.VeriSlopAST.«Row»))))) «_v3» ([(@_root_.List.foldl _root_.VeriSlopAST.«Stats» _root_.VeriSlopAST.«Event» (fun («_v5» : _root_.VeriSlopAST.«Stats») («_v6» : _root_.VeriSlopAST.«Event») => (@_root_.cond _root_.VeriSlopAST.«Stats» (_root_.Decidable.decide (((_root_.VeriSlopAST.«Event».«group» «_v6») = «_v2») ∧ (((@_root_.Option.isSome _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6»)) = _root_.Bool.true) ∧ (((_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) ≤ (_root_.VeriSlopAST.«Event».«time» «_v6»)) ∧ (((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.VeriSlopAST.«Input».«end» «_v0»)) ∧ ((_root_.VeriSlopAST.«Event».«time» «_v6») < (_root_.Int.add (_root_.Int.add (_root_.VeriSlopAST.«Input».«start» «_v0») (_root_.Int.mul (_root_.Int.ofNat «_v4») (_root_.VeriSlopAST.«Input».«width» «_v0»))) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) (_root_.VeriSlopAST.«Stats».«mk» (_root_.Nat.add (_root_.VeriSlopAST.«Stats».«count» «_v5») (1 : _root_.Nat)) (_root_.Int.add (_root_.VeriSlopAST.«Stats».«sum» «_v5») (@_root_.Option.getD _root_.Int (_root_.VeriSlopAST.«Event».«value» «_v6») (_root_.Int.ofNat 0)))) «_v5»)) (_root_.VeriSlopAST.«Stats».«mk» (0 : _root_.Nat) (_root_.Int.ofNat 0)) (_root_.VeriSlopAST.«Input».«events» «_v0»))] : (_root_.List _root_.VeriSlopAST.«Stats»)))) (_root_.VeriSlopAST.«State».«mk» (@_root_.Option.none _root_.Int) ([] : (_root_.List _root_.VeriSlopAST.«Row»))) (_root_.List.range (_root_.Int.toNat (_root_.Int.fdiv (_root_.Int.sub (_root_.Int.add (_root_.Int.sub (_root_.VeriSlopAST.«Input».«end» «_v0») (_root_.VeriSlopAST.«Input».«start» «_v0»)) (_root_.VeriSlopAST.«Input».«width» «_v0»)) (_root_.Int.ofNat 1)) (_root_.VeriSlopAST.«Input».«width» «_v0»)))))))) ([] : (_root_.List _root_.VeriSlopAST.«Row»)) (@_root_.List.mergeSort _root_.String (@_root_.List.eraseDups _root_.String (@_root_.instBEqOfDecidableEq _root_.String _root_.instDecidableEqString) (@_root_.List.map _root_.VeriSlopAST.«Event» _root_.String (fun («_v1» : _root_.VeriSlopAST.«Event») => (_root_.VeriSlopAST.«Event».«group» «_v1»)) (_root_.VeriSlopAST.«Input».«events» «_v0»))) (fun (_vs_left _vs_right : _root_.String) => _root_.Decidable.decide (_vs_left ≤ _vs_right))))))) := by exact _root_.VeriSlopAST.«aggregation_contract».1
end VeriSlopAST
