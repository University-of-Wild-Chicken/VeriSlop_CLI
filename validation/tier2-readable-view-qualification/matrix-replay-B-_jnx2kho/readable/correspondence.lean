namespace VeriSlopBridgeGoal.Readable
abbrev helper_2_compiled : VSCore3.CompiledFunction :=
  { id := "capturedFilter", params := VeriSlopReadableSource.helper_2_params, result := VeriSlopReadableSource.helper_2_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "capturedFilter")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_2 : (checkedProgram.helpers.find? (fun h => h.id == "capturedFilter")) = some helper_2_compiled := by with_unfolding_all rfl
theorem signature_helper_2 : helper_2_compiled.params = VeriSlopReadableSource.helper_2_params ∧ helper_2_compiled.result = VeriSlopReadableSource.helper_2_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_2 : Prop := VSCore3.ReadableRunEquals helper_2_compiled VeriSlopReadableSource.helper_2_params VeriSlopReadableSource.helper_2_result VeriSlopReadableSource.helper_2_run
set_option smartUnfolding false in
theorem runEquals_helper_2 : RunEquals_helper_2 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_3_compiled : VSCore3.CompiledFunction :=
  { id := "listAccumulator", params := VeriSlopReadableSource.helper_3_params, result := VeriSlopReadableSource.helper_3_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "listAccumulator")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_3 : (checkedProgram.helpers.find? (fun h => h.id == "listAccumulator")) = some helper_3_compiled := by with_unfolding_all rfl
theorem signature_helper_3 : helper_3_compiled.params = VeriSlopReadableSource.helper_3_params ∧ helper_3_compiled.result = VeriSlopReadableSource.helper_3_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_3 : Prop := VSCore3.ReadableRunEquals helper_3_compiled VeriSlopReadableSource.helper_3_params VeriSlopReadableSource.helper_3_result VeriSlopReadableSource.helper_3_run
set_option smartUnfolding false in
theorem runEquals_helper_3 : RunEquals_helper_3 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_4_compiled : VSCore3.CompiledFunction :=
  { id := "natAccumulator", params := VeriSlopReadableSource.helper_4_params, result := VeriSlopReadableSource.helper_4_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "natAccumulator")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_4 : (checkedProgram.helpers.find? (fun h => h.id == "natAccumulator")) = some helper_4_compiled := by with_unfolding_all rfl
theorem signature_helper_4 : helper_4_compiled.params = VeriSlopReadableSource.helper_4_params ∧ helper_4_compiled.result = VeriSlopReadableSource.helper_4_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_4 : Prop := VSCore3.ReadableRunEquals helper_4_compiled VeriSlopReadableSource.helper_4_params VeriSlopReadableSource.helper_4_result VeriSlopReadableSource.helper_4_run
set_option smartUnfolding false in
theorem runEquals_helper_4 : RunEquals_helper_4 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_5_compiled : VSCore3.CompiledFunction :=
  { id := "listCase", params := VeriSlopReadableSource.helper_5_params, result := VeriSlopReadableSource.helper_5_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "listCase")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_5 : (checkedProgram.helpers.find? (fun h => h.id == "listCase")) = some helper_5_compiled := by with_unfolding_all rfl
theorem signature_helper_5 : helper_5_compiled.params = VeriSlopReadableSource.helper_5_params ∧ helper_5_compiled.result = VeriSlopReadableSource.helper_5_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_5 : Prop := VSCore3.ReadableRunEquals helper_5_compiled VeriSlopReadableSource.helper_5_params VeriSlopReadableSource.helper_5_result VeriSlopReadableSource.helper_5_run
set_option smartUnfolding false in
theorem runEquals_helper_5 : RunEquals_helper_5 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_6_compiled : VSCore3.CompiledFunction :=
  { id := "optionCase", params := VeriSlopReadableSource.helper_6_params, result := VeriSlopReadableSource.helper_6_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "optionCase")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_6 : (checkedProgram.helpers.find? (fun h => h.id == "optionCase")) = some helper_6_compiled := by with_unfolding_all rfl
theorem signature_helper_6 : helper_6_compiled.params = VeriSlopReadableSource.helper_6_params ∧ helper_6_compiled.result = VeriSlopReadableSource.helper_6_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_6 : Prop := VSCore3.ReadableRunEquals helper_6_compiled VeriSlopReadableSource.helper_6_params VeriSlopReadableSource.helper_6_result VeriSlopReadableSource.helper_6_run
set_option smartUnfolding false in
theorem runEquals_helper_6 : RunEquals_helper_6 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_7_compiled : VSCore3.CompiledFunction :=
  { id := "resultCase", params := VeriSlopReadableSource.helper_7_params, result := VeriSlopReadableSource.helper_7_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "resultCase")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_7 : (checkedProgram.helpers.find? (fun h => h.id == "resultCase")) = some helper_7_compiled := by with_unfolding_all rfl
