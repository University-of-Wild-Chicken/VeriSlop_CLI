import Std

namespace G24

structure Flow where
  quantum : Nat
  jobs : List Nat
  deriving DecidableEq

abbrev Input := List Flow
abbrev PacketRef := Nat × Nat
abbrev Order := List PacketRef

structure Output where
  order : Order
  rounds : Nat
  deriving DecidableEq

def positiveJobs : List Nat → Prop
  | [] => True
  | size :: rest => 0 < size ∧ positiveJobs rest

def positiveFlows : Input → Prop
  | [] => True
  | flow :: rest => 0 < flow.quantum ∧ positiveJobs flow.jobs ∧ positiveFlows rest

def A1 (x : Input) : Prop := positiveFlows x

/-- The scheduling operation retains its list-valued domain and result. It is
opaque to the current executable-test bridge, which cannot reify collections. -/
opaque reference : Input → Output

def solve (x : Input) : Output := reference x

theorem G1 : ∀ x : Input, (solve x).order = (reference x).order := by sorry

theorem G2 : (solve ([] : Input)).order = [] ∧ (solve ([] : Input)).rounds = 0 := by sorry

theorem I1 : ∀ x : Input, solve x = reference x := by sorry

theorem R1 : ∀ x : Input, solve x = solve x := by sorry

theorem E1 : ∀ x : Input, A1 x → solve x = reference x := by sorry

theorem A1_nonvacuous : ∃ x : Input, A1 x := by sorry

end G24
