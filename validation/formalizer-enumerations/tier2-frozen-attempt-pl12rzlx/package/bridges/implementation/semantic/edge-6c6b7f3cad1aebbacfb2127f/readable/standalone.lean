import VSCore3
namespace VeriSlopReadableSource
abbrev entry_0_params : List VSCore3.Shape := [(.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))]
abbrev entry_0_result : VSCore3.Shape := (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))
def entry_0_body (env : VSCore3.Env entry_0_params.reverse) : VSCore3.Denote entry_0_result := by
  with_unfolding_all exact ((((env).1).1, ((if ((letI := VSCore3.denoteDecidableEq (.enum "Compass" ["north", "south", "center"]); decide ((((env).1).1) = ((⟨"north", by decide +kernel⟩ : VSCore3.Denote (.enum "Compass" ["north", "south", "center"])))))) then (((((env).1).2.1) + ((Int.ofNat 2)))) else (((((env).1).2.1) - ((Int.ofNat 3))))), ())) : VSCore3.Denote (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit))))
def entry_0_run (env : VSCore3.Env entry_0_params) : VSCore3.Denote entry_0_result :=
  entry_0_body (VSCore3.envReverse entry_0_params env)
def entry_0_named (p__0 : VSCore3.Denote (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))) : VSCore3.Denote entry_0_result :=
  entry_0_run (p__0, ())
end VeriSlopReadableSource
