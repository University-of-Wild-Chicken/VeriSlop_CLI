import Std
example : ([3, 1] : List Int).mergeSort (fun a b => decide (a ≤ b)) = [1, 3] := by decide +kernel
