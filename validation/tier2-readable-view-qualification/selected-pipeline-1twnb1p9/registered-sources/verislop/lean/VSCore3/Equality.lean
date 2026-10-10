import VSCore3.Syntax

/-! Total structural comparison of the delivered value representation. -/
namespace VSCore3

mutual
def valueEq : Value → Value → Bool
  | .nat a, .nat b => a == b
  | .int a, .int b => a == b
  | .string a, .string b => a == b
  | .bool a, .bool b => a == b
  | .unit, .unit => true
  | .enum a c, .enum b d => a == b && c == d
  | .ok a, .ok b => valueEq a b
  | .error a, .error b => valueEq a b
  | .record a fs, .record b gs => a == b && fieldsEq fs gs
  | .variant a c xs, .variant b d ys => a == b && c == d && argsEq xs ys
  | .none, .none => true
  | .some a, .some b => valueEq a b
  | .nil, .nil => true
  | .cons a as, .cons b bs => valueEq a b && valueEq as bs
  | _, _ => false
termination_by a _ => sizeOf a

def argsEq : List Value → List Value → Bool
  | [], [] => true
  | a :: as, b :: bs => valueEq a b && argsEq as bs
  | _, _ => false
termination_by as _ => sizeOf as

def fieldsEq : List (String × Value) → List (String × Value) → Bool
  | [], [] => true
  | (a, v) :: as, (b, w) :: bs => a == b && valueEq v w && fieldsEq as bs
  | _, _ => false
termination_by as _ => sizeOf as
end

mutual
theorem valueEq_eq_true (a b : Value) : valueEq a b = true ↔ a = b := by
  cases a <;> cases b <;> try simp only [valueEq, reduceCtorEq, Bool.and_eq_true, beq_iff_eq,
    Value.nat.injEq, Value.int.injEq, Value.string.injEq, Value.bool.injEq, Value.enum.injEq, Value.ok.injEq, Value.error.injEq,
    Value.record.injEq, Value.variant.injEq, Value.some.injEq, Value.cons.injEq]
  case ok.ok a b => exact valueEq_eq_true a b
  case error.error a b => exact valueEq_eq_true a b
  case record.record a fs b gs =>
    rw [fieldsEq_eq_true fs gs]
  case variant.variant a c xs b d ys =>
    rw [argsEq_eq_true xs ys]
    exact and_assoc
  case some.some a b => exact valueEq_eq_true a b
  case cons.cons a as b bs =>
    rw [valueEq_eq_true a b, valueEq_eq_true as bs]
termination_by sizeOf a

theorem argsEq_eq_true (as bs : List Value) : argsEq as bs = true ↔ as = bs := by
  cases as <;> cases bs <;> try simp only [argsEq, reduceCtorEq]
  case cons.cons a as b bs =>
    simp only [Bool.and_eq_true, List.cons.injEq]
    rw [valueEq_eq_true a b, argsEq_eq_true as bs]
termination_by sizeOf as

theorem fieldsEq_eq_true (as bs : List (String × Value)) : fieldsEq as bs = true ↔ as = bs := by
  cases as with
  | nil => cases bs <;> simp [fieldsEq]
  | cons a as =>
    cases a with
    | mk name value =>
      cases bs with
      | nil => simp [fieldsEq]
      | cons b bs =>
        cases b with
        | mk otherName otherValue =>
          simp only [fieldsEq, Bool.and_eq_true, beq_iff_eq, List.cons.injEq, Prod.mk.injEq]
          rw [valueEq_eq_true value otherValue, fieldsEq_eq_true as bs]
termination_by sizeOf as
end

instance (priority := high) : BEq Value := ⟨valueEq⟩

instance : LawfulBEq Value where
  eq_of_beq := by
    intro a b h
    exact (valueEq_eq_true a b).mp h
  rfl := by
    intro a
    exact (valueEq_eq_true a a).mpr rfl

theorem value_beq_iff (a b : Value) : (a == b) = true ↔ a = b :=
  valueEq_eq_true a b

/-- Constructor equality uses the proved total structural Boolean comparison. -/
instance : DecidableEq Value := fun a b =>
  decidable_of_iff (valueEq a b = true) (valueEq_eq_true a b)

end VSCore3
