import VSCore3
namespace VeriSlopReadableSource
abbrev helper_2_params : List VSCore3.Shape := [(.list .int), .int]
abbrev helper_2_result : VSCore3.Shape := (.list .int)
def helper_2_body (env : VSCore3.Env helper_2_params.reverse) : VSCore3.Denote helper_2_result := by
  with_unfolding_all exact (List.filter (fun v__1 => (decide ((v__1) ≤ ((env).1)))) ((env).2.1))
def helper_2_run (env : VSCore3.Env helper_2_params) : VSCore3.Denote helper_2_result :=
  helper_2_body (VSCore3.envReverse helper_2_params env)
def helper_2_named (p__0 : VSCore3.Denote (.list .int)) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_2_result :=
  helper_2_run (p__0, (p__1, ()))
abbrev helper_3_params : List VSCore3.Shape := [(.list .int), .int, .int]
abbrev helper_3_result : VSCore3.Shape := .int
def helper_3_body (env : VSCore3.Env helper_3_params.reverse) : VSCore3.Denote helper_3_result := by
  with_unfolding_all exact (List.foldl (fun v__1 v__2 => (((((v__1) + ((env).1))) - (v__2)))) ((env).2.1) ((env).2.2.1))
def helper_3_run (env : VSCore3.Env helper_3_params) : VSCore3.Denote helper_3_result :=
  helper_3_body (VSCore3.envReverse helper_3_params env)
def helper_3_named (p__0 : VSCore3.Denote (.list .int)) (p__1 : VSCore3.Denote .int) (p__2 : VSCore3.Denote .int) : VSCore3.Denote helper_3_result :=
  helper_3_run (p__0, (p__1, (p__2, ())))
abbrev helper_4_params : List VSCore3.Shape := [.nat, .nat, .nat]
abbrev helper_4_result : VSCore3.Shape := .nat
def helper_4_body (env : VSCore3.Env helper_4_params.reverse) : VSCore3.Denote helper_4_result := by
  with_unfolding_all exact (Nat.rec ((env).2.1) (fun v__2 v__1 => (((((v__1) + ((env).1))) - (v__2)))) ((env).2.2.1))
def helper_4_run (env : VSCore3.Env helper_4_params) : VSCore3.Denote helper_4_result :=
  helper_4_body (VSCore3.envReverse helper_4_params env)
def helper_4_named (p__0 : VSCore3.Denote .nat) (p__1 : VSCore3.Denote .nat) (p__2 : VSCore3.Denote .nat) : VSCore3.Denote helper_4_result :=
  helper_4_run (p__0, (p__1, (p__2, ())))
abbrev helper_5_params : List VSCore3.Shape := [(.list .int), .int]
abbrev helper_5_result : VSCore3.Shape := .int
def helper_5_body (env : VSCore3.Env helper_5_params.reverse) : VSCore3.Denote helper_5_result := by
  with_unfolding_all exact (List.casesOn ((env).2.1) ((env).1) (fun v__1 v__2 => (((v__1) - ((env).1)))))
def helper_5_run (env : VSCore3.Env helper_5_params) : VSCore3.Denote helper_5_result :=
  helper_5_body (VSCore3.envReverse helper_5_params env)
def helper_5_named (p__0 : VSCore3.Denote (.list .int)) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_5_result :=
  helper_5_run (p__0, (p__1, ()))
abbrev helper_6_params : List VSCore3.Shape := [(.option .int), .int]
abbrev helper_6_result : VSCore3.Shape := .int
def helper_6_body (env : VSCore3.Env helper_6_params.reverse) : VSCore3.Denote helper_6_result := by
  with_unfolding_all exact (Option.casesOn ((env).2.1) ((env).1) (fun v__1 => (((v__1) - ((env).1)))))
def helper_6_run (env : VSCore3.Env helper_6_params) : VSCore3.Denote helper_6_result :=
  helper_6_body (VSCore3.envReverse helper_6_params env)
def helper_6_named (p__0 : VSCore3.Denote (.option .int)) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_6_result :=
  helper_6_run (p__0, (p__1, ()))
