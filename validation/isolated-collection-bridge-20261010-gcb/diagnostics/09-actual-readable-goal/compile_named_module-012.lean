import VSCore3
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:e1c7ace9ca60f875ef507dd0ece6e6627fae549f0a002c86fbe30ecc16f29c94. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 116, 111, 110, 101, 34, 44, 34, 116, 121, 112, 101, 34, 58, 123, 34, 101, 110, 117, 109, 34, 58, 34, 84, 111, 110, 101, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 110, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 110, 97, 116, 34, 125, 93, 44, 34, 105, 100, 34, 58, 34, 65, 116, 111, 109, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 44, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 97, 116, 111, 109, 34, 44, 34, 116, 121, 112, 101, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 65, 116, 111, 109, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 108, 105, 118, 101, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 98, 111, 111, 108, 34, 125, 93, 44, 34, 105, 100, 34, 58, 34, 66, 111, 120, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 97, 116, 111, 109, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 116, 111, 110, 101, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 116, 111, 110, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 116, 111, 109, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 110, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 110, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 116, 111, 109, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 110, 97, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 49, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 125, 93, 44, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 65, 116, 111, 109, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 108, 105, 118, 101, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 108, 105, 118, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 93, 44, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 66, 111, 120, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 109, 97, 112, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 105, 100, 34, 58, 34, 114, 97, 105, 115, 101, 66, 111, 120, 101, 115, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 66, 111, 120, 34, 125, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 66, 111, 120, 34, 125, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 116, 111, 109, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 101, 113, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 102, 105, 108, 116, 101, 114, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 105, 100, 34, 58, 34, 107, 101, 101, 112, 65, 116, 111, 109, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 66, 111, 120, 34, 125, 125, 44, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 65, 116, 111, 109, 34, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 66, 111, 120, 34, 125, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 105, 110, 105, 116, 105, 97, 108, 34, 58, 123, 34, 116, 97, 103, 34, 58, 34, 110, 97, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 34, 48, 34, 125, 44, 34, 115, 111, 117, 114, 99, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 115, 116, 101, 112, 34, 58, 123, 34, 99, 111, 110, 100, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 116, 111, 110, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 116, 111, 109, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 99, 116, 111, 114, 34, 58, 34, 99, 111, 108, 100, 34, 44, 34, 101, 110, 117, 109, 34, 58, 34, 84, 111, 110, 101, 34, 44, 34, 116, 97, 103, 34, 58, 34, 101, 110, 117, 109, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 101, 113, 34, 125, 44, 34, 101, 108, 115, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 105, 102, 34, 44, 34, 116, 104, 101, 110, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 110, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 116, 111, 109, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 102, 111, 108, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 99, 111, 108, 100, 84, 111, 116, 97, 108, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 66, 111, 120, 34, 125, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 110, 97, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [(VSCore3.DataDecl.record "Atom" [("tone", (VSCore3.Ty.enum "Tone")), ("n", VSCore3.Ty.nat)]), (VSCore3.DataDecl.record "Box" [("atom", (VSCore3.Ty.record "Atom")), ("live", VSCore3.Ty.bool)])], helpers := [], entries := [{ id := "raiseBoxes", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Box"))], result := (VSCore3.Ty.list (VSCore3.Ty.record "Box")), body := (VSCore3.Expr.listMap (VSCore3.Expr.var 0) (VSCore3.Expr.record "Box" [("atom", (VSCore3.Expr.record "Atom" [("tone", (VSCore3.Expr.project (VSCore3.Expr.project (VSCore3.Expr.var 0) "atom") "tone")), ("n", (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.project (VSCore3.Expr.project (VSCore3.Expr.var 0) "atom") "n") (VSCore3.Expr.nat 1)))])), ("live", (VSCore3.Expr.project (VSCore3.Expr.var 0) "live"))])) },
{ id := "keepAtom", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Box")), (VSCore3.Ty.record "Atom")], result := (VSCore3.Ty.list (VSCore3.Ty.record "Box")), body := (VSCore3.Expr.listFilter (VSCore3.Expr.var 1) (VSCore3.Expr.bin VSCore.BinOp.eq (VSCore3.Expr.project (VSCore3.Expr.var 0) "atom") (VSCore3.Expr.var 1))) },
{ id := "coldTotal", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Box"))], result := VSCore3.Ty.nat, body := (VSCore3.Expr.listFold (VSCore3.Expr.var 0) (VSCore3.Expr.nat 0) (VSCore3.Expr.ite (VSCore3.Expr.bin VSCore.BinOp.eq (VSCore3.Expr.project (VSCore3.Expr.project (VSCore3.Expr.var 0) "atom") "tone") (VSCore3.Expr.enum "Tone" "cold")) (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.var 1) (VSCore3.Expr.project (VSCore3.Expr.project (VSCore3.Expr.var 0) "atom") "n")) (VSCore3.Expr.var 1))) }] }
def profile : VSCore3.Profile := { enums := [("Tone", ["cold", "warm"])] }
def signatures : List VSCore3.EntrySig := [{ id := "raiseBoxes", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Box"))], result := (VSCore3.Ty.list (VSCore3.Ty.record "Box")) },
  { id := "keepAtom", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Box")), (VSCore3.Ty.record "Atom")], result := (VSCore3.Ty.list (VSCore3.Ty.record "Box")) },
  { id := "coldTotal", params := [(VSCore3.Ty.list (VSCore3.Ty.record "Box"))], result := VSCore3.Ty.nat }]
def SourceParses : Prop := VSCore3.parseSource sourceBytes = .ok rawProgram
theorem source_parses : SourceParses := by rfl
def SourceChecks : Prop := VSCore3.checkProgram profile rawProgram = .ok signatures
theorem source_checks : SourceChecks := VSCore3.checkProgram_of_check (by decide +kernel)
def checkedProgram : VSCore3.CheckedProgram := (VSCore3.compileProgram profile rawProgram).toOption.getD
  { declarations := [], helpers := [], entries := [], signatures := [] }
theorem compiled_ok : VSCore3.compileProgram profile rawProgram = .ok checkedProgram := by with_unfolding_all rfl

/-- Exact accepted carrier {"enum":"Tone"}. -/
def adapter_0 : VSCore3.Adapter (.enum "Tone" ["cold", "warm"]) @VeriSlopAST.Tone :=
  { to := fun x => match x with | VeriSlopAST.Tone.cold => ⟨"cold", by decide +kernel⟩ | VeriSlopAST.Tone.warm => ⟨"warm", by decide +kernel⟩
    inv := fun x => if x.val = "cold" then @VeriSlopAST.Tone.cold else @VeriSlopAST.Tone.warm
    from_to := by intro x; cases x <;> rfl
    to_from := by intro x; rcases x with ⟨x, h⟩; simp only [List.mem_cons, List.not_mem_nil, or_false] at h; rcases h with rfl | rfl; all_goals rfl }
def adapter_0_raw : VSCore3.RawLaws (.enum "Tone" ["cold", "warm"]) := (VSCore3.enumRawLaws "Tone" ["cold", "warm"])
theorem adapter_0_decode_encode (x : @VeriSlopAST.Tone) :
    VSCore3.decode (.enum "Tone" ["cold", "warm"]) (adapter_0.encode x) = some (adapter_0.to x) :=
  adapter_0.decode_encode adapter_0_raw x

/-- Exact accepted carrier "Nat". -/
def adapter_1 : VSCore3.Adapter .nat @Nat :=
  VSCore3.natAdapter
def adapter_1_raw : VSCore3.RawLaws .nat := VSCore3.natRawLaws
theorem adapter_1_decode_encode (x : @Nat) :
    VSCore3.decode .nat (adapter_1.encode x) = some (adapter_1.to x) :=
  adapter_1.decode_encode adapter_1_raw x

/-- Exact accepted carrier {"record":"Atom"}. -/
def adapter_2 : VSCore3.Adapter (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) @VeriSlopAST.Atom :=
  { to := fun x => (adapter_0.to (@VeriSlopAST.Atom.tone x), (adapter_1.to (@VeriSlopAST.Atom.n x), ()))
    inv := fun x => @VeriSlopAST.Atom.mk (adapter_0.inv (x.1)) (adapter_1.inv (x.2.1))
    from_to := by intro x; cases x; simp [adapter_0.from_to, adapter_1.from_to]
    to_from := by intro x; rcases x with ⟨x0, x⟩; rcases x with ⟨x1, x⟩; cases x; simp [adapter_0.to_from, adapter_1.to_from] }
def adapter_2_raw : VSCore3.RawLaws (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) := (VSCore3.recordRawLaws "Atom" (VSCore3.RecordLayout.cons "tone" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Tone" ["cold", "warm"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws)))
theorem adapter_2_decode_encode (x : @VeriSlopAST.Atom) :
    VSCore3.decode (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (adapter_2.encode x) = some (adapter_2.to x) :=
  adapter_2.decode_encode adapter_2_raw x

/-- Exact accepted carrier "Bool". -/
def adapter_3 : VSCore3.Adapter .bool @Bool :=
  VSCore3.boolAdapter
def adapter_3_raw : VSCore3.RawLaws .bool := VSCore3.boolRawLaws
theorem adapter_3_decode_encode (x : @Bool) :
    VSCore3.decode .bool (adapter_3.encode x) = some (adapter_3.to x) :=
  adapter_3.decode_encode adapter_3_raw x

/-- Exact accepted carrier {"record":"Box"}. -/
def adapter_4 : VSCore3.Adapter (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))) @VeriSlopAST.Box :=
  { to := fun x => (adapter_2.to (@VeriSlopAST.Box.atom x), (adapter_3.to (@VeriSlopAST.Box.live x), ()))
    inv := fun x => @VeriSlopAST.Box.mk (adapter_2.inv (x.1)) (adapter_3.inv (x.2.1))
    from_to := by intro x; cases x; simp [adapter_2.from_to, adapter_3.from_to]
    to_from := by intro x; rcases x with ⟨x0, x⟩; rcases x with ⟨x1, x⟩; cases x; simp [adapter_2.to_from, adapter_3.to_from] }
def adapter_4_raw : VSCore3.RawLaws (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))) := (VSCore3.recordRawLaws "Box" (VSCore3.RecordLayout.cons "atom" (VSCore3.RecordLayout.cons "live" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Atom" (VSCore3.RecordLayout.cons "tone" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Tone" ["cold", "warm"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws)))
theorem adapter_4_decode_encode (x : @VeriSlopAST.Box) :
    VSCore3.decode (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))) (adapter_4.encode x) = some (adapter_4.to x) :=
  adapter_4.decode_encode adapter_4_raw x

/-- Exact accepted carrier {"list":{"record":"Box"}}. -/
def adapter_5 : VSCore3.Adapter (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))) (@List.{0} @VeriSlopAST.Box) :=
  VSCore3.listAdapter adapter_4
def adapter_5_raw : VSCore3.RawLaws (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))) := (VSCore3.listRawLaws (VSCore3.recordRawLaws "Box" (VSCore3.RecordLayout.cons "atom" (VSCore3.RecordLayout.cons "live" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Atom" (VSCore3.RecordLayout.cons "tone" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Tone" ["cold", "warm"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))
theorem adapter_5_decode_encode (x : (@List.{0} @VeriSlopAST.Box)) :
    VSCore3.decode (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))) (adapter_5.encode x) = some (adapter_5.to x) :=
  adapter_5.decode_encode adapter_5_raw x

abbrev entry_coldTotal : VSCore3.CompiledFunction :=
  { id := "coldTotal", params := [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))], result := .nat,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "coldTotal").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_coldTotal : VSCore3.findEntry checkedProgram "coldTotal" = some entry_coldTotal := by with_unfolding_all rfl
