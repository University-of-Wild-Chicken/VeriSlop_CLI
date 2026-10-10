import VSCore3
import VSCore3.SourceFacts
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:336673d4e500115544770925da3a090981c5b459d1b864a19cde75911d7bf0eb. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 100, 105, 114, 101, 99, 116, 105, 111, 110, 34, 44, 34, 116, 121, 112, 101, 34, 58, 123, 34, 101, 110, 117, 109, 34, 58, 34, 67, 111, 109, 112, 97, 115, 115, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 105, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 100, 105, 114, 101, 99, 116, 105, 111, 110, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 100, 105, 114, 101, 99, 116, 105, 111, 110, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 99, 111, 110, 100, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 100, 105, 114, 101, 99, 116, 105, 111, 110, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 99, 116, 111, 114, 34, 58, 34, 110, 111, 114, 116, 104, 34, 44, 34, 101, 110, 117, 109, 34, 58, 34, 67, 111, 109, 112, 97, 115, 115, 34, 44, 34, 116, 97, 103, 34, 58, 34, 101, 110, 117, 109, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 101, 113, 34, 125, 44, 34, 101, 108, 115, 101, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 105, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 51, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 115, 117, 98, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 105, 102, 34, 44, 34, 116, 104, 101, 110, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 105, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 50, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 125, 125, 93, 44, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 97, 100, 106, 117, 115, 116, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 125, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [(VSCore3.DataDecl.record "Packet" [("direction", (VSCore3.Ty.enum "Compass")), ("amount", VSCore3.Ty.int)])], helpers := [], entries := [{ id := "adjust", params := [(VSCore3.Ty.record "Packet")], result := (VSCore3.Ty.record "Packet"), body := (VSCore3.Expr.record "Packet" [("direction", (VSCore3.Expr.project (VSCore3.Expr.var 0) "direction")), ("amount", (VSCore3.Expr.ite (VSCore3.Expr.bin VSCore.BinOp.eq (VSCore3.Expr.project (VSCore3.Expr.var 0) "direction") (VSCore3.Expr.enum "Compass" "north")) (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.project (VSCore3.Expr.var 0) "amount") (VSCore3.Expr.int (Int.ofNat 2))) (VSCore3.Expr.bin VSCore.BinOp.sub (VSCore3.Expr.project (VSCore3.Expr.var 0) "amount") (VSCore3.Expr.int (Int.ofNat 3)))))]) }] }
def profile : VSCore3.Profile := { enums := [("Compass", ["north", "south", "center"])] }
def signatures : List VSCore3.EntrySig := [{ id := "adjust", params := [(VSCore3.Ty.record "Packet")], result := (VSCore3.Ty.record "Packet") }]
def SourceParses : Prop := VSCore3.parseSource sourceBytes = .ok rawProgram
theorem source_parses : SourceParses := by rfl
def SourceChecks : Prop := VSCore3.checkProgram profile rawProgram = .ok signatures
theorem source_checks : SourceChecks := VSCore3.checkProgram_of_check (by decide +kernel)
def checkedProgram : VSCore3.CheckedProgram := (VSCore3.compileProgram profile rawProgram).toOption.getD
  { declarations := [], helpers := [], entries := [], signatures := [] }
theorem compiled_ok : VSCore3.compileProgram profile rawProgram = .ok checkedProgram := by with_unfolding_all rfl

/-- Exact accepted carrier {"enum":"Compass"}. -/
def adapter_0 : VSCore3.Adapter (.enum "Compass" ["north", "south", "center"]) @VeriSlopAST.Compass :=
  { to := fun x => match x with | VeriSlopAST.Compass.north => ⟨"north", by decide +kernel⟩ | VeriSlopAST.Compass.south => ⟨"south", by decide +kernel⟩ | VeriSlopAST.Compass.center => ⟨"center", by decide +kernel⟩
    inv := fun x => if x.val = "north" then @VeriSlopAST.Compass.north else if x.val = "south" then @VeriSlopAST.Compass.south else @VeriSlopAST.Compass.center
    from_to := by intro x; cases x <;> rfl
    to_from := by intro x; rcases x with ⟨x, h⟩; simp only [List.mem_cons, List.not_mem_nil, or_false] at h; rcases h with rfl | rfl | rfl; all_goals rfl }
