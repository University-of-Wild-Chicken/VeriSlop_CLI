import VSCore3
namespace VeriSlopContract
def reference (xs : List Int) : Int := (xs.map (fun x => x + 1)).sum
theorem guarantee : (∀ (x__0 : (@List.{0} @Int)), (@Eq.{1} @Int (@VeriSlopContract.reference x__0) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Int @Int (fun (x__1 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__1 (@Int.ofNat (nat_lit 1)))) x__0)))) := by intro x; rfl
end VeriSlopContract
