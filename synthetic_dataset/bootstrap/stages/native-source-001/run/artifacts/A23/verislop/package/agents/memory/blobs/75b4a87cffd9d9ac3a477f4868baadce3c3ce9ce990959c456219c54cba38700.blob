import Std
namespace VeriSlopAST
structure «Input» where
  «n» : _root_.Int
  «m» : _root_.Int
  «a» : _root_.Int
  «b» : _root_.Int
def «solve» («_v0» : _root_.VeriSlopAST.«Input») : _root_.Int := (_root_.List.sum (@_root_.List.map _root_.Nat _root_.Int (fun («_v1» : _root_.Nat) => (_root_.Int.fdiv (_root_.Int.add (_root_.Int.mul (_root_.VeriSlopAST.«Input».«a» «_v0») (_root_.Int.ofNat «_v1»)) (_root_.VeriSlopAST.«Input».«b» «_v0»)) (_root_.VeriSlopAST.«Input».«m» «_v0»))) (_root_.List.range (_root_.Int.toNat (_root_.VeriSlopAST.«Input».«n» «_v0»)))))
theorem «_vs_body_solve» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«solve» «_v0») = (_root_.List.sum (@_root_.List.map _root_.Nat _root_.Int (fun («_v1» : _root_.Nat) => (_root_.Int.fdiv (_root_.Int.add (_root_.Int.mul (_root_.VeriSlopAST.«Input».«a» «_v0») (_root_.Int.ofNat «_v1»)) (_root_.VeriSlopAST.«Input».«b» «_v0»)) (_root_.VeriSlopAST.«Input».«m» «_v0»))) (_root_.List.range (_root_.Int.toNat (_root_.VeriSlopAST.«Input».«n» «_v0»))))))) := by intros; rfl
@[reducible] def «valid» («_v0» : _root_.VeriSlopAST.«Input») : Prop := (((_root_.Int.ofNat 0) ≤ (_root_.VeriSlopAST.«Input».«n» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«n» «_v0») ≤ (_root_.Int.ofNat 500)) ∧ ((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«m» «_v0»))))
theorem «_vs_predicate_valid» («_v0» : _root_.VeriSlopAST.«Input») : ((_root_.VeriSlopAST.«valid» «_v0») ↔ (((_root_.Int.ofNat 0) ≤ (_root_.VeriSlopAST.«Input».«n» «_v0»)) ∧ (((_root_.VeriSlopAST.«Input».«n» «_v0») ≤ (_root_.Int.ofNat 500)) ∧ ((_root_.Int.ofNat 0) < (_root_.VeriSlopAST.«Input».«m» «_v0»))))) := by rfl
theorem «exact_behavior» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«solve» «_v0») = (_root_.List.sum (@_root_.List.map _root_.Nat _root_.Int (fun («_v1» : _root_.Nat) => (_root_.Int.fdiv (_root_.Int.add (_root_.Int.mul (_root_.VeriSlopAST.«Input».«a» «_v0») (_root_.Int.ofNat «_v1»)) (_root_.VeriSlopAST.«Input».«b» «_v0»)) (_root_.VeriSlopAST.«Input».«m» «_v0»))) (_root_.List.range (_root_.Int.toNat (_root_.VeriSlopAST.«Input».«n» «_v0»))))))) := by sorry
theorem «examples» : (((_root_.VeriSlopAST.«solve» (_root_.VeriSlopAST.«Input».«mk» (_root_.Int.ofNat 4) (_root_.Int.ofNat 3) (_root_.Int.negSucc 1) (_root_.Int.ofNat 1))) = (_root_.Int.negSucc 3)) ∧ ((_root_.VeriSlopAST.«solve» (_root_.VeriSlopAST.«Input».«mk» (_root_.Int.ofNat 0) (_root_.Int.ofNat 7) (_root_.Int.ofNat 100) (_root_.Int.negSucc 98))) = (_root_.Int.ofNat 0))) := by sorry
theorem «valid_inhabited» : (∃ («_v0» : _root_.VeriSlopAST.«Input»), (_root_.VeriSlopAST.«valid» «_v0»)) := by sorry
end VeriSlopAST