abbrev helper_7_params : List VSCore3.Shape := [(.result .string .int), .int]
abbrev helper_7_result : VSCore3.Shape := .int
def helper_7_body (env : VSCore3.Env helper_7_params.reverse) : VSCore3.Denote helper_7_result := by
  with_unfolding_all exact (Sum.casesOn ((env).2.1) (fun v__2 => ((env).1)) (fun v__1 => (((v__1) + ((env).1)))))
def helper_7_run (env : VSCore3.Env helper_7_params) : VSCore3.Denote helper_7_result :=
  helper_7_body (VSCore3.envReverse helper_7_params env)
def helper_7_named (p__0 : VSCore3.Denote (.result .string .int)) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_7_result :=
  helper_7_run (p__0, (p__1, ()))
abbrev helper_8_params : List VSCore3.Shape := [.int]
abbrev helper_8_result : VSCore3.Shape := (.result .string .int)
def helper_8_body (env : VSCore3.Env helper_8_params.reverse) : VSCore3.Denote helper_8_result := by
  with_unfolding_all exact (Sum.inr ((env).1) : VSCore3.Denote (.result .string .int))
def helper_8_run (env : VSCore3.Env helper_8_params) : VSCore3.Denote helper_8_result :=
  helper_8_body (VSCore3.envReverse helper_8_params env)
def helper_8_named (p__0 : VSCore3.Denote .int) : VSCore3.Denote helper_8_result :=
  helper_8_run (p__0, ())
abbrev helper_9_params : List VSCore3.Shape := [.string]
abbrev helper_9_result : VSCore3.Shape := (.result .string .int)
def helper_9_body (env : VSCore3.Env helper_9_params.reverse) : VSCore3.Denote helper_9_result := by
  with_unfolding_all exact (Sum.inl ((env).1) : VSCore3.Denote (.result .string .int))
def helper_9_run (env : VSCore3.Env helper_9_params) : VSCore3.Denote helper_9_result :=
  helper_9_body (VSCore3.envReverse helper_9_params env)
def helper_9_named (p__0 : VSCore3.Denote .string) : VSCore3.Denote helper_9_result :=
  helper_9_run (p__0, ())
abbrev helper_10_params : List VSCore3.Shape := [.int, .bool]
abbrev helper_10_result : VSCore3.Shape := (.option .int)
def helper_10_body (env : VSCore3.Env helper_10_params.reverse) : VSCore3.Denote helper_10_result := by
  with_unfolding_all exact (if ((env).1) then ((some ((env).2.1))) else ((none : VSCore3.Denote (.option .int))))
def helper_10_run (env : VSCore3.Env helper_10_params) : VSCore3.Denote helper_10_result :=
  helper_10_body (VSCore3.envReverse helper_10_params env)
def helper_10_named (p__0 : VSCore3.Denote .int) (p__1 : VSCore3.Denote .bool) : VSCore3.Denote helper_10_result :=
  helper_10_run (p__0, (p__1, ()))
abbrev helper_11_params : List VSCore3.Shape := [.int, .int]
abbrev helper_11_result : VSCore3.Shape := .int
def helper_11_body (env : VSCore3.Env helper_11_params.reverse) : VSCore3.Denote helper_11_result := by
  with_unfolding_all exact (let v__1 : VSCore3.Denote .int := ((((env).2.1) * ((env).1))); (if (((decide (((env).2.1) < ((env).1))) && ((!((letI := VSCore3.denoteDecidableEq .int; decide (((env).2.1) = ((env).1)))))))) then ((Int.neg (v__1))) else ((Int.fdiv (v__1) ((env).1)))))
def helper_11_run (env : VSCore3.Env helper_11_params) : VSCore3.Denote helper_11_result :=
  helper_11_body (VSCore3.envReverse helper_11_params env)
def helper_11_named (p__0 : VSCore3.Denote .int) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_11_result :=
  helper_11_run (p__0, (p__1, ()))
abbrev helper_12_params : List VSCore3.Shape := [.nat, .nat]
abbrev helper_12_result : VSCore3.Shape := .nat
def helper_12_body (env : VSCore3.Env helper_12_params.reverse) : VSCore3.Denote helper_12_result := by
  with_unfolding_all exact (Int.toNat ((Int.ofNat ((((((env).2.1) + ((env).1))) * ((((env).2.1) - ((env).1))))))))
def helper_12_run (env : VSCore3.Env helper_12_params) : VSCore3.Denote helper_12_result :=
  helper_12_body (VSCore3.envReverse helper_12_params env)
