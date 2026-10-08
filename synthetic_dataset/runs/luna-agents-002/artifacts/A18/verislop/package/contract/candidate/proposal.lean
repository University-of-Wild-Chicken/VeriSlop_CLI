import Std

namespace MedianStream

inductive Operation where
  | add : String → Int → Operation
  | remove : String → Operation
  | median : Operation

def Input := List Operation

inductive Output where
  | empty : Output
  | rational : Int → Nat → Output

def Results := List Output

/-- The caller supplies well-shaped operations, with at most 100 operations. -/
def A1 (ops : Input) : Prop := ops.length ≤ 100

/-- These collection and execution terms retain the string, signed-integer,
and sequence model, which the executable generated-test bridge does not support. -/
opaque Entries : Type
opaque solve : Input → Results
opaque process : Entries → Operation → Entries
opaque query : Entries → Output
opaque addReplacesId : Entries → String → Int → Entries → Prop
opaque removePresentId : Entries → String → Entries → Prop
opaque removeAbsentIdUnchanged : Entries → String → Entries → Prop
opaque queryObservesPriorOperations : Entries → Input → Prop
opaque outputMatchesQueriesInOrder : Input → Results → Prop
opaque emptyPopulation : Entries → Prop
opaque reducedPositiveRational : Output → Prop
opaque conventionalMedian : Entries → Output → Prop
opaque oneCurrentValuePerId : Entries → Prop
opaque distinctIdsRemainSeparate : Entries → Prop
opaque standardLibraryPureDeterministic : Prop
opaque missingRemovalContinues : Entries → String → Input → Prop
opaque firstExample : Prop
opaque secondExample : Prop

/-- Each add, remove, and median transition follows its specified behavior
under the caller's schema and operation-count bound. -/
theorem O1 : ∀ ops : Input, A1 ops → ∀ before after : Entries,
  ∀ op : Operation, process before op = after →
    (match op with
     | .add id value => addReplacesId before id value after
     | .remove id =>
       (hasId before id → removePresentId before id after) ∧
       (¬ hasId before id → removeAbsentIdUnchanged before id after)
     | .median => queryObservesPriorOperations before ops) := by sorry

opaque hasId : Entries → String → Prop

theorem O2 : ∀ entries : Entries,
  (emptyPopulation entries → query entries = .empty) ∧
  (¬ emptyPopulation entries →
    ∃ numerator : Int, ∃ denominator : Nat,
      query entries = .rational numerator denominator ∧
      denominator > 0 ∧
      reducedPositiveRational (.rational numerator denominator) ∧
      conventionalMedian entries (.rational numerator denominator)) := by sorry

theorem O3 : firstExample ∧ secondExample := by sorry

theorem I1 : ∀ entries : Entries,
  oneCurrentValuePerId entries ∧ distinctIdsRemainSeparate entries := by sorry

theorem E1 : standardLibraryPureDeterministic := by sorry

theorem E2 : ∀ entries : Entries, ∀ id : String, ∀ rest : Input,
  ¬ hasId entries id → missingRemovalContinues entries id rest := by sorry

theorem A1_nonvacuity : ∃ ops : Input, A1 ops := by sorry

end MedianStream
