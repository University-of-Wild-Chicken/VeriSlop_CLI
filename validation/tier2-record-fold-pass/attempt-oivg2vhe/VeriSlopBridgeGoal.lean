import VSCore3
import VeriSlopContract

set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

namespace VeriSlopBridgeGoal

/-- Supervisor goal vscore.reference_refinement/0.3; exact delivered bytes sha256:e75dc169485d73bbbade5d5785814fa3718b08d8788eb2cd080e5851c8a95f59. -/
def sourceBytes : List Nat := [123, 34, 100, 101, 99, 108, 97, 114, 97, 116, 105, 111, 110, 115, 34, 58, 91, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 105, 100, 34, 58, 34, 108, 97, 98, 101, 108, 34, 44, 34, 116, 121, 112, 101, 34, 58, 34, 115, 116, 114, 105, 110, 103, 34, 125, 93, 44, 34, 105, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 93, 44, 34, 101, 110, 116, 114, 105, 101, 115, 34, 58, 91, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 108, 97, 98, 101, 108, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 108, 97, 98, 101, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 93, 44, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 109, 97, 112, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 105, 100, 34, 58, 34, 116, 114, 97, 110, 115, 102, 111, 114, 109, 101, 100, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 44, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 125, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 125, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 50, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 116, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 102, 105, 108, 116, 101, 114, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 105, 100, 34, 58, 34, 115, 101, 108, 101, 99, 116, 101, 100, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 44, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 125, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 125, 125, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 105, 110, 105, 116, 105, 97, 108, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 115, 111, 117, 114, 99, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 115, 116, 101, 112, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 102, 111, 108, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 102, 111, 108, 100, 101, 100, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 44, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 125, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 44, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 105, 110, 105, 116, 105, 97, 108, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 115, 111, 117, 114, 99, 101, 34, 58, 123, 34, 98, 111, 100, 121, 34, 58, 123, 34, 102, 105, 101, 108, 100, 115, 34, 58, 91, 123, 34, 105, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 51, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 125, 44, 123, 34, 105, 100, 34, 58, 34, 108, 97, 98, 101, 108, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 108, 97, 98, 101, 108, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 125, 93, 44, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 114, 101, 99, 111, 114, 100, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 109, 97, 112, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 115, 116, 101, 112, 34, 58, 123, 34, 108, 101, 102, 116, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 49, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 44, 34, 114, 105, 103, 104, 116, 34, 58, 123, 34, 102, 105, 101, 108, 100, 34, 58, 34, 97, 109, 111, 117, 110, 116, 34, 44, 34, 116, 97, 103, 34, 58, 34, 112, 114, 111, 106, 101, 99, 116, 34, 44, 34, 118, 97, 108, 117, 101, 34, 58, 123, 34, 105, 110, 100, 101, 120, 34, 58, 48, 44, 34, 116, 97, 103, 34, 58, 34, 118, 97, 114, 34, 125, 125, 44, 34, 116, 97, 103, 34, 58, 34, 97, 100, 100, 34, 125, 44, 34, 116, 97, 103, 34, 58, 34, 108, 105, 115, 116, 95, 102, 111, 108, 100, 34, 125, 44, 34, 105, 100, 34, 58, 34, 116, 114, 97, 110, 115, 102, 111, 114, 109, 101, 100, 95, 102, 111, 108, 100, 34, 44, 34, 112, 97, 114, 97, 109, 115, 34, 58, 91, 34, 105, 110, 116, 34, 44, 34, 105, 110, 116, 34, 44, 123, 34, 108, 105, 115, 116, 34, 58, 123, 34, 114, 101, 99, 111, 114, 100, 34, 58, 34, 80, 97, 99, 107, 101, 116, 34, 125, 125, 93, 44, 34, 114, 101, 115, 117, 108, 116, 34, 58, 34, 105, 110, 116, 34, 125, 93, 44, 34, 104, 101, 108, 112, 101, 114, 115, 34, 58, 91, 93, 44, 34, 108, 97, 110, 103, 117, 97, 103, 101, 34, 58, 34, 118, 115, 99, 111, 114, 101, 47, 48, 46, 51, 34, 44, 34, 112, 114, 111, 102, 105, 108, 101, 34, 58, 34, 100, 97, 116, 97, 45, 112, 105, 112, 101, 108, 105, 110, 101, 47, 48, 46, 51, 34, 125]
def rawProgram : VSCore3.Program := { language := "vscore/0.3", profile := "data-pipeline/0.3", declarations := [(VSCore3.DataDecl.record "Packet" [("amount", VSCore3.Ty.int), ("label", VSCore3.Ty.string)])], helpers := [], entries := [{ id := "transformed", params := [VSCore3.Ty.int, (VSCore3.Ty.list (VSCore3.Ty.record "Packet"))], result := (VSCore3.Ty.list (VSCore3.Ty.record "Packet")), body := (VSCore3.Expr.listMap (VSCore3.Expr.var 0) (VSCore3.Expr.record "Packet" [("amount", (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.project (VSCore3.Expr.var 0) "amount") (VSCore3.Expr.var 2))), ("label", (VSCore3.Expr.project (VSCore3.Expr.var 0) "label"))])) },
{ id := "selected", params := [VSCore3.Ty.int, (VSCore3.Ty.list (VSCore3.Ty.record "Packet"))], result := (VSCore3.Ty.list (VSCore3.Ty.record "Packet")), body := (VSCore3.Expr.listFilter (VSCore3.Expr.var 0) (VSCore3.Expr.bin VSCore.BinOp.lt (VSCore3.Expr.project (VSCore3.Expr.var 0) "amount") (VSCore3.Expr.var 2))) },
{ id := "folded", params := [VSCore3.Ty.int, (VSCore3.Ty.list (VSCore3.Ty.record "Packet"))], result := VSCore3.Ty.int, body := (VSCore3.Expr.listFold (VSCore3.Expr.var 0) (VSCore3.Expr.var 1) (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.var 1) (VSCore3.Expr.project (VSCore3.Expr.var 0) "amount"))) },
{ id := "transformed_fold", params := [VSCore3.Ty.int, VSCore3.Ty.int, (VSCore3.Ty.list (VSCore3.Ty.record "Packet"))], result := VSCore3.Ty.int, body := (VSCore3.Expr.listFold (VSCore3.Expr.listMap (VSCore3.Expr.var 0) (VSCore3.Expr.record "Packet" [("amount", (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.project (VSCore3.Expr.var 0) "amount") (VSCore3.Expr.var 3))), ("label", (VSCore3.Expr.project (VSCore3.Expr.var 0) "label"))])) (VSCore3.Expr.var 1) (VSCore3.Expr.bin VSCore.BinOp.add (VSCore3.Expr.var 1) (VSCore3.Expr.project (VSCore3.Expr.var 0) "amount"))) }] }
def profile : VSCore3.Profile := { enums := [] }
def signatures : List VSCore3.EntrySig := [{ id := "transformed", params := [VSCore3.Ty.int, (VSCore3.Ty.list (VSCore3.Ty.record "Packet"))], result := (VSCore3.Ty.list (VSCore3.Ty.record "Packet")) },
  { id := "selected", params := [VSCore3.Ty.int, (VSCore3.Ty.list (VSCore3.Ty.record "Packet"))], result := (VSCore3.Ty.list (VSCore3.Ty.record "Packet")) },
  { id := "folded", params := [VSCore3.Ty.int, (VSCore3.Ty.list (VSCore3.Ty.record "Packet"))], result := VSCore3.Ty.int },
  { id := "transformed_fold", params := [VSCore3.Ty.int, VSCore3.Ty.int, (VSCore3.Ty.list (VSCore3.Ty.record "Packet"))], result := VSCore3.Ty.int }]
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

