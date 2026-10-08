import Std

namespace VeriSlop.Contract

structure Input where
  «labels» : List String
  «prefix» : String

structure Output where
  «labels» : List String
  «count» : Nat

def solve (data : Input) : Output :=
  let kept : List String := data.「labels」.filter (fun s => !s.isEmpty)
  let mapped : List String := kept.map (fun s => data.「prefix」 ++ s)
  { 「labels」 := mapped, 「count」 := mapped.length }

def valid_input (data : Input) : Prop := True

theorem O1_output_shape (data : Input) (hA1 : valid_input data) :
  (solve data).「count」 = (solve data).「labels」.length := by sorry

theorem O2_labels_transform (data : Input) (hA1 : valid_input data) :
  (solve data).「labels」 = (data.「labels」.filter (fun s => !s.isEmpty)).map (fun s => data.「prefix」 ++ s) := by sorry

theorem O3_count_equals_length (data : Input) :
  (solve data).「count」 = (solve data).「labels」.length := by sorry

theorem O4_empty_result (data : Input) :
  (data.「labels」.filter (fun s => !s.isEmpty)).length = 0 →
    (solve data).「labels」 = [] ∧ (solve data).「count」 = 0 := by sorry

theorem O5_unicode_preserved (data : Input) (hA1 : valid_input data) :
  ∀ (s : String), s ∈ data.「labels」 → s ≠ "" → (data.「prefix」 ++ s) ∈ (solve data).「labels」 := by sorry

theorem witnesses_for_A1 : ∃ (data : Input), valid_input data := by sorry

end VeriSlop.Contract