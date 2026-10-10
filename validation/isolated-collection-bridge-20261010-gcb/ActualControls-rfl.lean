import VeriSlopBridgeGoal
set_option maxRecDepth 100000
set_option maxHeartbeats 20000000
namespace VeriSlopBridgeProof
open VeriSlopBridgeGoal

theorem ref_map : Refines_raiseBoxes := by
  intro xs
  rw [Readable.source_eq_raiseBoxes]
  with_unfolding_all rfl

theorem ref_filter : Refines_keepAtom := by
  intro xs needle
  rw [Readable.source_eq_keepAtom]
  with_unfolding_all rfl

theorem ref_fold : Refines_coldTotal := by
  intro xs
  rw [Readable.source_eq_coldTotal]
  with_unfolding_all rfl

theorem edge : EdgeProp := edge_of_refines ref_fold ref_filter ref_map
end VeriSlopBridgeProof
