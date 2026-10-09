import VSCore3
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:8cdd185aa20b40d1d32c1a299bbd8ff8aef470adfc00d3c01d9e1e9f922edbac. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 109, 97, 112, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 105, 100, 34, 58, 34, 115, 104, 105, 102, 116, 101, 100, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 44, 123, 34, 108, 105, 115, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 34, 105, 110, 116, 34, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 116, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 102, 105, 108, 116, 101, 114, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 105, 100, 34, 58, 34, 115, 101, 108, 101, 99, 116, 101, 100, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 44, 123, 34, 108, 105, 115, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 34, 105, 110, 116, 34, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 115, 117, 109, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 109, 97, 112, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 116, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 102, 105, 108, 116, 101, 114, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 125, 44, 34, 105, 100, 34, 58, 34, 116, 111, 116, 97, 108, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 44, 123, 34, 108, 105, 115, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [], helpers := [], entries := [{ id := "shifted", params := [VSCore3.Ty.int, (VSCore3.Ty.list VSCore3.Ty.int)], result := (VSCore3.Ty.list VSCore3.Ty.int), body := (VSCore3.Expr.listMap (VSCore3.Expr.var 0) (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.var 0) (VSCore3.Expr.var 2))) },
{ id := "selected", params := [VSCore3.Ty.int, (VSCore3.Ty.list VSCore3.Ty.int)], result := (VSCore3.Ty.list VSCore3.Ty.int), body := (VSCore3.Expr.listFilter (VSCore3.Expr.var 0) (VSCore3.Expr.bin VSCore.BinOp.lt (VSCore3.Expr.var 0) (VSCore3.Expr.var 2))) },
{ id := "total", params := [VSCore3.Ty.int, (VSCore3.Ty.list VSCore3.Ty.int)], result := VSCore3.Ty.int, body := (VSCore3.Expr.listSum (VSCore3.Expr.listMap (VSCore3.Expr.listFilter (VSCore3.Expr.var 0) (VSCore3.Expr.bin VSCore.BinOp.lt (VSCore3.Expr.var 0) (VSCore3.Expr.var 2))) (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.var 0) (VSCore3.Expr.var 2)))) }] }
def profile : VSCore3.Profile := { enums := [] }
def signatures : List VSCore3.EntrySig := [{ id := "shifted", params := [VSCore3.Ty.int, (VSCore3.Ty.list VSCore3.Ty.int)], result := (VSCore3.Ty.list VSCore3.Ty.int) },
  { id := "selected", params := [VSCore3.Ty.int, (VSCore3.Ty.list VSCore3.Ty.int)], result := (VSCore3.Ty.list VSCore3.Ty.int) },
  { id := "total", params := [VSCore3.Ty.int, (VSCore3.Ty.list VSCore3.Ty.int)], result := VSCore3.Ty.int }]
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

/-- Exact accepted carrier {"list":"Int"}. -/
def adapter_1 : VSCore3.Adapter (.list .int) (@List.{0} @Int) :=
  VSCore3.listAdapter adapter_0
def adapter_1_raw : VSCore3.RawLaws (.list .int) := (VSCore3.listRawLaws VSCore3.intRawLaws)
theorem adapter_1_decode_encode (x : (@List.{0} @Int)) :
    VSCore3.decode (.list .int) (adapter_1.encode x) = some (adapter_1.to x) :=
  adapter_1.decode_encode adapter_1_raw x

abbrev entry_shifted : VSCore3.CompiledFunction :=
  { id := "shifted", params := [.int, (.list .int)], result := (.list .int),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "shifted").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_shifted : VSCore3.findEntry checkedProgram "shifted" = some entry_shifted := by with_unfolding_all rfl
def source_fn_shifted (x__0 : @Int) (x__1 : (@List.{0} @Int)) : (@List.{0} @Int) := by
  with_unfolding_all exact adapter_1.inv (entry_shifted.run (adapter_0.to x__0, (adapter_1.to x__1, ())))
