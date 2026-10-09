import Std
example : (["beta", "amber"] : List String).mergeSort (fun a b => decide (a ≤ b)) = ["amber", "beta"] := by decide +kernel
