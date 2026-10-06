import Std

/-!
# Illustrative formal contract fixture

This file demonstrates a small contract and ordinary typed obligation metadata.
It does not implement VeriSlop CLI, a bridge to another implementation language,
or an exporter of accepted obligation IR. The mathematical domain is `Nat`;
there is no claim here about fixed-width integers, machine code, or a compiler.

A future exporter must inspect the elaborated declarations and their actual
types/proof terms in the accepted Lean environment. The `id` and `kind` fields
are explicit contract annotations, not facts inferred from an arbitrary theorem.
The proposition and proof are typed references to the accepted formal artifact,
not a copy of an earlier natural-language interpretation or candidate JSON.
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
  unfold increment at h
  split at h
  · exact (Except.ok.inj h).symm
  · contradiction

/-- I2: successful calls preserve the upper bound. -/
theorem success_preserves_bound (limit input output : Nat)
    (h : increment limit input = .ok output) : output ≤ limit := by
  unfold increment at h
  split at h
  next hlt =>
    have hout : output = input + 1 := (Except.ok.inj h).symm
    rw [hout]
    exact hlt
  next => contradiction

/-- E1: on the valid input domain, an error occurs exactly at the limit. -/
theorem error_iff_at_limit (limit input : Nat)
    (hvalid : validInput limit input) :
    increment limit input = .error .limitReached ↔ input = limit := by
  unfold validInput at hvalid
  unfold increment
  split
  next hlt =>
    constructor
    · intro herr
      contradiction
    · intro heq
      exact False.elim (Nat.ne_of_lt hlt heq)
  next hnot =>
    constructor
    · intro _
      exact Nat.le_antisymm hvalid (Nat.le_of_not_lt hnot)
    · intro _
      rfl

/-- W1: both valid success and valid error cases actually exist. -/
theorem non_vacuity :
    (∃ limit input output : Nat,
      validInput limit input ∧
      increment limit input = .ok output) ∧
    (∃ limit input : Nat,
      validInput limit input ∧
      increment limit input = .error .limitReached) := by
  constructor
  · exact ⟨1, 0, 1, by unfold validInput; decide, rfl⟩
  · exact ⟨1, 1, by unfold validInput; decide, rfl⟩

inductive ObligationKind where
  | postcondition
  | invariant
  | errorSemantics
  | nonVacuity
  deriving DecidableEq, Repr

/--
Ordinary Lean metadata: `evidence` is checked against `proposition`.
Unique IDs, source traceability, policy admissibility, and proof-dependency
extraction would be additional exporter/acceptance checks, not provided here.
-/
structure AcceptedObligation where
  id : String
  kind : ObligationKind
  proposition : Prop
  evidence : proposition

def O17 : AcceptedObligation where
  id := "O17"
  kind := .postcondition
  proposition := ∀ limit input output : Nat,
    increment limit input = .ok output → output = input + 1
  evidence := success_is_successor

def I2 : AcceptedObligation where
  id := "I2"
  kind := .invariant
  proposition := ∀ limit input output : Nat,
    increment limit input = .ok output → output ≤ limit
  evidence := success_preserves_bound

def E1 : AcceptedObligation where
  id := "E1"
  kind := .errorSemantics
  proposition := ∀ limit input : Nat, validInput limit input →
    (increment limit input = .error .limitReached ↔ input = limit)
  evidence := error_iff_at_limit

def W1 : AcceptedObligation where
  id := "W1"
  kind := .nonVacuity
  proposition :=
    (∃ limit input output : Nat,
      validInput limit input ∧
      increment limit input = .ok output) ∧
    (∃ limit input : Nat,
      validInput limit input ∧
      increment limit input = .error .limitReached)
  evidence := non_vacuity

-- These commands report the transitive axioms used by each accepted proof.
#print axioms success_is_successor
#print axioms success_preserves_bound
#print axioms error_iff_at_limit
#print axioms non_vacuity

end VeriSlop.BoundedIncrement