def source_fn_coldTotal (x__0 : (@List.{0} @VeriSlopAST.Box)) : @Nat := by
  with_unfolding_all exact adapter_1.inv (entry_coldTotal.run (adapter_5.to x__0, ()))
def Refines_coldTotal : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} @Nat (@VeriSlopBridgeGoal.source_fn_coldTotal x__0) (@VeriSlopAST.coldTotal x__0)))
def RawEval_coldTotal : Prop := ∀ (x__0 : (@List.{0} @VeriSlopAST.Box)),
  VSCore3.evalEntry profile rawProgram "coldTotal" [adapter_5.encode x__0] =
    .ok (adapter_1.encode (source_fn_coldTotal x__0))
theorem raw_eval_coldTotal : RawEval_coldTotal := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_coldTotal.params [adapter_5.encode x__0] = some (adapter_5.to x__0, ()) := by
      change VSCore3.decodeEnv [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))] [adapter_5.encode x__0] = some (adapter_5.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_5_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "coldTotal" [adapter_5.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_coldTotal, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_coldTotal, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .nat (entry_coldTotal.run (adapter_5.to x__0, ()))) =
      Except.ok (VSCore3.encode .nat (adapter_1.to (adapter_1.inv (entry_coldTotal.run (adapter_5.to x__0, ())))))
    rw [adapter_1.to_from]
def InputsCover_coldTotal : Prop := ∀ args, VSCore3.ArgsTyped entry_coldTotal args → ∃ (x__0 : (@List.{0} @VeriSlopAST.Box)), args = [adapter_5.encode x__0]
theorem inputs_cover_coldTotal : InputsCover_coldTotal := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Box" (VSCore3.RecordLayout.cons "atom" (VSCore3.RecordLayout.cons "live" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Atom" (VSCore3.RecordLayout.cons "tone" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Tone" ["cold", "warm"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))) args env hd
    rcases env with ⟨v__0, env⟩
    cases env
    refine ⟨adapter_5.inv v__0, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_5.to_from] using he.symm

abbrev entry_keepAtom : VSCore3.CompiledFunction :=
  { id := "keepAtom", params := [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit)))], result := (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "keepAtom").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_keepAtom : VSCore3.findEntry checkedProgram "keepAtom" = some entry_keepAtom := by with_unfolding_all rfl