def adapter_0_raw : VSCore3.RawLaws (.enum "Compass" ["north", "south", "center"]) := (VSCore3.enumRawLaws "Compass" ["north", "south", "center"])
theorem adapter_0_decode_encode (x : @VeriSlopAST.Compass) :
    VSCore3.decode (.enum "Compass" ["north", "south", "center"]) (adapter_0.encode x) = some (adapter_0.to x) :=
  adapter_0.decode_encode adapter_0_raw x

/-- Exact accepted carrier "Int". -/
def adapter_1 : VSCore3.Adapter .int @Int :=
  VSCore3.intAdapter
def adapter_1_raw : VSCore3.RawLaws .int := VSCore3.intRawLaws
theorem adapter_1_decode_encode (x : @Int) :
    VSCore3.decode .int (adapter_1.encode x) = some (adapter_1.to x) :=
  adapter_1.decode_encode adapter_1_raw x

/-- Exact accepted carrier {"record":"Packet"}. -/
def adapter_2 : VSCore3.Adapter (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit))) @VeriSlopAST.Packet :=
  { to := fun x => (adapter_0.to (@VeriSlopAST.Packet.direction x), (adapter_1.to (@VeriSlopAST.Packet.amount x), ()))
    inv := fun x => @VeriSlopAST.Packet.mk (adapter_0.inv (x.1)) (adapter_1.inv (x.2.1))
    from_to := by intro x; cases x; simp [adapter_0.from_to, adapter_1.from_to]
    to_from := by intro x; rcases x with ⟨x0, x⟩; rcases x with ⟨x1, x⟩; cases x; simp [adapter_0.to_from, adapter_1.to_from] }
def adapter_2_raw : VSCore3.RawLaws (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit))) := (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "direction" (VSCore3.RecordLayout.cons "amount" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Compass" ["north", "south", "center"]) (VSCore3.productRawLaws VSCore3.intRawLaws VSCore3.unitRawLaws)))
theorem adapter_2_decode_encode (x : @VeriSlopAST.Packet) :
    VSCore3.decode (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit))) (adapter_2.encode x) = some (adapter_2.to x) :=
  adapter_2.decode_encode adapter_2_raw x

abbrev entry_adjust : VSCore3.CompiledFunction :=
  { id := "adjust", params := [(.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))], result := (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit))),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "adjust").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_adjust : VSCore3.findEntry checkedProgram "adjust" = some entry_adjust := by with_unfolding_all rfl
def source_fn_adjust (x__0 : @VeriSlopAST.Packet) : @VeriSlopAST.Packet := by
  with_unfolding_all exact adapter_2.inv (entry_adjust.run (adapter_2.to x__0, ()))
def Refines_adjust : Prop := (∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @VeriSlopAST.Packet (@VeriSlopBridgeGoal.source_fn_adjust x__0) (@VeriSlopAST.adjust x__0)))
def RawEval_adjust : Prop := ∀ (x__0 : @VeriSlopAST.Packet),
  VSCore3.evalEntry profile rawProgram "adjust" [adapter_2.encode x__0] =
    .ok (adapter_2.encode (source_fn_adjust x__0))
theorem raw_eval_adjust : RawEval_adjust := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_adjust.params [adapter_2.encode x__0] = some (adapter_2.to x__0, ()) := by
      change VSCore3.decodeEnv [(.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))] [adapter_2.encode x__0] = some (adapter_2.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_2_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "adjust" [adapter_2.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_adjust, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_adjust, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit))) (entry_adjust.run (adapter_2.to x__0, ()))) =
      Except.ok (VSCore3.encode (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit))) (adapter_2.to (adapter_2.inv (entry_adjust.run (adapter_2.to x__0, ())))))
    rw [adapter_2.to_from]
def InputsCover_adjust : Prop := ∀ args, VSCore3.ArgsTyped entry_adjust args → ∃ (x__0 : @VeriSlopAST.Packet), args = [adapter_2.encode x__0]
theorem inputs_cover_adjust : InputsCover_adjust := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "direction" (VSCore3.RecordLayout.cons "amount" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Compass" ["north", "south", "center"]) (VSCore3.productRawLaws VSCore3.intRawLaws VSCore3.unitRawLaws)))) args env hd
    rcases env with ⟨v__0, env⟩
    cases env
    refine ⟨adapter_2.inv v__0, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_2.to_from] using he.symm

