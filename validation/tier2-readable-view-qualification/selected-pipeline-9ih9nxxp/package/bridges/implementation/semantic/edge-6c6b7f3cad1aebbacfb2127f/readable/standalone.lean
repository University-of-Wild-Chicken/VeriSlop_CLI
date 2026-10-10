import VSCore3
namespace VeriSlopReadableSource
abbrev entry_0_params : List VSCore3.Shape := [.int]
abbrev entry_0_result : VSCore3.Shape := .int
def entry_0_body (env : VSCore3.Env entry_0_params.reverse) : VSCore3.Denote entry_0_result := by
  with_unfolding_all exact (((env).1) + ((Int.negSucc 2)))
def entry_0_run (env : VSCore3.Env entry_0_params) : VSCore3.Denote entry_0_result :=
  entry_0_body (VSCore3.envReverse entry_0_params env)
def entry_0_named (p__0 : VSCore3.Denote .int) : VSCore3.Denote entry_0_result :=
  entry_0_run (p__0, ())
abbrev entry_1_params : List VSCore3.Shape := [(.record "Packet" ["amount", "words", "extra"] (.product .int (.product (.list .string) (.product (.option .int) .unit))))]
abbrev entry_1_result : VSCore3.Shape := .int
def entry_1_body (env : VSCore3.Env entry_1_params.reverse) : VSCore3.Denote entry_1_result := by
  with_unfolding_all exact ((((env).1).1) + ((Int.negSucc 2)))
def entry_1_run (env : VSCore3.Env entry_1_params) : VSCore3.Denote entry_1_result :=
  entry_1_body (VSCore3.envReverse entry_1_params env)
def entry_1_named (p__0 : VSCore3.Denote (.record "Packet" ["amount", "words", "extra"] (.product .int (.product (.list .string) (.product (.option .int) .unit))))) : VSCore3.Denote entry_1_result :=
  entry_1_run (p__0, ())
end VeriSlopReadableSource
