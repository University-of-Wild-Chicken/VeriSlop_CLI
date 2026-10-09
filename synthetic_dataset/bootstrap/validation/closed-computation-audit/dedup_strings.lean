import Std
example : (["beta", "amber", "beta"] : List String).eraseDups = ["beta", "amber"] := by decide +kernel
