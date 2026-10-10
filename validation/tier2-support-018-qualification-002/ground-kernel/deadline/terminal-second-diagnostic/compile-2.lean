import VeriSlopBridgeGoal
set_option maxRecDepth 100000
set_option maxHeartbeats 2000000
set_option smartUnfolding false
namespace VeriSlopReviewProbe
theorem result : (@And (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform (@Int.negSucc (nat_lit 1))) (@Int.negSucc (nat_lit 1))) (∀ (n__0 : @Nat), (∀ (h__1 : (@LE.le.{0} @Nat @instLENat (@OfNat.ofNat.{0} @Nat (nat_lit 0) (@instOfNatNat (nat_lit 0))) n__0)), (∀ (h__2 : (@LT.lt.{0} @Nat @instLTNat n__0 (@OfNat.ofNat.{0} @Nat (nat_lit 3) (@instOfNatNat (nat_lit 3))))), (@LE.le.{0} @Nat @instLENat n__0 (@OfNat.ofNat.{0} @Nat (nat_lit 3) (@instOfNatNat (nat_lit 3)))))))) := by
  with_unfolding_all
    simp only [eq_self, true_implies, implies_true, and_true, true_and, not_true_eq_false, not_false_eq_true]
    all_goals decide +kernel
end VeriSlopReviewProbe
