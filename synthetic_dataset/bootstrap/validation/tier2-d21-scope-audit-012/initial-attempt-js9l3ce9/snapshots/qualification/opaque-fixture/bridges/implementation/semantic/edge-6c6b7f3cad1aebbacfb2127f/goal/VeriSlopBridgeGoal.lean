import VSCore3
import VSCore3.SourceFacts
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:3f49720f68a80d1d953f6b1e848c785e8b4e3063b6b1b9f336d31fffe1720659. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 105, 100, 34, 58, 34, 119, 111, 114, 100, 115, 34, 44, 34, 116, 121, 112, 101, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 34, 115, 116, 114, 105, 110, 103, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 101, 120, 116, 114, 97, 34, 44, 34, 116, 121, 112, 101, 34, 58, 123, 34, 111, 112, 116, 105, 111, 110, 34, 58, 34, 105, 110, 116, 34, 125, 125, 93, 44, 34, 105, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 105, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 45, 51, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 115, 104, 105, 102, 116, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 105, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 45, 51, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 115, 111, 108, 118, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [(VSCore3.DataDecl.record "Packet" [("amount", VSCore3.Ty.int), ("words", (VSCore3.Ty.list VSCore3.Ty.string)), ("extra", (VSCore3.Ty.option VSCore3.Ty.int))])], helpers := [], entries := [{ id := "shift", params := [VSCore3.Ty.int], result := VSCore3.Ty.int, body := (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.var 0) (VSCore3.Expr.int (Int.negSucc 2))) },
{ id := "solve", params := [(VSCore3.Ty.record "Packet")], result := VSCore3.Ty.int, body := (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.project (VSCore3.Expr.var 0) "amount") (VSCore3.Expr.int (Int.negSucc 2))) }] }
def profile : VSCore3.Profile := { enums := [] }
def signatures : List VSCore3.EntrySig := [{ id := "shift", params := [VSCore3.Ty.int], result := VSCore3.Ty.int },
  { id := "solve", params := [(VSCore3.Ty.record "Packet")], result := VSCore3.Ty.int }]
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

/-- Exact accepted carrier "String". -/
def adapter_1 : VSCore3.Adapter .string @String :=
  VSCore3.stringAdapter
def adapter_1_raw : VSCore3.RawLaws .string := VSCore3.stringRawLaws
theorem adapter_1_decode_encode (x : @String) :
    VSCore3.decode .string (adapter_1.encode x) = some (adapter_1.to x) :=
  adapter_1.decode_encode adapter_1_raw x

/-- Exact accepted carrier {"list":"String"}. -/
def adapter_2 : VSCore3.Adapter (.list .string) (@List.{0} @String) :=
  VSCore3.listAdapter adapter_1
def adapter_2_raw : VSCore3.RawLaws (.list .string) := (VSCore3.listRawLaws VSCore3.stringRawLaws)
theorem adapter_2_decode_encode (x : (@List.{0} @String)) :
    VSCore3.decode (.list .string) (adapter_2.encode x) = some (adapter_2.to x) :=
  adapter_2.decode_encode adapter_2_raw x

/-- Exact accepted carrier {"option":"Int"}. -/
def adapter_3 : VSCore3.Adapter (.option .int) (@Option.{0} @Int) :=
  VSCore3.optionAdapter adapter_0
def adapter_3_raw : VSCore3.RawLaws (.option .int) := (VSCore3.optionRawLaws VSCore3.intRawLaws)
theorem adapter_3_decode_encode (x : (@Option.{0} @Int)) :
    VSCore3.decode (.option .int) (adapter_3.encode x) = some (adapter_3.to x) :=
  adapter_3.decode_encode adapter_3_raw x

/-- Exact accepted carrier {"record":"Packet"}. -/
def adapter_4 : VSCore3.Adapter (.record "Packet" ["amount", "words", "extra"] (.product .int (.product (.list .string) (.product (.option .int) .unit)))) @VeriSlopAST.Packet :=
  { to := fun x => (adapter_0.to (@VeriSlopAST.Packet.amount x), (adapter_2.to (@VeriSlopAST.Packet.words x), (adapter_3.to (@VeriSlopAST.Packet.extra x), ())))
    inv := fun x => @VeriSlopAST.Packet.mk (adapter_0.inv (x.1)) (adapter_2.inv (x.2.1)) (adapter_3.inv (x.2.2.1))
    from_to := by intro x; cases x; simp [adapter_0.from_to, adapter_2.from_to, adapter_3.from_to]
    to_from := by intro x; rcases x with ⟨x0, x⟩; rcases x with ⟨x1, x⟩; rcases x with ⟨x2, x⟩; cases x; simp [adapter_0.to_from, adapter_2.to_from, adapter_3.to_from] }
