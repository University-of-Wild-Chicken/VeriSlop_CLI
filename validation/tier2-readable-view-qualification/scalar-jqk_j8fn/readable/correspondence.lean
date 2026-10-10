namespace VeriSlopBridgeGoal.Readable
abbrev entry_0_compiled : VSCore3.CompiledFunction :=
  { id := "difference", params := VeriSlopReadableSource.entry_0_params, result := VeriSlopReadableSource.entry_0_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "difference").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_0 : (VSCore3.findEntry checkedProgram "difference") = some entry_0_compiled := by with_unfolding_all rfl
theorem signature_entry_0 : entry_0_compiled.params = VeriSlopReadableSource.entry_0_params ∧ entry_0_compiled.result = VeriSlopReadableSource.entry_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_0 : Prop := VSCore3.ReadableRunEquals entry_0_compiled VeriSlopReadableSource.entry_0_params VeriSlopReadableSource.entry_0_result VeriSlopReadableSource.entry_0_run
set_option smartUnfolding false in
theorem runEquals_entry_0 : RunEquals_entry_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
def readable_fn_difference (x__0 : @Int) (x__1 : @Int) : @Int := by
  with_unfolding_all exact adapter_0.inv (VeriSlopReadableSource.entry_0_run (adapter_0.to x__0, (adapter_0.to x__1, ())))
set_option smartUnfolding false in
theorem source_eq_difference (x__0 : @Int) (x__1 : @Int) : source_fn_difference x__0 x__1 = readable_fn_difference x__0 x__1 := by with_unfolding_all rfl
theorem raw_eval_difference (x__0 : @Int) (x__1 : @Int) :
  VSCore3.evalEntry profile rawProgram "difference" [adapter_0.encode x__0, adapter_0.encode x__1] =
    .ok (adapter_0.encode (readable_fn_difference x__0 x__1)) := by
  rw [← source_eq_difference x__0 x__1]
  exact VeriSlopBridgeGoal.raw_eval_difference x__0 x__1
end VeriSlopBridgeGoal.Readable