/-- Exact accepted carrier {"record":"Packet"}. -/
def adapter_2 : VSCore3.Adapter (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))) @RecordFoldFixture.Packet :=
  { to := fun x => (adapter_0.to (@RecordFoldFixture.Packet.amount x), (adapter_1.to (@RecordFoldFixture.Packet.label x), ()))
    inv := fun x => @RecordFoldFixture.Packet.mk (adapter_0.inv (x.1)) (adapter_1.inv (x.2.1))
    from_to := by intro x; cases x; simp [adapter_0.from_to, adapter_1.from_to]
    to_from := by intro x; rcases x with ⟨x0, x⟩; rcases x with ⟨x1, x⟩; cases x; simp [adapter_0.to_from, adapter_1.to_from] }
def adapter_2_raw : VSCore3.RawLaws (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))) := (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "amount" (VSCore3.RecordLayout.cons "label" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.stringRawLaws VSCore3.unitRawLaws)))
theorem adapter_2_decode_encode (x : @RecordFoldFixture.Packet) :
    VSCore3.decode (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))) (adapter_2.encode x) = some (adapter_2.to x) :=
  adapter_2.decode_encode adapter_2_raw x

/-- Exact accepted carrier {"list":{"record":"Packet"}}. -/
def adapter_3 : VSCore3.Adapter (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit)))) (@List.{0} @RecordFoldFixture.Packet) :=
  VSCore3.listAdapter adapter_2