def adapter_4_raw : VSCore3.RawLaws (.record "Packet" ["amount", "words", "extra"] (.product .int (.product (.list .string) (.product (.option .int) .unit)))) := (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "amount" (VSCore3.RecordLayout.cons "words" (VSCore3.RecordLayout.cons "extra" VSCore3.RecordLayout.nil))) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws (VSCore3.listRawLaws VSCore3.stringRawLaws) (VSCore3.productRawLaws (VSCore3.optionRawLaws VSCore3.intRawLaws) VSCore3.unitRawLaws))))
theorem adapter_4_decode_encode (x : @VeriSlopAST.Packet) :
    VSCore3.decode (.record "Packet" ["amount", "words", "extra"] (.product .int (.product (.list .string) (.product (.option .int) .unit)))) (adapter_4.encode x) = some (adapter_4.to x) :=
  adapter_4.decode_encode adapter_4_raw x

abbrev entry_shift : VSCore3.CompiledFunction :=
  { id := "shift", params := [.int], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "shift").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_shift : VSCore3.findEntry checkedProgram "shift" = some entry_shift := by with_unfolding_all rfl
def source_fn_shift (x__0 : @Int) : @Int := by
  with_unfolding_all exact adapter_0.inv (entry_shift.run (adapter_0.to x__0, ()))
def Refines_shift : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_shift x__0) (@VeriSlopAST.shift x__0)))
def RawEval_shift : Prop := ∀ (x__0 : @Int),
  VSCore3.evalEntry profile rawProgram "shift" [adapter_0.encode x__0] =
    .ok (adapter_0.encode (source_fn_shift x__0))
theorem raw_eval_shift : RawEval_shift := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_shift.params [adapter_0.encode x__0] = some (adapter_0.to x__0, ()) := by
      change VSCore3.decodeEnv [.int] [adapter_0.encode x__0] = some (adapter_0.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "shift" [adapter_0.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_shift, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_shift, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_shift.run (adapter_0.to x__0, ()))) =
      Except.ok (VSCore3.encode .int (adapter_0.to (adapter_0.inv (entry_shift.run (adapter_0.to x__0, ())))))
    rw [adapter_0.to_from]
def InputsCover_shift : Prop := ∀ args, VSCore3.ArgsTyped entry_shift args → ∃ (x__0 : @Int), args = [adapter_0.encode x__0]
theorem inputs_cover_shift : InputsCover_shift := by
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

def sourceFacts_shift : VeriSlop.Source.ModuleFacts :=
  let m := VSCore3.exactSourceFacts profile rawProgram "shift"
  { entries := m.entries.map (fun e => ⟨e.file, e.id, e.arity⟩),
    uniqueEntries := m.uniqueEntries, typedTotal := m.typedTotal, deterministic := m.deterministic,
    inputPreserved := m.inputPreserved, noExternalIO := m.noExternalIO,
    noFloatingPoint := m.noFloatingPoint, pureData := m.pureData,
    restrictedRuntimeOnly := m.restrictedRuntimeOnly }
def SourceAdequate_shift : Prop :=
  VSCore3.SourceFactsAdequate profile rawProgram "shift" checkedProgram entry_shift
theorem source_adequate_shift : SourceAdequate_shift := by
  with_unfolding_all
    exact VSCore3.exactSourceFacts_adequate compiled_ok find_shift
      (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact VSCore3.intRawLaws)
      adapter_0_raw

abbrev entry_solve : VSCore3.CompiledFunction :=
  { id := "solve", params := [(.record "Packet" ["amount", "words", "extra"] (.product .int (.product (.list .string) (.product (.option .int) .unit))))], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "solve").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_solve : VSCore3.findEntry checkedProgram "solve" = some entry_solve := by with_unfolding_all rfl
def source_fn_solve (x__0 : @VeriSlopAST.Packet) : @Int := by
  with_unfolding_all exact adapter_0.inv (entry_solve.run (adapter_4.to x__0, ()))
def Refines_solve : Prop := (∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@VeriSlopAST.solve x__0)))
def RawEval_solve : Prop := ∀ (x__0 : @VeriSlopAST.Packet),
  VSCore3.evalEntry profile rawProgram "solve" [adapter_4.encode x__0] =
    .ok (adapter_0.encode (source_fn_solve x__0))
