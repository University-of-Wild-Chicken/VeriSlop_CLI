import VSCore3
import VSCore3.SourceFacts
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:fc3e6141c0bead91c8e7a5561f9bc670abf833559d4ae0518fb32cb5bf437125. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 110, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 105, 100, 34, 58, 34, 109, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 105, 100, 34, 58, 34, 97, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 105, 100, 34, 58, 34, 98, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 105, 100, 34, 58, 34, 73, 110, 112, 117, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 115, 117, 109, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 110, 97, 116, 95, 116, 111, 95, 105, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 116, 97, 103, 34, 58, 34, 109, 117, 108, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 98, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 109, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 116, 97, 103, 34, 58, 34, 105, 110, 116, 95, 102, 100, 105, 118, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 109, 97, 112, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 114, 97, 110, 103, 101, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 105, 110, 116, 95, 116, 111, 95, 110, 97, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 110, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 125, 125, 125, 44, 34, 105, 100, 34, 58, 34, 115, 111, 108, 118, 101, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 73, 110, 112, 117, 116, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [(VSCore3.DataDecl.record "Input" [("n", VSCore3.Ty.int), ("m", VSCore3.Ty.int), ("a", VSCore3.Ty.int), ("b", VSCore3.Ty.int)])], helpers := [], entries := [{ id := "solve", params := [(VSCore3.Ty.record "Input")], result := VSCore3.Ty.int, body := (VSCore3.Expr.listSum (VSCore3.Expr.listMap (VSCore3.Expr.listRange (VSCore3.Expr.intToNat (VSCore3.Expr.project (VSCore3.Expr.var 0) "n"))) (VSCore3.Expr.intFdiv (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.bin VSCore.BinOp.mul (VSCore3.Expr.project (VSCore3.Expr.var 1) "a") (VSCore3.Expr.natToInt (VSCore3.Expr.var 0))) (VSCore3.Expr.project (VSCore3.Expr.var 1) "b")) (VSCore3.Expr.project (VSCore3.Expr.var 1) "m")))) }] }
def profile : VSCore3.Profile := { enums := [] }
def signatures : List VSCore3.EntrySig := [{ id := "solve", params := [(VSCore3.Ty.record "Input")], result := VSCore3.Ty.int }]
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

/-- Exact accepted carrier {"record":"Input"}. -/
def adapter_1 : VSCore3.Adapter (.record "Input" ["n", "m", "a", "b"] (.product .int (.product .int (.product .int (.product .int .unit))))) @VeriSlopAST.Input :=
  { to := fun x => (adapter_0.to (@VeriSlopAST.Input.n x), (adapter_0.to (@VeriSlopAST.Input.m x), (adapter_0.to (@VeriSlopAST.Input.a x), (adapter_0.to (@VeriSlopAST.Input.b x), ()))))
    inv := fun x => @VeriSlopAST.Input.mk (adapter_0.inv (x.1)) (adapter_0.inv (x.2.1)) (adapter_0.inv (x.2.2.1)) (adapter_0.inv (x.2.2.2.1))
    from_to := by intro x; cases x; simp [adapter_0.from_to, adapter_0.from_to, adapter_0.from_to, adapter_0.from_to]
    to_from := by intro x; rcases x with ⟨x0, x⟩; rcases x with ⟨x1, x⟩; rcases x with ⟨x2, x⟩; rcases x with ⟨x3, x⟩; cases x; simp [adapter_0.to_from, adapter_0.to_from, adapter_0.to_from, adapter_0.to_from] }
def adapter_1_raw : VSCore3.RawLaws (.record "Input" ["n", "m", "a", "b"] (.product .int (.product .int (.product .int (.product .int .unit))))) := (VSCore3.recordRawLaws "Input" (VSCore3.RecordLayout.cons "n" (VSCore3.RecordLayout.cons "m" (VSCore3.RecordLayout.cons "a" (VSCore3.RecordLayout.cons "b" VSCore3.RecordLayout.nil)))) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.intRawLaws VSCore3.unitRawLaws)))))
theorem adapter_1_decode_encode (x : @VeriSlopAST.Input) :
    VSCore3.decode (.record "Input" ["n", "m", "a", "b"] (.product .int (.product .int (.product .int (.product .int .unit))))) (adapter_1.encode x) = some (adapter_1.to x) :=
  adapter_1.decode_encode adapter_1_raw x

abbrev entry_solve : VSCore3.CompiledFunction :=
  { id := "solve", params := [(.record "Input" ["n", "m", "a", "b"] (.product .int (.product .int (.product .int (.product .int .unit)))))], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "solve").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_solve : VSCore3.findEntry checkedProgram "solve" = some entry_solve := by with_unfolding_all rfl
def source_fn_solve (x__0 : @VeriSlopAST.Input) : @Int := by
  with_unfolding_all exact adapter_0.inv (entry_solve.run (adapter_1.to x__0, ()))