def Refines_shifted : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@VeriSlopBridgeGoal.source_fn_shifted x__0 x__1) (@PrimitiveFixture.shifted x__0 x__1))))
def RawEval_shifted : Prop := ∀ (x__0 : @Int) (x__1 : (@List.{0} @Int)),
  VSCore3.evalEntry profile rawProgram "shifted" [adapter_0.encode x__0, adapter_1.encode x__1] =
    .ok (adapter_1.encode (source_fn_shifted x__0 x__1))
theorem raw_eval_shifted : RawEval_shifted := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_shifted.params [adapter_0.encode x__0, adapter_1.encode x__1] = some (adapter_0.to x__0, (adapter_1.to x__1, ())) := by
      change VSCore3.decodeEnv [.int, (.list .int)] [adapter_0.encode x__0, adapter_1.encode x__1] = some (adapter_0.to x__0, (adapter_1.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, adapter_1_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "shifted" [adapter_0.encode x__0, adapter_1.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_shifted, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_shifted, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.list .int) (entry_shifted.run (adapter_0.to x__0, (adapter_1.to x__1, ())))) =
      Except.ok (VSCore3.encode (.list .int) (adapter_1.to (adapter_1.inv (entry_shifted.run (adapter_0.to x__0, (adapter_1.to x__1, ()))))))
    rw [adapter_1.to_from]
def InputsCover_shifted : Prop := ∀ args, VSCore3.ArgsTyped entry_shifted args → ∃ (x__0 : @Int) (x__1 : (@List.{0} @Int)), args = [adapter_0.encode x__0, adapter_1.encode x__1]
theorem inputs_cover_shifted : InputsCover_shifted := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [.int, (.list .int)] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [.int, (.list .int)] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact VSCore3.intRawLaws
    · exact (VSCore3.listRawLaws VSCore3.intRawLaws)) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, adapter_1.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from, adapter_1.to_from] using he.symm

abbrev entry_selected : VSCore3.CompiledFunction :=
  { id := "selected", params := [.int, (.list .int)], result := (.list .int),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "selected").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_selected : VSCore3.findEntry checkedProgram "selected" = some entry_selected := by with_unfolding_all rfl
def source_fn_selected (x__0 : @Int) (x__1 : (@List.{0} @Int)) : (@List.{0} @Int) := by
  with_unfolding_all exact adapter_1.inv (entry_selected.run (adapter_0.to x__0, (adapter_1.to x__1, ())))
def Refines_selected : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@VeriSlopBridgeGoal.source_fn_selected x__0 x__1) (@PrimitiveFixture.selected x__0 x__1))))
def RawEval_selected : Prop := ∀ (x__0 : @Int) (x__1 : (@List.{0} @Int)),
  VSCore3.evalEntry profile rawProgram "selected" [adapter_0.encode x__0, adapter_1.encode x__1] =
    .ok (adapter_1.encode (source_fn_selected x__0 x__1))
theorem raw_eval_selected : RawEval_selected := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_selected.params [adapter_0.encode x__0, adapter_1.encode x__1] = some (adapter_0.to x__0, (adapter_1.to x__1, ())) := by
      change VSCore3.decodeEnv [.int, (.list .int)] [adapter_0.encode x__0, adapter_1.encode x__1] = some (adapter_0.to x__0, (adapter_1.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, adapter_1_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "selected" [adapter_0.encode x__0, adapter_1.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_selected, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_selected, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.list .int) (entry_selected.run (adapter_0.to x__0, (adapter_1.to x__1, ())))) =
      Except.ok (VSCore3.encode (.list .int) (adapter_1.to (adapter_1.inv (entry_selected.run (adapter_0.to x__0, (adapter_1.to x__1, ()))))))
    rw [adapter_1.to_from]
def InputsCover_selected : Prop := ∀ args, VSCore3.ArgsTyped entry_selected args → ∃ (x__0 : @Int) (x__1 : (@List.{0} @Int)), args = [adapter_0.encode x__0, adapter_1.encode x__1]
theorem inputs_cover_selected : InputsCover_selected := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [.int, (.list .int)] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [.int, (.list .int)] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact VSCore3.intRawLaws
    · exact (VSCore3.listRawLaws VSCore3.intRawLaws)) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, adapter_1.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from, adapter_1.to_from] using he.symm