theorem signature_helper_7 : helper_7_compiled.params = VeriSlopReadableSource.helper_7_params ∧ helper_7_compiled.result = VeriSlopReadableSource.helper_7_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_7 : Prop := VSCore3.ReadableRunEquals helper_7_compiled VeriSlopReadableSource.helper_7_params VeriSlopReadableSource.helper_7_result VeriSlopReadableSource.helper_7_run
set_option smartUnfolding false in
theorem runEquals_helper_7 : RunEquals_helper_7 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_8_compiled : VSCore3.CompiledFunction :=
  { id := "resultOk", params := VeriSlopReadableSource.helper_8_params, result := VeriSlopReadableSource.helper_8_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "resultOk")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_8 : (checkedProgram.helpers.find? (fun h => h.id == "resultOk")) = some helper_8_compiled := by with_unfolding_all rfl
theorem signature_helper_8 : helper_8_compiled.params = VeriSlopReadableSource.helper_8_params ∧ helper_8_compiled.result = VeriSlopReadableSource.helper_8_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_8 : Prop := VSCore3.ReadableRunEquals helper_8_compiled VeriSlopReadableSource.helper_8_params VeriSlopReadableSource.helper_8_result VeriSlopReadableSource.helper_8_run
set_option smartUnfolding false in
theorem runEquals_helper_8 : RunEquals_helper_8 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_9_compiled : VSCore3.CompiledFunction :=
  { id := "resultError", params := VeriSlopReadableSource.helper_9_params, result := VeriSlopReadableSource.helper_9_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "resultError")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_9 : (checkedProgram.helpers.find? (fun h => h.id == "resultError")) = some helper_9_compiled := by with_unfolding_all rfl
theorem signature_helper_9 : helper_9_compiled.params = VeriSlopReadableSource.helper_9_params ∧ helper_9_compiled.result = VeriSlopReadableSource.helper_9_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_9 : Prop := VSCore3.ReadableRunEquals helper_9_compiled VeriSlopReadableSource.helper_9_params VeriSlopReadableSource.helper_9_result VeriSlopReadableSource.helper_9_run
set_option smartUnfolding false in
theorem runEquals_helper_9 : RunEquals_helper_9 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_10_compiled : VSCore3.CompiledFunction :=
  { id := "maybe", params := VeriSlopReadableSource.helper_10_params, result := VeriSlopReadableSource.helper_10_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "maybe")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_10 : (checkedProgram.helpers.find? (fun h => h.id == "maybe")) = some helper_10_compiled := by with_unfolding_all rfl
theorem signature_helper_10 : helper_10_compiled.params = VeriSlopReadableSource.helper_10_params ∧ helper_10_compiled.result = VeriSlopReadableSource.helper_10_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_10 : Prop := VSCore3.ReadableRunEquals helper_10_compiled VeriSlopReadableSource.helper_10_params VeriSlopReadableSource.helper_10_result VeriSlopReadableSource.helper_10_run
set_option smartUnfolding false in
theorem runEquals_helper_10 : RunEquals_helper_10 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_11_compiled : VSCore3.CompiledFunction :=
  { id := "intMath", params := VeriSlopReadableSource.helper_11_params, result := VeriSlopReadableSource.helper_11_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "intMath")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_11 : (checkedProgram.helpers.find? (fun h => h.id == "intMath")) = some helper_11_compiled := by with_unfolding_all rfl
theorem signature_helper_11 : helper_11_compiled.params = VeriSlopReadableSource.helper_11_params ∧ helper_11_compiled.result = VeriSlopReadableSource.helper_11_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_11 : Prop := VSCore3.ReadableRunEquals helper_11_compiled VeriSlopReadableSource.helper_11_params VeriSlopReadableSource.helper_11_result VeriSlopReadableSource.helper_11_run
set_option smartUnfolding false in
theorem runEquals_helper_11 : RunEquals_helper_11 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_12_compiled : VSCore3.CompiledFunction :=
  { id := "natMath", params := VeriSlopReadableSource.helper_12_params, result := VeriSlopReadableSource.helper_12_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "natMath")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_12 : (checkedProgram.helpers.find? (fun h => h.id == "natMath")) = some helper_12_compiled := by with_unfolding_all rfl
