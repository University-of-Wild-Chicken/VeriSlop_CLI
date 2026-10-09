import VeriSlopBridgeGoal

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeProof

theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  intro x
  with_unfolding_all rfl

end VeriSlopBridgeProof