def adapter_3_raw : VSCore3.RawLaws (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit)))) := (VSCore3.listRawLaws (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "amount" (VSCore3.RecordLayout.cons "label" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.stringRawLaws VSCore3.unitRawLaws))))
theorem adapter_3_decode_encode (x : (@List.{0} @RecordFoldFixture.Packet)) :
    VSCore3.decode (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit)))) (adapter_3.encode x) = some (adapter_3.to x) :=
  adapter_3.decode_encode adapter_3_raw x

abbrev entry_transformed : VSCore3.CompiledFunction :=
  { id := "transformed", params := [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))], result := (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit)))),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "transformed").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_transformed : VSCore3.findEntry checkedProgram "transformed" = some entry_transformed := by with_unfolding_all rfl
def source_fn_transformed (x__0 : @Int) (x__1 : (@List.{0} @RecordFoldFixture.Packet)) : (@List.{0} @RecordFoldFixture.Packet) := by
  with_unfolding_all exact adapter_3.inv (entry_transformed.run (adapter_0.to x__0, (adapter_3.to x__1, ())))
def Refines_transformed : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@VeriSlopBridgeGoal.source_fn_transformed x__0 x__1) (@RecordFoldFixture.transformed x__0 x__1))))
def RawEval_transformed : Prop := ∀ (x__0 : @Int) (x__1 : (@List.{0} @RecordFoldFixture.Packet)),
  VSCore3.evalEntry profile rawProgram "transformed" [adapter_0.encode x__0, adapter_3.encode x__1] =
    .ok (adapter_3.encode (source_fn_transformed x__0 x__1))
theorem raw_eval_transformed : RawEval_transformed := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_transformed.params [adapter_0.encode x__0, adapter_3.encode x__1] = some (adapter_0.to x__0, (adapter_3.to x__1, ())) := by
      change VSCore3.decodeEnv [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] [adapter_0.encode x__0, adapter_3.encode x__1] = some (adapter_0.to x__0, (adapter_3.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, adapter_3_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "transformed" [adapter_0.encode x__0, adapter_3.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_transformed, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_transformed, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit)))) (entry_transformed.run (adapter_0.to x__0, (adapter_3.to x__1, ())))) =
      Except.ok (VSCore3.encode (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit)))) (adapter_3.to (adapter_3.inv (entry_transformed.run (adapter_0.to x__0, (adapter_3.to x__1, ()))))))
    rw [adapter_3.to_from]
def InputsCover_transformed : Prop := ∀ args, VSCore3.ArgsTyped entry_transformed args → ∃ (x__0 : @Int) (x__1 : (@List.{0} @RecordFoldFixture.Packet)), args = [adapter_0.encode x__0, adapter_3.encode x__1]
theorem inputs_cover_transformed : InputsCover_transformed := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact VSCore3.intRawLaws
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "amount" (VSCore3.RecordLayout.cons "label" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.stringRawLaws VSCore3.unitRawLaws))))) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, adapter_3.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from, adapter_3.to_from] using he.symm

abbrev entry_selected : VSCore3.CompiledFunction :=
  { id := "selected", params := [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))], result := (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit)))),
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "selected").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_selected : VSCore3.findEntry checkedProgram "selected" = some entry_selected := by with_unfolding_all rfl
def source_fn_selected (x__0 : @Int) (x__1 : (@List.{0} @RecordFoldFixture.Packet)) : (@List.{0} @RecordFoldFixture.Packet) := by
  with_unfolding_all exact adapter_3.inv (entry_selected.run (adapter_0.to x__0, (adapter_3.to x__1, ())))