def source_fn_keepAtom (x__0 : (@List.{0} @VeriSlopAST.Box)) (x__1 : @VeriSlopAST.Atom) : (@List.{0} @VeriSlopAST.Box) := by
  with_unfolding_all exact adapter_5.inv (entry_keepAtom.run (adapter_5.to x__0, (adapter_2.to x__1, ())))
def Refines_keepAtom : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (∀ (x__1 : @VeriSlopAST.Atom), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopBridgeGoal.source_fn_keepAtom x__0 x__1) (@VeriSlopAST.keepAtom x__0 x__1))))
def RawEval_keepAtom : Prop := ∀ (x__0 : (@List.{0} @VeriSlopAST.Box)) (x__1 : @VeriSlopAST.Atom),
  VSCore3.evalEntry profile rawProgram "keepAtom" [adapter_5.encode x__0, adapter_2.encode x__1] =
    .ok (adapter_5.encode (source_fn_keepAtom x__0 x__1))
theorem raw_eval_keepAtom : RawEval_keepAtom := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_keepAtom.params [adapter_5.encode x__0, adapter_2.encode x__1] = some (adapter_5.to x__0, (adapter_2.to x__1, ())) := by
      change VSCore3.decodeEnv [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit)))] [adapter_5.encode x__0, adapter_2.encode x__1] = some (adapter_5.to x__0, (adapter_2.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_5_decode_encode, adapter_2_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "keepAtom" [adapter_5.encode x__0, adapter_2.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_keepAtom, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_keepAtom, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))) (entry_keepAtom.run (adapter_5.to x__0, (adapter_2.to x__1, ())))) =
      Except.ok (VSCore3.encode (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))) (adapter_5.to (adapter_5.inv (entry_keepAtom.run (adapter_5.to x__0, (adapter_2.to x__1, ()))))))
    rw [adapter_5.to_from]
