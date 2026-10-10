namespace VeriSlopBridgeGoal.Readable
abbrev helper_0_compiled : VSCore3.CompiledFunction :=
  { id := "shiftParcel", params := VeriSlopReadableSource.helper_0_params, result := VeriSlopReadableSource.helper_0_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "shiftParcel")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_0 : (checkedProgram.helpers.find? (fun h => h.id == "shiftParcel")) = some helper_0_compiled := by with_unfolding_all rfl
theorem signature_helper_0 : helper_0_compiled.params = VeriSlopReadableSource.helper_0_params ∧ helper_0_compiled.result = VeriSlopReadableSource.helper_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_0 : Prop := VSCore3.ReadableRunEquals helper_0_compiled VeriSlopReadableSource.helper_0_params VeriSlopReadableSource.helper_0_result VeriSlopReadableSource.helper_0_run
set_option smartUnfolding false in
theorem runEquals_helper_0 : RunEquals_helper_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_1_compiled : VSCore3.CompiledFunction :=
  { id := "shiftEnvelope", params := VeriSlopReadableSource.helper_1_params, result := VeriSlopReadableSource.helper_1_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "shiftEnvelope")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_1 : (checkedProgram.helpers.find? (fun h => h.id == "shiftEnvelope")) = some helper_1_compiled := by with_unfolding_all rfl
theorem signature_helper_1 : helper_1_compiled.params = VeriSlopReadableSource.helper_1_params ∧ helper_1_compiled.result = VeriSlopReadableSource.helper_1_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_1 : Prop := VSCore3.ReadableRunEquals helper_1_compiled VeriSlopReadableSource.helper_1_params VeriSlopReadableSource.helper_1_result VeriSlopReadableSource.helper_1_run
set_option smartUnfolding false in
theorem runEquals_helper_1 : RunEquals_helper_1 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_2_compiled : VSCore3.CompiledFunction :=
  { id := "keepEnvelope", params := VeriSlopReadableSource.helper_2_params, result := VeriSlopReadableSource.helper_2_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "keepEnvelope")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_2 : (checkedProgram.helpers.find? (fun h => h.id == "keepEnvelope")) = some helper_2_compiled := by with_unfolding_all rfl
theorem signature_helper_2 : helper_2_compiled.params = VeriSlopReadableSource.helper_2_params ∧ helper_2_compiled.result = VeriSlopReadableSource.helper_2_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_2 : Prop := VSCore3.ReadableRunEquals helper_2_compiled VeriSlopReadableSource.helper_2_params VeriSlopReadableSource.helper_2_result VeriSlopReadableSource.helper_2_run
set_option smartUnfolding false in
theorem runEquals_helper_2 : RunEquals_helper_2 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_3_compiled : VSCore3.CompiledFunction :=
  { id := "totalStep", params := VeriSlopReadableSource.helper_3_params, result := VeriSlopReadableSource.helper_3_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "totalStep")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_3 : (checkedProgram.helpers.find? (fun h => h.id == "totalStep")) = some helper_3_compiled := by with_unfolding_all rfl
theorem signature_helper_3 : helper_3_compiled.params = VeriSlopReadableSource.helper_3_params ∧ helper_3_compiled.result = VeriSlopReadableSource.helper_3_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_3 : Prop := VSCore3.ReadableRunEquals helper_3_compiled VeriSlopReadableSource.helper_3_params VeriSlopReadableSource.helper_3_result VeriSlopReadableSource.helper_3_run
set_option smartUnfolding false in
theorem runEquals_helper_3 : RunEquals_helper_3 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_0_compiled : VSCore3.CompiledFunction :=
  { id := "shiftEnvelopes", params := VeriSlopReadableSource.entry_0_params, result := VeriSlopReadableSource.entry_0_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "shiftEnvelopes").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_0 : (VSCore3.findEntry checkedProgram "shiftEnvelopes") = some entry_0_compiled := by with_unfolding_all rfl
theorem signature_entry_0 : entry_0_compiled.params = VeriSlopReadableSource.entry_0_params ∧ entry_0_compiled.result = VeriSlopReadableSource.entry_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_0 : Prop := VSCore3.ReadableRunEquals entry_0_compiled VeriSlopReadableSource.entry_0_params VeriSlopReadableSource.entry_0_result VeriSlopReadableSource.entry_0_run
set_option smartUnfolding false in
theorem runEquals_entry_0 : RunEquals_entry_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_1_compiled : VSCore3.CompiledFunction :=
  { id := "keepParcel", params := VeriSlopReadableSource.entry_1_params, result := VeriSlopReadableSource.entry_1_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "keepParcel").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_1 : (VSCore3.findEntry checkedProgram "keepParcel") = some entry_1_compiled := by with_unfolding_all rfl