def Refines_selected : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@VeriSlopBridgeGoal.source_fn_selected x__0 x__1) (@RecordFoldFixture.selected x__0 x__1))))
def RawEval_selected : Prop := ∀ (x__0 : @Int) (x__1 : (@List.{0} @RecordFoldFixture.Packet)),
  VSCore3.evalEntry profile rawProgram "selected" [adapter_0.encode x__0, adapter_3.encode x__1] =
    .ok (adapter_3.encode (source_fn_selected x__0 x__1))
theorem raw_eval_selected : RawEval_selected := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_selected.params [adapter_0.encode x__0, adapter_3.encode x__1] = some (adapter_0.to x__0, (adapter_3.to x__1, ())) := by
      change VSCore3.decodeEnv [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] [adapter_0.encode x__0, adapter_3.encode x__1] = some (adapter_0.to x__0, (adapter_3.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, adapter_3_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "selected" [adapter_0.encode x__0, adapter_3.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_selected, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_selected, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit)))) (entry_selected.run (adapter_0.to x__0, (adapter_3.to x__1, ())))) =
      Except.ok (VSCore3.encode (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit)))) (adapter_3.to (adapter_3.inv (entry_selected.run (adapter_0.to x__0, (adapter_3.to x__1, ()))))))
    rw [adapter_3.to_from]
def InputsCover_selected : Prop := ∀ args, VSCore3.ArgsTyped entry_selected args → ∃ (x__0 : @Int) (x__1 : (@List.{0} @RecordFoldFixture.Packet)), args = [adapter_0.encode x__0, adapter_3.encode x__1]
theorem inputs_cover_selected : InputsCover_selected := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact VSCore3.intRawLaws
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "amount" (VSCore3.RecordLayout.cons "label" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.stringRawLaws VSCore3.unitRawLaws))))) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, adapter_3.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from, adapter_3.to_from] using he.symm

abbrev entry_folded : VSCore3.CompiledFunction :=
  { id := "folded", params := [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "folded").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_folded : VSCore3.findEntry checkedProgram "folded" = some entry_folded := by with_unfolding_all rfl
def source_fn_folded (x__0 : @Int) (x__1 : (@List.{0} @RecordFoldFixture.Packet)) : @Int := by
  with_unfolding_all exact adapter_0.inv (entry_folded.run (adapter_0.to x__0, (adapter_3.to x__1, ())))
def Refines_folded : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_folded x__0 x__1) (@RecordFoldFixture.folded x__0 x__1))))
def RawEval_folded : Prop := ∀ (x__0 : @Int) (x__1 : (@List.{0} @RecordFoldFixture.Packet)),
  VSCore3.evalEntry profile rawProgram "folded" [adapter_0.encode x__0, adapter_3.encode x__1] =
    .ok (adapter_0.encode (source_fn_folded x__0 x__1))
theorem raw_eval_folded : RawEval_folded := by
  with_unfolding_all
    intro x__0 x__1
    have hd : VSCore3.decodeEnv entry_folded.params [adapter_0.encode x__0, adapter_3.encode x__1] = some (adapter_0.to x__0, (adapter_3.to x__1, ())) := by
      change VSCore3.decodeEnv [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] [adapter_0.encode x__0, adapter_3.encode x__1] = some (adapter_0.to x__0, (adapter_3.to x__1, ()))
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, adapter_3_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "folded" [adapter_0.encode x__0, adapter_3.encode x__1] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_folded, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_folded, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_folded.run (adapter_0.to x__0, (adapter_3.to x__1, ())))) =
      Except.ok (VSCore3.encode .int (adapter_0.to (adapter_0.inv (entry_folded.run (adapter_0.to x__0, (adapter_3.to x__1, ()))))))
    rw [adapter_0.to_from]
def InputsCover_folded : Prop := ∀ args, VSCore3.ArgsTyped entry_folded args → ∃ (x__0 : @Int) (x__1 : (@List.{0} @RecordFoldFixture.Packet)), args = [adapter_0.encode x__0, adapter_3.encode x__1]
theorem inputs_cover_folded : InputsCover_folded := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [.int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl
    · exact VSCore3.intRawLaws
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "amount" (VSCore3.RecordLayout.cons "label" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.stringRawLaws VSCore3.unitRawLaws))))) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, adapter_3.inv v__1, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from, adapter_3.to_from] using he.symm

