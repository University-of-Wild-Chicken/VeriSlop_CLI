import VSCore3
namespace VeriSlopReadableSource
abbrev entry_0_params : List VSCore3.Shape := [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))]
abbrev entry_0_result : VSCore3.Shape := (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))
def entry_0_body (env : VSCore3.Env entry_0_params.reverse) : VSCore3.Denote entry_0_result := by
  with_unfolding_all exact (List.map (fun v__1 => (((((((v__1).1).1, (((((v__1).1).2.1) + ((1 : Nat))), ())) : VSCore3.Denote (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit)))), ((v__1).2.1, ())) : VSCore3.Denote (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))))) ((env).1))
def entry_0_run (env : VSCore3.Env entry_0_params) : VSCore3.Denote entry_0_result :=
  entry_0_body (VSCore3.envReverse entry_0_params env)
def entry_0_named (p__0 : VSCore3.Denote (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))) : VSCore3.Denote entry_0_result :=
  entry_0_run (p__0, ())
abbrev entry_1_params : List VSCore3.Shape := [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit)))]
abbrev entry_1_result : VSCore3.Shape := (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))
def entry_1_body (env : VSCore3.Env entry_1_params.reverse) : VSCore3.Denote entry_1_result := by
  with_unfolding_all exact (List.filter (fun v__1 => ((letI := VSCore3.denoteDecidableEq (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))); decide (((v__1).1) = ((env).1))))) ((env).2.1))
def entry_1_run (env : VSCore3.Env entry_1_params) : VSCore3.Denote entry_1_result :=
  entry_1_body (VSCore3.envReverse entry_1_params env)
def entry_1_named (p__0 : VSCore3.Denote (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))) (p__1 : VSCore3.Denote (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit)))) : VSCore3.Denote entry_1_result :=
  entry_1_run (p__0, (p__1, ()))
abbrev entry_2_params : List VSCore3.Shape := [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))]
abbrev entry_2_result : VSCore3.Shape := .nat
def entry_2_body (env : VSCore3.Env entry_2_params.reverse) : VSCore3.Denote entry_2_result := by
  with_unfolding_all exact (List.foldl (fun v__1 v__2 => ((if ((letI := VSCore3.denoteDecidableEq (.enum "Tone" ["cold", "warm"]); decide ((((v__2).1).1) = ((⟨"cold", by decide +kernel⟩ : VSCore3.Denote (.enum "Tone" ["cold", "warm"])))))) then (((v__1) + (((v__2).1).2.1))) else (v__1)))) ((0 : Nat)) ((env).1))
def entry_2_run (env : VSCore3.Env entry_2_params) : VSCore3.Denote entry_2_result :=
  entry_2_body (VSCore3.envReverse entry_2_params env)
def entry_2_named (p__0 : VSCore3.Denote (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))) : VSCore3.Denote entry_2_result :=
  entry_2_run (p__0, ())
end VeriSlopReadableSource
