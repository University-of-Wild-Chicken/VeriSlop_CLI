import Std

/-!
# Bounded increment — formalization candidate (statements only)

A candidate formalization of `examples/request.txt` for `verislop formalize --candidate`.
Theorem bodies are `sorry`: this file states the challenge; proofs are searched for after the
challenge is frozen. The bindings to obligation IDs are in `formalization.json`.
-/

namespace VeriSlop.BoundedIncrement

inductive IncrementError where
  | limitReached
  deriving DecidableEq, Repr

/-- The input contract for a caller that expects errors only at the limit. -/
def validInput (limit input : Nat) : Prop := input ≤ limit

/-- A mathematical reference function, not an externally linked executable. -/
def increment (limit input : Nat) : Except IncrementError Nat :=
  if input < limit then .ok (input + 1) else .error .limitReached

/-- O17: every successful result is exactly one more than the input. -/
theorem success_is_successor (limit input output : Nat)
    (h : increment limit input = .ok output) : output = input + 1 := by
  sorry

/-- I2: successful calls preserve the upper bound. -/
theorem success_preserves_bound (limit input output : Nat)
    (h : increment limit input = .ok output) : output ≤ limit := by
  sorry

/-- E1: on the valid input domain, an error occurs exactly at the limit. -/
theorem error_iff_at_limit (limit input : Nat)
    (hvalid : validInput limit input) :
    increment limit input = .error .limitReached ↔ input = limit := by
  sorry

/-- W1: both valid success and valid error cases actually exist. -/
theorem non_vacuity :
    (∃ limit input output : Nat,
      validInput limit input ∧
      increment limit input = .ok output) ∧
    (∃ limit input : Nat,
      validInput limit input ∧
      increment limit input = .error .limitReached) := by
  sorry

end VeriSlop.BoundedIncrement