abbrev entry_transformed_fold : VSCore3.CompiledFunction :=
  { id := "transformed_fold", params := [.int, .int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))], result := .int,
    run := by with_unfolding_all exact ((VSCore3.findEntry checkedProgram "transformed_fold").getD
      { id := "_missing", params := [], result := .unit, run := fun _ => () }).run }
theorem find_transformed_fold : VSCore3.findEntry checkedProgram "transformed_fold" = some entry_transformed_fold := by with_unfolding_all rfl
def source_fn_transformed_fold (x__0 : @Int) (x__1 : @Int) (x__2 : (@List.{0} @RecordFoldFixture.Packet)) : @Int := by
  with_unfolding_all exact adapter_0.inv (entry_transformed_fold.run (adapter_0.to x__0, (adapter_0.to x__1, (adapter_3.to x__2, ()))))
def Refines_transformed_fold : Prop := (∀ (x__0 : @Int), (∀ (x__1 : @Int), (∀ (x__2 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transformed_fold x__0 x__1 x__2) (@RecordFoldFixture.transformed_fold x__0 x__1 x__2)))))
def RawEval_transformed_fold : Prop := ∀ (x__0 : @Int) (x__1 : @Int) (x__2 : (@List.{0} @RecordFoldFixture.Packet)),
  VSCore3.evalEntry profile rawProgram "transformed_fold" [adapter_0.encode x__0, adapter_0.encode x__1, adapter_3.encode x__2] =
    .ok (adapter_0.encode (source_fn_transformed_fold x__0 x__1 x__2))
theorem raw_eval_transformed_fold : RawEval_transformed_fold := by
  with_unfolding_all
    intro x__0 x__1 x__2
    have hd : VSCore3.decodeEnv entry_transformed_fold.params [adapter_0.encode x__0, adapter_0.encode x__1, adapter_3.encode x__2] = some (adapter_0.to x__0, (adapter_0.to x__1, (adapter_3.to x__2, ()))) := by
      change VSCore3.decodeEnv [.int, .int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] [adapter_0.encode x__0, adapter_0.encode x__1, adapter_3.encode x__2] = some (adapter_0.to x__0, (adapter_0.to x__1, (adapter_3.to x__2, ())))
      simp only [VSCore3.decodeEnv, adapter_0_decode_encode, adapter_0_decode_encode, adapter_3_decode_encode, bind, Option.bind, pure]
    change VSCore3.evalEntry profile rawProgram "transformed_fold" [adapter_0.encode x__0, adapter_0.encode x__1, adapter_3.encode x__2] = _
    simp only [VSCore3.evalEntry, compiled_ok, find_transformed_fold, VSCore3.evalCheckedEntry, hd]
    simp only [source_fn_transformed_fold, VSCore3.Adapter.encode]
    change Except.ok (VSCore3.encode .int (entry_transformed_fold.run (adapter_0.to x__0, (adapter_0.to x__1, (adapter_3.to x__2, ()))))) =
      Except.ok (VSCore3.encode .int (adapter_0.to (adapter_0.inv (entry_transformed_fold.run (adapter_0.to x__0, (adapter_0.to x__1, (adapter_3.to x__2, ())))))))
    rw [adapter_0.to_from]
def InputsCover_transformed_fold : Prop := ∀ args, VSCore3.ArgsTyped entry_transformed_fold args → ∃ (x__0 : @Int) (x__1 : @Int) (x__2 : (@List.{0} @RecordFoldFixture.Packet)), args = [adapter_0.encode x__0, adapter_0.encode x__1, adapter_3.encode x__2]
theorem inputs_cover_transformed_fold : InputsCover_transformed_fold := by
  with_unfolding_all
    intro args h
    obtain ⟨env, hd⟩ := h
    change VSCore3.decodeEnv [.int, .int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] args = some env at hd
    have he := VSCore3.encodeEnv_decodeEnv [.int, .int, (.list (.record "Packet" ["amount", "label"] (.product .int (.product .string .unit))))] (by
    intro t h
    simp only [List.mem_cons, List.not_mem_nil, or_false] at h
    rcases h with rfl | rfl | rfl
    · exact VSCore3.intRawLaws
    · exact VSCore3.intRawLaws
    · exact (VSCore3.listRawLaws (VSCore3.recordRawLaws "Packet" (VSCore3.RecordLayout.cons "amount" (VSCore3.RecordLayout.cons "label" VSCore3.RecordLayout.nil)) (VSCore3.productRawLaws VSCore3.intRawLaws (VSCore3.productRawLaws VSCore3.stringRawLaws VSCore3.unitRawLaws))))) args env hd
    rcases env with ⟨v__0, env⟩
    rcases env with ⟨v__1, env⟩
    rcases env with ⟨v__2, env⟩
    cases env
    refine ⟨adapter_0.inv v__0, adapter_0.inv v__1, adapter_3.inv v__2, ?_⟩
    simpa only [VSCore3.encodeEnv, VSCore3.Adapter.encode, adapter_0.to_from, adapter_0.to_from, adapter_3.to_from] using he.symm

