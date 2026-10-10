import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  intro p
  change VeriSlopBridgeGoal.source_fn_adjust p = _
  rw [VeriSlopBridgeGoal.Readable.source_eq_adjust]
  rcases p with ⟨direction, amount⟩
  cases direction <;> with_unfolding_all rfl
end VeriSlopBridgeProof
