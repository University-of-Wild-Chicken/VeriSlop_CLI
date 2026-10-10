import VeriSlopBridgeGoal
namespace VeriSlopReviewProbe
theorem wrapper : True := VeriSlopContract.guarantee
theorem result : True := wrapper
end VeriSlopReviewProbe
