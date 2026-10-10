import VSCore3
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:cf7e0644acd90e4cbe0bf029031f63138c2561cbea937705382aed53b445b4cd. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 115, 99, 111, 114, 101, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 105, 100, 34, 58, 34, 101, 110, 97, 98, 108, 101, 100, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 98, 111, 111, 108, 34, 125, 93, 44, 34, 105, 100, 34, 58, 34, 83, 109, 97, 108, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 44, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 115, 109, 97, 108, 108, 34, 44, 34, 116, 121, 112, 101, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 83, 109, 97, 108, 108, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 105, 116, 101, 109, 115, 34, 44, 34, 116, 121, 112, 101, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 111, 112, 116, 105, 111, 110, 34, 58, 123, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 101, 114, 114, 111, 114, 34, 58, 34, 115, 116, 114, 105, 110, 103, 34, 44, 34, 111, 107, 34, 58, 34, 105, 110, 116, 34, 125, 125, 125, 125, 125, 93, 44, 34, 105, 100, 34, 58, 34, 67, 114, 97, 116, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 115, 117, 98, 34, 125, 44, 34, 105, 100, 34, 58, 34, 100, 105, 102, 102, 101, 114, 101, 110, 99, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 44, 34, 105, 110, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 99, 111, 110, 115, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 115, 117, 98, 34, 125, 44, 34, 110, 105, 108, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 115, 99, 114, 117, 116, 105, 110, 101, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 109, 97, 116, 99, 104, 95, 108, 105, 115, 116, 34, 125, 44, 34, 105, 100, 34, 58, 34, 108, 105, 115, 116, 67, 97, 115, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 108, 105, 115, 116, 34, 58, 34, 105, 110, 116, 34, 125, 44, 34, 105, 110, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 110, 111, 110, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 115, 99, 114, 117, 116, 105, 110, 101, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 115, 111, 109, 101, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 115, 117, 98, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 109, 97, 116, 99, 104, 95, 111, 112, 116, 105, 111, 110, 34, 125, 44, 34, 105, 100, 34, 58, 34, 111, 112, 116, 105, 111, 110, 67, 97, 115, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 111, 112, 116, 105, 111, 110, 34, 58, 34, 105, 110, 116, 34, 125, 44, 34, 105, 110, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 101, 114, 114, 111, 114, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 111, 107, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 44, 34, 115, 99, 114, 117, 116, 105, 110, 101, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 109, 97, 116, 99, 104, 95, 114, 101, 115, 117, 108, 116, 34, 125, 44, 34, 105, 100, 34, 58, 34, 114, 101, 115, 117, 108, 116, 67, 97, 115, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 101, 114, 114, 111, 114, 34, 58, 34, 115, 116, 114, 105, 110, 103, 34, 44, 34, 111, 107, 34, 58, 34, 105, 110, 116, 34, 125, 125, 44, 34, 105, 110, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [(VSCore3.DataDecl.record "Small" [("score", VSCore3.Ty.int), ("enabled", VSCore3.Ty.bool)]), (VSCore3.DataDecl.record "Crate" [("small", (VSCore3.Ty.record "Small")), ("items", (VSCore3.Ty.list (VSCore3.Ty.option (VSCore3.Ty.result VSCore3.Ty.string VSCore3.Ty.int))))])], helpers := [{ id := "listCase", params := [(VSCore3.Ty.list VSCore3.Ty.int), VSCore3.Ty.int], result := VSCore3.Ty.int, body := (VSCore3.Expr.matchList (VSCore3.Expr.var 1) (VSCore3.Expr.var 0) (VSCore3.Expr.bin VSCore.BinOp.sub (VSCore3.Expr.var 1) (VSCore3.Expr.var 2))) },
{ id := "optionCase", params := [(VSCore3.Ty.option VSCore3.Ty.int), VSCore3.Ty.int], result := VSCore3.Ty.int, body := (VSCore3.Expr.matchOption (VSCore3.Expr.var 1) (VSCore3.Expr.var 0) (VSCore3.Expr.bin VSCore.BinOp.sub (VSCore3.Expr.var 0) (VSCore3.Expr.var 1))) },
{ id := "resultCase", params := [(VSCore3.Ty.result VSCore3.Ty.string VSCore3.Ty.int), VSCore3.Ty.int], result := VSCore3.Ty.int, body := (VSCore3.Expr.matchResult (VSCore3.Expr.var 1) (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.var 0) (VSCore3.Expr.var 1)) (VSCore3.Expr.var 1)) }], entries := [{ id := "difference", params := [VSCore3.Ty.int, VSCore3.Ty.int], result := VSCore3.Ty.int, body := (VSCore3.Expr.bin VSCore.BinOp.sub (VSCore3.Expr.var 1) (VSCore3.Expr.var 0)) }] }
def profile : VSCore3.Profile := { enums := [("Mood", ["clear", "cloudy"])] }
def signatures : List VSCore3.EntrySig := [{ id := "difference", params := [VSCore3.Ty.int, VSCore3.Ty.int], result := VSCore3.Ty.int }]
def SourceParses : Prop := VSCore3.parseSource sourceBytes = .ok rawProgram
theorem source_parses : SourceParses := by rfl
def SourceChecks : Prop := VSCore3.checkProgram profile rawProgram = .ok signatures
theorem source_checks : SourceChecks := VSCore3.checkProgram_of_check (by decide +kernel)
def checkedProgram : VSCore3.CheckedProgram := (VSCore3.compileProgram profile rawProgram).toOption.getD
  { declarations := [], helpers := [], entries := [], signatures := [] }