def InputsCover_keepAtom : Prop := ∀ args, VSCore3.ArgsTyped entry_keepAtom args → ∃ (x__0 : (@List.{0} @VeriSlopAST.Box)) (x__1 : @VeriSlopAST.Atom), args = [adapter_5.encode x__0, adapter_2.encode x__1]
theorem inputs_cover_keepAtom : InputsCover_keepAtom := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit)))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))), (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit)))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Box" (VSCore3.RecordLayout.cons "atom" (VSCore3.RecordLayout.cons "live" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Atom" (VSCore3.RecordLayout.cons "tone" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Tone" ["cold", "warm"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))
    · exact (VSCore3.recordRawLaws "Atom" (VSCore3.RecordLayout.cons "tone" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Tone" ["cold", "warm"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws)))) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_5.inv v__0, adapter_2.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_5.to_from, adapter_2.to_from] using he.symm

abbrev entry_raiseBoxes : VSCore3.CompiledFunction :=
  { id := "raiseBoxes", params := [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))], result := (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "raiseBoxes").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_raiseBoxes : VSCore3.findEntry checkedProgram "raiseBoxes" = some entry_raiseBoxes := by with_unfolding_all rfl
def source_fn_raiseBoxes (x__0 : (@List.{0} @VeriSlopAST.Box)) : (@List.{0} @VeriSlopAST.Box) := by
  with_unfolding_all exact adapter_5.inv (entry_raiseBoxes.run (adapter_5.to x__0, ()))
def Refines_raiseBoxes : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopBridgeGoal.source_fn_raiseBoxes x__0) (@VeriSlopAST.raiseBoxes x__0)))
def RawEval_raiseBoxes : Prop := ∀ (x__0 : (@List.{0} @VeriSlopAST.Box)),
  VSCore3.evalEntry profile rawProgram "raiseBoxes" [adapter_5.encode x__0] =
    .ok (adapter_5.encode (source_fn_raiseBoxes x__0))
