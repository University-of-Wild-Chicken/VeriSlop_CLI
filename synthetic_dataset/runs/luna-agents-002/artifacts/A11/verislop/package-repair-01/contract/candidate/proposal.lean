import Std

namespace A11

/-- The input preserves the requested ordered list of signed integers. -/
structure Input where
  values : List Int

/-- The output preserves the difference and ascending left indices. -/
structure Output where
  difference : Int
  leftIndices : List Nat

/-- Supplied input lists have at most fourteen items. -/
def inputSchema (x : Input) : Prop := x.values.length ≤ 14

/-- The signed-list solver is retained as an opaque term because its domain is outside the executable bridge. -/
opaque solve : Input → Output

def indicesValid (x : Input) (indices : List Nat) : Prop :=
  ∀ i, i ∈ indices → i < x.values.length

def strictlyAscending (indices : List Nat) : Prop :=
  indices.Pairwise (· < ·)

def sideSum (x : Input) (indices : List Nat) : Int :=
  indices.foldl (fun total i => total + x.values.getD i 0) 0

def absoluteDifference (x : Input) (indices : List Nat) : Nat :=
  Int.natAbs (sideSum x indices - (x.values.foldl (· + ·) 0 - sideSum x indices))

def lexLess : List Nat → List Nat → Prop
  | [], [] => False
  | [], _ :: _ => True
  | _ :: _, [] => False
  | a :: as, b :: bs => a < b ∨ (a = b ∧ lexLess as bs)

def isPartition (x : Input) (left : List Nat) : Prop :=
  indicesValid x left ∧ strictlyAscending left

def optimalDifference (x : Input) (o : Output) : Prop :=
  isPartition x o.leftIndices ∧
  o.difference.natAbs = absoluteDifference x o.leftIndices ∧
  ∀ candidate, isPartition x candidate →
    o.difference.natAbs ≤ absoluteDifference x candidate

def canonicalTieBreak (x : Input) (o : Output) : Prop :=
  ∀ candidate, isPartition x candidate →
    absoluteDifference x candidate = o.difference.natAbs →
    ¬ lexLess candidate o.leftIndices

def partitionContract (x : Input) (o : Output) : Prop :=
  isPartition x o.leftIndices ∧ o.leftIndices.length ≤ x.values.length

def optimumAndTieBreakContract (x : Input) (o : Output) : Prop :=
  optimalDifference x o ∧ canonicalTieBreak x o

def structureAndOrderingContract (x : Input) (o : Output) : Prop :=
  indicesValid x o.leftIndices ∧ strictlyAscending o.leftIndices

def heldOutBehaviorContract (x : Input) (o : Output) : Prop :=
  optimumAndTieBreakContract x o

/-- Python library use and I/O behavior are outside the Lean executable contract profile. -/
opaque standardLibraryPureNoIOContract : Prop

def A1 (x : Input) : Prop := inputSchema x

theorem O1 (x : Input) : partitionContract x (solve x) := by sorry

theorem O2 (x : Input) : optimumAndTieBreakContract x (solve x) := by sorry

theorem O3 (x : Input) : structureAndOrderingContract x (solve x) := by sorry

theorem O4 (x : Input) : heldOutBehaviorContract x (solve x) := by sorry

theorem G1 : standardLibraryPureNoIOContract := by sorry

end A11