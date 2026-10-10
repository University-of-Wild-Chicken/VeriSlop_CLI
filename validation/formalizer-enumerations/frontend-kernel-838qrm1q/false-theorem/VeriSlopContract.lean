import Std
namespace VeriSlopAST
inductive «Alpha» where
  | «alpha»
  | «beta»
  deriving _root_.DecidableEq
theorem «falseChoice» : (_root_.VeriSlopAST.«Alpha».«alpha» = _root_.VeriSlopAST.«Alpha».«beta») := by decide
end VeriSlopAST
