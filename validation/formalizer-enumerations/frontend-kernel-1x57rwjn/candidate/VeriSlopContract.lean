import Std
namespace VeriSlopAST
inductive «Alpha» where
  | «alpha»
  | «beta»
  deriving _root_.DecidableEq
inductive «Beta» where
  | «alpha»
  | «beta»
  deriving _root_.DecidableEq
inductive «Gamma» where
  | «first»
  | «second»
  | «third»
  deriving _root_.DecidableEq
structure «Inner» where
  «pick» : _root_.VeriSlopAST.«Gamma»
structure «Packet» where
  «mode» : _root_.VeriSlopAST.«Alpha»
  «choices» : (_root_.List _root_.VeriSlopAST.«Gamma»)
  «optional» : (_root_.Option _root_.VeriSlopAST.«Inner»)
  «outcome» : (_root_.Except _root_.VeriSlopAST.«Beta» _root_.VeriSlopAST.«Gamma»)
@[reducible] def «isAlpha» («_v0» : _root_.VeriSlopAST.«Alpha») : Prop := («_v0» = _root_.VeriSlopAST.«Alpha».«alpha»)
theorem «_vs_predicate_isAlpha» («_v0» : _root_.VeriSlopAST.«Alpha») : ((_root_.VeriSlopAST.«isAlpha» «_v0») ↔ («_v0» = _root_.VeriSlopAST.«Alpha».«alpha»)) := by rfl
def «packet»  : _root_.VeriSlopAST.«Packet» := (_root_.VeriSlopAST.«Packet».«mk» _root_.VeriSlopAST.«Alpha».«alpha» ([_root_.VeriSlopAST.«Gamma».«first», _root_.VeriSlopAST.«Gamma».«third»] : (_root_.List _root_.VeriSlopAST.«Gamma»)) (@_root_.Option.some _root_.VeriSlopAST.«Inner» (_root_.VeriSlopAST.«Inner».«mk» _root_.VeriSlopAST.«Gamma».«second»)) (@_root_.Except.ok _root_.VeriSlopAST.«Beta» _root_.VeriSlopAST.«Gamma» _root_.VeriSlopAST.«Gamma».«third»))
theorem «_vs_body_packet» : ((_root_.VeriSlopAST.«packet») = (_root_.VeriSlopAST.«Packet».«mk» _root_.VeriSlopAST.«Alpha».«alpha» ([_root_.VeriSlopAST.«Gamma».«first», _root_.VeriSlopAST.«Gamma».«third»] : (_root_.List _root_.VeriSlopAST.«Gamma»)) (@_root_.Option.some _root_.VeriSlopAST.«Inner» (_root_.VeriSlopAST.«Inner».«mk» _root_.VeriSlopAST.«Gamma».«second»)) (@_root_.Except.ok _root_.VeriSlopAST.«Beta» _root_.VeriSlopAST.«Gamma» _root_.VeriSlopAST.«Gamma».«third»))) := by intros; rfl
def «sameAlpha» («_v0» : _root_.VeriSlopAST.«Alpha») («_v1» : _root_.VeriSlopAST.«Alpha») : _root_.Bool := (@_root_.Decidable.decide («_v0» = «_v1») (_root_.VeriSlopAST.«instDecidableEqAlpha» «_v0» «_v1»))
theorem «_vs_body_sameAlpha» : (∀ («_v0» : _root_.VeriSlopAST.«Alpha»), (∀ («_v1» : _root_.VeriSlopAST.«Alpha»), ((_root_.VeriSlopAST.«sameAlpha» «_v0» «_v1») = (@_root_.Decidable.decide («_v0» = «_v1») (_root_.VeriSlopAST.«instDecidableEqAlpha» «_v0» «_v1»))))) := by intros; rfl
def «sameGamma» («_v0» : _root_.VeriSlopAST.«Gamma») («_v1» : _root_.VeriSlopAST.«Gamma») : _root_.Bool := (@_root_.Decidable.decide («_v0» = «_v1») (_root_.VeriSlopAST.«instDecidableEqGamma» «_v0» «_v1»))
theorem «_vs_body_sameGamma» : (∀ («_v0» : _root_.VeriSlopAST.«Gamma»), (∀ («_v1» : _root_.VeriSlopAST.«Gamma»), ((_root_.VeriSlopAST.«sameGamma» «_v0» «_v1») = (@_root_.Decidable.decide («_v0» = «_v1») (_root_.VeriSlopAST.«instDecidableEqGamma» «_v0» «_v1»))))) := by intros; rfl
def «switchAlpha» («_v0» : _root_.VeriSlopAST.«Alpha») : _root_.VeriSlopAST.«Gamma» := (@_root_.cond _root_.VeriSlopAST.«Gamma» (@_root_.Decidable.decide («_v0» = _root_.VeriSlopAST.«Alpha».«alpha») (_root_.VeriSlopAST.«instDecidableEqAlpha» «_v0» _root_.VeriSlopAST.«Alpha».«alpha»)) _root_.VeriSlopAST.«Gamma».«first» _root_.VeriSlopAST.«Gamma».«third»)
theorem «_vs_body_switchAlpha» : (∀ («_v0» : _root_.VeriSlopAST.«Alpha»), ((_root_.VeriSlopAST.«switchAlpha» «_v0») = (@_root_.cond _root_.VeriSlopAST.«Gamma» (@_root_.Decidable.decide («_v0» = _root_.VeriSlopAST.«Alpha».«alpha») (_root_.VeriSlopAST.«instDecidableEqAlpha» «_v0» _root_.VeriSlopAST.«Alpha».«alpha»)) _root_.VeriSlopAST.«Gamma».«first» _root_.VeriSlopAST.«Gamma».«third»))) := by intros; rfl
theorem «Alpha_alpha_alpha» : ((_root_.VeriSlopAST.«sameAlpha» _root_.VeriSlopAST.«Alpha».«alpha» _root_.VeriSlopAST.«Alpha».«alpha») = _root_.Bool.true) := by sorry
theorem «Alpha_alpha_beta» : ((_root_.VeriSlopAST.«sameAlpha» _root_.VeriSlopAST.«Alpha».«alpha» _root_.VeriSlopAST.«Alpha».«beta») = _root_.Bool.false) := by sorry
theorem «Alpha_beta_alpha» : ((_root_.VeriSlopAST.«sameAlpha» _root_.VeriSlopAST.«Alpha».«beta» _root_.VeriSlopAST.«Alpha».«alpha») = _root_.Bool.false) := by sorry
theorem «Alpha_beta_beta» : ((_root_.VeriSlopAST.«sameAlpha» _root_.VeriSlopAST.«Alpha».«beta» _root_.VeriSlopAST.«Alpha».«beta») = _root_.Bool.true) := by sorry
theorem «Gamma_first_first» : ((_root_.VeriSlopAST.«sameGamma» _root_.VeriSlopAST.«Gamma».«first» _root_.VeriSlopAST.«Gamma».«first») = _root_.Bool.true) := by sorry
theorem «Gamma_first_second» : ((_root_.VeriSlopAST.«sameGamma» _root_.VeriSlopAST.«Gamma».«first» _root_.VeriSlopAST.«Gamma».«second») = _root_.Bool.false) := by sorry
theorem «Gamma_first_third» : ((_root_.VeriSlopAST.«sameGamma» _root_.VeriSlopAST.«Gamma».«first» _root_.VeriSlopAST.«Gamma».«third») = _root_.Bool.false) := by sorry
theorem «Gamma_second_first» : ((_root_.VeriSlopAST.«sameGamma» _root_.VeriSlopAST.«Gamma».«second» _root_.VeriSlopAST.«Gamma».«first») = _root_.Bool.false) := by sorry
theorem «Gamma_second_second» : ((_root_.VeriSlopAST.«sameGamma» _root_.VeriSlopAST.«Gamma».«second» _root_.VeriSlopAST.«Gamma».«second») = _root_.Bool.true) := by sorry
theorem «Gamma_second_third» : ((_root_.VeriSlopAST.«sameGamma» _root_.VeriSlopAST.«Gamma».«second» _root_.VeriSlopAST.«Gamma».«third») = _root_.Bool.false) := by sorry
theorem «Gamma_third_first» : ((_root_.VeriSlopAST.«sameGamma» _root_.VeriSlopAST.«Gamma».«third» _root_.VeriSlopAST.«Gamma».«first») = _root_.Bool.false) := by sorry
theorem «Gamma_third_second» : ((_root_.VeriSlopAST.«sameGamma» _root_.VeriSlopAST.«Gamma».«third» _root_.VeriSlopAST.«Gamma».«second») = _root_.Bool.false) := by sorry
theorem «Gamma_third_third» : ((_root_.VeriSlopAST.«sameGamma» _root_.VeriSlopAST.«Gamma».«third» _root_.VeriSlopAST.«Gamma».«third») = _root_.Bool.true) := by sorry
theorem «branch_alpha» : ((_root_.VeriSlopAST.«switchAlpha» _root_.VeriSlopAST.«Alpha».«alpha») = _root_.VeriSlopAST.«Gamma».«first») := by sorry
theorem «branch_beta» : ((_root_.VeriSlopAST.«switchAlpha» _root_.VeriSlopAST.«Alpha».«beta») = _root_.VeriSlopAST.«Gamma».«third») := by sorry
theorem «inhabited» : (∃ («_v0» : _root_.VeriSlopAST.«Alpha»), (_root_.VeriSlopAST.«isAlpha» «_v0»)) := by sorry
theorem «reflexive» : (∀ («_v0» : _root_.VeriSlopAST.«Alpha»), («_v0» = «_v0»)) := by sorry
end VeriSlopAST
