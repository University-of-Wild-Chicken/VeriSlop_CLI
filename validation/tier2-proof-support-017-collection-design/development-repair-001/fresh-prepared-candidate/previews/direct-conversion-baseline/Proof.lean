import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
open VeriSlopBridgeGoal VSCore3.ProofSupport
set_option maxRecDepth 100000
set_option maxHeartbeats 20000000
theorem direct_shiftEnvelopes : Refines_shiftEnvelopes := by
  intro xs increment
  rw [Readable.source_eq_shiftEnvelopes]
  with_unfolding_all rfl
theorem direct_keepParcel : Refines_keepParcel := by
  intro xs needle
  rw [Readable.source_eq_keepParcel]
  with_unfolding_all rfl
theorem direct_shadeTotal : Refines_shadeTotal := by
  intro xs initial chosen
  rw [Readable.source_eq_shadeTotal]
  with_unfolding_all rfl
theorem direct_sameShade : Refines_sameShade := by
  intro x y
  rw [Readable.source_eq_sameShade]
  with_unfolding_all rfl
end VeriSlopBridgeProof
