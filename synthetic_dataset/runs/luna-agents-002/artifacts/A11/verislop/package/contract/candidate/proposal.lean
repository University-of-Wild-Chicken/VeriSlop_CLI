import Std

namespace A11

/-- The input preserves the ordered list of signed values. This domain is outside the generated-test bridge. -/
structure Input where
  values : List Int
  deriving Nonempty

/-- The output preserves the signed difference and ascending left indices. -/
structure Output where
  difference : Int
  leftIndices : List Nat
  deriving Nonempty

/-- Opaque because the faithful list-and-signed-integer model is unsupported by the executable bridge. -/
opaque solve : Input → Output

def inputSchema (x : Input) : Prop := x.values.length ≤ 14

def indicesValid (x : Input) (indices : List Nat) : Prop :=
  ∀ i, i ∈ indices → i < x.values.length

def strictlyAscending (indices : List Nat) : Prop :=
  indices.Pairwise (· < ·)

def sideSum (x : Input) (indices : List Nat) : Int :=
  indices.foldl (fun total i => total + (x.values.getD i 0)) 0

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

def standardLibraryPureNoIOContract : Prop := True

def A1 (x : Input) : Prop := inputSchema x

theorem O1 (x : Input) : partitionContract x (solve x) := by sorry

theorem O2 (x : Input) : optimumAndTieBreakContract x (solve x) := by sorry

theorem O3 (x : Input) : structureAndOrderingContract x (solve x) := by sorry

theorem O4 (x : Input) : heldOutBehaviorContract x (solve x) := by sorry

theorem G1 : standardLibraryPureNoIOContract := by sorry

end A11