theorem signature_entry_1 : entry_1_compiled.params = VeriSlopReadableSource.entry_1_params ∧ entry_1_compiled.result = VeriSlopReadableSource.entry_1_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_1 : Prop := VSCore3.ReadableRunEquals entry_1_compiled VeriSlopReadableSource.entry_1_params VeriSlopReadableSource.entry_1_result VeriSlopReadableSource.entry_1_run
set_option smartUnfolding false in
theorem runEquals_entry_1 : RunEquals_entry_1 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_2_compiled : VSCore3.CompiledFunction :=
  { id := "shadeTotal", params := VeriSlopReadableSource.entry_2_params, result := VeriSlopReadableSource.entry_2_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "shadeTotal").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_2 : (VSCore3.findEntry checkedProgram "shadeTotal") = some entry_2_compiled := by with_unfolding_all rfl
theorem signature_entry_2 : entry_2_compiled.params = VeriSlopReadableSource.entry_2_params ∧ entry_2_compiled.result = VeriSlopReadableSource.entry_2_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_2 : Prop := VSCore3.ReadableRunEquals entry_2_compiled VeriSlopReadableSource.entry_2_params VeriSlopReadableSource.entry_2_result VeriSlopReadableSource.entry_2_run
set_option smartUnfolding false in
theorem runEquals_entry_2 : RunEquals_entry_2 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_3_compiled : VSCore3.CompiledFunction :=
  { id := "sameShade", params := VeriSlopReadableSource.entry_3_params, result := VeriSlopReadableSource.entry_3_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "sameShade").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_3 : (VSCore3.findEntry checkedProgram "sameShade") = some entry_3_compiled := by with_unfolding_all rfl
theorem signature_entry_3 : entry_3_compiled.params = VeriSlopReadableSource.entry_3_params ∧ entry_3_compiled.result = VeriSlopReadableSource.entry_3_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_3 : Prop := VSCore3.ReadableRunEquals entry_3_compiled VeriSlopReadableSource.entry_3_params VeriSlopReadableSource.entry_3_result VeriSlopReadableSource.entry_3_run
set_option smartUnfolding false in
theorem runEquals_entry_3 : RunEquals_entry_3 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev entry_4_compiled : VSCore3.CompiledFunction :=
  { id := "inspectEnvelope", params := VeriSlopReadableSource.entry_4_params, result := VeriSlopReadableSource.entry_4_result,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "inspectEnvelope").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_entry_4 : (VSCore3.findEntry checkedProgram "inspectEnvelope") = some entry_4_compiled := by with_unfolding_all rfl
theorem signature_entry_4 : entry_4_compiled.params = VeriSlopReadableSource.entry_4_params ∧ entry_4_compiled.result = VeriSlopReadableSource.entry_4_result := by exact ⟨rfl, rfl⟩
def RunEquals_entry_4 : Prop := VSCore3.ReadableRunEquals entry_4_compiled VeriSlopReadableSource.entry_4_params VeriSlopReadableSource.entry_4_result VeriSlopReadableSource.entry_4_run
set_option smartUnfolding false in
theorem runEquals_entry_4 : RunEquals_entry_4 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
def readable_fn_inspectEnvelope (x__0 : @VeriSlopAST.Envelope) : @Nat := by
  with_unfolding_all exact adapter_1.inv (VeriSlopReadableSource.entry_4_run (adapter_4.to x__0, ()))
set_option smartUnfolding false in
theorem source_eq_inspectEnvelope (x__0 : @VeriSlopAST.Envelope) : source_fn_inspectEnvelope x__0 = readable_fn_inspectEnvelope x__0 := by with_unfolding_all rfl
theorem raw_eval_inspectEnvelope (x__0 : @VeriSlopAST.Envelope) :
  VSCore3.evalEntry profile rawProgram "inspectEnvelope" [adapter_4.encode x__0] =
    .ok (adapter_1.encode (readable_fn_inspectEnvelope x__0)) := by
  rw [← source_eq_inspectEnvelope x__0]
  exact VeriSlopBridgeGoal.raw_eval_inspectEnvelope x__0