def Refines_solve : Prop := (∀ (x__0 : @VeriSlopAST.Input), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@VeriSlopAST.solve x__0)))
def RawEval_solve : Prop := ∀ (x__0 : @VeriSlopAST.Input),
  VSCore3.evalEntry profile rawProgram "solve" [adapter_1.encode x__0] =
    .ok (adapter_0.encode (source_fn_solve x__0))
theorem raw_eval_solve : RawEval_solve := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_solve.params [adapter_1.encode x__0] = some (adapter_1.to x__0, ()) := by
      change VSCore3.decodeEnv [(.record "Input" ["n", "m", "a", "b"] (.product .int (.product .int (.product .int (.product .int .unit)))))] [adapter_1.encode x__0] = some (adapter_1.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_1_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "solve" [adapter_1.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_solve, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_solve, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_solve.run (adapter_1.to x__0, ()))) =
      Except.ok (VSCore3.encode .int (adapter_0.to (adapter_0.inv (entry_solve.run (adapter_1.to x__0, ())))))
    rw [adapter_0.to_from]
def InputsCover_solve : Prop := ∀ args, VSCore3.ArgsTyped entry_solve args → ∃ (x__0 : @VeriSlopAST.Input), args = [adapter_1.encode x__0]
theorem inputs_cover_solve : InputsCover_solve := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.record "Input" ["n", "m", "a", "b"] (.product .int (.product .int (.product .int (.product .int .unit)))))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.record "Input" ["n", "m", "a", "b"] (.product .int (.product .int (.product .int (.product .int .unit)))))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.recordRawLaws "Input" (VSCore3.RecordLayout.cons "n" (VSCore3.RecordLayout.cons "m" (VSCore3.RecordLayout.cons "a" (VSCore3.RecordLayout.cons "b" VSCore3.RecordLayout.nil)))) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.intRawLaws VSCore3.unitRawLaws)))))) args env hd
    rcases env with ⟨v__0, env⟩
    cases env
    refine ⟨adapter_1.inv v__0, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_1.to_from] using he.symm

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
    · exact (VSCore3.recordRawLaws "Input" (VSCore3.RecordLayout.cons "n" (VSCore3.RecordLayout.cons "m" (VSCore3.RecordLayout.cons "a" (VSCore3.RecordLayout.cons "b" VSCore3.RecordLayout.nil)))) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.intRawLaws VSCore3.unitRawLaws))))))
      adapter_0_raw

/-- Accepted obligation O1, theorem VeriSlopAST.solve_contract, hash sha256:d7c12941d49c5ec7597445cc043f5e5707b9dac8dd6e4bc97de18b4a56e9aecd. -/
def Transfer_O1 : Prop := (@And (∀ (x__0 : @VeriSlopAST.Input), (∀ (h__1 : (@And (@And (@LE.le.{0} @Int @Int.instLEInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.n x__0)) (@LE.le.{0} @Int @Int.instLEInt (@VeriSlopAST.Input.n x__0) (@Int.ofNat (nat_lit 500)))) (@LT.lt.{0} @Int @Int.instLTInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.m x__0)))), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Nat @Int (fun (x__2 : @Nat) => (@Int.fdiv (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@HMul.hMul.{0, 0, 0} @Int @Int @Int (@instHMul.{0} @Int @Int.instMul) (@VeriSlopAST.Input.a x__0) (@Int.ofNat x__2)) (@VeriSlopAST.Input.b x__0)) (@VeriSlopAST.Input.m x__0))) (@List.range (@Int.toNat (@VeriSlopAST.Input.n x__0)))))))) (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Input), @Int) @VeriSlopAST.solve_source) @VeriSlopBridgeGoal.sourceFacts_solve))
theorem transfer_O1 (h_solve : Refines_solve) : Transfer_O1 := by
  have haccepted := @VeriSlopAST.solve_contract
  have eq_solve : source_fn_solve = @VeriSlopAST.solve := by
    apply funext; intro x__0
    exact h_solve x__0
  have htransfer : ((∀ (x__0 : @VeriSlopAST.Input), (∀ (h__1 : (@And (@And (@LE.le.{0} @Int @Int.instLEInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.n x__0)) (@LE.le.{0} @Int @Int.instLEInt (@VeriSlopAST.Input.n x__0) (@Int.ofNat (nat_lit 500)))) (@LT.lt.{0} @Int @Int.instLTInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.m x__0)))), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Nat @Int (fun (x__2 : @Nat) => (@Int.fdiv (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@HMul.hMul.{0, 0, 0} @Int @Int @Int (@instHMul.{0} @Int @Int.instMul) (@VeriSlopAST.Input.a x__0) (@Int.ofNat x__2)) (@VeriSlopAST.Input.b x__0)) (@VeriSlopAST.Input.m x__0))) (@List.range (@Int.toNat (@VeriSlopAST.Input.n x__0))))))))) = ((∀ (x__0 : @VeriSlopAST.Input), (∀ (h__1 : (@And (@And (@LE.le.{0} @Int @Int.instLEInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.n x__0)) (@LE.le.{0} @Int @Int.instLEInt (@VeriSlopAST.Input.n x__0) (@Int.ofNat (nat_lit 500)))) (@LT.lt.{0} @Int @Int.instLTInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.m x__0)))), (@Eq.{1} @Int (@VeriSlopAST.solve x__0) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Nat @Int (fun (x__2 : @Nat) => (@Int.fdiv (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@HMul.hMul.{0, 0, 0} @Int @Int @Int (@instHMul.{0} @Int @Int.instMul) (@VeriSlopAST.Input.a x__0) (@Int.ofNat x__2)) (@VeriSlopAST.Input.b x__0)) (@VeriSlopAST.Input.m x__0))) (@List.range (@Int.toNat (@VeriSlopAST.Input.n x__0))))))))) := by
    rw [eq_solve]
  have hvalue : ((∀ (x__0 : @VeriSlopAST.Input), (∀ (h__1 : (@And (@And (@LE.le.{0} @Int @Int.instLEInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.n x__0)) (@LE.le.{0} @Int @Int.instLEInt (@VeriSlopAST.Input.n x__0) (@Int.ofNat (nat_lit 500)))) (@LT.lt.{0} @Int @Int.instLTInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.m x__0)))), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Nat @Int (fun (x__2 : @Nat) => (@Int.fdiv (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@HMul.hMul.{0, 0, 0} @Int @Int @Int (@instHMul.{0} @Int @Int.instMul) (@VeriSlopAST.Input.a x__0) (@Int.ofNat x__2)) (@VeriSlopAST.Input.b x__0)) (@VeriSlopAST.Input.m x__0))) (@List.range (@Int.toNat (@VeriSlopAST.Input.n x__0))))))))) := htransfer.symm ▸ (haccepted.1)
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Input), @Int) @VeriSlopAST.solve_source) @VeriSlopBridgeGoal.sourceFacts_solve)) := by
    apply (haccepted.2).1 sourceFacts_solve
    with_unfolding_all rfl
  exact ⟨hvalue, hsource_0⟩

