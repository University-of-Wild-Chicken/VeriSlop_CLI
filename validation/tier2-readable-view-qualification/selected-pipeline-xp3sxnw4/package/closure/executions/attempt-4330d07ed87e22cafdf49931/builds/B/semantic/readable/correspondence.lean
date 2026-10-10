namespace VeriSlopBridgeGoal.Readable
abbrev entry_0_compiled : VSCore3.CompiledFunction :=
  { id := "shift", params := VeriSlopReadableSource.entry_0_params, result := VeriSlopReadableSource.entry_0_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "shift").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_0 : (VSCore3.findEntry checkedProgram "shift") = some entry_0_compiled := by with_unfolding_all rfl
theorem signature_entry_0 : entry_0_compiled.params = VeriSlopReadableSource.entry_0_params ∧ entry_0_compiled.result = VeriSlopReadableSource.entry_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_0 : Prop := VSCore3.ReadableRunEquals entry_0_compiled VeriSlopReadableSource.entry_0_params VeriSlopReadableSource.entry_0_result VeriSlopReadableSource.entry_0_run
set_option smartUnfolding false in
theorem runEquals_entry_0 : RunEquals_entry_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_1_compiled : VSCore3.CompiledFunction :=
  { id := "solve", params := VeriSlopReadableSource.entry_1_params, result := VeriSlopReadableSource.entry_1_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "solve").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_1 : (VSCore3.findEntry checkedProgram "solve") = some entry_1_compiled := by with_unfolding_all rfl
theorem signature_entry_1 : entry_1_compiled.params = VeriSlopReadableSource.entry_1_params ∧ entry_1_compiled.result = VeriSlopReadableSource.entry_1_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_1 : Prop := VSCore3.ReadableRunEquals entry_1_compiled VeriSlopReadableSource.entry_1_params VeriSlopReadableSource.entry_1_result VeriSlopReadableSource.entry_1_run
set_option smartUnfolding false in
theorem runEquals_entry_1 : RunEquals_entry_1 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
def readable_fn_shift (x__0 : @Int) : @Int := by
  with_unfolding_all exact adapter_0.inv (VeriSlopReadableSource.entry_0_run (adapter_0.to x__0, ()))
set_option smartUnfolding false in
theorem source_eq_shift (x__0 : @Int) : source_fn_shift x__0 = readable_fn_shift x__0 := by with_unfolding_all rfl
theorem raw_eval_shift (x__0 : @Int) :
  VSCore3.evalEntry profile rawProgram "shift" [adapter_0.encode x__0] =
    .ok (adapter_0.encode (readable_fn_shift x__0)) := by
  rw [← source_eq_shift x__0]
  exact VeriSlopBridgeGoal.raw_eval_shift x__0
def readable_fn_solve (x__0 : @VeriSlopAST.Packet) : @Int := by
  with_unfolding_all exact adapter_0.inv (VeriSlopReadableSource.entry_1_run (adapter_4.to x__0, ()))
set_option smartUnfolding false in
theorem source_eq_solve (x__0 : @VeriSlopAST.Packet) : source_fn_solve x__0 = readable_fn_solve x__0 := by with_unfolding_all rfl
theorem raw_eval_solve (x__0 : @VeriSlopAST.Packet) :
  VSCore3.evalEntry profile rawProgram "solve" [adapter_4.encode x__0] =
    .ok (adapter_0.encode (readable_fn_solve x__0)) := by
  rw [← source_eq_solve x__0]
  exact VeriSlopBridgeGoal.raw_eval_solve x__0
end VeriSlopBridgeGoal.Readable
