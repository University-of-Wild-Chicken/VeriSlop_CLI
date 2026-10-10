namespace VeriSlopReadableSource
abbrev entry_0_params : List VSCore3.Shape := [.int, .int]
abbrev entry_0_result : VSCore3.Shape := .int
def entry_0_body (env : VSCore3.Env entry_0_params.reverse) : VSCore3.Denote entry_0_result := by
  with_unfolding_all exact (((env).2.1) - ((env).1))
def entry_0_run (env : VSCore3.Env entry_0_params) : VSCore3.Denote entry_0_result :=
  entry_0_body (VSCore3.envReverse entry_0_params env)
def entry_0_named (p__0 : VSCore3.Denote .int) (p__1 : VSCore3.Denote .int) : VSCore3.Denote entry_0_result :=
  entry_0_run (p__0, (p__1, ()))
end VeriSlopReadableSource
