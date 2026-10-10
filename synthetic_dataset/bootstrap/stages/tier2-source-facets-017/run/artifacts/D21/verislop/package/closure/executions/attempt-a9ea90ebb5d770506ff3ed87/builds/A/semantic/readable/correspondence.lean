namespace VeriSlopBridgeGoal.Readable
abbrev helper_0_compiled : VSCore3.CompiledFunction :=
  { id := "aggregate", params := VeriSlopReadableSource.helper_0_params, result := VeriSlopReadableSource.helper_0_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "aggregate")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_0 : (checkedProgram.helpers.find? (fun h => h.id == "aggregate")) = some helper_0_compiled := by with_unfolding_all rfl
theorem signature_helper_0 : helper_0_compiled.params = VeriSlopReadableSource.helper_0_params ∧ helper_0_compiled.result = VeriSlopReadableSource.helper_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_0 : Prop := VSCore3.ReadableRunEquals helper_0_compiled VeriSlopReadableSource.helper_0_params VeriSlopReadableSource.helper_0_result VeriSlopReadableSource.helper_0_run
set_option smartUnfolding false in
theorem runEquals_helper_0 : RunEquals_helper_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_1_compiled : VSCore3.CompiledFunction :=
  { id := "group_rows", params := VeriSlopReadableSource.helper_1_params, result := VeriSlopReadableSource.helper_1_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "group_rows")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_1 : (checkedProgram.helpers.find? (fun h => h.id == "group_rows")) = some helper_1_compiled := by with_unfolding_all rfl
theorem signature_helper_1 : helper_1_compiled.params = VeriSlopReadableSource.helper_1_params ∧ helper_1_compiled.result = VeriSlopReadableSource.helper_1_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_1 : Prop := VSCore3.ReadableRunEquals helper_1_compiled VeriSlopReadableSource.helper_1_params VeriSlopReadableSource.helper_1_result VeriSlopReadableSource.helper_1_run
set_option smartUnfolding false in
theorem runEquals_helper_1 : RunEquals_helper_1 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_0_compiled : VSCore3.CompiledFunction :=
  { id := "solve", params := VeriSlopReadableSource.entry_0_params, result := VeriSlopReadableSource.entry_0_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "solve").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_0 : (VSCore3.findEntry checkedProgram "solve") = some entry_0_compiled := by with_unfolding_all rfl
theorem signature_entry_0 : entry_0_compiled.params = VeriSlopReadableSource.entry_0_params ∧ entry_0_compiled.result = VeriSlopReadableSource.entry_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_0 : Prop := VSCore3.ReadableRunEquals entry_0_compiled VeriSlopReadableSource.entry_0_params VeriSlopReadableSource.entry_0_result VeriSlopReadableSource.entry_0_run
set_option smartUnfolding false in
theorem runEquals_entry_0 : RunEquals_entry_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
def readable_fn_solve (x__0 : @VeriSlopAST.Input) : (@List.{0} @VeriSlopAST.Row) := by
  with_unfolding_all exact adapter_9.inv (VeriSlopReadableSource.entry_0_run (adapter_6.to x__0, ()))
set_option smartUnfolding false in
theorem source_eq_solve (x__0 : @VeriSlopAST.Input) : source_fn_solve x__0 = readable_fn_solve x__0 := by with_unfolding_all rfl
theorem raw_eval_solve (x__0 : @VeriSlopAST.Input) :
  VSCore3.evalEntry profile rawProgram "solve" [adapter_6.encode x__0] =
    .ok (adapter_9.encode (readable_fn_solve x__0)) := by
  rw [← source_eq_solve x__0]
  exact VeriSlopBridgeGoal.raw_eval_solve x__0
end VeriSlopBridgeGoal.Readable