def helper_12_named (p__0 : VSCore3.Denote .nat) (p__1 : VSCore3.Denote .nat) : VSCore3.Denote helper_12_result :=
  helper_12_run (p__0, (p__1, ()))
abbrev helper_13_params : List VSCore3.Shape := [(.list .int), .nat]
abbrev helper_13_result : VSCore3.Shape := .int
def helper_13_body (env : VSCore3.Env helper_13_params.reverse) : VSCore3.Denote helper_13_result := by
  with_unfolding_all exact (List.sum ((List.eraseDups ((List.mergeSort ((List.reverse ((((env).2.1) ++ ((((Int.negSucc 6)) :: (([] : VSCore3.Denote (.list .int))))))))) (fun a b => decide (a ≤ b)))))))
def helper_13_run (env : VSCore3.Env helper_13_params) : VSCore3.Denote helper_13_result :=
  helper_13_body (VSCore3.envReverse helper_13_params env)
def helper_13_named (p__0 : VSCore3.Denote (.list .int)) (p__1 : VSCore3.Denote .nat) : VSCore3.Denote helper_13_result :=
  helper_13_run (p__0, (p__1, ()))
abbrev helper_14_params : List VSCore3.Shape := [.nat]
abbrev helper_14_result : VSCore3.Shape := (.option .nat)
def helper_14_body (env : VSCore3.Env helper_14_params.reverse) : VSCore3.Denote helper_14_result := by
  with_unfolding_all exact (List.get?Internal ((List.range ((env).1))) ((List.length ((List.range ((env).1))))))
def helper_14_run (env : VSCore3.Env helper_14_params) : VSCore3.Denote helper_14_result :=
  helper_14_body (VSCore3.envReverse helper_14_params env)
def helper_14_named (p__0 : VSCore3.Denote .nat) : VSCore3.Denote helper_14_result :=
  helper_14_run (p__0, ())
abbrev helper_15_params : List VSCore3.Shape := [(.list .string), .string]
abbrev helper_15_result : VSCore3.Shape := (.list .string)
def helper_15_body (env : VSCore3.Env helper_15_params.reverse) : VSCore3.Denote helper_15_result := by
  with_unfolding_all exact (List.mergeSort ((List.eraseDups (((String.ofList ([955, 32, 115, 110, 111, 119].map Char.ofNat)) :: ((env).2.1))))) (fun a b => decide (a ≤ b)))
def helper_15_run (env : VSCore3.Env helper_15_params) : VSCore3.Denote helper_15_result :=
  helper_15_body (VSCore3.envReverse helper_15_params env)
def helper_15_named (p__0 : VSCore3.Denote (.list .string)) (p__1 : VSCore3.Denote .string) : VSCore3.Denote helper_15_result :=
  helper_15_run (p__0, (p__1, ()))
abbrev helper_16_params : List VSCore3.Shape := [.string, .string]
abbrev helper_16_result : VSCore3.Shape := .bool
def helper_16_body (env : VSCore3.Env helper_16_params.reverse) : VSCore3.Denote helper_16_result := by
  with_unfolding_all exact ((decide (((env).2.1) < ((env).1))) || (decide (((env).2.1) ≤ ((env).1))))
def helper_16_run (env : VSCore3.Env helper_16_params) : VSCore3.Denote helper_16_result :=
  helper_16_body (VSCore3.envReverse helper_16_params env)
def helper_16_named (p__0 : VSCore3.Denote .string) (p__1 : VSCore3.Denote .string) : VSCore3.Denote helper_16_result :=
  helper_16_run (p__0, (p__1, ()))
abbrev helper_17_params : List VSCore3.Shape := []
abbrev helper_17_result : VSCore3.Shape := .unit
def helper_17_body (env : VSCore3.Env helper_17_params.reverse) : VSCore3.Denote helper_17_result := by
  with_unfolding_all exact ()
def helper_17_run (env : VSCore3.Env helper_17_params) : VSCore3.Denote helper_17_result :=
  helper_17_body (VSCore3.envReverse helper_17_params env)
def helper_17_named  : VSCore3.Denote helper_17_result :=
  helper_17_run ()
