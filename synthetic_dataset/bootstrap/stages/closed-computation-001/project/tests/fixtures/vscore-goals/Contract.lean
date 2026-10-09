namespace VSCoreGoalFixture

inductive Flag where
  | on
  | off
  deriving DecidableEq

def f (n : Nat) := n
def f_iff (n : Nat) := n
def unitResult (_ : Nat) : Unit := ()
def unitConsumer (_ : Unit) : Nat := 0
def g (n : Nat) : Except Flag Nat := .ok n
def combine (x : Nat) (b : Bool) (y : Nat) := if b then x - y else y
def boolIdentity (b : Bool) := b
def enumIdentity (e : Flag) := e
def resultIdentity (r : Except Flag Nat) := r
def nestedResultIdentity (r : Except (Except Flag Nat) (Except Flag Nat)) := r
def zero : Nat := 0
def validInput (n : Nat) : Prop := n ≤ n + 1
def identityProperty (n : Nat) : Prop := f n = n

theorem reflexive (n : Nat) : f n = f n := rfl
theorem nontrivialIff (n : Nat) : f n = f n ↔ f n = n :=
  ⟨fun _ => rfl, fun _ => rfl⟩
theorem implication (n : Nat) : f n = f n → f n = n := fun _ => rfl
theorem predicateAlias (n : Nat) (_ : validInput n) : identityProperty n := rfl
theorem collision (n : Nat) : f n = f_iff n := rfl
theorem unitOutput (n : Nat) : unitResult n = () := rfl
theorem nestedUnit (n : Nat) : unitConsumer (unitResult n) = 0 := rfl

theorem nestedCalls (n : Nat) : g (f n) = .ok n := rfl
theorem argumentOrder (x y : Nat) : combine x true y = x - y := rfl
theorem enumInput (e : Flag) : enumIdentity e = e := rfl
theorem resultInput (r : Except Flag Nat) : resultIdentity r = r := rfl
theorem nestedResultInput (r : Except (Except Flag Nat) (Except Flag Nat)) :
    nestedResultIdentity r = r := rfl
theorem resultError : resultIdentity (.error Flag.off) = .error Flag.off := rfl
theorem holdsBool : boolIdentity true = true := rfl
theorem zeroArity : zero = 0 := rfl
theorem forallRange (n k : Nat) (_ : n ≤ k) (_ : k < n + 1) : f k = k := rfl
theorem existsRange (n : Nat) : ∃ k, n ≤ k ∧ k < n + 1 ∧ f k = k :=
  ⟨n, Nat.le_refl n, Nat.lt_succ_self n, rfl⟩

end VSCoreGoalFixture
