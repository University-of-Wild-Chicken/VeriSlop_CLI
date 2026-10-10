namespace VeriSlopReadableSource
abbrev helper_0_params : List VSCore3.Shape := [.nat, (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))]
abbrev helper_0_result : VSCore3.Shape := (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))
def helper_0_body (env : VSCore3.Env helper_0_params.reverse) : VSCore3.Denote helper_0_result := by
  with_unfolding_all exact ((((env).1).1, (((((env).1).2.1) + ((env).2.1)), ())) : VSCore3.Denote (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))))
def helper_0_run (env : VSCore3.Env helper_0_params) : VSCore3.Denote helper_0_result :=
  helper_0_body (VSCore3.envReverse helper_0_params env)
def helper_0_named (p__0 : VSCore3.Denote .nat) (p__1 : VSCore3.Denote (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))) : VSCore3.Denote helper_0_result :=
  helper_0_run (p__0, (p__1, ()))
abbrev helper_1_params : List VSCore3.Shape := [.nat, (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))]
abbrev helper_1_result : VSCore3.Shape := (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))
def helper_1_body (env : VSCore3.Env helper_1_params.reverse) : VSCore3.Denote helper_1_result := by
  with_unfolding_all exact (((helper_0_named ((env).2.1) (((env).1).1)), (((env).1).2.1, ())) : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))
def helper_1_run (env : VSCore3.Env helper_1_params) : VSCore3.Denote helper_1_result :=
  helper_1_body (VSCore3.envReverse helper_1_params env)
def helper_1_named (p__0 : VSCore3.Denote .nat) (p__1 : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) : VSCore3.Denote helper_1_result :=
  helper_1_run (p__0, (p__1, ()))
abbrev helper_2_params : List VSCore3.Shape := [(.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))), (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))]
abbrev helper_2_result : VSCore3.Shape := .bool
def helper_2_body (env : VSCore3.Env helper_2_params.reverse) : VSCore3.Denote helper_2_result := by
  with_unfolding_all exact (letI := VSCore3.denoteDecidableEq (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))); decide ((((env).1).1) = ((env).2.1)))
def helper_2_run (env : VSCore3.Env helper_2_params) : VSCore3.Denote helper_2_result :=
  helper_2_body (VSCore3.envReverse helper_2_params env)
def helper_2_named (p__0 : VSCore3.Denote (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))) (p__1 : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) : VSCore3.Denote helper_2_result :=
  helper_2_run (p__0, (p__1, ()))
abbrev helper_3_params : List VSCore3.Shape := [(.enum "Shade" ["light", "dark", "neutral"]), .nat, (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))]
abbrev helper_3_result : VSCore3.Shape := .nat
def helper_3_body (env : VSCore3.Env helper_3_params.reverse) : VSCore3.Denote helper_3_result := by
  with_unfolding_all exact (if ((letI := VSCore3.denoteDecidableEq (.enum "Shade" ["light", "dark", "neutral"]); decide (((((env).1).1).1) = ((env).2.2.1)))) then ((((env).2.1) + ((((env).1).1).2.1))) else ((env).2.1))
def helper_3_run (env : VSCore3.Env helper_3_params) : VSCore3.Denote helper_3_result :=
  helper_3_body (VSCore3.envReverse helper_3_params env)
def helper_3_named (p__0 : VSCore3.Denote (.enum "Shade" ["light", "dark", "neutral"])) (p__1 : VSCore3.Denote .nat) (p__2 : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) : VSCore3.Denote helper_3_result :=
  helper_3_run (p__0, (p__1, (p__2, ())))
abbrev entry_0_params : List VSCore3.Shape := [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat]
abbrev entry_0_result : VSCore3.Shape := (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))
def entry_0_body (env : VSCore3.Env entry_0_params.reverse) : VSCore3.Denote entry_0_result := by
  with_unfolding_all exact (List.map (fun v__1 => ((helper_1_named ((env).1) (v__1)))) ((env).2.1))
