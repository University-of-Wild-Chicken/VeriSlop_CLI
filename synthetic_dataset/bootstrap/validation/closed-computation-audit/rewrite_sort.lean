import Std
structure Cell where
  label : String
  quotient : Option Int
  deriving DecidableEq
def catalogue (labels : List String) : List Cell :=
  ((labels.eraseDups).mergeSort (fun a b => decide (a ≤ b))).map
    (fun label => Cell.mk label (some ((Int.ofNat label.length).fdiv 4)))
def folded : Int := [9, -3, 2].foldl Int.add 0
theorem demo : catalogue ["beta", "amber", "beta"] =
    [Cell.mk "amber" (some 1), Cell.mk "beta" (some 1)] ∧ folded = 8 := by
  simp only [catalogue, List.mergeSort]; decide +kernel