abbrev helper_18_params : List VSCore3.Shape := []
abbrev helper_18_result : VSCore3.Shape := .bool
def helper_18_body (env : VSCore3.Env helper_18_params.reverse) : VSCore3.Denote helper_18_result := by
  with_unfolding_all exact true
def helper_18_run (env : VSCore3.Env helper_18_params) : VSCore3.Denote helper_18_result :=
  helper_18_body (VSCore3.envReverse helper_18_params env)
def helper_18_named  : VSCore3.Denote helper_18_result :=
  helper_18_run ()
abbrev helper_19_params : List VSCore3.Shape := []
abbrev helper_19_result : VSCore3.Shape := .nat
def helper_19_body (env : VSCore3.Env helper_19_params.reverse) : VSCore3.Denote helper_19_result := by
  with_unfolding_all exact (11 : Nat)
def helper_19_run (env : VSCore3.Env helper_19_params) : VSCore3.Denote helper_19_result :=
  helper_19_body (VSCore3.envReverse helper_19_params env)
def helper_19_named  : VSCore3.Denote helper_19_result :=
  helper_19_run ()
abbrev helper_20_params : List VSCore3.Shape := []
abbrev helper_20_result : VSCore3.Shape := (.enum "Mood" ["clear", "cloudy"])
def helper_20_body (env : VSCore3.Env helper_20_params.reverse) : VSCore3.Denote helper_20_result := by
  with_unfolding_all exact (⟨"clear", by decide +kernel⟩ : VSCore3.Denote (.enum "Mood" ["clear", "cloudy"]))
def helper_20_run (env : VSCore3.Env helper_20_params) : VSCore3.Denote helper_20_result :=
  helper_20_body (VSCore3.envReverse helper_20_params env)
def helper_20_named  : VSCore3.Denote helper_20_result :=
  helper_20_run ()
abbrev helper_21_params : List VSCore3.Shape := [.int, .bool]
abbrev helper_21_result : VSCore3.Shape := (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit)))
def helper_21_body (env : VSCore3.Env helper_21_params.reverse) : VSCore3.Denote helper_21_result := by
  with_unfolding_all exact (((env).2.1, ((env).1, ())) : VSCore3.Denote (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))))
def helper_21_run (env : VSCore3.Env helper_21_params) : VSCore3.Denote helper_21_result :=
  helper_21_body (VSCore3.envReverse helper_21_params env)
def helper_21_named (p__0 : VSCore3.Denote .int) (p__1 : VSCore3.Denote .bool) : VSCore3.Denote helper_21_result :=
  helper_21_run (p__0, (p__1, ()))
abbrev helper_22_params : List VSCore3.Shape := [(.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))), (.list (.option (.result .string .int)))]
abbrev helper_22_result : VSCore3.Shape := (.record "Crate" ["small", "items"] (.product (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))) (.product (.list (.option (.result .string .int))) .unit)))
def helper_22_body (env : VSCore3.Env helper_22_params.reverse) : VSCore3.Denote helper_22_result := by
  with_unfolding_all exact (((env).2.1, ((env).1, ())) : VSCore3.Denote (.record "Crate" ["small", "items"] (.product (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))) (.product (.list (.option (.result .string .int))) .unit))))
def helper_22_run (env : VSCore3.Env helper_22_params) : VSCore3.Denote helper_22_result :=
  helper_22_body (VSCore3.envReverse helper_22_params env)
def helper_22_named (p__0 : VSCore3.Denote (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit)))) (p__1 : VSCore3.Denote (.list (.option (.result .string .int)))) : VSCore3.Denote helper_22_result :=
  helper_22_run (p__0, (p__1, ()))
abbrev helper_23_params : List VSCore3.Shape := [(.record "Crate" ["small", "items"] (.product (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))) (.product (.list (.option (.result .string .int))) .unit)))]
abbrev helper_23_result : VSCore3.Shape := .int
def helper_23_body (env : VSCore3.Env helper_23_params.reverse) : VSCore3.Denote helper_23_result := by
  with_unfolding_all exact (((env).1).1).1
def helper_23_run (env : VSCore3.Env helper_23_params) : VSCore3.Denote helper_23_result :=
  helper_23_body (VSCore3.envReverse helper_23_params env)
def helper_23_named (p__0 : VSCore3.Denote (.record "Crate" ["small", "items"] (.product (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))) (.product (.list (.option (.result .string .int))) .unit)))) : VSCore3.Denote helper_23_result :=
  helper_23_run (p__0, ())
