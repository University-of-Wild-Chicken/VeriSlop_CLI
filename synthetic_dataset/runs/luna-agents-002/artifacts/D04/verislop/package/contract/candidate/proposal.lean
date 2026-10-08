import Std

namespace D04

structure Comparator where
  op : String
  version : String
  deriving Inhabited

def Clause := List Comparator

structure Input where
  versions : List String
  clauses : List Clause
  deriving Inhabited

structure Output where
  accepted : List String
  invalid : List Nat
  deriving Inhabited

opaque parseSemVer : String → Option (Nat × Nat × Nat × List String × List String)

def validSemVer (s : String) : Prop := (parseSemVer s).isSome = true

def comparatorValid (c : Comparator) : Prop :=
  (c.op = "=" ∨ c.op = "<" ∨ c.op = "<=" ∨ c.op = ">" ∨ c.op = ">=") ∧ validSemVer c.version

opaque solve : Input → Output
opaque strictSemVerParsingContract : Input → Output → Prop
opaque semVerPrecedenceContract : Input → Output → Prop
opaque clauseMatchingContract : Input → Output → Prop
opaque outputOrderingAndIndicesContract : Input → Output → Prop
opaque publicExamplesContract : Prop
opaque pureStandardLibraryAndNoIOContract : Input → Output → Prop
opaque boundedNumericSupportContract : Input → Output → Prop

theorem O1 : ∀ i : Input, strictSemVerParsingContract i (solve i) := by sorry
theorem O2 : ∀ i : Input, semVerPrecedenceContract i (solve i) := by sorry
theorem O3 : ∀ i : Input, clauseMatchingContract i (solve i) := by sorry
theorem O4 : ∀ i : Input, outputOrderingAndIndicesContract i (solve i) := by sorry
theorem O5 : publicExamplesContract := by sorry
theorem I1 : ∀ i : Input, pureStandardLibraryAndNoIOContract i (solve i) := by sorry
theorem R1 : ∀ i : Input, boundedNumericSupportContract i (solve i) := by sorry

end D04