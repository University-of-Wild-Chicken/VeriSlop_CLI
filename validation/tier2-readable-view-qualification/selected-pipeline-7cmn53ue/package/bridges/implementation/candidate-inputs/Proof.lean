import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  · intro x
    change VeriSlopBridgeGoal.source_fn_shift x = _
    rw [VeriSlopBridgeGoal.Readable.source_eq_shift]
    with_unfolding_all rfl
  · intro x
    change VeriSlopBridgeGoal.source_fn_solve x = _
    rw [VeriSlopBridgeGoal.Readable.source_eq_solve]
    with_unfolding_all rfl
end VeriSlopBridgeProof