theorem raw_eval_raiseBoxes : RawEval_raiseBoxes := by
  with_unfolding_all
    intro x__0
    have hd : VSCore3.decodeEnv entry_raiseBoxes.params [adapter_5.encode x__0] = some (adapter_5.to x__0, ()) := by
      change VSCore3.decodeEnv [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))] [adapter_5.encode x__0] = some (adapter_5.to x__0, ())
      simp only [VSCore3.decodeEnv, adapter_5_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "raiseBoxes" [adapter_5.encode x__0] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_raiseBoxes, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_raiseBoxes, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))) (entry_raiseBoxes.run (adapter_5.to x__0, ()))) =
      Except.ok (VSCore3.encode (.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit)))) (adapter_5.to (adapter_5.inv (entry_raiseBoxes.run (adapter_5.to x__0, ())))))
    rw [adapter_5.to_from]
def InputsCover_raiseBoxes : Prop := ∀ args, VSCore3.ArgsTyped entry_raiseBoxes args → ∃ (x__0 : (@List.{0} @VeriSlopAST.Box)), args = [adapter_5.encode x__0]
theorem inputs_cover_raiseBoxes : InputsCover_raiseBoxes := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [(.list (.record "Box" ["atom", "live"] (.product (.record "Atom" ["tone", "n"] (.product (.enum "Tone" ["cold", "warm"]) (.product .nat .unit))) (.product .bool .unit))))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Box" (VSCore3.RecordLayout.cons "atom" (VSCore3.RecordLayout.cons "live" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.recordRawLaws "Atom" (VSCore3.RecordLayout.cons "tone" (VSCore3.RecordLayout.cons "n" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws (VSCore3.enumRawLaws "Tone" ["cold", "warm"]) (VSCore3.productRawLaws VSCore3.natRawLaws VSCore3.unitRawLaws))) (VSCore3.productRawLaws VSCore3.boolRawLaws VSCore3.unitRawLaws))))) args env hd
    rcases env with ⟨v__0, env⟩
    cases env
    refine ⟨adapter_5.inv v__0, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_5.to_from] using he.symm

