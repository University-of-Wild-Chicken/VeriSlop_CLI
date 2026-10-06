import Std

/-!
# Checked subtraction over mathematical Nat

This independent contract fixture has no width restriction or narrower success-domain
assumption. The redundant nonnegative-domain predicate records the caller's Nat domain
explicitly and supplies the accepted concrete non-vacuity witnesses.
-/

namespace VeriSlop.CheckedSubtraction

inductive DebitError where
  | insufficient
  deriving DecidableEq, Repr

def validOperands (balance amount : Nat) : Prop := 0 ≤ balance ∧ 0 ≤ amount

def subtractIfEnough (balance amount : Nat) : Except DebitError Nat :=
  if amount ≤ balance then .ok (balance - amount) else .error .insufficient

theorem success_equation (balance amount : Nat) (h : amount ≤ balance) :
    subtractIfEnough balance amount = .ok (balance - amount) := by
  simp [subtractIfEnough, h]

theorem success_reconstructs (balance amount remaining : Nat)
    (h : subtractIfEnough balance amount = .ok remaining) :
    remaining + amount = balance := by
  unfold subtractIfEnough at h
  split at h
  next enough =>
    have hr : remaining = balance - amount := (Except.ok.inj h).symm
    rw [hr]
    exact Nat.sub_add_cancel enough
  next => contradiction

theorem success_is_bounded (balance amount remaining : Nat)
    (h : subtractIfEnough balance amount = .ok remaining) :
    remaining ≤ balance := by
  unfold subtractIfEnough at h
  split at h
  · have hr : remaining = balance - amount := (Except.ok.inj h).symm
    rw [hr]
    exact Nat.sub_le balance amount
  · contradiction

theorem error_iff_insufficient (balance amount : Nat) :
    subtractIfEnough balance amount = .error .insufficient ↔ balance < amount := by
  unfold subtractIfEnough
  split
  next enough => simp [Nat.not_lt_of_ge enough]
  next insufficient => simp [Nat.lt_of_not_ge insufficient]

theorem non_vacuity :
    (∃ balance amount remaining : Nat,
      validOperands balance amount ∧ balance = 0 ∧ amount = 0 ∧
      subtractIfEnough balance amount = .ok remaining) ∧
    (∃ balance amount remaining : Nat,
      validOperands balance amount ∧ balance = 7 ∧ amount = 7 ∧
      subtractIfEnough balance amount = .ok remaining) ∧
    (∃ balance amount : Nat,
      validOperands balance amount ∧ balance = 2 ∧ amount = 3 ∧
      subtractIfEnough balance amount = .error .insufficient) := by
  refine ⟨⟨0, 0, 0, ?_, rfl, rfl, rfl⟩,
    ⟨7, 7, 0, ?_, rfl, rfl, rfl⟩,
    ⟨2, 3, ?_, rfl, rfl, rfl⟩⟩ <;> unfold validOperands <;> decide

end VeriSlop.CheckedSubtraction
