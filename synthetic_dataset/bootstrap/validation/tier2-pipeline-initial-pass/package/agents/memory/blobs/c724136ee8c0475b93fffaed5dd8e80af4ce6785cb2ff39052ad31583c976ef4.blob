import Std
namespace VeriSlopAST
structure «Packet» where
  «amount» : _root_.Int
  «words» : (_root_.List _root_.String)
  «extra» : (_root_.Option _root_.Int)
def «shift» («_v0» : _root_.Int) : _root_.Int := (_root_.Int.add «_v0» (_root_.Int.negSucc 2))
theorem «_vs_body_shift» : (∀ («_v0» : _root_.Int), ((_root_.VeriSlopAST.«shift» «_v0») = (_root_.Int.add «_v0» (_root_.Int.negSucc 2)))) := by intros; rfl
def «solve» («_v0» : _root_.VeriSlopAST.«Packet») : _root_.Int := (_root_.Int.add (_root_.VeriSlopAST.«Packet».«amount» «_v0») (_root_.Int.negSucc 2))
theorem «_vs_body_solve» : (∀ («_v0» : _root_.VeriSlopAST.«Packet»), ((_root_.VeriSlopAST.«solve» «_v0») = (_root_.Int.add (_root_.VeriSlopAST.«Packet».«amount» «_v0») (_root_.Int.negSucc 2)))) := by intros; rfl
theorem «binder» : (∀ («_v0» : (_root_.List _root_.Int)), ((@_root_.List.map _root_.Int _root_.Int (fun («_v1» : _root_.Int) => (_root_.VeriSlopAST.«shift» «_v1»)) «_v0») = (@_root_.List.map _root_.Int _root_.Int (fun («_v1» : _root_.Int) => (_root_.Int.add «_v1» (_root_.Int.negSucc 2))) «_v0»))) := by sorry
theorem «result» : (∀ («_v0» : _root_.VeriSlopAST.«Packet»), ((_root_.VeriSlopAST.«solve» «_v0») = (_root_.Int.add (_root_.VeriSlopAST.«Packet».«amount» «_v0») (_root_.Int.negSucc 2)))) := by sorry
end VeriSlopAST