theorem compiled_ok : VSCore3.compileProgram profile rawProgram = .ok checkedProgram := by with_unfolding_all rfl

/-- Exact accepted carrier "Int". -/
def adapter_0 : VSCore3.Adapter .int @Int :=
  VSCore3.intAdapter
def adapter_0_raw : VSCore3.RawLaws .int := VSCore3.intRawLaws
theorem adapter_0_decode_encode (x : @Int) :
    VSCore3.decode .int (adapter_0.encode x) = some (adapter_0.to x) :=
  adapter_0.decode_encode adapter_0_raw x

abbrev entry_difference : VSCore3.CompiledFunction :=
  { id := "difference", params := [.int, .int], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "difference").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_difference : VSCore3.findEntry checkedProgram "difference" = some entry_difference := by with_unfolding_all rfl
def source_fn_difference (x__0 : @Int) (x__1 : @Int) : @Int := by
  with_unfolding_all exact adapter_0.inv (entry_difference.run (adapter_0.to x__0, (adapter_0.to x__1, ())))
def Refines_difference : Prop := (∀ (x__0 : @Int), (∀ (x__1 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_difference x__0 x__1) (@ReadableFixture.difference x__0 x__1))))
def RawEval_difference : Prop := ∀ (x__0 : @Int) (x__1 : @Int),
  VSCore3.evalEntry profile rawProgram "difference" [adapter_0.encode x__0, adapter_0.encode x__1] =
    .ok (adapter_0.encode (source_fn_difference x__0 x__1))
theorem raw_eval_difference : RawEval_difference := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_difference.params [adapter_0.encode x__0, adapter_0.encode x__1] = some (adapter_0.to x__0, (adapter_0.to x__1, ())) := by
      change VSCore3.decodeEnv [.int, .int] [adapter_0.encode x__0, adapter_0.encode x__1] = some (adapter_0.to x__0, (adapter_0.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, adapter_0_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "difference" [adapter_0.encode x__0, adapter_0.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_difference, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_difference, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_difference.run (adapter_0.to x__0, (adapter_0.to x__1, ())))) =
      Except.ok (VSCore3.encode .int (adapter_0.to (adapter_0.inv (entry_difference.run (adapter_0.to x__0, (adapter_0.to x__1, ()))))))
    rw [adapter_0.to_from]
def InputsCover_difference : Prop := ∀ args, VSCore3.ArgsTyped entry_difference args → ∃ (x__0 : @Int) (x__1 : @Int), args = [adapter_0.encode x__0, adapter_0.encode x__1]
theorem inputs_cover_difference : InputsCover_difference := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [.int, .int] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [.int, .int] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact VSCore3.intRawLaws
    · exact VSCore3.intRawLaws) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, adapter_0.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from, adapter_0.to_from] using he.symm

