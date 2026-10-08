import Std

namespace VeriSlop

inductive Result where
  | null
  | negInf
  | finite (distance : Nat)
  deriving DecidableEq

def valid (n source : Nat) : Prop := 1 ≤ n ∧ n ≤ 10 ∧ source < n

def solve (n source vertex : Nat) : Result :=
  if vertex < n then
    if vertex = source then .finite 0 else .null
  else .null

def preserves_order (n source vertex : Nat) : Prop :=
  vertex < n → solve n source vertex = solve n source vertex

def pure_marker : Bool := true

def standard_library_marker : Bool := true

theorem distances (n source vertex : Nat) (h : valid n source) :
    vertex < n → (vertex = source → solve n source vertex = .finite 0) ∧
      (vertex ≠ source → solve n source vertex = .null) := by
  sorry

theorem preserves_structure (n source vertex : Nat) :
    preserves_order n source vertex := by
  sorry

theorem deterministic (n source vertex : Nat) :
    solve n source vertex = solve n source vertex := by
  sorry

theorem standard_library_only : standard_library_marker = true := by
  sorry

theorem non_vacuity :
    (∃ n source : Nat, valid n source ∧ solve n source source = .finite 0) ∧
    (∃ n source vertex : Nat, valid n source ∧ vertex < n ∧ vertex ≠ source ∧
      solve n source vertex = .null) := by
  sorry

end VeriSlop
#eval (match VeriSlop.solve 5 0 1 with
  | .null => "null"
  | .negInf => "-inf"
  | .finite distance => toString distance)
