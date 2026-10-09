import VSCore
import VeriSlopContract

/-!
# VeriSlop bridge goal (verifier-generated; candidates cannot change it)

Template `vscore.reference_refinement/0.1`, language `vscore/0.1`, semantics `vscore-semantics/0.1`.
Source: sha256:d877f4e986cbb576527acc2467d11f69517c68d01196111537af608b9f378313 (503 bytes).

A candidate proof module `VeriSlopBridgeProof` must import only this module (and
toolchain modules) and prove `theorem edge : VeriSlopBridgeGoal.EdgeProp`, normally as
`VeriSlopBridgeGoal.edge_of_refines` applied to proofs of every `Refines_<symbol>`.
-/

namespace VeriSlopBridgeGoal

/-- Exact bytes of the frozen source artifact sha256:d877f4e986cbb576527acc2467d11f69517c68d01196111537af608b9f378313. -/
def sourceBytes : List Nat := [123, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 99, 111, 110, 100, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 116, 34, 125, 44, 34, 101, 108, 115, 101, 34, 58, 123, 34, 111, 107, 95, 116, 121, 112, 101, 34, 58, 34, 110, 97, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 101, 114, 114, 111, 114, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 99, 116, 111, 114, 34, 58, 34, 108, 105, 109, 105, 116, 82, 101, 97, 99, 104, 101, 100, 34, 44, 34, 101, 110, 117, 109, 34, 58, 34, 73, 110, 99, 114, 101, 109, 101, 110, 116, 69, 114, 114, 111, 114, 34, 44, 34, 116, 97, 103, 34, 58, 34, 101, 110, 117, 109, 34, 125, 125, 44, 34, 116, 97, 103, 34, 58, 34, 105, 102, 34, 44, 34, 116, 104, 101, 110, 34, 58, 123, 34, 101, 114, 114, 111, 114, 95, 116, 121, 112, 101, 34, 58, 123, 34, 101, 110, 117, 109, 34, 58, 34, 73, 110, 99, 114, 101, 109, 101, 110, 116, 69, 114, 114, 111, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 111, 107, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 110, 97, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 49, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 125, 125, 44, 34, 105, 100, 34, 58, 34, 105, 110, 99, 114, 101, 109, 101, 110, 116, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 110, 97, 116, 34, 44, 34, 110, 97, 116, 34, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 101, 114, 114, 111, 114, 34, 58, 123, 34, 101, 110, 117, 109, 34, 58, 34, 73, 110, 99, 114, 101, 109, 101, 110, 116, 69, 114, 114, 111, 114, 34, 125, 44, 34, 111, 107, 34, 58, 34, 110, 97, 116, 34, 125, 125, 125, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 49, 34, 125]

/-- Host-proposed decoding; its authority is only the kernel-checked `source_parses`. -/
def rawProgram : VSCore.Program :=
  { language := "vscore/0.1",
    entries := [
    { id := "increment",
      params := [VSCore.Ty.nat, VSCore.Ty.nat],
      result := (VSCore.Ty.result (VSCore.Ty.enum "IncrementError") VSCore.Ty.nat),
      body := (VSCore.Expr.ite (VSCore.Expr.bin VSCore.BinOp.lt (VSCore.Expr.var 0) (VSCore.Expr.var 1)) (VSCore.Expr.ok (VSCore.Ty.enum "IncrementError") (VSCore.Expr.bin VSCore.BinOp.add (VSCore.Expr.var 0) (VSCore.Expr.nat 1))) (VSCore.Expr.error VSCore.Ty.nat (VSCore.Expr.enum "IncrementError" "limitReached"))) }] }

/-- The accepted contract's enumeration registry (IDs and constructor order). -/
def profile : VSCore.Profile := { enums := [("IncrementError", ["limitReached"])] }

def signatures : List VSCore.EntrySig :=
  [{ id := "increment", params := [VSCore.Ty.nat, VSCore.Ty.nat], result := (VSCore.Ty.result (VSCore.Ty.enum "IncrementError") VSCore.Ty.nat) }]

theorem source_parses : VSCore.parseSource sourceBytes = .ok rawProgram :=
  VSCore.parseSource_of_check (by decide +kernel)

theorem source_checks : VSCore.checkProgram profile rawProgram = .ok signatures :=
  VSCore.checkProgram_of_check (by decide +kernel)

