import Std
-- Fixture prerequisite: pinned Std does not provide Except DecidableEq.
deriving instance DecidableEq for Except
namespace VeriSlopAST
inductive «Token» where
  | «amber»
  | «violet»
  deriving _root_.DecidableEq
structure «ZLeaf» where
  «token» : _root_.VeriSlopAST.«Token»
  «amount» : _root_.Nat
structure «AParcel» where
  «leaf» : _root_.VeriSlopAST.«ZLeaf»
  «spare» : (_root_.Option _root_.VeriSlopAST.«Token»)
  «history» : (_root_.List _root_.VeriSlopAST.«ZLeaf»)
  «outcome» : (_root_.Except _root_.VeriSlopAST.«Token» _root_.VeriSlopAST.«ZLeaf»)
def «swap» («_v0» : _root_.VeriSlopAST.«Token») : _root_.VeriSlopAST.«Token» := (@_root_.cond _root_.VeriSlopAST.«Token» (@_root_.Decidable.decide («_v0» = _root_.VeriSlopAST.«Token».«amber») (_root_.VeriSlopAST.«instDecidableEqToken» «_v0» _root_.VeriSlopAST.«Token».«amber»)) _root_.VeriSlopAST.«Token».«violet» _root_.VeriSlopAST.«Token».«amber»)
theorem «_vs_body_swap» : (∀ («_v0» : _root_.VeriSlopAST.«Token»), ((_root_.VeriSlopAST.«swap» «_v0») = (@_root_.cond _root_.VeriSlopAST.«Token» (@_root_.Decidable.decide («_v0» = _root_.VeriSlopAST.«Token».«amber») (_root_.VeriSlopAST.«instDecidableEqToken» «_v0» _root_.VeriSlopAST.«Token».«amber»)) _root_.VeriSlopAST.«Token».«violet» _root_.VeriSlopAST.«Token».«amber»))) := by intros; rfl
def «carry» («_v0» : _root_.VeriSlopAST.«AParcel») : _root_.VeriSlopAST.«AParcel» := (_root_.VeriSlopAST.«AParcel».«mk» (_root_.VeriSlopAST.«ZLeaf».«mk» (_root_.VeriSlopAST.«swap» (_root_.VeriSlopAST.«ZLeaf».«token» (_root_.VeriSlopAST.«AParcel».«leaf» «_v0»))) (_root_.VeriSlopAST.«ZLeaf».«amount» (_root_.VeriSlopAST.«AParcel».«leaf» «_v0»))) (_root_.VeriSlopAST.«AParcel».«spare» «_v0») (_root_.VeriSlopAST.«AParcel».«history» «_v0») (_root_.VeriSlopAST.«AParcel».«outcome» «_v0»))
theorem «_vs_body_carry» : (∀ («_v0» : _root_.VeriSlopAST.«AParcel»), ((_root_.VeriSlopAST.«carry» «_v0») = (_root_.VeriSlopAST.«AParcel».«mk» (_root_.VeriSlopAST.«ZLeaf».«mk» (_root_.VeriSlopAST.«swap» (_root_.VeriSlopAST.«ZLeaf».«token» (_root_.VeriSlopAST.«AParcel».«leaf» «_v0»))) (_root_.VeriSlopAST.«ZLeaf».«amount» (_root_.VeriSlopAST.«AParcel».«leaf» «_v0»))) (_root_.VeriSlopAST.«AParcel».«spare» «_v0») (_root_.VeriSlopAST.«AParcel».«history» «_v0») (_root_.VeriSlopAST.«AParcel».«outcome» «_v0»)))) := by intros; rfl
theorem «rightToken» : (∀ («_v0» : _root_.VeriSlopAST.«Token»), ((_root_.VeriSlopAST.«swap» (_root_.VeriSlopAST.«swap» «_v0»)) = «_v0»)) := by sorry
end VeriSlopAST