theorem raw_eval_solve : RawEval_solve := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_solve.params [adapter_4.encode x__0] = some (adapter_4.to x__0, ()) := by
      change VSCore3.decodeEnv [(.record "Packet" ["amount", "words", "extra"] (.product .int (.product (.list .string) (.product (.option .int) .unit))))] [adapter_4.encode x__0] = some (adapter_4.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_4_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "solve" [adapter_4.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_solve, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_solve, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_solve.run (adapter_4.to x__0, ()))) =
      Except.ok (VSCore3.encode .int (adapter_0.to (adapter_0.inv (entry_solve.run (adapter_4.to x__0, ())))))
    rw [adapter_0.to_from]
def InputsCover_solve : Prop := ∀ args, VSCore3.ArgsTyped entry_solve args → ∃ (x__0 : @VeriSlopAST.Packet), args = [adapter_4.encode x__0]
theorem inputs_cover_solve : InputsCover_solve := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.record "Packet" ["amount", "words", "extra"] (.product .int (.product (.list .string) (.product (.option .int) .unit))))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.record "Packet" ["amount", "words", "extra"] (.product .int (.product (.list .string) (.product (.option .int) .unit))))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "amount" (VSCore3.RecordLayout.cons "words" (VSCore3.RecordLayout.cons "extra" VSCore3.RecordLayout.nil))) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws (VSCore3.listRawLaws VSCore3.stringRawLaws) (VSCore3.productRawLaws (VSCore3.optionRawLaws VSCore3.intRawLaws) VSCore3.unitRawLaws))))) args env hd
    rcases env with ⟨v__0, env⟩
    cases env
    refine ⟨adapter_4.inv v__0, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_4.to_from] using he.symm

def sourceFacts_solve : VeriSlop.Source.ModuleFacts :=
  let m := VSCore3.exactSourceFacts profile rawProgram "solve"
  { entries := m.entries.map (fun e => ⟨e.file, e.id, e.arity⟩),
    uniqueEntries := m.uniqueEntries, typedTotal := m.typedTotal, deterministic := m.deterministic,
    inputPreserved := m.inputPreserved, noExternalIO := m.noExternalIO,
    noFloatingPoint := m.noFloatingPoint, pureData := m.pureData,
    restrictedRuntimeOnly := m.restrictedRuntimeOnly }
def SourceAdequate_solve : Prop :=
  VSCore3.SourceFactsAdequate profile rawProgram "solve" checkedProgram entry_solve
theorem source_adequate_solve : SourceAdequate_solve := by
  with_unfolding_all
    exact VSCore3.exactSourceFacts_adequate compiled_ok find_solve
      (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "amount" (VSCore3.RecordLayout.cons "words" (VSCore3.RecordLayout.cons "extra" VSCore3.RecordLayout.nil))) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws (VSCore3.listRawLaws VSCore3.stringRawLaws) (VSCore3.productRawLaws (VSCore3.optionRawLaws VSCore3.intRawLaws) VSCore3.unitRawLaws)))))
      adapter_0_raw

/-- Accepted obligation O1, theorem VeriSlopAST.result, hash sha256:b50d811dd69050e5c1d09100cfccb441313339c35aca5f121a559d338d82d03f. -/
def Transfer_O1 : Prop := (@And (∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@VeriSlopAST.Packet.amount x__0) (@Int.negSucc (nat_lit 2))))) (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Packet), @Int) @VeriSlopAST.Delivery) @VeriSlopBridgeGoal.sourceFacts_solve))
theorem transfer_O1 (h_solve : Refines_solve) : Transfer_O1 := by
  have haccepted := @VeriSlopAST.result
  have eq_solve : source_fn_solve = @VeriSlopAST.solve := by
    apply funext; intro x__0
    exact h_solve x__0
  have htransfer : ((∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@VeriSlopAST.Packet.amount x__0) (@Int.negSucc (nat_lit 2)))))) = ((∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @Int (@VeriSlopAST.solve x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@VeriSlopAST.Packet.amount x__0) (@Int.negSucc (nat_lit 2)))))) := by
    rw [eq_solve]
  have hvalue : ((∀ (x__0 : @VeriSlopAST.Packet), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@VeriSlopAST.Packet.amount x__0) (@Int.negSucc (nat_lit 2)))))) := htransfer.symm ▸ (haccepted.1)
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Packet), @Int) @VeriSlopAST.Delivery) @VeriSlopBridgeGoal.sourceFacts_solve)) := by
    apply (haccepted.2).1 sourceFacts_solve
    with_unfolding_all rfl
  exact ⟨hvalue, hsource_0⟩