theorem signature_helper_12 : helper_12_compiled.params = VeriSlopReadableSource.helper_12_params ∧ helper_12_compiled.result = VeriSlopReadableSource.helper_12_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_12 : Prop := VSCore3.ReadableRunEquals helper_12_compiled VeriSlopReadableSource.helper_12_params VeriSlopReadableSource.helper_12_result VeriSlopReadableSource.helper_12_run
set_option smartUnfolding false in
theorem runEquals_helper_12 : RunEquals_helper_12 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_13_compiled : VSCore3.CompiledFunction :=
  { id := "listPrimitives", params := VeriSlopReadableSource.helper_13_params, result := VeriSlopReadableSource.helper_13_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "listPrimitives")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_13 : (checkedProgram.helpers.find? (fun h => h.id == "listPrimitives")) = some helper_13_compiled := by with_unfolding_all rfl
theorem signature_helper_13 : helper_13_compiled.params = VeriSlopReadableSource.helper_13_params ∧ helper_13_compiled.result = VeriSlopReadableSource.helper_13_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_13 : Prop := VSCore3.ReadableRunEquals helper_13_compiled VeriSlopReadableSource.helper_13_params VeriSlopReadableSource.helper_13_result VeriSlopReadableSource.helper_13_run
set_option smartUnfolding false in
theorem runEquals_helper_13 : RunEquals_helper_13 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_14_compiled : VSCore3.CompiledFunction :=
  { id := "natPrimitives", params := VeriSlopReadableSource.helper_14_params, result := VeriSlopReadableSource.helper_14_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "natPrimitives")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_14 : (checkedProgram.helpers.find? (fun h => h.id == "natPrimitives")) = some helper_14_compiled := by with_unfolding_all rfl
theorem signature_helper_14 : helper_14_compiled.params = VeriSlopReadableSource.helper_14_params ∧ helper_14_compiled.result = VeriSlopReadableSource.helper_14_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_14 : Prop := VSCore3.ReadableRunEquals helper_14_compiled VeriSlopReadableSource.helper_14_params VeriSlopReadableSource.helper_14_result VeriSlopReadableSource.helper_14_run
set_option smartUnfolding false in
theorem runEquals_helper_14 : RunEquals_helper_14 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_15_compiled : VSCore3.CompiledFunction :=
  { id := "stringOrder", params := VeriSlopReadableSource.helper_15_params, result := VeriSlopReadableSource.helper_15_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "stringOrder")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_15 : (checkedProgram.helpers.find? (fun h => h.id == "stringOrder")) = some helper_15_compiled := by with_unfolding_all rfl
theorem signature_helper_15 : helper_15_compiled.params = VeriSlopReadableSource.helper_15_params ∧ helper_15_compiled.result = VeriSlopReadableSource.helper_15_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_15 : Prop := VSCore3.ReadableRunEquals helper_15_compiled VeriSlopReadableSource.helper_15_params VeriSlopReadableSource.helper_15_result VeriSlopReadableSource.helper_15_run
set_option smartUnfolding false in
theorem runEquals_helper_15 : RunEquals_helper_15 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_16_compiled : VSCore3.CompiledFunction :=
  { id := "stringCompare", params := VeriSlopReadableSource.helper_16_params, result := VeriSlopReadableSource.helper_16_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "stringCompare")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_16 : (checkedProgram.helpers.find? (fun h => h.id == "stringCompare")) = some helper_16_compiled := by with_unfolding_all rfl
theorem signature_helper_16 : helper_16_compiled.params = VeriSlopReadableSource.helper_16_params ∧ helper_16_compiled.result = VeriSlopReadableSource.helper_16_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_16 : Prop := VSCore3.ReadableRunEquals helper_16_compiled VeriSlopReadableSource.helper_16_params VeriSlopReadableSource.helper_16_result VeriSlopReadableSource.helper_16_run
set_option smartUnfolding false in
theorem runEquals_helper_16 : RunEquals_helper_16 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_17_compiled : VSCore3.CompiledFunction :=
  { id := "unitValue", params := VeriSlopReadableSource.helper_17_params, result := VeriSlopReadableSource.helper_17_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "unitValue")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_17 : (checkedProgram.helpers.find? (fun h => h.id == "unitValue")) = some helper_17_compiled := by with_unfolding_all rfl
