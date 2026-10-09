import Std

namespace SignedFloorSum

structure Input where
  «n» : Int
  «m» : Int
  «a» : Int
  «b» : Int

abbrev Output := Int

def valid (data : Input) : Prop :=
  0 ≤ data.n ∧ data.n ≤ 500 ∧ 0 < data.m

def solve (data : Input) : Output :=
  (List.range data.n.toNat).foldl
    (fun total i => total + Int.fdiv (data.a * Int.ofNat i + data.b) data.m) (0 : Int)

theorem mathematical_specification : ∀ data : Input, valid data →
  solve data = ((List.range data.n.toNat).map (fun i => Int.fdiv (data.a * Int.ofNat i + data.b) data.m)).sum ∧
  (∀ i : Nat, i < data.n.toNat →
    ∀ q : Int,
      (q * data.m ≤ data.a * Int.ofNat i + data.b ∧
       data.a * Int.ofNat i + data.b < (q + 1) * data.m) ↔
      q = Int.fdiv (data.a * Int.ofNat i + data.b) data.m) ∧
  (data.n = 0 → solve data = (0 : Int)) ∧
  solve { «n» := 4, «m» := 3, «a» := -2, «b» := 1 } = (-4 : Int) ∧
  solve { «n» := 0, «m» := 7, «a» := 100, «b» := -99 } = (0 : Int) := by sorry

theorem total_deterministic_execution : ∀ data : Input, valid data →
  ∃ result : Output,
    solve data = result ∧
    result = ((List.range data.n.toNat).map (fun i => Int.fdiv (data.a * Int.ofNat i + data.b) data.m)).sum ∧
    (∀ other : Output, solve data = other → other = result) := by sorry

theorem pure_execution : ∀ data : Input,
  solve data = ((List.range data.n.toNat).map (fun i => Int.fdiv (data.a * Int.ofNat i + data.b) data.m)).sum := by sorry

theorem exact_integer_arithmetic : ∀ data : Input, valid data →
  solve data = ((List.range data.n.toNat).map (fun i => Int.fdiv (data.a * Int.ofNat i + data.b) data.m)).sum ∧
  (∀ i : Nat, i < data.n.toNat →
    ∃ q : Int,
      q = Int.fdiv (data.a * Int.ofNat i + data.b) data.m ∧
      q * data.m ≤ data.a * Int.ofNat i + data.b ∧
      data.a * Int.ofNat i + data.b < (q + 1) * data.m) := by sorry

theorem valid_input_exists : ∃ data : Input, valid data := by sorry

end SignedFloorSum
