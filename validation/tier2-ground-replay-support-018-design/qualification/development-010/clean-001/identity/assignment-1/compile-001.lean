import VeriSlopBridgeGoal
set_option maxRecDepth 100000
set_option maxHeartbeats 2000000
set_option smartUnfolding false
namespace VeriSlopReviewProbe
theorem result : (@Not (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform (@Int.ofNat (nat_lit 7))) (@Int.ofNat (nat_lit 7)))) := by
  with_unfolding_all
    simp only [eq_self, true_implies, implies_true, and_true, true_and, not_true_eq_false, not_false_eq_true]
    all_goals decide +kernel
end VeriSlopReviewProbe
