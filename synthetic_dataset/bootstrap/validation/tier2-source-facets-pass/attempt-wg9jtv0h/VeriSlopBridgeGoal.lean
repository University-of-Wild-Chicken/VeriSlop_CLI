import VSCore3
import VSCore3.SourceFacts
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:6ae693b6ff2b6b44d09d8f782d9e3df9ded02bc1e729307343d04ea17fba0613. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 105, 100, 34, 58, 34, 105, 100, 101, 110, 116, 105, 116, 121, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 101, 110, 117, 109, 34, 58, 34, 77, 111, 100, 101, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 101, 110, 117, 109, 34, 58, 34, 77, 111, 100, 101, 34, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 105, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 49, 55, 34, 125, 44, 34, 105, 100, 34, 58, 34, 117, 110, 99, 111, 110, 115, 116, 114, 97, 105, 110, 101, 100, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [], helpers := [], entries := [{ id := "identity", params := [(VSCore3.Ty.enum "Mode")], result := (VSCore3.Ty.enum "Mode"), body := (VSCore3.Expr.var 0) },
{ id := "unconstrained", params := [VSCore3.Ty.int], result := VSCore3.Ty.int, body := (VSCore3.Expr.int (Int.ofNat 17)) }] }
def profile : VSCore3.Profile := { enums := [("Mode", ["left", "right"])] }
def signatures : List VSCore3.EntrySig := [{ id := "identity", params := [(VSCore3.Ty.enum "Mode")], result := (VSCore3.Ty.enum "Mode") },
  { id := "unconstrained", params := [VSCore3.Ty.int], result := VSCore3.Ty.int }]
def SourceParses : Prop := VSCore3.parseSource sourceBytes = .ok rawProgram
theorem source_parses : SourceParses := by rfl
def SourceChecks : Prop := VSCore3.checkProgram profile rawProgram = .ok signatures
theorem source_checks : SourceChecks := VSCore3.checkProgram_of_check (by decide +kernel)
def checkedProgram : VSCore3.CheckedProgram := (VSCore3.compileProgram profile rawProgram).toOption.getD
  { declarations := [], helpers := [], entries := [], signatures := [] }
theorem compiled_ok : VSCore3.compileProgram profile rawProgram = .ok checkedProgram := by with_unfolding_all rfl

/-- Exact accepted carrier {"enum":"Mode"}. -/
def adapter_0 : VSCore3.Adapter (.enum "Mode" ["left", "right"]) @Other.Mode :=
  { to := fun x => match x with | Other.Mode.left => ⟨"left", by decide +kernel⟩ | Other.Mode.right => ⟨"right", by decide +kernel⟩
    inv := fun x => if x.val = "left" then @Other.Mode.left else @Other.Mode.right
    from_to := by intro x; cases x <;> rfl
    to_from := by intro x; rcases x with ⟨x, h⟩; simp only [List.mem_cons, List.not_mem_nil, or_false] at h; rcases h with rfl | rfl; all_goals rfl }
def adapter_0_raw : VSCore3.RawLaws (.enum "Mode" ["left", "right"]) := (VSCore3.enumRawLaws "Mode" ["left", "right"])
theorem adapter_0_decode_encode (x : @Other.Mode) :
    VSCore3.decode (.enum "Mode" ["left", "right"]) (adapter_0.encode x) = some (adapter_0.to x) :=
  adapter_0.decode_encode adapter_0_raw x

/-- Exact accepted carrier "Int". -/
def adapter_1 : VSCore3.Adapter .int @Int :=
  VSCore3.intAdapter
def adapter_1_raw : VSCore3.RawLaws .int := VSCore3.intRawLaws
theorem adapter_1_decode_encode (x : @Int) :
    VSCore3.decode .int (adapter_1.encode x) = some (adapter_1.to x) :=
  adapter_1.decode_encode adapter_1_raw x

abbrev entry_identity : VSCore3.CompiledFunction :=
  { id := "identity", params := [(.enum "Mode" ["left", "right"])], result := (.enum "Mode" ["left", "right"]),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "identity").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_identity : VSCore3.findEntry checkedProgram "identity" = some entry_identity := by with_unfolding_all rfl
def source_fn_identity (x__0 : @Other.Mode) : @Other.Mode := by
  with_unfolding_all exact adapter_0.inv (entry_identity.run (adapter_0.to x__0, ()))
def Refines_identity : Prop := (∀ (x__0 : @Other.Mode), (@Eq.{1} @Other.Mode (@VeriSlopBridgeGoal.source_fn_identity x__0) (@Other.identity x__0)))
def RawEval_identity : Prop := ∀ (x__0 : @Other.Mode),
  VSCore3.evalEntry profile rawProgram "identity" [adapter_0.encode x__0] =
    .ok (adapter_0.encode (source_fn_identity x__0))
theorem raw_eval_identity : RawEval_identity := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_identity.params [adapter_0.encode x__0] = some (adapter_0.to x__0, ()) := by
      change VSCore3.decodeEnv [(.enum "Mode" ["left", "right"])] [adapter_0.encode x__0] = some (adapter_0.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "identity" [adapter_0.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_identity, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_identity, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.enum "Mode" ["left", "right"]) (entry_identity.run (adapter_0.to x__0, ()))) =
      Except.ok (VSCore3.encode (.enum "Mode" ["left", "right"]) (adapter_0.to (adapter_0.inv (entry_identity.run (adapter_0.to x__0, ())))))
    rw [adapter_0.to_from]
