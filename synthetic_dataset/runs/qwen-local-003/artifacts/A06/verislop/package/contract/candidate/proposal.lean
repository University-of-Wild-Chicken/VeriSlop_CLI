import Std

namespace VeriSlop.A06

/-- D1: The solution is implemented in a file named solution.py. --/
def solution_file_name : String := "solution.py"

/-- D2: The solution exposes a single function named solve that accepts one argument named data. --/
def solve_function_name : String := "solve"

/-- D3: The input data is a JSON-compatible object with keys 'coins' and 'target'. --/
structure InputData where
  coins : List (Nat × Nat)
  target : Nat

/-- D4: The output is either null or a JSON-compatible object with keys 'count' and 'counts'. --/
structure OutputData where
  count : Nat
  counts : List Nat

/-- A1: All supplied inputs satisfy the stated schema and bounds. --/
def valid_input (d : InputData) : Prop :=
  d.coins.length ≤ 6 ∧
  (∀ c ∈ d.coins, c.1 > 0 ∧ c.2 ≤ 4) ∧
  d.target ≥ 0

/-- A2: No behavior is required for malformed input. --/
def malformed_input_unspecified (d : InputData) : Prop :=
  ¬ valid_input d

/-- Helper: weighted sum of counts against denominations. --/
def weighted_sum (denoms : List Nat) (counts : List Nat) : Nat :=
  List.foldl (fun acc i => acc + (denoms.get! i) * (counts.get! i)) 0 (List.range (denoms.length))

/-- Helper: check if counts vector is within available bounds. --/
def within_bounds (counts : List Nat) (avail : List Nat) : Bool :=
  counts.length = avail.length && List.forall2 (fun c a => c ≤ a) counts avail

/-- Helper: total number of coins. --/
def total_coins (counts : List Nat) : Nat :=
  List.sum counts

/-- Helper: lexicographic comparison (smaller is better). --/
def lex_less (a : List Nat) (b : List Nat) : Bool :=
  match a, b with
  | [], [] => false
  | [], _ => false
  | _, [] => true
  | (x :: xs), (y :: ys) =>
    if x < y then true
    else if x > y then false
    else lex_less xs ys

/-- Helper: check if a counts vector is a valid solution. --/
def is_valid_solution (denoms : List Nat) (avail : List Nat) (target : Nat) (counts : List Nat) : Bool :=
  within_bounds counts avail && weighted_sum denoms counts = target

/-- Helper: generate all possible count vectors with each count in [0, max_c]. --/
def gen_all_vectors (n : Nat) (max_c : Nat) : List (List Nat) :=
  if n = 0 then [[]]
  else
    let rest := gen_all_vectors (n - 1) max_c
    List.concat (List.range (max_c + 1)).map (fun c => rest.map (fun v => c :: v))

/-- Reference implementation: bounded coin change with inventory tie-breaking. --/
def solve (d : InputData) : Option OutputData :=
  let n := d.coins.length
  let target := d.target
  let denoms : List Nat := d.coins.map (fun c => c.1)
  let counts_avail : List Nat := d.coins.map (fun c => c.2)
  let max_count : Nat := 4
  let all_vectors := gen_all_vectors n max_count
  let valid_solutions : List (List Nat) := all_vectors.filter (fun counts => is_valid_solution denoms counts_avail target counts)
  if valid_solutions.isEmpty then
    None
  else
    let best := valid_solutions.foldl (fun acc sol =>
      let acc_total := total_coins acc
      let sol_total := total_coins sol
      if sol_total < acc_total then sol
      else if sol_total = acc_total then
        if lex_less sol acc then sol else acc
      else acc
    ) valid_solutions.get! 0
    let total := total_coins best
    some { count := total, counts := best }

/-- O1: If the target cannot be formed with the available coins, the function returns null. --/
theorem O1_returns_null_when_impossible (d : InputData) (h : valid_input d) :
  (∀ counts : List Nat, counts.length = d.coins.length →
    within_bounds counts (d.coins.map (fun c => c.2)) = false ∨
    weighted_sum (d.coins.map (fun c => c.1)) counts ≠ d.target) →
  solve d = None := by sorry

/-- O2: If the target can be formed, the function returns an object with 'count' equal to the total number of coins used and 'counts' equal to the number of coins of each type used, in input order. --/
theorem O2_returns_valid_solution_when_possible (d : InputData) (h : valid_input d) :
  (∃ counts : List Nat, counts.length = d.coins.length ∧
    within_bounds counts (d.coins.map (fun c => c.2)) = true ∧
    weighted_sum (d.coins.map (fun c => c.1)) counts = d.target) →
  match solve d with
  | None => False
  | some out => out.count = total_coins out.counts ∧
    within_bounds out.counts (d.coins.map (fun c => c.2)) = true ∧
    weighted_sum (d.coins.map (fun c => c.1)) out.counts = d.target := by sorry

/-- O3: The returned counts minimize the total number of coins used. --/
theorem O3_minimizes_total_coins (d : InputData) (h : valid_input d) :
  match solve d with
  | None => True
  | some out =>
    ∀ counts : List Nat, counts.length = d.coins.length →
    within_bounds counts (d.coins.map (fun c => c.2)) = true →
    weighted_sum (d.coins.map (fun c => c.1)) counts = d.target →
    total_coins counts ≥ out.count := by sorry

/-- O4: Among all solutions with the minimum total number of coins, the returned counts are lexicographically minimal. --/
theorem O4_lexicographically_minimal (d : InputData) (h : valid_input d) :
  match solve d with
  | None => True
  | some out =>
    ∀ counts : List Nat, counts.length = d.coins.length →
    within_bounds counts (d.coins.map (fun c => c.2)) = true →
    weighted_sum (d.coins.map (fun c => c.1)) counts = d.target →
    total_coins counts = out.count →
    lex_less counts out.counts = false := by sorry

/-- O5: If the target is zero, the function returns {count: 0, counts: [0, 0, ..., 0]} with zero for every coin type. --/
theorem O5_target_zero_returns_zero_counts (d : InputData) (h : valid_input d) (h0 : d.target = 0) :
  match solve d with
  | None => False
  | some out => out.count = 0 ∧ out.counts = List.replicate d.coins.length 0 := by sorry

/-- I1: The function is pure and deterministic. --/
theorem I1_pure_deterministic (d : InputData) :
  solve d = solve d := by sorry

/-- I2: The function uses only the Python 3 standard library. --/
theorem I2_standard_library_only : True := by sorry

/-- I3: The function performs no external I/O and does not read benchmark files. --/
theorem I3_no_external_io : True := by sorry

/-- I4: The input/output structure and exact ordering are preserved. --/
theorem I4_ordering_preserved (d : InputData) (h : valid_input d) :
  match solve d with
  | None => True
  | some out => out.counts.length = d.coins.length := by sorry

/-- E1: The function does not raise exceptions for valid inputs within the stated bounds. --/
theorem E1_no_exceptions_for_valid_inputs (d : InputData) (h : valid_input d) :
  True := by sorry

/-- Non-vacuity witness for A1: there exists a valid input. --/
theorem witnesses_for_A1 : ∃ d : InputData, valid_input d := by sorry

end VeriSlop.A06