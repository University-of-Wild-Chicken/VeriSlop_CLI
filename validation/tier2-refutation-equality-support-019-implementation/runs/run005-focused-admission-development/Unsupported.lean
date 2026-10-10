import Std
namespace AdmissionEquality019
structure Indexed where
  amount : Nat
  index : Fin amount
inductive Recursive where
  | base
  | step (previous : Recursive)
theorem reflexive (x : Indexed) : x = x := by rfl
end AdmissionEquality019
