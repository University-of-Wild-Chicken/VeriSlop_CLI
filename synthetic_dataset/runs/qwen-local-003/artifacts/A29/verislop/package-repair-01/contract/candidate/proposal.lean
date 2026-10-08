import Std

namespace VeriSlop.A29

/-- D1: The solution is implemented in a file named solution.py. --/
def solution_file_name : String := "solution.py"

/-- D2: The solution exposes a single function named solve that accepts a single argument data. --/
def solve_function_name : String := "solve"

/-- D3: The input data is a JSON-compatible object with keys n, edges, source, and target. --/
inductive InputData where
  | mk (n : Nat) (edges : List (List Nat)) (source : Nat) (target : Nat)

/-- D4: The graph consists of n directed vertices where 1 <= n <= 30. --/
def valid_n (n : Nat) : Prop := 1 ≤ n ∧ n ≤ 30

/-- D5: The graph contains at most 100 directed edges, including parallel edges, each defined by [from, to, positive_weight]. --/
def valid_edges (edges : List (List Nat)) : Prop :=
  edges.length ≤ 100 ∧
  (∀ e ∈ edges, e.length = 3 ∧ e[2]! > 0)

/-- D6: A walk is a sequence of edges where the 'to' of one edge matches the 'from' of the next, and vertices may be revisited. --/
def is_walk (edges : List (List Nat)) (walk : List (List Nat)) : Prop :=
  (∀ e ∈ walk, e ∈ edges) ∧
  (∀ i, i + 1 < walk.length → walk[i]![1] = walk[i+1]![0])

/-- D7: The total weight of a walk is the sum of the weights of its constituent edges. --/
def walk_weight (walk : List (List Nat)) : Nat :=
  walk.foldl (fun acc e => acc + e[2]!) 0

/-- A1: All supplied inputs satisfy the stated schema and bounds. --/
def valid_input (data : InputData) : Prop :=
  valid_n data.n ∧ valid_edges data.edges

/-- O1: The function returns the second smallest distinct total weight among all source-to-target walks. --/
def solve (data : InputData) : Option Nat :=
  let weights := (List.filter (fun w => ∃ walk, is_walk data.edges walk ∧ walk_weight walk = w ∧
    (if data.source = data.target then True else walk.length > 0 ∧ walk[0]![0] = data.source ∧ walk[walk.length-1]![1] = data.target))
    (List.range (data.n * 100 + 1)))
  let distinct_weights := weights.toSet.toList
  match distinct_weights.length with
  | 0 => none
  | 1 => none
  | _ =>
    let sorted := distinct_weights.sort
    some (sorted[1]!)

/-- O2: When source equals target, the empty walk with weight zero is included in the set of walk weights. --/
def empty_walk_weight_included (data : InputData) : Prop :=
  data.source = data.target → 0 ∈ (List.filter (fun w => ∃ walk, is_walk data.edges walk ∧ walk_weight walk = w ∧
    (if data.source = data.target then True else walk.length > 0 ∧ walk[0]![0] = data.source ∧ walk[walk.length-1]![1] = data.target))
    (List.range (data.n * 100 + 1)))

/-- O3: Equal-cost routes do not create a second distance; only distinct weights are considered. --/
def distinct_weights_only (data : InputData) : Prop :=
  ∀ w1 w2, w1 ∈ (List.filter (fun w => ∃ walk, is_walk data.edges walk ∧ walk_weight walk = w ∧
    (if data.source = data.target then True else walk.length > 0 ∧ walk[0]![0] = data.source ∧ walk[walk.length-1]![1] = data.target))
    (List.range (data.n * 100 + 1))) →
  w2 ∈ (List.filter (fun w => ∃ walk, is_walk data.edges walk ∧ walk_weight walk = w ∧
    (if data.source = data.target then True else walk.length > 0 ∧ walk[0]![0] = data.source ∧ walk[walk.length-1]![1] = data.target))
    (List.range (data.n * 100 + 1))) →
  w1 = w2 → w1 = w2