def sourceFacts_adjust : VeriSlop.Source.ModuleFacts :=
  let m := VSCore3.exactSourceFacts profile rawProgram "adjust"
  { entries := m.entries.map (fun e => ⟨e.file, e.id, e.arity⟩),
    uniqueEntries := m.uniqueEntries, typedTotal := m.typedTotal, deterministic := m.deterministic,
    inputPreserved := m.inputPreserved, noExternalIO := m.noExternalIO,
    noFloatingPoint := m.noFloatingPoint, pureData := m.pureData,
    restrictedRuntimeOnly := m.restrictedRuntimeOnly }
def SourceAdequate_adjust : Prop :=
  VSCore3.SourceFactsAdequate profile rawProgram "adjust" checkedProgram entry_adjust
theorem source_adequate_adjust : SourceAdequate_adjust := by
  with_unfolding_all
    exact VSCore3.exactSourceFacts_adequate compiled_ok find_adjust
      (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "direction" (VSCore3.RecordLayout.cons "amount" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Compass" ["north", "south", "center"]) (VSCore3.productRawLaws VSCore3.intRawLaws VSCore3.unitRawLaws))))
      adapter_2_raw

/-- Accepted obligation O1, theorem VeriSlopAST.adjustment, hash sha256:7f83d8ba80a2fc378c9cb1e68c5eb88b6890db94dbee96e18f21b370f83881f3. -/
def Transfer_O1 : Prop := (@And (∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @VeriSlopAST.Packet (@VeriSlopBridgeGoal.source_fn_adjust x__0) (@VeriSlopAST.Packet.mk (@VeriSlopAST.Packet.direction x__0) (@cond.{1} @Int (@Decidable.decide (@Eq.{1} @VeriSlopAST.Compass (@VeriSlopAST.Packet.direction x__0) @VeriSlopAST.Compass.north) (@VeriSlopAST.instDecidableEqCompass (@VeriSlopAST.Packet.direction x__0) @VeriSlopAST.Compass.north)) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@VeriSlopAST.Packet.amount x__0) (@Int.ofNat (nat_lit 2))) (@HSub.hSub.{0, 0, 0} @Int @Int @Int (@instHSub.{0} @Int @Int.instSub) (@VeriSlopAST.Packet.amount x__0) (@Int.ofNat (nat_lit 3))))))) (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Packet), @VeriSlopAST.Packet) @VeriSlopAST.Delivery) @VeriSlopBridgeGoal.sourceFacts_adjust))
theorem transfer_O1 (h_adjust : Refines_adjust) : Transfer_O1 := by
  have haccepted := @VeriSlopAST.adjustment
  have eq_adjust : source_fn_adjust = @VeriSlopAST.adjust := by
    apply funext; intro x__0
    exact h_adjust x__0
  have htransfer : ((∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @VeriSlopAST.Packet (@VeriSlopBridgeGoal.source_fn_adjust x__0) (@VeriSlopAST.Packet.mk (@VeriSlopAST.Packet.direction x__0) (@cond.{1} @Int (@Decidable.decide (@Eq.{1} @VeriSlopAST.Compass (@VeriSlopAST.Packet.direction x__0) @VeriSlopAST.Compass.north) (@VeriSlopAST.instDecidableEqCompass (@VeriSlopAST.Packet.direction x__0) @VeriSlopAST.Compass.north)) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@VeriSlopAST.Packet.amount x__0) (@Int.ofNat (nat_lit 2))) (@HSub.hSub.{0, 0, 0} @Int @Int @Int (@instHSub.{0} @Int @Int.instSub) (@VeriSlopAST.Packet.amount x__0) (@Int.ofNat (nat_lit 3)))))))) = ((∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @VeriSlopAST.Packet (@VeriSlopAST.adjust x__0) (@VeriSlopAST.Packet.mk (@VeriSlopAST.Packet.direction x__0) (@cond.{1} @Int (@Decidable.decide (@Eq.{1} @VeriSlopAST.Compass (@VeriSlopAST.Packet.direction x__0) @VeriSlopAST.Compass.north) (@VeriSlopAST.instDecidableEqCompass (@VeriSlopAST.Packet.direction x__0) @VeriSlopAST.Compass.north)) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@VeriSlopAST.Packet.amount x__0) (@Int.ofNat (nat_lit 2))) (@HSub.hSub.{0, 0, 0} @Int @Int @Int (@instHSub.{0} @Int @Int.instSub) (@VeriSlopAST.Packet.amount x__0) (@Int.ofNat (nat_lit 3)))))))) := by
    rw [eq_adjust]
  have hvalue : ((∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @VeriSlopAST.Packet (@VeriSlopBridgeGoal.source_fn_adjust x__0) (@VeriSlopAST.Packet.mk (@VeriSlopAST.Packet.direction x__0) (@cond.{1} @Int (@Decidable.decide (@Eq.{1} @VeriSlopAST.Compass (@VeriSlopAST.Packet.direction x__0) @VeriSlopAST.Compass.north) (@VeriSlopAST.instDecidableEqCompass (@VeriSlopAST.Packet.direction x__0) @VeriSlopAST.Compass.north)) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@VeriSlopAST.Packet.amount x__0) (@Int.ofNat (nat_lit 2))) (@HSub.hSub.{0, 0, 0} @Int @Int @Int (@instHSub.{0} @Int @Int.instSub) (@VeriSlopAST.Packet.amount x__0) (@Int.ofNat (nat_lit 3)))))))) := htransfer.symm ▸ (haccepted.1)
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Packet), @VeriSlopAST.Packet) @VeriSlopAST.Delivery) @VeriSlopBridgeGoal.sourceFacts_adjust)) := by
    apply (haccepted.2).1 sourceFacts_adjust
    with_unfolding_all rfl
  exact ⟨hvalue, hsource_0⟩