/-- Accepted obligation G-filter, theorem VeriSlopAST.law_keepAtom, hash sha256:7f27145f58c65d8f80456e378ed2a65fff295609e7909e91902141533901cf59. -/
def «Transfer_G-filter» : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (∀ (x__1 : @VeriSlopAST.Atom), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopBridgeGoal.source_fn_keepAtom x__0 x__1) (@List.filter.{0} @VeriSlopAST.Box (fun (x__2 : @VeriSlopAST.Box) => (@Bool.and (@Decidable.decide (@Eq.{1} @VeriSlopAST.Tone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.tone x__1)) (@VeriSlopAST.instDecidableEqTone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.tone x__1))) (@Decidable.decide (@Eq.{1} @Nat (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.n x__1)) (@instDecidableEqNat (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.n x__1))))) x__0))))
theorem «transfer_G-filter» (h_keepAtom : Refines_keepAtom) : «Transfer_G-filter» := by
  have eq_keepAtom : source_fn_keepAtom = @VeriSlopAST.keepAtom := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_keepAtom x__0 x__1
  have htransfer : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (∀ (x__1 : @VeriSlopAST.Atom), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopBridgeGoal.source_fn_keepAtom x__0 x__1) (@List.filter.{0} @VeriSlopAST.Box (fun (x__2 : @VeriSlopAST.Box) => (@Bool.and (@Decidable.decide (@Eq.{1} @VeriSlopAST.Tone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.tone x__1)) (@VeriSlopAST.instDecidableEqTone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.tone x__1))) (@Decidable.decide (@Eq.{1} @Nat (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.n x__1)) (@instDecidableEqNat (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.n x__1))))) x__0))))) = ((∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (∀ (x__1 : @VeriSlopAST.Atom), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopAST.keepAtom x__0 x__1) (@List.filter.{0} @VeriSlopAST.Box (fun (x__2 : @VeriSlopAST.Box) => (@Bool.and (@Decidable.decide (@Eq.{1} @VeriSlopAST.Tone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.tone x__1)) (@VeriSlopAST.instDecidableEqTone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.tone x__1))) (@Decidable.decide (@Eq.{1} @Nat (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.n x__1)) (@instDecidableEqNat (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.n x__1))))) x__0))))) := by
    rw [eq_keepAtom]
  have hvalue : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (∀ (x__1 : @VeriSlopAST.Atom), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopBridgeGoal.source_fn_keepAtom x__0 x__1) (@List.filter.{0} @VeriSlopAST.Box (fun (x__2 : @VeriSlopAST.Box) => (@Bool.and (@Decidable.decide (@Eq.{1} @VeriSlopAST.Tone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.tone x__1)) (@VeriSlopAST.instDecidableEqTone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.tone x__1))) (@Decidable.decide (@Eq.{1} @Nat (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.n x__1)) (@instDecidableEqNat (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2)) (@VeriSlopAST.Atom.n x__1))))) x__0))))) := htransfer.symm ▸ (@VeriSlopAST.law_keepAtom)
  exact hvalue