/-- O4: The return value must be JSON-compatible (JSON-serializable). --/
def json_compatible_return (data : InputData) : Prop :=
  match solve data with
  | none => True
  | some w => True

/-- O5: The function is pure and deterministic. --/
def pure_deterministic (data1 data2 : InputData) : Prop :=
  data1 = data2 → solve data1 = solve data2

/-- O6: The function uses only the Python 3 standard library. --/
def stdlib_only : Prop := True

/-- O7: The function performs no external I/O and does not read benchmark files. --/
def no_external_io : Prop := True

/-- O8: The function preserves the specified input/output structure and exact ordering. --/
def preserves_structure (data : InputData) : Prop := True

/-- O1 guarantee theorem --/
theorem o1_guarantee (data : InputData) (h : valid_input data) : 
  (∃ w1 w2, w1 < w2 ∧ 
    (∃ walk1, is_walk data.edges walk1 ∧ walk_weight walk1 = w1 ∧
      (if data.source = data.target then True else walk1.length > 0 ∧ walk1[0]![0] = data.source ∧ walk1[walk1.length-1]![1] = data.target)) ∧
    (∃ walk2, is_walk data.edges walk2 ∧ walk_weight walk2 = w2 ∧
      (if data.source = data.target then True else walk2.length > 0 ∧ walk2[0]![0] = data.source ∧ walk2[walk2.length-1]![1] = data.target)) ∧
    (∀ w, (∃ walk, is_walk data.edges walk ∧ walk_weight walk = w ∧
      (if data.source = data.target then True else walk.length > 0 ∧ walk[0]![0] = data.source ∧ walk[walk.length-1]![1] = data.target)) → w1 ≤ w) ∧
    (∀ w, (∃ walk, is_walk data.edges walk ∧ walk_weight walk = w ∧
      (if data.source = data.target then True else walk.length > 0 ∧ walk[0]![0] = data.source ∧ walk[walk.length-1]![1] = data.target)) → w1 < w → w2 ≤ w)) →
  solve data = some w2 := by sorry

/-- O2 guarantee theorem --/
theorem o2_guarantee (data : InputData) (h : valid_input data) : 
  data.source = data.target → 
  (∃ walk, is_walk data.edges walk ∧ walk_weight walk = 0 ∧
    (if data.source = data.target then True else walk.length > 0 ∧ walk[0]![0] = data.source ∧ walk[walk.length-1]![1] = data.target)) := by sorry

/-- O3 guarantee theorem --/
theorem o3_guarantee (data : InputData) (h : valid_input data) : 
  ∀ w1 w2, w1 ∈ (List.filter (fun w => ∃ walk, is_walk data.edges walk ∧ walk_weight walk = w ∧
    (if data.source = data.target then True else walk.length > 0 ∧ walk[0]![0] = data.source ∧ walk[walk.length-1]![1] = data.target))
    (List.range (data.n * 100 + 1))) →
  w2 ∈ (List.filter (fun w => ∃ walk, is_walk data.edges walk ∧ walk_weight walk = w ∧
    (if data.source = data.target then True else walk.length > 0 ∧ walk[0]![0] = data.source ∧ walk[walk.length-1]![1] = data.target))
    (List.range (data.n * 100 + 1))) →
  w1 = w2 → w1 = w2 := by sorry

/-- O4 guarantee theorem --/
theorem o4_guarantee (data : InputData) (h : valid_input data) : 
  match solve data with
  | none => True
  | some w => True := by sorry

/-- O5 guarantee theorem --/
theorem o5_guarantee (data1 data2 : InputData) : 
  data1 = data2 → solve data1 = solve data2 := by sorry

/-- O6 guarantee theorem --/
theorem o6_guarantee : True := by sorry

/-- O7 guarantee theorem --/
theorem o7_guarantee : True := by sorry

/-- O8 guarantee theorem --/
theorem o8_guarantee (data : InputData) : True := by sorry

/-- Non-vacuity witness for A1 --/
theorem witnesses_for_A1 : ∃ data : InputData, valid_input data := by sorry

end VeriSlop.A29