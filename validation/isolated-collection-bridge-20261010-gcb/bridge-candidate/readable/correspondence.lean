namespace VeriSlopBridgeGoal.Readable
abbrev entry_0_compiled : VSCore3.CompiledFunction :=
  { id := "raiseBoxes", params := VeriSlopReadableSource.entry_0_params, result := VeriSlopReadableSource.entry_0_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "raiseBoxes").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_0 : (VSCore3.findEntry checkedProgram "raiseBoxes") = some entry_0_compiled := by with_unfolding_all rfl
theorem signature_entry_0 : entry_0_compiled.params = VeriSlopReadableSource.entry_0_params ∧ entry_0_compiled.result = VeriSlopReadableSource.entry_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_0 : Prop := VSCore3.ReadableRunEquals entry_0_compiled VeriSlopReadableSource.entry_0_params VeriSlopReadableSource.entry_0_result VeriSlopReadableSource.entry_0_run
set_option smartUnfolding false in
theorem runEquals_entry_0 : RunEquals_entry_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_1_compiled : VSCore3.CompiledFunction :=
  { id := "keepAtom", params := VeriSlopReadableSource.entry_1_params, result := VeriSlopReadableSource.entry_1_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "keepAtom").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_1 : (VSCore3.findEntry checkedProgram "keepAtom") = some entry_1_compiled := by with_unfolding_all rfl
theorem signature_entry_1 : entry_1_compiled.params = VeriSlopReadableSource.entry_1_params ∧ entry_1_compiled.result = VeriSlopReadableSource.entry_1_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_1 : Prop := VSCore3.ReadableRunEquals entry_1_compiled VeriSlopReadableSource.entry_1_params VeriSlopReadableSource.entry_1_result VeriSlopReadableSource.entry_1_run
set_option smartUnfolding false in
theorem runEquals_entry_1 : RunEquals_entry_1 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_2_compiled : VSCore3.CompiledFunction :=
  { id := "coldTotal", params := VeriSlopReadableSource.entry_2_params, result := VeriSlopReadableSource.entry_2_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "coldTotal").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_2 : (VSCore3.findEntry checkedProgram "coldTotal") = some entry_2_compiled := by with_unfolding_all rfl
theorem signature_entry_2 : entry_2_compiled.params = VeriSlopReadableSource.entry_2_params ∧ entry_2_compiled.result = VeriSlopReadableSource.entry_2_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_2 : Prop := VSCore3.ReadableRunEquals entry_2_compiled VeriSlopReadableSource.entry_2_params VeriSlopReadableSource.entry_2_result VeriSlopReadableSource.entry_2_run
set_option smartUnfolding false in
theorem runEquals_entry_2 : RunEquals_entry_2 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
def readable_fn_coldTotal (x__0 : (@List.{0} @VeriSlopAST.Box)) : @Nat := by
  with_unfolding_all exact adapter_1.inv (VeriSlopReadableSource.entry_2_run (adapter_5.to x__0, ()))
set_option smartUnfolding false in
theorem source_eq_coldTotal (x__0 : (@List.{0} @VeriSlopAST.Box)) : source_fn_coldTotal x__0 = readable_fn_coldTotal x__0 := by with_unfolding_all rfl
theorem raw_eval_coldTotal (x__0 : (@List.{0} @VeriSlopAST.Box)) :
  VSCore3.evalEntry profile rawProgram "coldTotal" [adapter_5.encode x__0] =
    .ok (adapter_1.encode (readable_fn_coldTotal x__0)) := by
  rw [← source_eq_coldTotal x__0]
  exact VeriSlopBridgeGoal.raw_eval_coldTotal x__0
def readable_fn_keepAtom (x__0 : (@List.{0} @VeriSlopAST.Box)) (x__1 : @VeriSlopAST.Atom) : (@List.{0} @VeriSlopAST.Box) := by
  with_unfolding_all exact adapter_5.inv (VeriSlopReadableSource.entry_1_run (adapter_5.to x__0, (adapter_2.to x__1, ())))
set_option smartUnfolding false in
theorem source_eq_keepAtom (x__0 : (@List.{0} @VeriSlopAST.Box)) (x__1 : @VeriSlopAST.Atom) : source_fn_keepAtom x__0 x__1 = readable_fn_keepAtom x__0 x__1 := by with_unfolding_all rfl
theorem raw_eval_keepAtom (x__0 : (@List.{0} @VeriSlopAST.Box)) (x__1 : @VeriSlopAST.Atom) :
  VSCore3.evalEntry profile rawProgram "keepAtom" [adapter_5.encode x__0, adapter_2.encode x__1] =
    .ok (adapter_5.encode (readable_fn_keepAtom x__0 x__1)) := by
  rw [← source_eq_keepAtom x__0 x__1]
  exact VeriSlopBridgeGoal.raw_eval_keepAtom x__0 x__1
def readable_fn_raiseBoxes (x__0 : (@List.{0} @VeriSlopAST.Box)) : (@List.{0} @VeriSlopAST.Box) := by
  with_unfolding_all exact adapter_5.inv (VeriSlopReadableSource.entry_0_run (adapter_5.to x__0, ()))
set_option smartUnfolding false in
theorem source_eq_raiseBoxes (x__0 : (@List.{0} @VeriSlopAST.Box)) : source_fn_raiseBoxes x__0 = readable_fn_raiseBoxes x__0 := by with_unfolding_all rfl
theorem raw_eval_raiseBoxes (x__0 : (@List.{0} @VeriSlopAST.Box)) :
  VSCore3.evalEntry profile rawProgram "raiseBoxes" [adapter_5.encode x__0] =
    .ok (adapter_5.encode (readable_fn_raiseBoxes x__0)) := by
  rw [← source_eq_raiseBoxes x__0]
  exact VeriSlopBridgeGoal.raw_eval_raiseBoxes x__0
end VeriSlopBridgeGoal.Readable