abbrev entry_total : VSCore3.CompiledFunction :=
  { id := "total", params := [.int, (.list .int)], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "total").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_total : VSCore3.findEntry checkedProgram "total" = some entry_total := by with_unfolding_all rfl
def source_fn_total (x__0 : @Int) (x__1 : (@List.{0} @Int)) : @Int := by
  with_unfolding_all exact adapter_0.inv (entry_total.run (adapter_0.to x__0, (adapter_1.to x__1, ())))
def Refines_total : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_total x__0 x__1) (@PrimitiveFixture.total x__0 x__1))))
def RawEval_total : Prop := ∀ (x__0 : @Int) (x__1 : (@List.{0} @Int)),
  VSCore3.evalEntry profile rawProgram "total" [adapter_0.encode x__0, adapter_1.encode x__1] =
    .ok (adapter_0.encode (source_fn_total x__0 x__1))
theorem raw_eval_total : RawEval_total := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_total.params [adapter_0.encode x__0, adapter_1.encode x__1] = some (adapter_0.to x__0, (adapter_1.to x__1, ())) := by
      change VSCore3.decodeEnv [.int, (.list .int)] [adapter_0.encode x__0, adapter_1.encode x__1] = some (adapter_0.to x__0, (adapter_1.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, adapter_1_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "total" [adapter_0.encode x__0, adapter_1.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_total, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_total, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_total.run (adapter_0.to x__0, (adapter_1.to x__1, ())))) =
      Except.ok (VSCore3.encode .int (adapter_0.to (adapter_0.inv (entry_total.run (adapter_0.to x__0, (adapter_1.to x__1, ()))))))
    rw [adapter_0.to_from]
def InputsCover_total : Prop := ∀ args, VSCore3.ArgsTyped entry_total args → ∃ (x__0 : @Int) (x__1 : (@List.{0} @Int)), args = [adapter_0.encode x__0, adapter_1.encode x__1]
theorem inputs_cover_total : InputsCover_total := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [.int, (.list .int)] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [.int, (.list .int)] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact VSCore3.intRawLaws
    · exact (VSCore3.listRawLaws VSCore3.intRawLaws)) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, adapter_1.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from, adapter_1.to_from] using he.symm

/-- Accepted obligation O1, theorem PrimitiveFixture.shifted_contract, hash sha256:1111111111111111111111111111111111111111111111111111111111111111. -/
def Transfer_O1 : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@VeriSlopBridgeGoal.source_fn_shifted x__0 x__1) (@List.map.{0, 0} @Int @Int (fun (x__2 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__2 x__0)) x__1))))
theorem transfer_O1 (h_shifted : Refines_shifted) : Transfer_O1 := by
  have eq_shifted : source_fn_shifted = @PrimitiveFixture.shifted := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_shifted x__0 x__1
  have htransfer : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@VeriSlopBridgeGoal.source_fn_shifted x__0 x__1) (@List.map.{0, 0} @Int @Int (fun (x__2 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__2 x__0)) x__1))))) = ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@PrimitiveFixture.shifted x__0 x__1) (@List.map.{0, 0} @Int @Int (fun (x__2 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__2 x__0)) x__1))))) := by
    rw [eq_shifted]
  have hvalue : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@VeriSlopBridgeGoal.source_fn_shifted x__0 x__1) (@List.map.{0, 0} @Int @Int (fun (x__2 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__2 x__0)) x__1))))) := htransfer.symm ▸ (@PrimitiveFixture.shifted_contract)
  exact hvalue