/-- Accepted obligation O1, theorem RecordFoldFixture.transformed_contract, hash sha256:1111111111111111111111111111111111111111111111111111111111111111. -/
def Transfer_O1 : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@VeriSlopBridgeGoal.source_fn_transformed x__0 x__1) (@List.map.{0, 0} @RecordFoldFixture.Packet @RecordFoldFixture.Packet (fun (x__2 : @RecordFoldFixture.Packet) => (@RecordFoldFixture.Packet.mk (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@RecordFoldFixture.Packet.amount x__2) x__0) (@RecordFoldFixture.Packet.label x__2))) x__1))))
theorem transfer_O1 (h_transformed : Refines_transformed) : Transfer_O1 := by
  have eq_transformed : source_fn_transformed = @RecordFoldFixture.transformed := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_transformed x__0 x__1
  have htransfer : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@VeriSlopBridgeGoal.source_fn_transformed x__0 x__1) (@List.map.{0, 0} @RecordFoldFixture.Packet @RecordFoldFixture.Packet (fun (x__2 : @RecordFoldFixture.Packet) => (@RecordFoldFixture.Packet.mk (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@RecordFoldFixture.Packet.amount x__2) x__0) (@RecordFoldFixture.Packet.label x__2))) x__1))))) = ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@RecordFoldFixture.transformed x__0 x__1) (@List.map.{0, 0} @RecordFoldFixture.Packet @RecordFoldFixture.Packet (fun (x__2 : @RecordFoldFixture.Packet) => (@RecordFoldFixture.Packet.mk (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@RecordFoldFixture.Packet.amount x__2) x__0) (@RecordFoldFixture.Packet.label x__2))) x__1))))) := by
    rw [eq_transformed]
  have hvalue : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@VeriSlopBridgeGoal.source_fn_transformed x__0 x__1) (@List.map.{0, 0} @RecordFoldFixture.Packet @RecordFoldFixture.Packet (fun (x__2 : @RecordFoldFixture.Packet) => (@RecordFoldFixture.Packet.mk (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@RecordFoldFixture.Packet.amount x__2) x__0) (@RecordFoldFixture.Packet.label x__2))) x__1))))) := htransfer.symm ▸ (@RecordFoldFixture.transformed_contract)
  exact hvalue

/-- Accepted obligation O2, theorem RecordFoldFixture.selected_contract, hash sha256:2222222222222222222222222222222222222222222222222222222222222222. -/
def Transfer_O2 : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@VeriSlopBridgeGoal.source_fn_selected x__0 x__1) (@List.filter.{0} @RecordFoldFixture.Packet (fun (x__2 : @RecordFoldFixture.Packet) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt (@RecordFoldFixture.Packet.amount x__2) x__0) (@Int.decLt (@RecordFoldFixture.Packet.amount x__2) x__0))) x__1))))
theorem transfer_O2 (h_selected : Refines_selected) : Transfer_O2 := by
  have eq_selected : source_fn_selected = @RecordFoldFixture.selected := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_selected x__0 x__1
  have htransfer : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@VeriSlopBridgeGoal.source_fn_selected x__0 x__1) (@List.filter.{0} @RecordFoldFixture.Packet (fun (x__2 : @RecordFoldFixture.Packet) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt (@RecordFoldFixture.Packet.amount x__2) x__0) (@Int.decLt (@RecordFoldFixture.Packet.amount x__2) x__0))) x__1))))) = ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@RecordFoldFixture.selected x__0 x__1) (@List.filter.{0} @RecordFoldFixture.Packet (fun (x__2 : @RecordFoldFixture.Packet) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt (@RecordFoldFixture.Packet.amount x__2) x__0) (@Int.decLt (@RecordFoldFixture.Packet.amount x__2) x__0))) x__1))))) := by
    rw [eq_selected]
  have hvalue : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} (@List.{0} @RecordFoldFixture.Packet) (@VeriSlopBridgeGoal.source_fn_selected x__0 x__1) (@List.filter.{0} @RecordFoldFixture.Packet (fun (x__2 : @RecordFoldFixture.Packet) => (@Decidable.decide (@LT.lt.{0} @Int @Int.instLTInt (@RecordFoldFixture.Packet.amount x__2) x__0) (@Int.decLt (@RecordFoldFixture.Packet.amount x__2) x__0))) x__1))))) := htransfer.symm ▸ (@RecordFoldFixture.selected_contract)
  exact hvalue

