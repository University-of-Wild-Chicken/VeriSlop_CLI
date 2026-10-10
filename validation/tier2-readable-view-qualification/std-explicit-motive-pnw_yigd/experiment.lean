import Std
namespace GenericExplicitMotive
universe u v w

theorem option_direct {A : Type u} {B : Type v} (x : Option A) (n : B) (s : A -> B) :
    (match x with | none => n | some a => s a) =
      Option.casesOn (motive := fun _ => B) x n s := by
  with_unfolding_all rfl

theorem list_direct {A : Type u} {B : Type v} (xs : List A) (n : B) (c : A -> List A -> B) :
    (match xs with | [] => n | a :: tail => c a tail) =
      List.casesOn (motive := fun _ => B) xs n c := by
  with_unfolding_all rfl

theorem sum_direct {A : Type u} {C : Type v} {B : Type w}
    (x : Sum A C) (l : A -> B) (r : C -> B) :
    (match x with | .inl a => l a | .inr c => r c) =
      Sum.casesOn (motive := fun _ => B) x l r := by
  with_unfolding_all rfl

#print axioms option_direct
#print axioms list_direct
#print axioms sum_direct
end GenericExplicitMotive
