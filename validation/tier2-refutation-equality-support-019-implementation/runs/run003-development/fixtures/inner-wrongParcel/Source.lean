import Std
-- Fixture prerequisite: pinned Std does not provide Except DecidableEq.
deriving instance DecidableEq for Except
namespace RefutationEquality019
inductive Token where | amber | violet
  deriving DecidableEq
structure ZLeaf where
  token : Token
  amount : Nat
  deriving DecidableEq
structure AParcel where
  leaf : ZLeaf
  spare : Option Token
  history : List ZLeaf
  outcome : Except Token ZLeaf
def swap (t : Token) : Token :=
  match t with | .amber => .violet | .violet => .amber
def carry (p : AParcel) : AParcel :=
  { p with leaf := { p.leaf with token := swap p.leaf.token } }
theorem wrongToken (t : Token) : swap t = t := by sorry
theorem rightToken (t : Token) : swap (swap t) = t := by cases t <;> rfl
theorem wrongParcel (p : AParcel) : carry p = p := by sorry
theorem rightParcel (p : AParcel) : carry (carry p) = p := by
  cases p with
  | mk leaf spare history outcome =>
    cases leaf with
    | mk token amount => cases token <;> rfl
end RefutationEquality019
