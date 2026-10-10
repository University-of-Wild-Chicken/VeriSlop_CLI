import VSCore3
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:f46b8de25a7339198ce3e7d8feeba48ac4213e823eb57ddc00eca66e796ad15b. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 105, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 53, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 98, 117, 109, 112, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [], helpers := [], entries := [{ id := "bump", params := [VSCore3.Ty.int], result := VSCore3.Ty.int, body := (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.var 0) (VSCore3.Expr.int (Int.ofNat 5))) }] }
def profile : VSCore3.Profile := { enums := [] }
def signatures : List VSCore3.EntrySig := [{ id := "bump", params := [VSCore3.Ty.int], result := VSCore3.Ty.int }]
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

abbrev entry_bump : VSCore3.CompiledFunction :=
  { id := "bump", params := [.int], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "bump").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_bump : VSCore3.findEntry checkedProgram "bump" = some entry_bump := by with_unfolding_all rfl
def source_fn_bump (x__0 : @Int) : @Int := by
  with_unfolding_all exact adapter_0.inv (entry_bump.run (adapter_0.to x__0, ()))
def Refines_bump : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@NameFixture.bump x__0)))
def RawEval_bump : Prop := ∀ (x__0 : @Int),
  VSCore3.evalEntry profile rawProgram "bump" [adapter_0.encode x__0] =
    .ok (adapter_0.encode (source_fn_bump x__0))
theorem raw_eval_bump : RawEval_bump := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_bump.params [adapter_0.encode x__0] = some (adapter_0.to x__0, ()) := by
      change VSCore3.decodeEnv [.int] [adapter_0.encode x__0] = some (adapter_0.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "bump" [adapter_0.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_bump, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_bump, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_bump.run (adapter_0.to x__0, ()))) =
      Except.ok (VSCore3.encode .int (adapter_0.to (adapter_0.inv (entry_bump.run (adapter_0.to x__0, ())))))
    rw [adapter_0.to_from]
def InputsCover_bump : Prop := ∀ args, VSCore3.ArgsTyped entry_bump args → ∃ (x__0 : @Int), args = [adapter_0.encode x__0]
theorem inputs_cover_bump : InputsCover_bump := by
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

/-- Accepted obligation N-bump, theorem NameFixture.«bump-law», hash sha256:cf75d3d0dee5ad3050816a87d7dad39098707cc53600de5f5f1b049b2c200492. -/
def «Transfer_N-bump» : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))
theorem «transfer_N-bump» (h_bump : Refines_bump) : «Transfer_N-bump» := by
  have eq_bump : source_fn_bump = @NameFixture.bump := by
    apply funext; intro x__0
    exact h_bump x__0
  have htransfer : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) = ((∀ (x__0 : @Int), (@Eq.{1} @Int (@NameFixture.bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := by
    rw [eq_bump]
  have hvalue : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := htransfer.symm ▸ (@NameFixture.«bump-law»)
  exact hvalue

/-- Accepted obligation N.bump, theorem NameFixture.«bump.law», hash sha256:fc6f21086ada0f4a2acb232e85fd6186fae0680ba0dfa967800ef9cd2cd4b939. -/
def «Transfer_N.bump» : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))
theorem transfer_N.bump (h_bump : Refines_bump) : «Transfer_N.bump» := by
  have eq_bump : source_fn_bump = @NameFixture.bump := by
    apply funext; intro x__0
    exact h_bump x__0
  have htransfer : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) = ((∀ (x__0 : @Int), (@Eq.{1} @Int (@NameFixture.bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := by
    rw [eq_bump]
  have hvalue : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := htransfer.symm ▸ (@NameFixture.«bump.law»)
  exact hvalue

/-- Accepted obligation N:7, theorem NameFixture.«7», hash sha256:0ea994bfcc60b96118e371312cb42c24f07140c670341f4e974b41686ae22c7f. -/
def «Transfer_N:7» : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))
theorem «transfer_N:7» (h_bump : Refines_bump) : «Transfer_N:7» := by
  have eq_bump : source_fn_bump = @NameFixture.bump := by
    apply funext; intro x__0
    exact h_bump x__0
  have htransfer : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) = ((∀ (x__0 : @Int), (@Eq.{1} @Int (@NameFixture.bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := by
    rw [eq_bump]
  have hvalue : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := htransfer.symm ▸ (@NameFixture.«7»)
  exact hvalue

/-- Accepted obligation N:bump, theorem NameFixture.«bump:law», hash sha256:7225027acce5dd034fc954069b7707e9f2f9e85c8862d923eee27ec09de261a2. -/
def «Transfer_N:bump» : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))
theorem «transfer_N:bump» (h_bump : Refines_bump) : «Transfer_N:bump» := by
  have eq_bump : source_fn_bump = @NameFixture.bump := by
    apply funext; intro x__0
    exact h_bump x__0
  have htransfer : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) = ((∀ (x__0 : @Int), (@Eq.{1} @Int (@NameFixture.bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := by
    rw [eq_bump]
  have hvalue : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := htransfer.symm ▸ (@NameFixture.«bump:law»)
  exact hvalue

/-- Accepted obligation N_bump, theorem NameFixture.«plain_law», hash sha256:cd452e76866a875a3a4bb9a0f9a5c95cff2cd9a2cb07af655e2137fb2191f68f. -/
def Transfer_N_bump : Prop := (∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))
theorem transfer_N_bump (h_bump : Refines_bump) : Transfer_N_bump := by
  have eq_bump : source_fn_bump = @NameFixture.bump := by
    apply funext; intro x__0
    exact h_bump x__0
  have htransfer : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) = ((∀ (x__0 : @Int), (@Eq.{1} @Int (@NameFixture.bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := by
    rw [eq_bump]
  have hvalue : ((∀ (x__0 : @Int), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_bump x__0) (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) x__0 (@Int.ofNat (nat_lit 5)))))) := htransfer.symm ▸ (@NameFixture.plain_law)
  exact hvalue

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_bump (@And @VeriSlopBridgeGoal.RawEval_bump (@And @VeriSlopBridgeGoal.Refines_bump (@And @VeriSlopBridgeGoal.«Transfer_N-bump» (@And @VeriSlopBridgeGoal.«Transfer_N.bump» (@And @VeriSlopBridgeGoal.«Transfer_N:7» (@And @VeriSlopBridgeGoal.«Transfer_N:bump» @VeriSlopBridgeGoal.Transfer_N_bump)))))))))
theorem edge_of_refines (h_bump : Refines_bump) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_bump, raw_eval_bump, h_bump, «transfer_N-bump» h_bump, transfer_N.bump h_bump, «transfer_N:7» h_bump, «transfer_N:bump» h_bump, transfer_N_bump h_bump⟩

end VeriSlopBridgeGoal