/-- Accepted obligation O2, theorem VeriSlopAST.solve_contract, hash sha256:d7c12941d49c5ec7597445cc043f5e5707b9dac8dd6e4bc97de18b4a56e9aecd. -/
def Transfer_O2 : Prop := (@And (∀ (x__0 : @VeriSlopAST.Input), (∀ (h__1 : (@And (@And (@LE.le.{0} @Int @Int.instLEInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.n x__0)) (@LE.le.{0} @Int @Int.instLEInt (@VeriSlopAST.Input.n x__0) (@Int.ofNat (nat_lit 500)))) (@LT.lt.{0} @Int @Int.instLTInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.m x__0)))), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Nat @Int (fun (x__2 : @Nat) => (@Int.fdiv (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@HMul.hMul.{0, 0, 0} @Int @Int @Int (@instHMul.{0} @Int @Int.instMul) (@VeriSlopAST.Input.a x__0) (@Int.ofNat x__2)) (@VeriSlopAST.Input.b x__0)) (@VeriSlopAST.Input.m x__0))) (@List.range (@Int.toNat (@VeriSlopAST.Input.n x__0)))))))) (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Input), @Int) @VeriSlopAST.solve_source) @VeriSlopBridgeGoal.sourceFacts_solve))
theorem transfer_O2 (h_solve : Refines_solve) : Transfer_O2 := by
  have haccepted := @VeriSlopAST.solve_contract
  have eq_solve : source_fn_solve = @VeriSlopAST.solve := by
    apply funext; intro x__0
    exact h_solve x__0
  have htransfer : ((∀ (x__0 : @VeriSlopAST.Input), (∀ (h__1 : (@And (@And (@LE.le.{0} @Int @Int.instLEInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.n x__0)) (@LE.le.{0} @Int @Int.instLEInt (@VeriSlopAST.Input.n x__0) (@Int.ofNat (nat_lit 500)))) (@LT.lt.{0} @Int @Int.instLTInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.m x__0)))), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Nat @Int (fun (x__2 : @Nat) => (@Int.fdiv (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@HMul.hMul.{0, 0, 0} @Int @Int @Int (@instHMul.{0} @Int @Int.instMul) (@VeriSlopAST.Input.a x__0) (@Int.ofNat x__2)) (@VeriSlopAST.Input.b x__0)) (@VeriSlopAST.Input.m x__0))) (@List.range (@Int.toNat (@VeriSlopAST.Input.n x__0))))))))) = ((∀ (x__0 : @VeriSlopAST.Input), (∀ (h__1 : (@And (@And (@LE.le.{0} @Int @Int.instLEInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.n x__0)) (@LE.le.{0} @Int @Int.instLEInt (@VeriSlopAST.Input.n x__0) (@Int.ofNat (nat_lit 500)))) (@LT.lt.{0} @Int @Int.instLTInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.m x__0)))), (@Eq.{1} @Int (@VeriSlopAST.solve x__0) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Nat @Int (fun (x__2 : @Nat) => (@Int.fdiv (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@HMul.hMul.{0, 0, 0} @Int @Int @Int (@instHMul.{0} @Int @Int.instMul) (@VeriSlopAST.Input.a x__0) (@Int.ofNat x__2)) (@VeriSlopAST.Input.b x__0)) (@VeriSlopAST.Input.m x__0))) (@List.range (@Int.toNat (@VeriSlopAST.Input.n x__0))))))))) := by
    rw [eq_solve]
  have hvalue : ((∀ (x__0 : @VeriSlopAST.Input), (∀ (h__1 : (@And (@And (@LE.le.{0} @Int @Int.instLEInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.n x__0)) (@LE.le.{0} @Int @Int.instLEInt (@VeriSlopAST.Input.n x__0) (@Int.ofNat (nat_lit 500)))) (@LT.lt.{0} @Int @Int.instLTInt (@Int.ofNat (nat_lit 0)) (@VeriSlopAST.Input.m x__0)))), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_solve x__0) (@List.sum.{0} @Int @Int.instAdd (@Zero.ofOfNat0.{0} @Int (@instOfNat (nat_lit 0))) (@List.map.{0, 0} @Nat @Int (fun (x__2 : @Nat) => (@Int.fdiv (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@HMul.hMul.{0, 0, 0} @Int @Int @Int (@instHMul.{0} @Int @Int.instMul) (@VeriSlopAST.Input.a x__0) (@Int.ofNat x__2)) (@VeriSlopAST.Input.b x__0)) (@VeriSlopAST.Input.m x__0))) (@List.range (@Int.toNat (@VeriSlopAST.Input.n x__0))))))))) := htransfer.symm ▸ (haccepted.1)
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Input), @Int) @VeriSlopAST.solve_source) @VeriSlopBridgeGoal.sourceFacts_solve)) := by
    apply (haccepted.2).1 sourceFacts_solve
    with_unfolding_all rfl
  exact ⟨hvalue, hsource_0⟩