/-- Registered names of enumeration IncrementError (VeriSlop.BoundedIncrement.IncrementError). -/
def name_0 : @VeriSlop.BoundedIncrement.IncrementError → String
  | @VeriSlop.BoundedIncrement.IncrementError.limitReached => "limitReached"

/-- Representation adapter for sort "Nat". -/
def adapter_0 : VSCore.Adapter profile @Nat VSCore.Ty.nat :=
  VSCore.natAdapter profile

/-- Representation adapter for sort {"enum":"IncrementError"}. -/
def adapter_1 : VSCore.Adapter profile @VeriSlop.BoundedIncrement.IncrementError (VSCore.Ty.enum "IncrementError") :=
  VSCore.enumAdapter "IncrementError" name_0 [@VeriSlop.BoundedIncrement.IncrementError.limitReached]
    (by intro a; cases a <;> simp)
    (by intro a b h; cases a <;> cases b <;> simp_all [name_0])
    (by decide +kernel)

/-- Representation adapter for sort {"result":{"error":{"enum":"IncrementError"},"ok":"Nat"}}. -/
def adapter_2 : VSCore.Adapter profile (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat) (VSCore.Ty.result (VSCore.Ty.enum "IncrementError") VSCore.Ty.nat) :=
  VSCore.exceptAdapter adapter_1 adapter_0 (by decide +kernel) (by decide +kernel)

/-- Implementation relation of accepted symbol `increment` (VeriSlop.BoundedIncrement.increment) bound to entry "increment": the entry returns exactly the encoded result. -/
def impl_increment (x__0 : @Nat) (x__1 : @Nat) (r__2 : (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat)) : Prop :=
  (@Eq.{1} (@Except.{0, 0} @VSCore.EvalError @VSCore.Value) (@VSCore.evalEntry @VeriSlopBridgeGoal.rawProgram "increment" (@List.cons.{0} @VSCore.Value (@VSCore.Adapter.enc @VeriSlopBridgeGoal.profile @Nat @VSCore.Ty.nat @VeriSlopBridgeGoal.adapter_0 x__0) (@List.cons.{0} @VSCore.Value (@VSCore.Adapter.enc @VeriSlopBridgeGoal.profile @Nat @VSCore.Ty.nat @VeriSlopBridgeGoal.adapter_0 x__1) (@List.nil.{0} @VSCore.Value)))) (@Except.ok.{0, 0} @VSCore.EvalError @VSCore.Value (@VSCore.Adapter.enc @VeriSlopBridgeGoal.profile (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat) (@VSCore.Ty.result (@VSCore.Ty.enum "IncrementError") @VSCore.Ty.nat) @VeriSlopBridgeGoal.adapter_2 r__2)))

/-- Refinement target: entry "increment" computes the accepted reference `VeriSlop.BoundedIncrement.increment` on every input. -/
def Refines_increment : Prop :=
  (∀ (x__0 : @Nat), (∀ (x__1 : @Nat), (@VeriSlopBridgeGoal.impl_increment x__0 x__1 (@VeriSlop.BoundedIncrement.increment x__0 x__1))))

/-- Every well-typed argument list of entry "increment" encodes contract inputs. -/
def InputsCover_increment : Prop :=
  (∀ (args__0 : (@List.{0} @VSCore.Value)), (∀ (h__1 : (@VSCore.ArgsTypedIn @VeriSlopBridgeGoal.profile args__0 (@List.cons.{0} @VSCore.Ty @VSCore.Ty.nat (@List.cons.{0} @VSCore.Ty @VSCore.Ty.nat (@List.nil.{0} @VSCore.Ty))))), (@Exists.{1} @Nat (fun (x__2 : @Nat) => (@Exists.{1} @Nat (fun (x__3 : @Nat) => (@Eq.{1} (@List.{0} @VSCore.Value) args__0 (@List.cons.{0} @VSCore.Value (@VSCore.Adapter.enc @VeriSlopBridgeGoal.profile @Nat @VSCore.Ty.nat @VeriSlopBridgeGoal.adapter_0 x__2) (@List.cons.{0} @VSCore.Value (@VSCore.Adapter.enc @VeriSlopBridgeGoal.profile @Nat @VSCore.Ty.nat @VeriSlopBridgeGoal.adapter_0 x__3) (@List.nil.{0} @VSCore.Value))))))))))

