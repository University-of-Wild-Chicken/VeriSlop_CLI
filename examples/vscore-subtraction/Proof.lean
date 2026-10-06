import VeriSlopBridgeGoal

/-!
# Candidate refinement proof for checked subtraction

The generated goal supplies exact source decoding, typing, input coverage and the
transport of all four accepted guarantees. This theorem handles every Nat argument.
-/

namespace VeriSlopBridgeProof

open VeriSlopBridgeGoal in
theorem refines_subtractIfEnough : Refines_subtractIfEnough := by
  intro balance amount
  unfold impl_subtractIfEnough VeriSlop.CheckedSubtraction.subtractIfEnough
  by_cases h : amount ≤ balance <;>
    simp [h, rawProgram, VSCore.evalEntry, VSCore.findEntry, VSCore.evalExpr, VSCore.evalBin,
      adapter_0, adapter_1, adapter_2, name_0,
      VSCore.natAdapter, VSCore.enumAdapter, VSCore.exceptAdapter]

theorem edge : VeriSlopBridgeGoal.EdgeProp :=
  VeriSlopBridgeGoal.edge_of_refines refines_subtractIfEnough

/- Concrete fixture checks evaluate the delivered source in the normative Lean semantics.
They are not runtime-campaign evidence. The final value is greater than 2^64. -/
open VeriSlopBridgeGoal in
theorem zero_case : VSCore.evalEntry rawProgram "subtractIfEnough" [.nat 0, .nat 0] =
    .ok (.ok (.nat 0)) := by rfl

open VeriSlopBridgeGoal in
theorem equality_case : VSCore.evalEntry rawProgram "subtractIfEnough" [.nat 7, .nat 7] =
    .ok (.ok (.nat 0)) := by rfl

open VeriSlopBridgeGoal in
theorem underflow_case : VSCore.evalEntry rawProgram "subtractIfEnough" [.nat 2, .nat 3] =
    .ok (.error (.enum "DebitError" "insufficient")) := by rfl

open VeriSlopBridgeGoal in
theorem unbounded_case : VSCore.evalEntry rawProgram "subtractIfEnough"
    [.nat 18446744073709551625, .nat 3] =
    .ok (.ok (.nat 18446744073709551622)) := by rfl

end VeriSlopBridgeProof
