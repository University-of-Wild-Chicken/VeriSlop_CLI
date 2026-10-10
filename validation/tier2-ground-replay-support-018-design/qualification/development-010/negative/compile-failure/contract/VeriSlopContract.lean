import VSCore3
namespace VeriSlopContract
def reference (x : Int) : Int := x
theorem guarantee : (∀ (x__0 : @Int), (@And (@Eq.{1} @Int (@VeriSlopContract.reference x__0) x__0) (∀ (n__1 : @Nat), (∀ (h__2 : (@LE.le.{0} @Nat @instLENat (@OfNat.ofNat.{0} @Nat (nat_lit 0) (@instOfNatNat (nat_lit 0))) n__1)), (∀ (h__3 : (@LT.lt.{0} @Nat @instLTNat n__1 (@OfNat.ofNat.{0} @Nat (nat_lit 3) (@instOfNatNat (nat_lit 3))))), (@LE.le.{0} @Nat @instLENat n__1 (@OfNat.ofNat.{0} @Nat (nat_lit 3) (@instOfNatNat (nat_lit 3))))))))) := by
  intro x
  constructor
  · rfl
  · intro n hlo hhi
    exact Nat.le_of_lt hhi
end VeriSlopContract
