import Std

namespace A11

/-- Faithful input domain: an ordered list of signed integers, outside the executable bridge profile. -/
structure Input where
  values : List Int

/-- Faithful output domain: a signed difference and ordered left indices. -/
structure Output where
  difference : Int
  leftIndices : List Nat
  deriving Nonempty

/-- The deterministic solver is opaque because signed integers and lists are unsupported by the executable bridge. -/
opaque solve : Input → Output

/-- The supplied-input schema requires at most fourteen signed values. -/
def inputSchema (x : Input) : Prop := x.values.length ≤ 14

/-- Contract for assigning every input index to exactly one labeled side and returning the specified fields. -/
opaque partitionContract : Input → Output → Prop

/-- Contract for minimum absolute difference and the lexicographically smallest ascending left-index list among minimizers. -/
opaque optimumAndTieBreakContract : Input → Output → Prop

/-- Contract for preserving the specified input/output structures and ascending left-index order. -/
opaque structureAndOrderingContract : Input → Output → Prop

/-- Contract for applying the objective and tie-break to every valid input, including held-out cases. -/
opaque heldOutBehaviorContract : Input → Output → Prop

/-- Python standard-library use, purity, determinism, and absence of external I/O lie outside this Lean profile. -/
opaque standardLibraryPureNoIOContract : Prop

def A1 (x : Input) : Prop := inputSchema x

theorem O1 (x : Input) : partitionContract x (solve x) := by sorry

theorem O2 (x : Input) : optimumAndTieBreakContract x (solve x) := by sorry

theorem O3 (x : Input) : structureAndOrderingContract x (solve x) := by sorry

theorem O4 (x : Input) : heldOutBehaviorContract x (solve x) := by sorry

theorem G1 : standardLibraryPureNoIOContract := by sorry

end A11