/-- Accepted obligation O2, theorem PrimitiveFixture.selected_contract, hash sha256:2222222222222222222222222222222222222222222222222222222222222222. -/
def Transfer_O2 : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@VeriSlopBridgeGoal.source_fn_selected x__0 x__1) (@List.filter.{0} @Int (fun (x__2 : @Int) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt x__2 x__0) (@Int.decLt x__2 x__0))) x__1))))
theorem transfer_O2 (h_selected : Refines_selected) : Transfer_O2 := by
  have eq_selected : source_fn_selected = @PrimitiveFixture.selected := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_selected x__0 x__1
  have htransfer : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@VeriSlopBridgeGoal.source_fn_selected x__0 x__1) (@List.filter.{0} @Int (fun (x__2 : @Int) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt x__2 x__0) (@Int.decLt x__2 x__0))) x__1))))) = ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@PrimitiveFixture.selected x__0 x__1) (@List.filter.{0} @Int (fun (x__2 : @Int) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt x__2 x__0) (@Int.decLt x__2 x__0))) x__1))))) := by
    rw [eq_selected]
  have hvalue : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@VeriSlopBridgeGoal.source_fn_selected x__0 x__1) (@List.filter.{0} @Int (fun (x__2 : @Int) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt x__2 x__0) (@Int.decLt x__2 x__0))) x__1))))) := htransfer.symm ▸ (@PrimitiveFixture.selected_contract)
  exact hvalue

/-- Accepted obligation O3, theorem PrimitiveFixture.total_contract, hash sha256:3333333333333333333333333333333333333333333333333333333333333333. -/
def Transfer_O3 : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_total x__0 x__1) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Int @Int (fun (x__2 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__2 x__0)) (@List.filter.{0} @Int (fun (x__2 : @Int) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt x__2 x__0) (@Int.decLt x__2 x__0))) x__1))))))
theorem transfer_O3 (h_total : Refines_total) : Transfer_O3 := by
  have eq_total : source_fn_total = @PrimitiveFixture.total := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_total x__0 x__1
  have htransfer : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_total x__0 x__1) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Int @Int (fun (x__2 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__2 x__0)) (@List.filter.{0} @Int (fun (x__2 : @Int) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt x__2 x__0) (@Int.decLt x__2 x__0))) x__1))))))) = ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} @Int (@PrimitiveFixture.total x__0 x__1) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Int @Int (fun (x__2 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__2 x__0)) (@List.filter.{0} @Int (fun (x__2 : @Int) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt x__2 x__0) (@Int.decLt x__2 x__0))) x__1))))))) := by
    rw [eq_total]
  have hvalue : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @Int)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_total x__0 x__1) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Int @Int (fun (x__2 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__2 x__0)) (@List.filter.{0} @Int (fun (x__2 : @Int) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt x__2 x__0) (@Int.decLt x__2 x__0))) x__1))))))) := htransfer.symm ▸ (@PrimitiveFixture.total_contract)
  exact hvalue

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_shifted (@And @VeriSlopBridgeGoal.RawEval_shifted (@And @VeriSlopBridgeGoal.Refines_shifted (@And @VeriSlopBridgeGoal.InputsCover_selected (@And @VeriSlopBridgeGoal.RawEval_selected (@And @VeriSlopBridgeGoal.Refines_selected (@And @VeriSlopBridgeGoal.InputsCover_total (@And @VeriSlopBridgeGoal.RawEval_total (@And @VeriSlopBridgeGoal.Refines_total (@And @VeriSlopBridgeGoal.Transfer_O1 (@And @VeriSlopBridgeGoal.Transfer_O2 @VeriSlopBridgeGoal.Transfer_O3)))))))))))))
theorem edge_of_refines (h_shifted : Refines_shifted) (h_selected : Refines_selected) (h_total : Refines_total) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_shifted, raw_eval_shifted, h_shifted, inputs_cover_selected, raw_eval_selected, h_selected, inputs_cover_total, raw_eval_total, h_total, transfer_O1 h_shifted, transfer_O2 h_selected, transfer_O3 h_total⟩

end VeriSlopBridgeGoal