/-- Accepted obligation O2, theorem VeriSlopAST.binder, hash sha256:a0f4938f37b9e83aa7b7ccccae862270993e6aee8610d0a6ead7b8818db8b655. -/
def Transfer_O2 : Prop := (@And (∀ (x__0 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@List.map.{0, 0} @Int @Int (fun (x__1 : @Int) => (@VeriSlopBridgeGoal.source_fn_shift x__1)) x__0) (@List.map.{0, 0} @Int @Int (fun (x__1 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__1 (@Int.negSucc (nat_lit 2)))) x__0))) (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @Int), @Int) @VeriSlopAST.ShiftDelivery) @VeriSlopBridgeGoal.sourceFacts_shift))
theorem transfer_O2 (h_shift : Refines_shift) : Transfer_O2 := by
  have haccepted := @VeriSlopAST.binder
  have eq_shift : source_fn_shift = @VeriSlopAST.shift := by
    apply funext; intro x__0
    exact h_shift x__0
  have htransfer : ((∀ (x__0 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@List.map.{0, 0} @Int @Int (fun (x__1 : @Int) => (@VeriSlopBridgeGoal.source_fn_shift x__1)) x__0) (@List.map.{0, 0} @Int @Int (fun (x__1 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__1 (@Int.negSucc (nat_lit 2)))) x__0)))) = ((∀ (x__0 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@List.map.{0, 0} @Int @Int (fun (x__1 : @Int) => (@VeriSlopAST.shift x__1)) x__0) (@List.map.{0, 0} @Int @Int (fun (x__1 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__1 (@Int.negSucc (nat_lit 2)))) x__0)))) := by
    rw [eq_shift]
  have hvalue : ((∀ (x__0 : (@List.{0} @Int)), (@Eq.{1} (@List.{0} @Int) (@List.map.{0, 0} @Int @Int (fun (x__1 : @Int) => (@VeriSlopBridgeGoal.source_fn_shift x__1)) x__0) (@List.map.{0, 0} @Int @Int (fun (x__1 : @Int) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__1 (@Int.negSucc (nat_lit 2)))) x__0)))) := htransfer.symm ▸ (haccepted.1)
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @Int), @Int) @VeriSlopAST.ShiftDelivery) @VeriSlopBridgeGoal.sourceFacts_shift)) := by
    apply (haccepted.2).1 sourceFacts_shift
    with_unfolding_all rfl
  exact ⟨hvalue, hsource_0⟩

/-- Accepted obligation S1, theorem VeriSlopAST.source_only, hash sha256:81c2821dbd7570dd2c1b032de633f3e24c8af8273dae77c19fc016e9d90f5b94. -/
def Transfer_S1 : Prop := (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Packet), @Int) @VeriSlopAST.Delivery) @VeriSlopBridgeGoal.sourceFacts_solve)
theorem transfer_S1  : Transfer_S1 := by
  have haccepted := @VeriSlopAST.source_only
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Packet), @Int) @VeriSlopAST.Delivery) @VeriSlopBridgeGoal.sourceFacts_solve)) := by
    apply (haccepted).1 sourceFacts_solve
    with_unfolding_all rfl
  exact hsource_0

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_shift (@And @VeriSlopBridgeGoal.RawEval_shift (@And @VeriSlopBridgeGoal.Refines_shift (@And @VeriSlopBridgeGoal.SourceAdequate_shift (@And @VeriSlopBridgeGoal.InputsCover_solve (@And @VeriSlopBridgeGoal.RawEval_solve (@And @VeriSlopBridgeGoal.Refines_solve (@And @VeriSlopBridgeGoal.SourceAdequate_solve (@And @VeriSlopBridgeGoal.Transfer_O1 (@And @VeriSlopBridgeGoal.Transfer_O2 @VeriSlopBridgeGoal.Transfer_S1))))))))))))
theorem edge_of_refines (h_shift : Refines_shift) (h_solve : Refines_solve) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_shift, raw_eval_shift, h_shift, source_adequate_shift, inputs_cover_solve, raw_eval_solve, h_solve, source_adequate_solve, transfer_O1 h_solve, transfer_O2 h_shift, transfer_S1 ⟩

end VeriSlopBridgeGoal
