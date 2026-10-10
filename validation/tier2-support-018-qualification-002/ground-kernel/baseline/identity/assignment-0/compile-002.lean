import VeriSlopBridgeGoal
set_option maxRecDepth 100000
set_option maxHeartbeats 2000000
namespace VeriSlopReviewProbe
theorem result : (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform (@Int.negSucc (nat_lit 1))) (@Int.negSucc (nat_lit 1))) := by decide +kernel
end VeriSlopReviewProbe
