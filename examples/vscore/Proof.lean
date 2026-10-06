import VeriSlopBridgeGoal

/-!
# Candidate proof for the bounded-increment VSCore bridge

Untrusted candidate input. It proves the frozen refinement target for the only bound symbol
and obtains the edge proposition from the verifier-generated `edge_of_refines`, which already
derives input coverage and the transfer of O17, I2 and E1 from the accepted theorems.
-/

namespace VeriSlopBridgeProof

open VeriSlopBridgeGoal in
theorem refines_increment : Refines_increment := by
  intro limit input
  unfold impl_increment VeriSlop.BoundedIncrement.increment
  by_cases h : input < limit <;>
    simp [h, rawProgram, VSCore.evalEntry, VSCore.findEntry, VSCore.evalExpr, VSCore.evalBin,
      adapter_0, adapter_1, adapter_2, name_0,
      VSCore.natAdapter, VSCore.enumAdapter, VSCore.exceptAdapter]

theorem edge : VeriSlopBridgeGoal.EdgeProp :=
  VeriSlopBridgeGoal.edge_of_refines refines_increment

end VeriSlopBridgeProof
