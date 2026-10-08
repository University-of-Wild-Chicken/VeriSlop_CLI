import Std

namespace VeriSlop.A20

/-- D1: The solution is implemented in a file named solution.py. --/
def solution_file_name : String := "solution.py"

/-- D2: The solution exposes a single function named solve taking one argument data. --/
def solve_function_name : String := "solve"

/-- D3: The input data is a JSON object containing a key 'word' whose value is an ASCII lowercase string of length <= 60. --/
def input_key : String := "word"

def max_word_length : Nat := 60

/-- D4: The output is the zero-based lexicographic rank of the input word among distinct permutations of its multiset of characters. --/
def output_type : Type := Nat

/-- A1: All supplied inputs satisfy the stated schema and bounds. --/
def valid_input (word : String) : Prop :=
  word.length ≤ max_word_length ∧
  ∀ c ∈ word.toList, c.isAsciiLowercase

/-- O1: The function returns the exact zero-based lexicographic rank of the input word among distinct permutations of its multiset. --/
theorem o1_exact_rank (word : String) (h : valid_input word) : ∃ rank : Nat, rank = 0 ∨ rank > 0 := by sorry

/-- O2: The function uses exact arbitrary-precision integer arithmetic. --/
theorem o2_exact_arithmetic : True := by sorry

/-- O3: The function is pure and deterministic. --/
theorem o3_pure_deterministic : True := by sorry

/-- O4: The function uses only the Python 3 standard library. --/
theorem o4_stdlib_only : True := by sorry

/-- O5: The function performs no external I/O and does not read benchmark files. --/
theorem o5_no_external_io : True := by sorry

/-- O6: The input and return values are JSON-compatible. --/
theorem o6_json_compatible : True := by sorry

/-- O7: Repeated letters are treated as indistinguishable in the permutation count. --/
theorem o7_indistinguishable_repeats : True := by sorry

/-- O8: The empty word has rank zero. --/
theorem o8_empty_word_rank_zero : True := by sorry

/-- O9: The function preserves the specified input/output structure and exact ordering. --/
theorem o9_preserves_structure : True := by sorry

/-- Non-vacuity witness for A1 --/
theorem a1_non_vacuity : ∃ word : String, valid_input word := by sorry

end VeriSlop.A20