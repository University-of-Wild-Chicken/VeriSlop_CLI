import VeriSlopBridgeGoal
namespace GenericActualEquality
open VeriSlopBridgeGoal
set_option maxRecDepth 100000
set_option maxHeartbeats 20000000
theorem fixed_enum_decision (x y : VeriSlopAST.Tone) :
    (letI := VSCore3.denoteDecidableEq (.enum "Tone" ["cold", "warm"]);
      decide (adapter_0.to x = adapter_0.to y)) =
    @decide (x = y) (VeriSlopAST.instDecidableEqTone x y) := by
  with_unfolding_all rfl
end GenericActualEquality
