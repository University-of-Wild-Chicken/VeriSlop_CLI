import Std
namespace GenericMatcherLaw
universe u v w

theorem option_apply {A : Type u} {E : Type v} {B : Type w}
    (x : Option A) (n : E -> B) (s : A -> E -> B) (env : E) :
    (Option.casesOn (motive := fun _ => E -> B) x n s) env =
      Option.casesOn (motive := fun _ => B) x (n env) (fun a => s a env) := by
  fail_if_success with_unfolding_all rfl
  cases x <;> rfl

theorem list_apply {A : Type u} {E : Type v} {B : Type w}
    (xs : List A) (n : E -> B) (c : A -> List A -> E -> B) (env : E) :
    (List.casesOn (motive := fun _ => E -> B) xs n c) env =
      List.casesOn (motive := fun _ => B) xs (n env) (fun a tail => c a tail env) := by
  fail_if_success with_unfolding_all rfl
  cases xs <;> rfl

theorem sum_apply {A : Type u} {C : Type v} {E : Type w} {B : Type}
    (x : Sum A C) (l : A -> E -> B) (r : C -> E -> B) (env : E) :
    (Sum.casesOn (motive := fun _ => E -> B) x l r) env =
      Sum.casesOn (motive := fun _ => B) x (fun a => l a env) (fun c => r c env) := by
  fail_if_success with_unfolding_all rfl
  cases x <;> rfl

theorem option_direct {A : Type u} {B : Type v} (x : Option A) (n : B) (s : A -> B) :
    (match x with | none => n | some a => s a) = Option.casesOn x n s := by
  fail_if_success with_unfolding_all rfl
  cases x <;> rfl

theorem list_direct {A : Type u} {B : Type v} (xs : List A) (n : B) (c : A -> List A -> B) :
    (match xs with | [] => n | a :: tail => c a tail) = List.casesOn xs n c := by
  fail_if_success with_unfolding_all rfl
  cases xs <;> rfl

theorem sum_direct {A : Type u} {C : Type v} {B : Type w}
    (x : Sum A C) (l : A -> B) (r : C -> B) :
    (match x with | .inl a => l a | .inr c => r c) = Sum.casesOn x l r := by
  fail_if_success with_unfolding_all rfl
  cases x <;> rfl

#print axioms option_apply
#print axioms list_apply
#print axioms sum_apply
#print axioms option_direct
#print axioms list_direct
#print axioms sum_direct
set_option pp.all true in
#reduce fun (x : Option Nat) (n : Nat) (s : Nat -> Nat) => (match x with | none => n | some a => s a)
set_option pp.all true in
#reduce fun (x : Option Nat) (n : Nat) (s : Nat -> Nat) => Option.casesOn x n s
end GenericMatcherLaw
