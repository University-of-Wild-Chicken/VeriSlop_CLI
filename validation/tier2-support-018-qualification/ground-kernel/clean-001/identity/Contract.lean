import VSCore3
namespace VeriSlopContract
def reference (x : Int) : Int := x
theorem guarantee : (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopContract.reference x__0) x__0)) := by intro x; rfl
end VeriSlopContract
