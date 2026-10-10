import VeriSlopBridgeGoal
set_option maxRecDepth 100000
set_option maxHeartbeats 2000000
set_option smartUnfolding false
namespace VeriSlopReviewProbe
theorem result : (@Not (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform (@List.cons.{0} @Int (@Int.negSucc (nat_lit 3)) (@List.cons.{0} @Int (@Int.ofNat (nat_lit 2)) (@List.cons.{0} @Int (@Int.ofNat (nat_lit 9)) (@List.nil.{0} @Int))))) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Int @Int (fun (x__0 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 1)))) (@List.cons.{0} @Int (@Int.negSucc (nat_lit 3)) (@List.cons.{0} @Int (@Int.ofNat (nat_lit 2)) (@List.cons.{0} @Int (@Int.ofNat (nat_lit 9)) (@List.nil.{0} @Int)))))))) := by
  with_unfolding_all
    simp only [eq_self, true_implies, implies_true, and_true, true_and, not_true_eq_false, not_false_eq_true]
    all_goals decide +kernel
end VeriSlopReviewProbe
