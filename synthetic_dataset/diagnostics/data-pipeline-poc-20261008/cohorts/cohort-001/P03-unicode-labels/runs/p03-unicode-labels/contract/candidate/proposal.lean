import Std

namespace VeriSlop.Contract

structure Input where
  labels : List String
  prefix : String

structure Output where
  labels : List String
  count : Nat

def solve (data : Input) : Output :=
  let kept : List String := List.filter (fun s => s != "") data.labels
  { labels := List.map (fun s => data.prefix ++ s) kept, count := List.length kept }

def valid_input (data : Input) : Prop := True

theorem O1_filter_nonempty (data : Input) (h : valid_input data) :
  solve data.labels = List.map (fun s => data.prefix ++ s) (List.filter (fun s => s != "") data.labels) := by sorry

theorem O2_concatenation (data : Input) (h : valid_input data) :
  solve data.labels = { labels := List.map (fun s => data.prefix ++ s) (List.filter (fun s => s != "") data.labels),
                        count := List.length (List.filter (fun s => s != "") data.labels) } := by sorry

theorem O3_unicode_preserved (data : Input) (h : valid_input data) :
  solve data.labels = { labels := List.map (fun s => data.prefix ++ s) (List.filter (fun s => s != "") data.labels),
                        count := List.length (List.filter (fun s => s != "") data.labels) } := by sorry

theorem O4_empty_result (data : Input) (h : valid_input data) :
  (List.filter (fun s => s != "") data.labels = []) → solve data.labels = { labels := [], count := 0 } := by sorry

theorem O5_empty_prefix (data : Input) (h : valid_input data) :
  data.prefix = "" → solve data.labels = { labels := List.filter (fun s => s != "") data.labels,
                                            count := List.length (List.filter (fun s => s != "") data.labels) } := by sorry

theorem witnesses_for_A1 : ∃ (data : Input), valid_input data := by sorry

end VeriSlop.Contract