/-- Accepted obligation S1, theorem VeriSlopAST.source_delivery, hash sha256:933a74c619d0cb4465bc18af0f665bb88efbe768e920ba22c1d7a03d81d98585. -/
def Transfer_S1 : Prop := (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Packet), @VeriSlopAST.Packet) @VeriSlopAST.Delivery) @VeriSlopBridgeGoal.sourceFacts_adjust)
theorem transfer_S1  : Transfer_S1 := by
  have haccepted := @VeriSlopAST.source_delivery
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Packet), @VeriSlopAST.Packet) @VeriSlopAST.Delivery) @VeriSlopBridgeGoal.sourceFacts_adjust)) := by
    apply (haccepted).1 sourceFacts_adjust
    with_unfolding_all rfl
  exact hsource_0

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_adjust (@And @VeriSlopBridgeGoal.RawEval_adjust (@And @VeriSlopBridgeGoal.Refines_adjust (@And @VeriSlopBridgeGoal.SourceAdequate_adjust (@And @VeriSlopBridgeGoal.Transfer_O1 @VeriSlopBridgeGoal.Transfer_S1)))))))
theorem edge_of_refines (h_adjust : Refines_adjust) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_adjust, raw_eval_adjust, h_adjust, source_adequate_adjust, transfer_O1 h_adjust, transfer_S1 ⟩

end VeriSlopBridgeGoal

namespace VeriSlopReadableSource
abbrev entry_0_params : List VSCore3.Shape := [(.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))]
abbrev entry_0_result : VSCore3.Shape := (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))
def entry_0_body (env : VSCore3.Env entry_0_params.reverse) : VSCore3.Denote entry_0_result := by
  with_unfolding_all exact ((((env).1).1, ((if ((letI := VSCore3.denoteDecidableEq (.enum "Compass" ["north", "south", "center"]); decide ((((env).1).1) = ((⟨"north", by decide +kernel⟩ : VSCore3.Denote (.enum "Compass" ["north", "south", "center"])))))) then (((((env).1).2.1) + ((Int.ofNat 2)))) else (((((env).1).2.1) - ((Int.ofNat 3))))), ())) : VSCore3.Denote (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit))))
def entry_0_run (env : VSCore3.Env entry_0_params) : VSCore3.Denote entry_0_result :=
  entry_0_body (VSCore3.envReverse entry_0_params env)
def entry_0_named (p__0 : VSCore3.Denote (.record "Packet" ["direction", "amount"] (.product (.enum "Compass" ["north", "south", "center"]) (.product .int .unit)))) : VSCore3.Denote entry_0_result :=
  entry_0_run (p__0, ())
end VeriSlopReadableSource

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
