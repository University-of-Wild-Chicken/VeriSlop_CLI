import Std
example : ([9, -3, 2] : List Int).foldl Int.add 0 = 8 := by decide +kernel