/-- Accepted obligation G-fold, theorem VeriSlopAST.law_coldTotal, hash sha256:46d435c560d3e78edcb9315dff8f674deb44ee493ebd727236823989e7162c40. -/
def «Transfer_G-fold» : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} @Nat (@VeriSlopBridgeGoal.source_fn_coldTotal x__0) (@List.foldl.{0, 0} @Nat @VeriSlopAST.Box (fun (acc__1 : @Nat) => (fun (x__2 : @VeriSlopAST.Box) => (@cond.{1} @Nat (@Decidable.decide (@Eq.{1} @VeriSlopAST.Tone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) @VeriSlopAST.Tone.cold) (@VeriSlopAST.instDecidableEqTone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) @VeriSlopAST.Tone.cold)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) acc__1 (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2))) acc__1))) (@OfNat.ofNat.{0} @Nat (nat_lit 0) (@instOfNatNat (nat_lit 0))) x__0)))
theorem «transfer_G-fold» (h_coldTotal : Refines_coldTotal) : «Transfer_G-fold» := by
  have eq_coldTotal : source_fn_coldTotal = @VeriSlopAST.coldTotal := by
    apply funext; intro x__0
    exact h_coldTotal x__0
  have htransfer : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} @Nat (@VeriSlopBridgeGoal.source_fn_coldTotal x__0) (@List.foldl.{0, 0} @Nat @VeriSlopAST.Box (fun (acc__1 : @Nat) => (fun (x__2 : @VeriSlopAST.Box) => (@cond.{1} @Nat (@Decidable.decide (@Eq.{1} @VeriSlopAST.Tone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) @VeriSlopAST.Tone.cold) (@VeriSlopAST.instDecidableEqTone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) @VeriSlopAST.Tone.cold)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) acc__1 (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2))) acc__1))) (@OfNat.ofNat.{0} @Nat (nat_lit 0) (@instOfNatNat (nat_lit 0))) x__0)))) = ((∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} @Nat (@VeriSlopAST.coldTotal x__0) (@List.foldl.{0, 0} @Nat @VeriSlopAST.Box (fun (acc__1 : @Nat) => (fun (x__2 : @VeriSlopAST.Box) => (@cond.{1} @Nat (@Decidable.decide (@Eq.{1} @VeriSlopAST.Tone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) @VeriSlopAST.Tone.cold) (@VeriSlopAST.instDecidableEqTone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) @VeriSlopAST.Tone.cold)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) acc__1 (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2))) acc__1))) (@OfNat.ofNat.{0} @Nat (nat_lit 0) (@instOfNatNat (nat_lit 0))) x__0)))) := by
    rw [eq_coldTotal]
  have hvalue : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} @Nat (@VeriSlopBridgeGoal.source_fn_coldTotal x__0) (@List.foldl.{0, 0} @Nat @VeriSlopAST.Box (fun (acc__1 : @Nat) => (fun (x__2 : @VeriSlopAST.Box) => (@cond.{1} @Nat (@Decidable.decide (@Eq.{1} @VeriSlopAST.Tone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) @VeriSlopAST.Tone.cold) (@VeriSlopAST.instDecidableEqTone (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__2)) @VeriSlopAST.Tone.cold)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) acc__1 (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__2))) acc__1))) (@OfNat.ofNat.{0} @Nat (nat_lit 0) (@instOfNatNat (nat_lit 0))) x__0)))) := htransfer.symm ▸ (@VeriSlopAST.law_coldTotal)
  exact hvalue