theorem inputs_cover_increment : InputsCover_increment := by
  intro args h
  cases h with | cons h__0 h =>
  cases h with | cons h__1 h =>
  cases h
  obtain ⟨x__0, hx__0⟩ := adapter_0.represents h__0
  obtain ⟨x__1, hx__1⟩ := adapter_0.represents h__1
  exact ⟨x__0, x__1, by rw [hx__0, hx__1]⟩

theorem Internal.impl_increment_iff (h : Refines_increment) (x__0 : @Nat) (x__1 : @Nat) (r : (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat)) :
    _root_.VeriSlopBridgeGoal.impl_increment x__0 x__1 r ↔ r = @VeriSlop.BoundedIncrement.increment x__0 x__1 := by
  have hx : _root_.VeriSlopBridgeGoal.impl_increment x__0 x__1 (@VeriSlop.BoundedIncrement.increment x__0 x__1) := h x__0 x__1
  constructor
  · intro hr
    unfold _root_.VeriSlopBridgeGoal.impl_increment at hr hx
    exact (VSCore.Adapter.enc_eq_iff adapter_2).mp (Except.ok.inj (hr.symm.trans hx))
  · intro hr
    cases hr
    exact hx

theorem Internal.forall_impl_increment (h : Refines_increment) (x__0 : @Nat) (x__1 : @Nat) (P : (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat) → Prop) :
    (∀ r, _root_.VeriSlopBridgeGoal.impl_increment x__0 x__1 r → P r) ↔ P (@VeriSlop.BoundedIncrement.increment x__0 x__1) := by
  constructor
  · intro hp
    exact hp (@VeriSlop.BoundedIncrement.increment x__0 x__1) (h x__0 x__1)
  · intro hp r hr
    have he := (_root_.VeriSlopBridgeGoal.Internal.impl_increment_iff h x__0 x__1 r).mp hr
    cases he
    exact hp

/-- Implementation reading of accepted obligation E1 (VeriSlop.BoundedIncrement.error_iff_at_limit, statement sha256:13ec4ce859108031a8b74820e1d2fdd7c21b2dda46ec43d1f3e46e6710f26bf2): ∀ x0 : Nat, ∀ x1 : Nat, (x1 ≤ x0 → (increment(x0, x1) = error(IncrementError.limitReached) ↔ x1 = x0)) -/
def Transfer_E1 : Prop :=
  (∀ (x__0 : @Nat), (∀ (x__1 : @Nat), (∀ (h__2 : (@LE.le.{0} @Nat @instLENat x__1 x__0)), (@Iff (∀ (r__3 : (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat)), (∀ (h__4 : (@VeriSlopBridgeGoal.impl_increment x__0 x__1 r__3)), (@Eq.{1} (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat) r__3 (@Except.error.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat @VeriSlop.BoundedIncrement.IncrementError.limitReached)))) (@Eq.{1} @Nat x__1 x__0)))))

theorem transfer_E1 (h_increment : Refines_increment) : Transfer_E1 := by
  have htransfer : Transfer_E1 ↔ (∀ (x__0 : @Nat), (∀ (x__1 : @Nat), (∀ (h__2 : (@LE.le.{0} @Nat @instLENat x__1 x__0)), (@Iff (@Eq.{1} (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat) (@VeriSlop.BoundedIncrement.increment x__0 x__1) (@Except.error.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat @VeriSlop.BoundedIncrement.IncrementError.limitReached)) (@Eq.{1} @Nat x__1 x__0))))) := by
    unfold Transfer_E1
    simp only [Internal.forall_impl_increment h_increment]
  exact htransfer.mpr @VeriSlop.BoundedIncrement.error_iff_at_limit

/-- Implementation reading of accepted obligation I2 (VeriSlop.BoundedIncrement.success_preserves_bound, statement sha256:9d7d94d5df7928eb453ae26c51afd40bd3aa56822700b4ae4951be3c323ace3f): ∀ x0 : Nat, ∀ x1 : Nat, ∀ x2 : Nat, (increment(x0, x1) = ok(x2) → x2 ≤ x0) -/
def Transfer_I2 : Prop :=
  (∀ (x__0 : @Nat), (∀ (x__1 : @Nat), (∀ (x__2 : @Nat), (∀ (h__3 : (∀ (r__3 : (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat)), (∀ (h__4 : (@VeriSlopBridgeGoal.impl_increment x__0 x__1 r__3)), (@Eq.{1} (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat) r__3 (@Except.ok.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat x__2))))), (@LE.le.{0} @Nat @instLENat x__2 x__0)))))