/-- Accepted obligation S1, theorem VeriSlopAST.solve_operational, hash sha256:805b0eb6145bc700a584a1c9ef55cde22f647021dd03a6636555ff876caf8015. -/
def Transfer_S1 : Prop := (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Input), @Int) @VeriSlopAST.solve_source) @VeriSlopBridgeGoal.sourceFacts_solve)
theorem transfer_S1  : Transfer_S1 := by
  have haccepted := @VeriSlopAST.solve_operational
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Input), @Int) @VeriSlopAST.solve_source) @VeriSlopBridgeGoal.sourceFacts_solve)) := by
    apply (haccepted).1 sourceFacts_solve
    with_unfolding_all rfl
  exact hsource_0

/-- Accepted obligation S2, theorem VeriSlopAST.solve_operational, hash sha256:805b0eb6145bc700a584a1c9ef55cde22f647021dd03a6636555ff876caf8015. -/
def Transfer_S2 : Prop := (@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Input), @Int) @VeriSlopAST.solve_source) @VeriSlopBridgeGoal.sourceFacts_solve)
theorem transfer_S2  : Transfer_S2 := by
  have haccepted := @VeriSlopAST.solve_operational
  have hsource_0 : ((@VeriSlop.Source.HoldsBoundary (@VeriSlop.Source.SourceDefinition.requirements (∀ (x__0 : @VeriSlopAST.Input), @Int) @VeriSlopAST.solve_source) @VeriSlopBridgeGoal.sourceFacts_solve)) := by
    apply (haccepted).1 sourceFacts_solve
    with_unfolding_all rfl
  exact hsource_0

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_solve (@And @VeriSlopBridgeGoal.RawEval_solve (@And @VeriSlopBridgeGoal.Refines_solve (@And @VeriSlopBridgeGoal.SourceAdequate_solve (@And @VeriSlopBridgeGoal.Transfer_O1 (@And @VeriSlopBridgeGoal.Transfer_O2 (@And @VeriSlopBridgeGoal.Transfer_S1 @VeriSlopBridgeGoal.Transfer_S2)))))))))
theorem edge_of_refines (h_solve : Refines_solve) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_solve, raw_eval_solve, h_solve, source_adequate_solve, transfer_O1 h_solve, transfer_O2 h_solve, transfer_S1 , transfer_S2 ⟩

end VeriSlopBridgeGoal
