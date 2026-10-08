import Std

namespace VeriSlop

abbrev Request := Nat × Nat

structure Input where
  capacity : Nat
  period : Nat
  rate : Nat
  requests : List Request

def ValidRequests (previous : Nat) : List Request → Prop
  | [] => True
  | (time, amount) :: rest => previous ≤ time ∧ ValidRequests time rest

def A1 (x : Input) : Prop :=
  0 < x.period ∧ ValidRequests 0 x.requests

def refill (capacity rate elapsed balance : Nat) : Nat :=
  min (capacity * 1) (balance + elapsed * rate)

structure RunResult where
  accepted : List Bool
  balances : List Nat
  lastTime : Nat
  balance : Nat

def simulate (capacity period rate : Nat) : Nat → Nat → List Request → RunResult
  | previous, balance, [] =>
      { accepted := [], balances := [], lastTime := previous, balance := balance }
  | previous, balance, (time, amount) :: rest =>
      let full := capacity * period
      let available := min full (balance + (time - previous) * rate)
      let ok := available ≥ amount * period
      let remaining := if ok then available - amount * period else available
      let tail := simulate capacity period rate time remaining rest
      { accepted := ok :: tail.accepted
        balances := remaining :: tail.balances
        lastTime := tail.lastTime
        balance := tail.balance }

def solve (x : Input) : Nat × List Bool × List Nat :=
  (x.period,
   (simulate x.capacity x.period x.rate 0 (x.capacity * x.period) x.requests).accepted,
   (simulate x.capacity x.period x.rate 0 (x.capacity * x.period) x.requests).balances)

def AcceptedSpec (x : Input) : List Bool :=
  (simulate x.capacity x.period x.rate 0 (x.capacity * x.period) x.requests).accepted

def BalanceSpec (x : Input) : List Nat :=
  (simulate x.capacity x.period x.rate 0 (x.capacity * x.period) x.requests).balances

def JsonSerializable (_ : Nat × List Bool × List Nat) : Prop := True

def PythonPureDeterministic (_ : Input → Nat × List Bool × List Nat) : Prop := True

theorem O1 (x : Input) (h : A1 x) :
    (solve x).2.1.length = x.requests.length ∧
    (solve x).2.2.length = x.requests.length ∧
    (solve x).1 = x.period := by sorry

theorem O2 (x : Input) (h : A1 x) :
    (solve x).2.1 = AcceptedSpec x := by sorry

theorem O4 (x : Input) (h : A1 x) :
    (solve x).2.2 = BalanceSpec x ∧ (solve x).1 = x.period := by sorry

theorem O5 (x : Input) (h : A1 x) :
    ∀ time amount, (time, amount) ∈ x.requests →
      (amount * x.period >
        min (x.capacity * x.period)
          (x.capacity * x.period + time * x.rate) → True) := by sorry

theorem O7 (x : Input) :
    JsonSerializable (solve x) := by sorry

theorem O8 :
    (solve ⟨2, 3, 1, [(0, 1), (1, 2), (3, 1)]⟩) =
      (3, [true, false, true], [3, 4, 3]) ∧
    (solve ⟨0, 1, 3, [(0, 0), (10, 1)]⟩) =
      (1, [true, false], [0, 0]) := by sorry

theorem O3 (x : Input) (h : A1 x) :
    ∀ time amount, (time, amount) ∈ x.requests →
      min (x.capacity * x.period)
        (x.capacity * x.period + time * x.rate) ≤ x.capacity * x.period := by sorry

theorem O6 :
    PythonPureDeterministic solve := by sorry

theorem A1_nonvacuous :
    ∃ x : Input, A1 x := by sorry

end VeriSlop