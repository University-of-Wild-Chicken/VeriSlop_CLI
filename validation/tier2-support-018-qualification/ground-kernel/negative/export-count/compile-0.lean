import VSCore3
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:f70fb3d66695f21accb9485026a7603acf2e5c4d748a1df4fe3f7bcde38aa98b. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 105, 100, 34, 58, 34, 116, 114, 97, 110, 115, 102, 111, 114, 109, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [], helpers := [], entries := [{ id := "transform", params := [VSCore3.Ty.int], result := VSCore3.Ty.int, body := (VSCore3.Expr.var 0) }] }
def profile : VSCore3.Profile := { enums := [] }
def signatures : List VSCore3.EntrySig := [{ id := "transform", params := [VSCore3.Ty.int], result := VSCore3.Ty.int }]
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

abbrev entry_transform : VSCore3.CompiledFunction :=
  { id := "transform", params := [.int], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "transform").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_transform : VSCore3.findEntry checkedProgram "transform" = some entry_transform := by with_unfolding_all rfl
def source_fn_transform (x__0 : @Int) : @Int := by
  with_unfolding_all exact adapter_0.inv (entry_transform.run (adapter_0.to x__0, ()))
def Refines_transform : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform x__0) (@VeriSlopContract.reference x__0)))
def RawEval_transform : Prop := ∀ (x__0 : @Int),
  VSCore3.evalEntry profile rawProgram "transform" [adapter_0.encode x__0] =
    .ok (adapter_0.encode (source_fn_transform x__0))
theorem raw_eval_transform : RawEval_transform := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_transform.params [adapter_0.encode x__0] = some (adapter_0.to x__0, ()) := by
      change VSCore3.decodeEnv [.int] [adapter_0.encode x__0] = some (adapter_0.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "transform" [adapter_0.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_transform, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_transform, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_transform.run (adapter_0.to x__0, ()))) =
      Except.ok (VSCore3.encode .int (adapter_0.to (adapter_0.inv (entry_transform.run (adapter_0.to x__0, ())))))
    rw [adapter_0.to_from]
def InputsCover_transform : Prop := ∀ args, VSCore3.ArgsTyped entry_transform args → ∃ (x__0 : @Int), args = [adapter_0.encode x__0]
theorem inputs_cover_transform : InputsCover_transform := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [.int] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [.int] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact VSCore3.intRawLaws) args env hd
    rcases env with ⟨v__0, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from] using he.symm

/-- Accepted obligation GENERIC, theorem VeriSlopContract.guarantee, hash sha256:61f98725ea7299ae6445b86827f9bf96277919ce24ece2603034ab9169d08a9d. -/
def Transfer_GENERIC : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform x__0) x__0))
theorem transfer_GENERIC (h_transform : Refines_transform) : Transfer_GENERIC := by
  have eq_transform : source_fn_transform = @VeriSlopContract.reference := by
    apply funext; intro x__0
    exact h_transform x__0
  have htransfer : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform x__0) x__0))) = ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopContract.reference x__0) x__0))) := by
    rw [eq_transform]
  have hvalue : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transform x__0) x__0))) := htransfer.symm ▸ (@VeriSlopContract.guarantee)
  exact hvalue

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_transform (@And @VeriSlopBridgeGoal.RawEval_transform (@And @VeriSlopBridgeGoal.Refines_transform @VeriSlopBridgeGoal.Transfer_GENERIC)))))
theorem edge_of_refines (h_transform : Refines_transform) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_transform, raw_eval_transform, h_transform, transfer_GENERIC h_transform⟩

end VeriSlopBridgeGoal