def InputsCover_identity : Prop := ∀ args, VSCore3.ArgsTyped entry_identity args → ∃ (x__0 : @Other.Mode), args = [adapter_0.encode x__0]
theorem inputs_cover_identity : InputsCover_identity := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.enum "Mode" ["left", "right"])] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.enum "Mode" ["left", "right"])] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.enumRawLaws "Mode" ["left", "right"])) args env hd
    rcases env with ⟨v__0, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from] using he.symm

abbrev entry_unconstrained : VSCore3.CompiledFunction :=
  { id := "unconstrained", params := [.int], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "unconstrained").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_unconstrained : VSCore3.findEntry checkedProgram "unconstrained" = some entry_unconstrained := by with_unfolding_all rfl
def source_fn_unconstrained (x__0 : @Int) : @Int := by
  with_unfolding_all exact adapter_1.inv (entry_unconstrained.run (adapter_1.to x__0, ()))
def Refines_unconstrained : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_unconstrained x__0) (@Other.unconstrained x__0)))
def RawEval_unconstrained : Prop := ∀ (x__0 : @Int),
  VSCore3.evalEntry profile rawProgram "unconstrained" [adapter_1.encode x__0] =
    .ok (adapter_1.encode (source_fn_unconstrained x__0))
theorem raw_eval_unconstrained : RawEval_unconstrained := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_unconstrained.params [adapter_1.encode x__0] = some (adapter_1.to x__0, ()) := by
      change VSCore3.decodeEnv [.int] [adapter_1.encode x__0] = some (adapter_1.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_1_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "unconstrained" [adapter_1.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_unconstrained, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_unconstrained, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_unconstrained.run (adapter_1.to x__0, ()))) =
      Except.ok (VSCore3.encode .int (adapter_1.to (adapter_1.inv (entry_unconstrained.run (adapter_1.to x__0, ())))))
    rw [adapter_1.to_from]
def InputsCover_unconstrained : Prop := ∀ args, VSCore3.ArgsTyped entry_unconstrained args → ∃ (x__0 : @Int), args = [adapter_1.encode x__0]
theorem inputs_cover_unconstrained : InputsCover_unconstrained := by
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
    refine ⟨adapter_1.inv v__0, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_1.to_from] using he.symm

def sourceFacts_unconstrained : VeriSlop.Source.ModuleFacts :=
  let m := VSCore3.exactSourceFacts profile rawProgram "unconstrained"
  { entries := m.entries.map (fun e => ⟨e.file, e.id, e.arity⟩),
    uniqueEntries := m.uniqueEntries, typedTotal := m.typedTotal, deterministic := m.deterministic,
    inputPreserved := m.inputPreserved, noExternalIO := m.noExternalIO,
    noFloatingPoint := m.noFloatingPoint, pureData := m.pureData,
    restrictedRuntimeOnly := m.restrictedRuntimeOnly }
def SourceAdequate_unconstrained : Prop :=
  VSCore3.SourceFactsAdequate profile rawProgram "unconstrained" checkedProgram entry_unconstrained
theorem source_adequate_unconstrained : SourceAdequate_unconstrained := by
  with_unfolding_all
    exact VSCore3.exactSourceFacts_adequate compiled_ok find_unconstrained
      (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact VSCore3.intRawLaws)
      adapter_1_raw

/-- Accepted obligation O1, theorem Other.identity_contract, hash sha256:5555555555555555555555555555555555555555555555555555555555555555. -/
def Transfer_O1 : Prop := (∀ (x__0 : @Other.Mode), (@Eq.{1} @Other.Mode (@VeriSlopBridgeGoal.source_fn_identity x__0) x__0))
theorem transfer_O1 (h_identity : Refines_identity) : Transfer_O1 := by
  have eq_identity : source_fn_identity = @Other.identity := by
    apply funext; intro x__0
    exact h_identity x__0
  have htransfer : ((∀ (x__0 : @Other.Mode), (@Eq.{1} @Other.Mode (@VeriSlopBridgeGoal.source_fn_identity x__0) x__0))) = ((∀ (x__0 : @Other.Mode), (@Eq.{1} @Other.Mode (@Other.identity x__0) x__0))) := by
    rw [eq_identity]
  have hvalue : ((∀ (x__0 : @Other.Mode), (@Eq.{1} @Other.Mode (@VeriSlopBridgeGoal.source_fn_identity x__0) x__0))) := htransfer.symm ▸ (@Other.identity_contract)
  exact hvalue

/-- Accepted obligation S1, theorem Other.source_only, hash sha256:6666666666666666666666666666666666666666666666666666666666666666. -/
def Transfer_S1 : Prop := (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @Int), @Int) @Other.source) @VeriSlopBridgeGoal.sourceFacts_unconstrained)
theorem transfer_S1  : Transfer_S1 := by
  have haccepted := @Other.source_only
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @Int), @Int) @Other.source) @VeriSlopBridgeGoal.sourceFacts_unconstrained)) := by
    apply (haccepted).1 sourceFacts_unconstrained
    with_unfolding_all rfl
  exact hsource_0

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_identity (@And @VeriSlopBridgeGoal.RawEval_identity (@And @VeriSlopBridgeGoal.Refines_identity (@And @VeriSlopBridgeGoal.InputsCover_unconstrained (@And @VeriSlopBridgeGoal.RawEval_unconstrained (@And @VeriSlopBridgeGoal.SourceAdequate_unconstrained (@And @VeriSlopBridgeGoal.Transfer_O1 @VeriSlopBridgeGoal.Transfer_S1)))))))))
theorem edge_of_refines (h_identity : Refines_identity) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_identity, raw_eval_identity, h_identity, inputs_cover_unconstrained, raw_eval_unconstrained, source_adequate_unconstrained, transfer_O1 h_identity, transfer_S1 ⟩

end VeriSlopBridgeGoal