/-- Accepted obligation RD1, theorem ReadableFixture.difference_contract, hash sha256:3333333333333333333333333333333333333333333333333333333333333333. -/
def Transfer_RD1 : Prop := (∀ (x__0 : @Int), (∀ (x__1 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_difference x__0 x__1) (@HSub.hSub.{0, 0, 0} @Int @Int @Int (@instHSub.{0} @Int @Int.instSub) x__0 x__1))))
theorem transfer_RD1 (h_difference : Refines_difference) : Transfer_RD1 := by
  have eq_difference : source_fn_difference = @ReadableFixture.difference := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_difference x__0 x__1
  have htransfer : ((∀ (x__0 : @Int), (∀ (x__1 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_difference x__0 x__1) (@HSub.hSub.{0, 0, 0} @Int @Int @Int (@instHSub.{0} @Int @Int.instSub) x__0 x__1))))) = ((∀ (x__0 : @Int), (∀ (x__1 : @Int), (@Eq.{1} @Int (@ReadableFixture.difference x__0 x__1) (@HSub.hSub.{0, 0, 0} @Int @Int @Int (@instHSub.{0} @Int @Int.instSub) x__0 x__1))))) := by
    rw [eq_difference]
  have hvalue : ((∀ (x__0 : @Int), (∀ (x__1 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_difference x__0 x__1) (@HSub.hSub.{0, 0, 0} @Int @Int @Int (@instHSub.{0} @Int @Int.instSub) x__0 x__1))))) := htransfer.symm ▸ (@ReadableFixture.difference_contract)
  exact hvalue

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_difference (@And @VeriSlopBridgeGoal.RawEval_difference (@And @VeriSlopBridgeGoal.Refines_difference @VeriSlopBridgeGoal.Transfer_RD1)))))
theorem edge_of_refines (h_difference : Refines_difference) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_difference, raw_eval_difference, h_difference, transfer_RD1 h_difference⟩

end VeriSlopBridgeGoal

namespace VeriSlopReadableSource
abbrev helper_0_params : List VSCore3.Shape := [(.list .int), .int]
abbrev helper_0_result : VSCore3.Shape := .int
def helper_0_body (env : VSCore3.Env helper_0_params.reverse) : VSCore3.Denote helper_0_result := by
  with_unfolding_all exact (List.casesOn ((env).2.1) ((env).1) (fun v__1 v__2 => (((v__1) - ((env).1)))))
def helper_0_run (env : VSCore3.Env helper_0_params) : VSCore3.Denote helper_0_result :=
  helper_0_body (VSCore3.envReverse helper_0_params env)
def helper_0_named (p__0 : VSCore3.Denote (.list .int)) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_0_result :=
  helper_0_run (p__0, (p__1, ()))
abbrev helper_1_params : List VSCore3.Shape := [(.option .int), .int]
abbrev helper_1_result : VSCore3.Shape := .int
def helper_1_body (env : VSCore3.Env helper_1_params.reverse) : VSCore3.Denote helper_1_result := by
  with_unfolding_all exact (Option.casesOn ((env).2.1) ((env).1) (fun v__1 => (((v__1) - ((env).1)))))
def helper_1_run (env : VSCore3.Env helper_1_params) : VSCore3.Denote helper_1_result :=
  helper_1_body (VSCore3.envReverse helper_1_params env)
def helper_1_named (p__0 : VSCore3.Denote (.option .int)) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_1_result :=
  helper_1_run (p__0, (p__1, ()))
abbrev helper_2_params : List VSCore3.Shape := [(.result .string .int), .int]
abbrev helper_2_result : VSCore3.Shape := .int
def helper_2_body (env : VSCore3.Env helper_2_params.reverse) : VSCore3.Denote helper_2_result := by
  with_unfolding_all exact (Sum.casesOn ((env).2.1) (fun v__2 => ((env).1)) (fun v__1 => (((v__1) + ((env).1)))))
def helper_2_run (env : VSCore3.Env helper_2_params) : VSCore3.Denote helper_2_result :=
  helper_2_body (VSCore3.envReverse helper_2_params env)
def helper_2_named (p__0 : VSCore3.Denote (.result .string .int)) (p__1 : VSCore3.Denote .int) : VSCore3.Denote helper_2_result :=
  helper_2_run (p__0, (p__1, ()))
abbrev entry_0_params : List VSCore3.Shape := [.int, .int]
abbrev entry_0_result : VSCore3.Shape := .int
def entry_0_body (env : VSCore3.Env entry_0_params.reverse) : VSCore3.Denote entry_0_result := by
  with_unfolding_all exact (((env).2.1) - ((env).1))
def entry_0_run (env : VSCore3.Env entry_0_params) : VSCore3.Denote entry_0_result :=
  entry_0_body (VSCore3.envReverse entry_0_params env)
def entry_0_named (p__0 : VSCore3.Denote .int) (p__1 : VSCore3.Denote .int) : VSCore3.Denote entry_0_result :=
  entry_0_run (p__0, (p__1, ()))
end VeriSlopReadableSource

namespace VeriSlopBridgeGoal.Readable
abbrev helper_0_compiled : VSCore3.CompiledFunction :=
  { id := "listCase", params := VeriSlopReadableSource.helper_0_params, result := VeriSlopReadableSource.helper_0_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "listCase")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
set_option pp.all false
#reduce (types := true) (proofs := true) helper_0_compiled.run
#reduce (types := true) (proofs := true) VeriSlopReadableSource.helper_0_run
end Readable
end VeriSlopBridgeGoal