/-- Accepted obligation G-map, theorem VeriSlopAST.law_raiseBoxes, hash sha256:42ae7524598e0e0aa8fcd15f3240b1bf74022bd7dbac1aa1b19b246e5612ab0f. -/
def «Transfer_G-map» : Prop := (∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopBridgeGoal.source_fn_raiseBoxes x__0) (@List.map.{0, 0} @VeriSlopAST.Box @VeriSlopAST.Box (fun (x__1 : @VeriSlopAST.Box) => (@VeriSlopAST.Box.mk (@VeriSlopAST.Atom.mk (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__1)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__1)) (@OfNat.ofNat.{0} @Nat (nat_lit 1) (@instOfNatNat (nat_lit 1))))) (@VeriSlopAST.Box.live x__1))) x__0)))
theorem «transfer_G-map» (h_raiseBoxes : Refines_raiseBoxes) : «Transfer_G-map» := by
  have eq_raiseBoxes : source_fn_raiseBoxes = @VeriSlopAST.raiseBoxes := by
    apply funext; intro x__0
    exact h_raiseBoxes x__0
  have htransfer : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopBridgeGoal.source_fn_raiseBoxes x__0) (@List.map.{0, 0} @VeriSlopAST.Box @VeriSlopAST.Box (fun (x__1 : @VeriSlopAST.Box) => (@VeriSlopAST.Box.mk (@VeriSlopAST.Atom.mk (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__1)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__1)) (@OfNat.ofNat.{0} @Nat (nat_lit 1) (@instOfNatNat (nat_lit 1))))) (@VeriSlopAST.Box.live x__1))) x__0)))) = ((∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopAST.raiseBoxes x__0) (@List.map.{0, 0} @VeriSlopAST.Box @VeriSlopAST.Box (fun (x__1 : @VeriSlopAST.Box) => (@VeriSlopAST.Box.mk (@VeriSlopAST.Atom.mk (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__1)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__1)) (@OfNat.ofNat.{0} @Nat (nat_lit 1) (@instOfNatNat (nat_lit 1))))) (@VeriSlopAST.Box.live x__1))) x__0)))) := by
    rw [eq_raiseBoxes]
  have hvalue : ((∀ (x__0 : (@List.{0} @VeriSlopAST.Box)), (@Eq.{1} (@List.{0} @VeriSlopAST.Box) (@VeriSlopBridgeGoal.source_fn_raiseBoxes x__0) (@List.map.{0, 0} @VeriSlopAST.Box @VeriSlopAST.Box (fun (x__1 : @VeriSlopAST.Box) => (@VeriSlopAST.Box.mk (@VeriSlopAST.Atom.mk (@VeriSlopAST.Atom.tone (@VeriSlopAST.Box.atom x__1)) (@HAdd.hAdd.{0, 0, 0} @Nat @Nat @Nat (@instHAdd.{0} @Nat @instAddNat) (@VeriSlopAST.Atom.n (@VeriSlopAST.Box.atom x__1)) (@OfNat.ofNat.{0} @Nat (nat_lit 1) (@instOfNatNat (nat_lit 1))))) (@VeriSlopAST.Box.live x__1))) x__0)))) := htransfer.symm ▸ (@VeriSlopAST.law_raiseBoxes)
  exact hvalue

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_coldTotal (@And @VeriSlopBridgeGoal.RawEval_coldTotal (@And @VeriSlopBridgeGoal.Refines_coldTotal (@And @VeriSlopBridgeGoal.InputsCover_keepAtom (@And @VeriSlopBridgeGoal.RawEval_keepAtom (@And @VeriSlopBridgeGoal.Refines_keepAtom (@And @VeriSlopBridgeGoal.InputsCover_raiseBoxes (@And @VeriSlopBridgeGoal.RawEval_raiseBoxes (@And @VeriSlopBridgeGoal.Refines_raiseBoxes (@And @VeriSlopBridgeGoal.«Transfer_G-filter» (@And @VeriSlopBridgeGoal.«Transfer_G-fold» @VeriSlopBridgeGoal.«Transfer_G-map»)))))))))))))
theorem edge_of_refines (h_coldTotal : Refines_coldTotal) (h_keepAtom : Refines_keepAtom) (h_raiseBoxes : Refines_raiseBoxes) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_coldTotal, raw_eval_coldTotal, h_coldTotal, inputs_cover_keepAtom, raw_eval_keepAtom, h_keepAtom, inputs_cover_raiseBoxes, raw_eval_raiseBoxes, h_raiseBoxes, «transfer_G-filter» h_keepAtom, «transfer_G-fold» h_coldTotal, «transfer_G-map» h_raiseBoxes⟩

end VeriSlopBridgeGoal
