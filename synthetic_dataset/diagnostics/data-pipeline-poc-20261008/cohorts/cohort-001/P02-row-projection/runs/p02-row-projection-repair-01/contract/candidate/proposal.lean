import Std

namespace Contract

structure Row where
  tag : String
  amount : Int
  enabled : Bool

structure Input where
  rows : List Row
  minimum : Int

structure OutRow where
  tag : String
  amount : Int

structure Output where
  rows : List OutRow
  total : Int
  count : Nat

def solve (data : Input) : Output :=
  let retained : List Row := data.rows.filter (fun r => r.enabled && r.amount >= data.minimum)
  let outRows : List OutRow := retained.map (fun r => { tag := r.tag, amount := r.amount })
  let total : Int := retained.foldl (fun acc r => acc + r.amount) 0
  { rows := outRows, total := total, count := retained.length }

theorem O1_output_shape (data : Input) :
  ∃ (out : Output), out = solve data := by sorry

theorem O2_retained_rows (data : Input) :
  (solve data).rows = (data.rows.filter (fun r => r.enabled && r.amount >= data.minimum)).map (fun r => { tag := r.tag, amount := r.amount }) := by sorry

theorem O3_row_projection (data : Input) :
  ((solve data).rows).map (fun o => o.tag) = (data.rows.filter (fun r => r.enabled && r.amount >= data.minimum)).map (fun r => r.tag) ∧
  ((solve data).rows).map (fun o => o.amount) = (data.rows.filter (fun r => r.enabled && r.amount >= data.minimum)).map (fun r => r.amount) := by sorry

theorem O4_total_and_count (data : Input) :
  (solve data).total = (data.rows.filter (fun r => r.enabled && r.amount >= data.minimum)).map (fun r => r.amount).sum ∧
  (solve data).count = (data.rows.filter (fun r => r.enabled && r.amount >= data.minimum)).length := by sorry

theorem O5_empty_result (data : Input) :
  (data.rows.filter (fun r => r.enabled && r.amount >= data.minimum)).length = 0 →
  (solve data).rows = [] ∧ (solve data).total = 0 ∧ (solve data).count = 0 := by sorry

theorem I1_exact_int_arithmetic (data : Input) :
  (solve data).total = (data.rows.filter (fun r => r.enabled && r.amount >= data.minimum)).map (fun r => r.amount).sum := by sorry

theorem I2_unicode_preservation (data : Input) :
  ((solve data).rows).map (fun o => o.tag) = (data.rows.filter (fun r => r.enabled && r.amount >= data.minimum)).map (fun r => r.tag) := by sorry

end Contract