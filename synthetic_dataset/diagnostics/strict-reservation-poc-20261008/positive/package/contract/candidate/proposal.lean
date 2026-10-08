import Std

namespace VeriSlop.Reserve

inductive ReserveError where
  | insufficient

/-- The function reserve takes two arguments, balance and amount, which are unbounded natural numbers including zero. -/
def reserve (balance amount : Nat) : Except ReserveError Nat :=
  if amount <= balance then
    .ok (balance - amount)
  else
    .error ReserveError.insufficient

/-- If amount <= balance, the function returns the tuple ("ok", balance - amount). -/
theorem reserve_ok_when_sufficient (balance amount : Nat) : amount <= balance → reserve balance amount = .ok (balance - amount) := by sorry

/-- If balance < amount, the function returns the tuple ("error", "insufficient"). -/
theorem reserve_error_when_insufficient (balance amount : Nat) : balance < amount → reserve balance amount = .error ReserveError.insufficient := by sorry

/-- If amount is zero, the function returns the tuple ("ok", balance). -/
theorem reserve_zero_amount (balance : Nat) : reserve balance 0 = .ok balance := by sorry

/-- The subtraction in the successful branch is ordinary exact subtraction. -/
theorem reserve_exact_subtraction (balance amount : Nat) : amount <= balance → reserve balance amount = .ok (balance - amount) := by sorry

/-- On the successful branch, the returned balance is at most the original balance. -/
theorem reserve_success_balance_at_most_original (balance amount : Nat) : amount <= balance → ∃ new_balance : Nat, reserve balance amount = .ok new_balance ∧ new_balance <= balance := by sorry

end VeriSlop.Reserve