theorem transfer_I2 (h_increment : Refines_increment) : Transfer_I2 := by
  have htransfer : Transfer_I2 ↔ (∀ (x__0 : @Nat), (∀ (x__1 : @Nat), (∀ (x__2 : @Nat), (∀ (h__3 : (@Eq.{1} (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat) (@VeriSlop.BoundedIncrement.increment x__0 x__1) (@Except.ok.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat x__2))), (@LE.le.{0} @Nat @instLENat x__2 x__0))))) := by
    unfold Transfer_I2
    simp only [Internal.forall_impl_increment h_increment]
  exact htransfer.mpr @VeriSlop.BoundedIncrement.success_preserves_bound

/-- Implementation reading of accepted obligation O17 (VeriSlop.BoundedIncrement.success_is_successor, statement sha256:631369a2ae47959bac1f73fa6a1d7901e1952384699faf97ec83ee177bc79162): ∀ x0 : Nat, ∀ x1 : Nat, ∀ x2 : Nat, (increment(x0, x1) = ok(x2) → x2 = (x1 + 1)) -/
def Transfer_O17 : Prop :=
  (∀ (x__0 : @Nat), (∀ (x__1 : @Nat), (∀ (x__2 : @Nat), (∀ (h__3 : (∀ (r__3 : (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat)), (∀ (h__4 : (@VeriSlopBridgeGoal.impl_increment x__0 x__1 r__3)), (@Eq.{1} (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat) r__3 (@Except.ok.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat x__2))))), (@Eq.{1} @Nat x__2 (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) x__1 (@OfNat.ofNat.{0} @Nat (nat_lit 1) (@instOfNatNat (nat_lit 1)))))))))

theorem transfer_O17 (h_increment : Refines_increment) : Transfer_O17 := by
  have htransfer : Transfer_O17 ↔ (∀ (x__0 : @Nat), (∀ (x__1 : @Nat), (∀ (x__2 : @Nat), (∀ (h__3 : (@Eq.{1} (@Except.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat) (@VeriSlop.BoundedIncrement.increment x__0 x__1) (@Except.ok.{0, 0} @VeriSlop.BoundedIncrement.IncrementError @Nat x__2))), (@Eq.{1} @Nat x__2 (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) x__1 (@OfNat.ofNat.{0} @Nat (nat_lit 1) (@instOfNatNat (nat_lit 1))))))))) := by
    unfold Transfer_O17
    simp only [Internal.forall_impl_increment h_increment]
  exact htransfer.mpr @VeriSlop.BoundedIncrement.success_is_successor

/-- The edge proposition: exact parse and typing, input coverage, refinement and transfer of every covered accepted obligation. -/
def EdgeProp : Prop :=
  (@And (@Eq.{1} (@Except.{0, 0} @String @VSCore.Program) (@VSCore.parseSource @VeriSlopBridgeGoal.sourceBytes) (@Except.ok.{0, 0} @String @VSCore.Program @VeriSlopBridgeGoal.rawProgram)) (@And (@Eq.{1} (@Except.{0, 0} @String (@List.{0} @VSCore.EntrySig)) (@VSCore.checkProgram @VeriSlopBridgeGoal.profile @VeriSlopBridgeGoal.rawProgram) (@Except.ok.{0, 0} @String (@List.{0} @VSCore.EntrySig) @VeriSlopBridgeGoal.signatures)) (@And @VeriSlopBridgeGoal.InputsCover_increment (@And @VeriSlopBridgeGoal.Refines_increment (@And @VeriSlopBridgeGoal.Transfer_E1 (@And @VeriSlopBridgeGoal.Transfer_I2 @VeriSlopBridgeGoal.Transfer_O17))))))

theorem edge_of_refines (h_increment : Refines_increment) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_increment, h_increment, (transfer_E1 h_increment), (transfer_I2 h_increment), (transfer_O17 h_increment)⟩

end VeriSlopBridgeGoal
