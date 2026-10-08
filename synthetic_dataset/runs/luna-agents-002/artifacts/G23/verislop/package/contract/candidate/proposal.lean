import Std

namespace VeriSlop

structure Request where
  time : Nat
  amount : Nat
  deriving Repr, DecidableEq

structure Input where
  capacity : Nat
  period : Nat
  rate : Nat
  requests : List Request
  deriving Repr, DecidableEq

structure Output where
  accepted : List Bool
  balances : List Nat
  denominator : Nat
  deriving Repr, DecidableEq

def validRequests : List Request → Prop
  | [] => True
  | r :: rest =>
      (match rest with
       | [] => True
       | s :: _ => r.time ≤ s.time) ∧ validRequests rest

def A1 (x : Input) : Prop :=
  0 < x.period ∧ validRequests x.requests

def simulate (capacity period rate : Nat) : Nat → Nat → List Request → List Bool × List Nat
  | balance, lastTime, [] => ([], [])
  | balance, lastTime, r :: rest =>
      let cap := capacity * period
      let elapsed := r.time - lastTime
      let refilled := min cap (balance + elapsed * rate)
      let enough := refilled ≥ r.amount * period
      let remaining := if enough then refilled - r.amount * period else refilled
      let (acceptedTail, balancesTail) :=
        simulate capacity period rate remaining r.time rest
      (enough :: acceptedTail, remaining :: balancesTail)

def solve (x : Input) : Output :=
  let (accepted, balances) :=
    simulate x.capacity x.period x.rate (x.capacity * x.period) 0 x.requests
  ⟨accepted, balances, x.period⟩

def hasOutputShape (x : Input) (y : Output) : Prop :=
  y.accepted.length = x.requests.length ∧
  y.balances.length = x.requests.length ∧
  y.denominator = x.period

def acceptedCorrect (x : Input) (y : Output) : Prop :=
  y.accepted = (solve x).accepted

def balancesCorrect (x : Input) (y : Output) : Prop :=
  y.balances = (solve x).balances ∧ y.denominator = x.period

def failedRetains (capacity period rate : Nat) :
    Nat → Nat → List Request → List Bool → List Nat → Prop
  | balance, lastTime, [], [], [] => True
  | balance, lastTime, r :: rest, accepted :: acceptedTail, scaled :: balancesTail =>
      let cap := capacity * period
      let refilled := min cap (balance + (r.time - lastTime) * rate)
      let enough := refilled ≥ r.amount * period
      let remaining := if enough then refilled - r.amount * period else refilled
      (accepted = enough) ∧
      (scaled = remaining) ∧
      ((¬ enough → scaled = refilled) ∧
       failedRetains capacity period rate remaining r.time rest acceptedTail balancesTail)
  | balance, lastTime, _, _, _ => False

def failedRequestRetainsRefilled (x : Input) (y : Output) : Prop :=
  failedRetains x.capacity x.period x.rate (x.capacity * x.period) 0 x.requests
    y.accepted y.balances

def jsonSerializable (y : Output) : Prop :=
  (∀ b, b ∈ y.accepted → b = true ∨ b = false) ∧
  (∀ n, n ∈ y.balances → n = n)

def publicExamplesMatch : Prop :=
  solve ⟨2, 3, 1, [⟨0, 1⟩, ⟨1, 2⟩, ⟨3, 1⟩]⟩ =
      ⟨[true, false, true], [3, 4, 3], 3⟩ ∧
  solve ⟨0, 1, 3, [⟨0, 0⟩, ⟨10, 1⟩]⟩ =
      ⟨[true, false], [0, 0], 1⟩

def exactScaledInvariant (x : Input) (y : Output) : Prop :=
  y.accepted = (solve x).accepted ∧ y.balances = (solve x).balances

opaque pythonStandardLibraryAndNoIO : Prop

theorem O1 (x : Input) (h : A1 x) : hasOutputShape x (solve x) := by sorry
theorem O2 (x : Input) (h : A1 x) : acceptedCorrect x (solve x) := by sorry
theorem O4 (x : Input) (h : A1 x) : balancesCorrect x (solve x) := by sorry
theorem O5 (x : Input) (h : A1 x) : failedRequestRetainsRefilled x (solve x) := by sorry
theorem O7 (x : Input) : jsonSerializable (solve x) := by sorry
theorem O8 : publicExamplesMatch := by sorry
theorem O3 (x : Input) (h : A1 x) : exactScaledInvariant x (solve x) := by sorry
theorem O6 : pythonStandardLibraryAndNoIO := by sorry

theorem A1_nonvacuous : ∃ x : Input, A1 x := by sorry

end VeriSlop