abbrev helper_24_params : List VSCore3.Shape := [(.record "Crate" ["small", "items"] (.product (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))) (.product (.list (.option (.result .string .int))) .unit))), (.record "Crate" ["small", "items"] (.product (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))) (.product (.list (.option (.result .string .int))) .unit)))]
abbrev helper_24_result : VSCore3.Shape := .bool
def helper_24_body (env : VSCore3.Env helper_24_params.reverse) : VSCore3.Denote helper_24_result := by
  with_unfolding_all exact (letI := VSCore3.denoteDecidableEq (.record "Crate" ["small", "items"] (.product (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))) (.product (.list (.option (.result .string .int))) .unit))); decide (((env).2.1) = ((env).1)))
def helper_24_run (env : VSCore3.Env helper_24_params) : VSCore3.Denote helper_24_result :=
  helper_24_body (VSCore3.envReverse helper_24_params env)
def helper_24_named (p__0 : VSCore3.Denote (.record "Crate" ["small", "items"] (.product (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))) (.product (.list (.option (.result .string .int))) .unit)))) (p__1 : VSCore3.Denote (.record "Crate" ["small", "items"] (.product (.record "Small" ["score", "enabled"] (.product .int (.product .bool .unit))) (.product (.list (.option (.result .string .int))) .unit)))) : VSCore3.Denote helper_24_result :=
  helper_24_run (p__0, (p__1, ()))
abbrev helper_25_params : List VSCore3.Shape := [.int, .int]
abbrev helper_25_result : VSCore3.Shape := .int
def helper_25_body (env : VSCore3.Env helper_25_params.reverse) : VSCore3.Denote helper_25_result := by
  with_unfolding_all exact (((env).2.1) - ((env).1))
def helper_25_run (env : VSCore3.Env helper_25_params) : VSCore3.Denote helper_25_result :=
  helper_25_body (VSCore3.envReverse helper_25_params env)
def helper_25_named (p__0 : VSCore3.Denote .int) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_25_result :=
  helper_25_run (p__0, (p__1, ()))
abbrev helper_0_params : List VSCore3.Shape := [.int, .int]
abbrev helper_0_result : VSCore3.Shape := .int
def helper_0_body (env : VSCore3.Env helper_0_params.reverse) : VSCore3.Denote helper_0_result := by
  with_unfolding_all exact (helper_25_named ((env).2.1) ((env).1))
def helper_0_run (env : VSCore3.Env helper_0_params) : VSCore3.Denote helper_0_result :=
  helper_0_body (VSCore3.envReverse helper_0_params env)
def helper_0_named (p__0 : VSCore3.Denote .int) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_0_result :=
  helper_0_run (p__0, (p__1, ()))
abbrev helper_1_params : List VSCore3.Shape := [(.list .int), .int]
abbrev helper_1_result : VSCore3.Shape := (.list .int)
def helper_1_body (env : VSCore3.Env helper_1_params.reverse) : VSCore3.Denote helper_1_result := by
  with_unfolding_all exact (List.map (fun v__1 => ((helper_0_named (v__1) ((env).1)))) ((env).2.1))
def helper_1_run (env : VSCore3.Env helper_1_params) : VSCore3.Denote helper_1_result :=
  helper_1_body (VSCore3.envReverse helper_1_params env)
def helper_1_named (p__0 : VSCore3.Denote (.list .int)) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_1_result :=
  helper_1_run (p__0, (p__1, ()))
abbrev entry_0_params : List VSCore3.Shape := [.int, .int]
abbrev entry_0_result : VSCore3.Shape := .int
def entry_0_body (env : VSCore3.Env entry_0_params.reverse) : VSCore3.Denote entry_0_result := by
  with_unfolding_all exact (((env).2.1) - ((env).1))
def entry_0_run (env : VSCore3.Env entry_0_params) : VSCore3.Denote entry_0_result :=
  entry_0_body (VSCore3.envReverse entry_0_params env)
def entry_0_named (p__0 : VSCore3.Denote .int) (p__1 : VSCore3.Denote .int) : VSCore3.Denote entry_0_result :=
  entry_0_run (p__0, (p__1, ()))
end VeriSlopReadableSource
