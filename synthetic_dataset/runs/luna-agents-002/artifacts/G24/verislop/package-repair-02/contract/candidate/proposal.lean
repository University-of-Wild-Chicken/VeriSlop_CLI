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

structure State where
  deficits : List Nat
  remaining : List (List (Nat × Nat))
  order : Order
  rounds : Nat
  deriving DecidableEq

def positiveJobs (jobs : List Nat) : Prop :=
  jobs.all (fun size => 0 < size) = true

def positiveFlows (flows : Input) : Prop :=
  flows.all (fun flow => 0 < flow.quantum ∧ positiveJobs flow.jobs) = true

def A1 (flows : Input) : Prop := positiveFlows flows

def indexedJobs (jobs : List Nat) : List (Nat × Nat) :=
  List.zip (List.range jobs.length) jobs

def initialState (flows : Input) : State :=
  { deficits := flows.map (fun _ => 0)
    remaining := flows.map (fun flow => indexedJobs flow.jobs)
    order := []
    rounds := 0 }

def allDone (remaining : List (List (Nat × Nat))) : Bool :=
  remaining.all (fun jobs => jobs.isEmpty)

def sendCovered (flowIndex : Nat) (jobs : List (Nat × Nat)) (deficit : Nat) : Nat × List (Nat × Nat) × Order :=
  jobs.foldl
    (fun acc packet =>
      let (left, pending, emitted) := acc
      match pending with
      | [] => acc
      | head :: tail =>
        if left < head.2 then acc
        else (left - head.2, tail, emitted ++ [(flowIndex, head.1)]))
    (deficit, jobs, [])

def visitFlows (flows : Input) (deficits : List Nat)
    (remaining : List (List (Nat × Nat))) : List Nat × List (List (Nat × Nat)) × Order :=
  let indexed := List.zip3 (List.range flows.length) flows (List.zip deficits remaining)
  indexed.foldl
    (fun acc item =>
      let (ds, js, emitted) := acc
      let (index, flow, pair) := item
      let (deficit, jobs) := pair
      if flow.jobs.isEmpty then (ds ++ [0], js ++ [[]], emitted)
      else
        let (left, restJobs, sent) := sendCovered index jobs (deficit + flow.quantum)
        (ds ++ [left], js ++ [restJobs], emitted ++ sent))
    ([], [], [])

def roundOnce (flows : Input) (state : State) : State :=
  let (deficits, remaining, emitted) := visitFlows flows state.deficits state.remaining
  { deficits := deficits
    remaining := remaining
    order := state.order ++ emitted
    rounds := state.rounds + 1 }

def packetBound (flows : Input) : Nat :=
  flows.foldl (fun total flow => total + flow.jobs.foldl (fun n size => n + size) 0) 0

def runRounds (flows : Input) (state : State) : State :=
  (List.range (packetBound flows + 1)).foldl
    (fun current _ => if allDone current.remaining then current else roundOnce flows current)
    state

def reference (flows : Input) : Output :=
  let result := runRounds flows (initialState flows)
  { order := result.order, rounds := result.rounds }

def solve (flows : Input) : Output := reference flows

theorem G1 : ∀ flows : Input, (solve flows).order = (reference flows).order := by sorry

theorem G2 : (solve ([] : Input)).order = [] ∧ (solve ([] : Input)).rounds = 0 := by sorry

theorem I1 : ∀ flows : Input, ∀ state : State,
  roundOnce flows state =
    { deficits := (visitFlows flows state.deficits state.remaining).1
      remaining := (visitFlows flows state.deficits state.remaining).2.1
      order := state.order ++ (visitFlows flows state.deficits state.remaining).2.2
      rounds := state.rounds + 1 } := by sorry

theorem R1 : ∀ flows : Input, solve flows = reference flows := by sorry

theorem E1 : ∀ flows : Input, A1 flows → solve flows = reference flows := by sorry

theorem A1_nonvacuous : ∃ flows : Input, A1 flows := by sorry

end G24
