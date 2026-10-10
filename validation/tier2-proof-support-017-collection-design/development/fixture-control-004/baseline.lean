import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
open VeriSlopBridgeGoal VSCore3.ProofSupport
set_option maxRecDepth 100000
set_option maxHeartbeats 20000000
theorem direct_shiftEnvelopes : Refines_shiftEnvelopes := by
  intros
  rw [Readable.source_eq_shiftEnvelopes]
  with_unfolding_all rfl
theorem direct_keepParcel : Refines_keepParcel := by
  intros
  rw [Readable.source_eq_keepParcel]
  with_unfolding_all rfl
theorem direct_shadeTotal : Refines_shadeTotal := by
  intros
  rw [Readable.source_eq_shadeTotal]
  with_unfolding_all rfl
theorem direct_sameShade : Refines_sameShade := by
  intros
  rw [Readable.source_eq_sameShade]
  with_unfolding_all rfl
end VeriSlopBridgeProof
