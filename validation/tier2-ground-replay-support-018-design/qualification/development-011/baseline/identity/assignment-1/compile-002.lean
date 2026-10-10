import VeriSlopBridgeGoal
set_option maxRecDepth 100000
set_option maxHeartbeats 2000000
namespace VeriSlopReviewProbe
theorem result : (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform (@Int.ofNat (nat_lit 7))) (@Int.ofNat (nat_lit 7))) := by decide +kernel
end VeriSlopReviewProbe
