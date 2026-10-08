import Std
namespace VeriSlopAST
structure «Input» where
  «labels» : (_root_.List _root_.String)
  «prefix» : _root_.String
structure «Output» where
  «labels» : (_root_.List _root_.String)
  «count» : _root_.Nat
def «processed» («_v0» : _root_.VeriSlopAST.«Input») : (_root_.List _root_.String) := (@_root_.List.map _root_.String _root_.String (fun («_v1» : _root_.String) => (_root_.String.append (_root_.VeriSlopAST.«Input».«prefix» «_v0») «_v1»)) (@_root_.List.filter _root_.String (fun («_v1» : _root_.String) => (_root_.String.isEmpty «_v1»)) (_root_.VeriSlopAST.«Input».«labels» «_v0»)))
theorem «_vs_body_processed» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«processed» «_v0») = (@_root_.List.map _root_.String _root_.String (fun («_v1» : _root_.String) => (_root_.String.append (_root_.VeriSlopAST.«Input».«prefix» «_v0») «_v1»)) (@_root_.List.filter _root_.String (fun («_v1» : _root_.String) => (_root_.String.isEmpty «_v1»)) (_root_.VeriSlopAST.«Input».«labels» «_v0»))))) := by intros; rfl
def «solve» («_v0» : _root_.VeriSlopAST.«Input») : _root_.VeriSlopAST.«Output» := (_root_.VeriSlopAST.«Output».«mk» (_root_.VeriSlopAST.«processed» «_v0») (@_root_.List.length _root_.String (_root_.VeriSlopAST.«processed» «_v0»)))
theorem «_vs_body_solve» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), ((_root_.VeriSlopAST.«solve» «_v0») = (_root_.VeriSlopAST.«Output».«mk» (_root_.VeriSlopAST.«processed» «_v0») (@_root_.List.length _root_.String (_root_.VeriSlopAST.«processed» «_v0»))))) := by intros; rfl
theorem «solve_spec» : (∀ («_v0» : _root_.VeriSlopAST.«Input»), (((_root_.VeriSlopAST.«Output».«labels» (_root_.VeriSlopAST.«solve» «_v0»)) = (@_root_.List.map _root_.String _root_.String (fun («_v1» : _root_.String) => (_root_.String.append (_root_.VeriSlopAST.«Input».«prefix» «_v0») «_v1»)) (@_root_.List.filter _root_.String (fun («_v1» : _root_.String) => (_root_.String.isEmpty «_v1»)) (_root_.VeriSlopAST.«Input».«labels» «_v0»)))) ∧ ((_root_.VeriSlopAST.«Output».«count» (_root_.VeriSlopAST.«solve» «_v0»)) = (@_root_.List.length _root_.String (@_root_.List.map _root_.String _root_.String (fun («_v1» : _root_.String) => (_root_.String.append (_root_.VeriSlopAST.«Input».«prefix» «_v0») «_v1»)) (@_root_.List.filter _root_.String (fun («_v1» : _root_.String) => (_root_.String.isEmpty «_v1»)) (_root_.VeriSlopAST.«Input».«labels» «_v0»))))))) := by sorry
end VeriSlopAST
