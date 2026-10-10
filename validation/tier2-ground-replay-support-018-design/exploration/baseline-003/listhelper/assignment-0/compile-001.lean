import VeriSlopBridgeGoal
set_option maxRecDepth 100000
set_option maxHeartbeats 2000000
namespace VeriSlopReviewProbe
theorem result : (@Not (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform (@List.nil.{0} @Int)) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Int @Int (fun (x__0 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 1)))) (@List.nil.{0} @Int))))) := by decide +kernel
end VeriSlopReviewProbe