/-- Accepted obligation O3, theorem RecordFoldFixture.folded_contract, hash sha256:3333333333333333333333333333333333333333333333333333333333333333. -/
def Transfer_O3 : Prop := (∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_folded x__0 x__1) (@List.foldl.{0, 0} @Int @RecordFoldFixture.Packet (fun (acc__2 : @Int) => (fun (x__3 : @RecordFoldFixture.Packet) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) acc__2 (@RecordFoldFixture.Packet.amount x__3)))) x__0 x__1))))
theorem transfer_O3 (h_folded : Refines_folded) : Transfer_O3 := by
  have eq_folded : source_fn_folded = @RecordFoldFixture.folded := by
    apply funext; intro x__0; apply funext; intro x__1
    exact h_folded x__0 x__1
  have htransfer : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_folded x__0 x__1) (@List.foldl.{0, 0} @Int @RecordFoldFixture.Packet (fun (acc__2 : @Int) => (fun (x__3 : @RecordFoldFixture.Packet) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) acc__2 (@RecordFoldFixture.Packet.amount x__3)))) x__0 x__1))))) = ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@RecordFoldFixture.folded x__0 x__1) (@List.foldl.{0, 0} @Int @RecordFoldFixture.Packet (fun (acc__2 : @Int) => (fun (x__3 : @RecordFoldFixture.Packet) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) acc__2 (@RecordFoldFixture.Packet.amount x__3)))) x__0 x__1))))) := by
    rw [eq_folded]
  have hvalue : ((∀ (x__0 : @Int), (∀ (x__1 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_folded x__0 x__1) (@List.foldl.{0, 0} @Int @RecordFoldFixture.Packet (fun (acc__2 : @Int) => (fun (x__3 : @RecordFoldFixture.Packet) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) acc__2 (@RecordFoldFixture.Packet.amount x__3)))) x__0 x__1))))) := htransfer.symm ▸ (@RecordFoldFixture.folded_contract)
  exact hvalue