theorem signature_helper_17 : helper_17_compiled.params = VeriSlopReadableSource.helper_17_params ∧ helper_17_compiled.result = VeriSlopReadableSource.helper_17_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_17 : Prop := VSCore3.ReadableRunEquals helper_17_compiled VeriSlopReadableSource.helper_17_params VeriSlopReadableSource.helper_17_result VeriSlopReadableSource.helper_17_run
set_option smartUnfolding false in
theorem runEquals_helper_17 : RunEquals_helper_17 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_18_compiled : VSCore3.CompiledFunction :=
  { id := "boolValue", params := VeriSlopReadableSource.helper_18_params, result := VeriSlopReadableSource.helper_18_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "boolValue")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_18 : (checkedProgram.helpers.find? (fun h => h.id == "boolValue")) = some helper_18_compiled := by with_unfolding_all rfl
theorem signature_helper_18 : helper_18_compiled.params = VeriSlopReadableSource.helper_18_params ∧ helper_18_compiled.result = VeriSlopReadableSource.helper_18_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_18 : Prop := VSCore3.ReadableRunEquals helper_18_compiled VeriSlopReadableSource.helper_18_params VeriSlopReadableSource.helper_18_result VeriSlopReadableSource.helper_18_run
set_option smartUnfolding false in
theorem runEquals_helper_18 : RunEquals_helper_18 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_19_compiled : VSCore3.CompiledFunction :=
  { id := "natValue", params := VeriSlopReadableSource.helper_19_params, result := VeriSlopReadableSource.helper_19_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "natValue")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_19 : (checkedProgram.helpers.find? (fun h => h.id == "natValue")) = some helper_19_compiled := by with_unfolding_all rfl
theorem signature_helper_19 : helper_19_compiled.params = VeriSlopReadableSource.helper_19_params ∧ helper_19_compiled.result = VeriSlopReadableSource.helper_19_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_19 : Prop := VSCore3.ReadableRunEquals helper_19_compiled VeriSlopReadableSource.helper_19_params VeriSlopReadableSource.helper_19_result VeriSlopReadableSource.helper_19_run
set_option smartUnfolding false in
theorem runEquals_helper_19 : RunEquals_helper_19 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_20_compiled : VSCore3.CompiledFunction :=
  { id := "enumValue", params := VeriSlopReadableSource.helper_20_params, result := VeriSlopReadableSource.helper_20_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "enumValue")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_20 : (checkedProgram.helpers.find? (fun h => h.id == "enumValue")) = some helper_20_compiled := by with_unfolding_all rfl
theorem signature_helper_20 : helper_20_compiled.params = VeriSlopReadableSource.helper_20_params ∧ helper_20_compiled.result = VeriSlopReadableSource.helper_20_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_20 : Prop := VSCore3.ReadableRunEquals helper_20_compiled VeriSlopReadableSource.helper_20_params VeriSlopReadableSource.helper_20_result VeriSlopReadableSource.helper_20_run
set_option smartUnfolding false in
theorem runEquals_helper_20 : RunEquals_helper_20 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_21_compiled : VSCore3.CompiledFunction :=
  { id := "makeSmall", params := VeriSlopReadableSource.helper_21_params, result := VeriSlopReadableSource.helper_21_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "makeSmall")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_21 : (checkedProgram.helpers.find? (fun h => h.id == "makeSmall")) = some helper_21_compiled := by with_unfolding_all rfl
theorem signature_helper_21 : helper_21_compiled.params = VeriSlopReadableSource.helper_21_params ∧ helper_21_compiled.result = VeriSlopReadableSource.helper_21_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_21 : Prop := VSCore3.ReadableRunEquals helper_21_compiled VeriSlopReadableSource.helper_21_params VeriSlopReadableSource.helper_21_result VeriSlopReadableSource.helper_21_run
set_option smartUnfolding false in
theorem runEquals_helper_21 : RunEquals_helper_21 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_22_compiled : VSCore3.CompiledFunction :=
  { id := "makeCrate", params := VeriSlopReadableSource.helper_22_params, result := VeriSlopReadableSource.helper_22_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "makeCrate")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_22 : (checkedProgram.helpers.find? (fun h => h.id == "makeCrate")) = some helper_22_compiled := by with_unfolding_all rfl
theorem signature_helper_22 : helper_22_compiled.params = VeriSlopReadableSource.helper_22_params ∧ helper_22_compiled.result = VeriSlopReadableSource.helper_22_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_22 : Prop := VSCore3.ReadableRunEquals helper_22_compiled VeriSlopReadableSource.helper_22_params VeriSlopReadableSource.helper_22_result VeriSlopReadableSource.helper_22_run
set_option smartUnfolding false in
theorem runEquals_helper_22 : RunEquals_helper_22 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_23_compiled : VSCore3.CompiledFunction :=
  { id := "nestedField", params := VeriSlopReadableSource.helper_23_params, result := VeriSlopReadableSource.helper_23_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "nestedField")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_23 : (checkedProgram.helpers.find? (fun h => h.id == "nestedField")) = some helper_23_compiled := by with_unfolding_all rfl
