namespace VeriSlopBridgeGoal.Readable
abbrev entry_0_compiled : VSCore3.CompiledFunction :=
  { id := "adjust", params := VeriSlopReadableSource.entry_0_params, result := VeriSlopReadableSource.entry_0_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "adjust").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_0 : (VSCore3.findEntry checkedProgram "adjust") = some entry_0_compiled := by with_unfolding_all rfl
theorem signature_entry_0 : entry_0_compiled.params = VeriSlopReadableSource.entry_0_params ∧ entry_0_compiled.result = VeriSlopReadableSource.entry_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_0 : Prop := VSCore3.ReadableRunEquals entry_0_compiled VeriSlopReadableSource.entry_0_params VeriSlopReadableSource.entry_0_result VeriSlopReadableSource.entry_0_run
set_option smartUnfolding false in
theorem runEquals_entry_0 : RunEquals_entry_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
def readable_fn_adjust (x__0 : @VeriSlopAST.Packet) : @VeriSlopAST.Packet := by
  with_unfolding_all exact adapter_2.inv (VeriSlopReadableSource.entry_0_run (adapter_2.to x__0, ()))
set_option smartUnfolding false in
theorem source_eq_adjust (x__0 : @VeriSlopAST.Packet) : source_fn_adjust x__0 = readable_fn_adjust x__0 := by with_unfolding_all rfl
theorem raw_eval_adjust (x__0 : @VeriSlopAST.Packet) :
  VSCore3.evalEntry profile rawProgram "adjust" [adapter_2.encode x__0] =
    .ok (adapter_2.encode (readable_fn_adjust x__0)) := by
  rw [← source_eq_adjust x__0]
  exact VeriSlopBridgeGoal.raw_eval_adjust x__0
end VeriSlopBridgeGoal.Readable