/-- Accepted obligation O4, theorem RecordFoldFixture.transformed_fold_contract, hash sha256:4444444444444444444444444444444444444444444444444444444444444444. -/
def Transfer_O4 : Prop := (∀ (x__0 : @Int), (∀ (x__1 : @Int), (∀ (x__2 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transformed_fold x__0 x__1 x__2) (@List.foldl.{0, 0} @Int @RecordFoldFixture.Packet (fun (acc__3 : @Int) => (fun (x__4 : @RecordFoldFixture.Packet) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) acc__3 (@RecordFoldFixture.Packet.amount x__4)))) x__1 (@List.map.{0, 0} @RecordFoldFixture.Packet @RecordFoldFixture.Packet (fun (x__3 : @RecordFoldFixture.Packet) => (@RecordFoldFixture.Packet.mk (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@RecordFoldFixture.Packet.amount x__3) x__0) (@RecordFoldFixture.Packet.label x__3))) x__2))))))
theorem transfer_O4 (h_transformed_fold : Refines_transformed_fold) : Transfer_O4 := by
  have eq_transformed_fold : source_fn_transformed_fold = @RecordFoldFixture.transformed_fold := by
    apply funext; intro x__0; apply funext; intro x__1; apply funext; intro x__2
    exact h_transformed_fold x__0 x__1 x__2
  have htransfer : ((∀ (x__0 : @Int), (∀ (x__1 : @Int), (∀ (x__2 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transformed_fold x__0 x__1 x__2) (@List.foldl.{0, 0} @Int @RecordFoldFixture.Packet (fun (acc__3 : @Int) => (fun (x__4 : @RecordFoldFixture.Packet) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) acc__3 (@RecordFoldFixture.Packet.amount x__4)))) x__1 (@List.map.{0, 0} @RecordFoldFixture.Packet @RecordFoldFixture.Packet (fun (x__3 : @RecordFoldFixture.Packet) => (@RecordFoldFixture.Packet.mk (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@RecordFoldFixture.Packet.amount x__3) x__0) (@RecordFoldFixture.Packet.label x__3))) x__2))))))) = ((∀ (x__0 : @Int), (∀ (x__1 : @Int), (∀ (x__2 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@RecordFoldFixture.transformed_fold x__0 x__1 x__2) (@List.foldl.{0, 0} @Int @RecordFoldFixture.Packet (fun (acc__3 : @Int) => (fun (x__4 : @RecordFoldFixture.Packet) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) acc__3 (@RecordFoldFixture.Packet.amount x__4)))) x__1 (@List.map.{0, 0} @RecordFoldFixture.Packet @RecordFoldFixture.Packet (fun (x__3 : @RecordFoldFixture.Packet) => (@RecordFoldFixture.Packet.mk (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@RecordFoldFixture.Packet.amount x__3) x__0) (@RecordFoldFixture.Packet.label x__3))) x__2))))))) := by
    rw [eq_transformed_fold]
  have hvalue : ((∀ (x__0 : @Int), (∀ (x__1 : @Int), (∀ (x__2 : (@List.{0} @RecordFoldFixture.Packet)), (@Eq.{1} @Int (@VeriSlopBridgeGoal.source_fn_transformed_fold x__0 x__1 x__2) (@List.foldl.{0, 0} @Int @RecordFoldFixture.Packet (fun (acc__3 : @Int) => (fun (x__4 : @RecordFoldFixture.Packet) => (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) acc__3 (@RecordFoldFixture.Packet.amount x__4)))) x__1 (@List.map.{0, 0} @RecordFoldFixture.Packet @RecordFoldFixture.Packet (fun (x__3 : @RecordFoldFixture.Packet) => (@RecordFoldFixture.Packet.mk (@HAdd.hAdd.{0, 0, 0} @Int @Int @Int (@instHAdd.{0} @Int @Int.instAdd) (@RecordFoldFixture.Packet.amount x__3) x__0) (@RecordFoldFixture.Packet.label x__3))) x__2))))))) := htransfer.symm ▸ (@RecordFoldFixture.transformed_fold_contract)
  exact hvalue

def EdgeProp : Prop := (@And @VeriSlopBridgeGoal.SourceParses (@And @VeriSlopBridgeGoal.SourceChecks (@And @VeriSlopBridgeGoal.InputsCover_transformed (@And @VeriSlopBridgeGoal.RawEval_transformed (@And @VeriSlopBridgeGoal.Refines_transformed (@And @VeriSlopBridgeGoal.InputsCover_selected (@And @VeriSlopBridgeGoal.RawEval_selected (@And @VeriSlopBridgeGoal.Refines_selected (@And @VeriSlopBridgeGoal.InputsCover_folded (@And @VeriSlopBridgeGoal.RawEval_folded (@And @VeriSlopBridgeGoal.Refines_folded (@And @VeriSlopBridgeGoal.InputsCover_transformed_fold (@And @VeriSlopBridgeGoal.RawEval_transformed_fold (@And @VeriSlopBridgeGoal.Refines_transformed_fold (@And @VeriSlopBridgeGoal.Transfer_O1 (@And @VeriSlopBridgeGoal.Transfer_O2 (@And @VeriSlopBridgeGoal.Transfer_O3 @VeriSlopBridgeGoal.Transfer_O4)))))))))))))))))
theorem edge_of_refines (h_transformed : Refines_transformed) (h_selected : Refines_selected) (h_folded : Refines_folded) (h_transformed_fold : Refines_transformed_fold) : EdgeProp :=
  ⟨source_parses, source_checks, inputs_cover_transformed, raw_eval_transformed, h_transformed, inputs_cover_selected, raw_eval_selected, h_selected, inputs_cover_folded, raw_eval_folded, h_folded, inputs_cover_transformed_fold, raw_eval_transformed_fold, h_transformed_fold, transfer_O1 h_transformed, transfer_O2 h_selected, transfer_O3 h_folded, transfer_O4 h_transformed_fold⟩

end VeriSlopBridgeGoal