def readable_fn_keepParcel (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @VeriSlopAST.Parcel) : (@List.{0} @VeriSlopAST.Envelope) := by
  with_unfolding_all exact adapter_5.inv (VeriSlopReadableSource.entry_1_run (adapter_5.to x__0, (adapter_2.to x__1, ())))
set_option smartUnfolding false in
theorem source_eq_keepParcel (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @VeriSlopAST.Parcel) : source_fn_keepParcel x__0 x__1 = readable_fn_keepParcel x__0 x__1 := by with_unfolding_all rfl
theorem raw_eval_keepParcel (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @VeriSlopAST.Parcel) :
  VSCore3.evalEntry profile rawProgram "keepParcel" [adapter_5.encode x__0, adapter_2.encode x__1] =
    .ok (adapter_5.encode (readable_fn_keepParcel x__0 x__1)) := by
  rw [← source_eq_keepParcel x__0 x__1]
  exact VeriSlopBridgeGoal.raw_eval_keepParcel x__0 x__1
def readable_fn_sameShade (x__0 : @VeriSlopAST.Shade) (x__1 : @VeriSlopAST.Shade) : @Bool := by
  with_unfolding_all exact adapter_3.inv (VeriSlopReadableSource.entry_3_run (adapter_0.to x__0, (adapter_0.to x__1, ())))
set_option smartUnfolding false in
theorem source_eq_sameShade (x__0 : @VeriSlopAST.Shade) (x__1 : @VeriSlopAST.Shade) : source_fn_sameShade x__0 x__1 = readable_fn_sameShade x__0 x__1 := by with_unfolding_all rfl
theorem raw_eval_sameShade (x__0 : @VeriSlopAST.Shade) (x__1 : @VeriSlopAST.Shade) :
  VSCore3.evalEntry profile rawProgram "sameShade" [adapter_0.encode x__0, adapter_0.encode x__1] =
    .ok (adapter_3.encode (readable_fn_sameShade x__0 x__1)) := by
  rw [← source_eq_sameShade x__0 x__1]
  exact VeriSlopBridgeGoal.raw_eval_sameShade x__0 x__1
def readable_fn_shadeTotal (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) (x__2 : @VeriSlopAST.Shade) : @Nat := by
  with_unfolding_all exact adapter_1.inv (VeriSlopReadableSource.entry_2_run (adapter_5.to x__0, (adapter_1.to x__1, (adapter_0.to x__2, ()))))
set_option smartUnfolding false in
theorem source_eq_shadeTotal (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) (x__2 : @VeriSlopAST.Shade) : source_fn_shadeTotal x__0 x__1 x__2 = readable_fn_shadeTotal x__0 x__1 x__2 := by with_unfolding_all rfl
theorem raw_eval_shadeTotal (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) (x__2 : @VeriSlopAST.Shade) :
  VSCore3.evalEntry profile rawProgram "shadeTotal" [adapter_5.encode x__0, adapter_1.encode x__1, adapter_0.encode x__2] =
    .ok (adapter_1.encode (readable_fn_shadeTotal x__0 x__1 x__2)) := by
  rw [← source_eq_shadeTotal x__0 x__1 x__2]
  exact VeriSlopBridgeGoal.raw_eval_shadeTotal x__0 x__1 x__2
def readable_fn_shiftEnvelopes (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) : (@List.{0} @VeriSlopAST.Envelope) := by
  with_unfolding_all exact adapter_5.inv (VeriSlopReadableSource.entry_0_run (adapter_5.to x__0, (adapter_1.to x__1, ())))
set_option smartUnfolding false in
theorem source_eq_shiftEnvelopes (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) : source_fn_shiftEnvelopes x__0 x__1 = readable_fn_shiftEnvelopes x__0 x__1 := by with_unfolding_all rfl
theorem raw_eval_shiftEnvelopes (x__0 : (@List.{0} @VeriSlopAST.Envelope)) (x__1 : @Nat) :
  VSCore3.evalEntry profile rawProgram "shiftEnvelopes" [adapter_5.encode x__0, adapter_1.encode x__1] =
    .ok (adapter_5.encode (readable_fn_shiftEnvelopes x__0 x__1)) := by
  rw [← source_eq_shiftEnvelopes x__0 x__1]
  exact VeriSlopBridgeGoal.raw_eval_shiftEnvelopes x__0 x__1
end VeriSlopBridgeGoal.Readable