theorem signature_helper_23 : helper_23_compiled.params = VeriSlopReadableSource.helper_23_params ∧ helper_23_compiled.result = VeriSlopReadableSource.helper_23_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_23 : Prop := VSCore3.ReadableRunEquals helper_23_compiled VeriSlopReadableSource.helper_23_params VeriSlopReadableSource.helper_23_result VeriSlopReadableSource.helper_23_run
set_option smartUnfolding false in
theorem runEquals_helper_23 : RunEquals_helper_23 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_24_compiled : VSCore3.CompiledFunction :=
  { id := "nominalEq", params := VeriSlopReadableSource.helper_24_params, result := VeriSlopReadableSource.helper_24_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "nominalEq")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_24 : (checkedProgram.helpers.find? (fun h => h.id == "nominalEq")) = some helper_24_compiled := by with_unfolding_all rfl
theorem signature_helper_24 : helper_24_compiled.params = VeriSlopReadableSource.helper_24_params ∧ helper_24_compiled.result = VeriSlopReadableSource.helper_24_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_24 : Prop := VSCore3.ReadableRunEquals helper_24_compiled VeriSlopReadableSource.helper_24_params VeriSlopReadableSource.helper_24_result VeriSlopReadableSource.helper_24_run
set_option smartUnfolding false in
theorem runEquals_helper_24 : RunEquals_helper_24 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_25_compiled : VSCore3.CompiledFunction :=
  { id := "leaf", params := VeriSlopReadableSource.helper_25_params, result := VeriSlopReadableSource.helper_25_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "leaf")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_25 : (checkedProgram.helpers.find? (fun h => h.id == "leaf")) = some helper_25_compiled := by with_unfolding_all rfl
theorem signature_helper_25 : helper_25_compiled.params = VeriSlopReadableSource.helper_25_params ∧ helper_25_compiled.result = VeriSlopReadableSource.helper_25_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_25 : Prop := VSCore3.ReadableRunEquals helper_25_compiled VeriSlopReadableSource.helper_25_params VeriSlopReadableSource.helper_25_result VeriSlopReadableSource.helper_25_run
set_option smartUnfolding false in
theorem runEquals_helper_25 : RunEquals_helper_25 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_0_compiled : VSCore3.CompiledFunction :=
  { id := "early", params := VeriSlopReadableSource.helper_0_params, result := VeriSlopReadableSource.helper_0_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "early")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_0 : (checkedProgram.helpers.find? (fun h => h.id == "early")) = some helper_0_compiled := by with_unfolding_all rfl
theorem signature_helper_0 : helper_0_compiled.params = VeriSlopReadableSource.helper_0_params ∧ helper_0_compiled.result = VeriSlopReadableSource.helper_0_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_0 : Prop := VSCore3.ReadableRunEquals helper_0_compiled VeriSlopReadableSource.helper_0_params VeriSlopReadableSource.helper_0_result VeriSlopReadableSource.helper_0_run
set_option smartUnfolding false in
theorem runEquals_helper_0 : RunEquals_helper_0 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
abbrev helper_1_compiled : VSCore3.CompiledFunction :=
  { id := "capturedMap", params := VeriSlopReadableSource.helper_1_params, result := VeriSlopReadableSource.helper_1_result,
    run := by with_unfolding_all exact ((checkedProgram.helpers.find? (fun h => h.id == "capturedMap")).getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem lookup_helper_1 : (checkedProgram.helpers.find? (fun h => h.id == "capturedMap")) = some helper_1_compiled := by with_unfolding_all rfl
theorem signature_helper_1 : helper_1_compiled.params = VeriSlopReadableSource.helper_1_params ∧ helper_1_compiled.result = VeriSlopReadableSource.helper_1_result := by exact ⟨rfl, rfl⟩
def RunEquals_helper_1 : Prop := VSCore3.ReadableRunEquals helper_1_compiled VeriSlopReadableSource.helper_1_params VeriSlopReadableSource.helper_1_result VeriSlopReadableSource.helper_1_run
set_option smartUnfolding false in
theorem runEquals_helper_1 : RunEquals_helper_1 := by
  with_unfolding_all
    refine ⟨rfl, rfl, ?_⟩
    intro env
    rfl
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
