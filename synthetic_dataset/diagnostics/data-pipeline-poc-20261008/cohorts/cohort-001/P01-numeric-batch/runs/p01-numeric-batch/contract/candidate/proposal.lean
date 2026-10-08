import Std

namespace VeriSlop.Contract

structure Input where
  values : List Int
  minimum : Int
  factor : Int

structure Output where
  values : List Int
  total : Int
  count : Int

def solve (data : Input) : Output :=
  let kept : List Int := data.values.filter (fun v => v >= data.minimum)
  let scaled : List Int := kept.map (fun v => v * data.factor)
  { values := scaled, total := scaled.sum, count := scaled.length }

theorem O1_filtering (data : Input) :
  (solve data).values = (data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor) := by sorry

theorem O2_multiplication (data : Input) :
  (solve data).values = (data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor) := by sorry

theorem O3_output_shape (data : Input) :
  (solve data).values = (data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor) ∧
  (solve data).total = ((data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor)).sum ∧
  (solve data).count = ((data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor)).length := by sorry

theorem O4_output_values (data : Input) :
  (solve data).values = (data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor) := by sorry

theorem O5_output_total (data : Input) :
  (solve data).total = ((data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor)).sum := by sorry

theorem O6_output_count (data : Input) :
  (solve data).count = ((data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor)).length := by sorry

theorem O7_empty_result (data : Input) :
  (data.values.filter (fun v => v >= data.minimum)).length = 0 →
    (solve data).values = [] ∧ (solve data).total = 0 ∧ (solve data).count = 0 := by sorry

theorem I1_exact_int_arithmetic (data : Input) :
  (solve data).values = (data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor) ∧
  (solve data).total = ((data.values.filter (fun v => v >= data.minimum)).map (fun v => v * data.factor)).sum := by sorry

end VeriSlop.Contract