def entry_0_run (env : VSCore3.Env entry_0_params) : VSCore3.Denote entry_0_result :=
  entry_0_body (VSCore3.envReverse entry_0_params env)
def entry_0_named (p__0 : VSCore3.Denote (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))) (p__1 : VSCore3.Denote .nat) : VSCore3.Denote entry_0_result :=
  entry_0_run (p__0, (p__1, ()))
abbrev entry_1_params : List VSCore3.Shape := [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))]
abbrev entry_1_result : VSCore3.Shape := (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))
def entry_1_body (env : VSCore3.Env entry_1_params.reverse) : VSCore3.Denote entry_1_result := by
  with_unfolding_all exact (List.filter (fun v__1 => ((helper_2_named ((env).1) (v__1)))) ((env).2.1))
def entry_1_run (env : VSCore3.Env entry_1_params) : VSCore3.Denote entry_1_result :=
  entry_1_body (VSCore3.envReverse entry_1_params env)
def entry_1_named (p__0 : VSCore3.Denote (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))) (p__1 : VSCore3.Denote (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))) : VSCore3.Denote entry_1_result :=
  entry_1_run (p__0, (p__1, ()))
abbrev entry_2_params : List VSCore3.Shape := [(.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))), .nat, (.enum "Shade" ["light", "dark", "neutral"])]
abbrev entry_2_result : VSCore3.Shape := .nat
def entry_2_body (env : VSCore3.Env entry_2_params.reverse) : VSCore3.Denote entry_2_result := by
  with_unfolding_all exact (List.foldl (fun v__1 v__2 => ((helper_3_named ((env).1) (v__1) (v__2)))) ((env).2.1) ((env).2.2.1))
def entry_2_run (env : VSCore3.Env entry_2_params) : VSCore3.Denote entry_2_result :=
  entry_2_body (VSCore3.envReverse entry_2_params env)
def entry_2_named (p__0 : VSCore3.Denote (.list (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit))))) (p__1 : VSCore3.Denote .nat) (p__2 : VSCore3.Denote (.enum "Shade" ["light", "dark", "neutral"])) : VSCore3.Denote entry_2_result :=
  entry_2_run (p__0, (p__1, (p__2, ())))
abbrev entry_3_params : List VSCore3.Shape := [(.enum "Shade" ["light", "dark", "neutral"]), (.enum "Shade" ["light", "dark", "neutral"])]
abbrev entry_3_result : VSCore3.Shape := .bool
def entry_3_body (env : VSCore3.Env entry_3_params.reverse) : VSCore3.Denote entry_3_result := by
  with_unfolding_all exact (letI := VSCore3.denoteDecidableEq (.enum "Shade" ["light", "dark", "neutral"]); decide (((env).2.1) = ((env).1)))
def entry_3_run (env : VSCore3.Env entry_3_params) : VSCore3.Denote entry_3_result :=
  entry_3_body (VSCore3.envReverse entry_3_params env)
def entry_3_named (p__0 : VSCore3.Denote (.enum "Shade" ["light", "dark", "neutral"])) (p__1 : VSCore3.Denote (.enum "Shade" ["light", "dark", "neutral"])) : VSCore3.Denote entry_3_result :=
  entry_3_run (p__0, (p__1, ()))
abbrev entry_4_params : List VSCore3.Shape := [(.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))]
abbrev entry_4_result : VSCore3.Shape := .nat
def entry_4_body (env : VSCore3.Env entry_4_params.reverse) : VSCore3.Denote entry_4_result := by
  with_unfolding_all exact (0 : Nat)
def entry_4_run (env : VSCore3.Env entry_4_params) : VSCore3.Denote entry_4_result :=
  entry_4_body (VSCore3.envReverse entry_4_params env)
def entry_4_named (p__0 : VSCore3.Denote (.record "Envelope" ["parcel", "active"] (.product (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit))) (.product .bool .unit)))) : VSCore3.Denote entry_4_result :=
  entry_4_run (p__0, ())
end VeriSlopReadableSource
