import Std

namespace G24

/-- Packet sequences are represented explicitly; packet sizes are positive naturals by A1. -/
inductive Packets where
  | nil : Packets
  | cons : Nat → Packets → Packets

inductive Flows where
  | nil : Flows
  | cons : Nat → Packets → Flows → Flows

inductive Entries where
  | nil : Entries
  | cons : Nat → Nat → Entries → Entries

structure Input where
  flows : Flows

structure Output where
  order : Entries
  rounds : Nat

def positivePackets : Packets → Prop
  | .nil => True
  | .cons size rest => 0 < size ∧ positivePackets rest

def positiveFlows : Flows → Prop
  | .nil => True
  | .cons quantum jobs rest => 0 < quantum ∧ positivePackets jobs ∧ positiveFlows rest

def A1 (x : Input) : Prop := positiveFlows x.flows

def countPackets : Packets → Nat
  | .nil => 0
  | .cons _ rest => 1 + countPackets rest

def countFlows : Flows → Nat
  | .nil => 0
  | .cons _ _ rest => 1 + countFlows rest

def totalJobs : Flows → Nat
  | .nil => 0
  | .cons _ jobs rest => countPackets jobs + totalJobs rest

def getFlow : Flows → Nat → Option (Nat × Packets)
  | .nil, _ => none
  | .cons quantum jobs _, 0 => some (quantum, jobs)
  | .cons _ _ rest, index + 1 => getFlow rest index

def updateFlow : Flows → Nat → Packets → Flows
  | .nil, _, _ => .nil
  | .cons quantum _ rest, 0, jobs => .cons quantum jobs rest
  | .cons quantum jobs rest, index + 1, replacement => .cons quantum jobs (updateFlow rest index replacement)

def emitCovered : Nat → Nat → Packets → Nat × Packets × Entries
  | _, _, .nil => (0, .nil, .nil)
  | deficit, index, .cons size rest =>
      if size ≤ deficit then
        let tail := emitCovered (deficit - size) (index + 1) rest
        (deficit - size, tail.2.1, .cons index 0 tail.2.2)
      else
        (deficit, .cons size rest, .nil)

def visitFlows : Flows → Nat → Nat → Entries × Flows
  | .nil, _, _ => (.nil, .nil)
  | .cons quantum jobs rest, deficit, flowIndex =>
      match jobs with
      | .nil =>
          let tail := visitFlows rest (deficit + 1) (flowIndex + 1)
          (tail.1, .cons quantum .nil tail.2)
      | .cons _ _ _ =>
          let emitted := emitCovered (deficit + quantum) flowIndex jobs
          let tail := visitFlows rest (emitted.1 + 1) (flowIndex + 1)
          (appendEntries emitted.2.2 tail.1, .cons quantum emitted.2.1 tail.2)
where
  appendEntries : Entries → Entries → Entries
    | .nil, ys => ys
    | .cons flow job rest, ys => .cons flow job (appendEntries rest ys)

def appendEntryLists : Entries → Entries → Entries
  | .nil, ys => ys
  | .cons flow job rest, ys => .cons flow job (appendEntryLists rest ys)

def scheduleFuel : Nat → Flows → Nat → Entries → Nat → Output
  | 0, flows, _, order, rounds => ⟨order, rounds⟩
  | fuel + 1, flows, deficit, order, rounds =>
      if totalJobs flows = 0 then ⟨order, rounds⟩ else
        let visited := visitFlows flows deficit 0
        let nextOrder := appendEntryLists order visited.1
        let nextFlows := visited.2
        if totalJobs nextFlows = 0 then ⟨nextOrder, rounds + 1⟩
        else scheduleFuel fuel nextFlows deficit nextOrder (rounds + 1)

def solve (x : Input) : Output :=
  scheduleFuel (totalJobs x.flows + 1) x.flows 0 .nil 0

theorem G1 : ∀ x : Input, A1 x → ∃ order rounds, (solve x).order = order ∧ (solve x).rounds = rounds := by sorry

theorem G2 : ∀ x : Input, totalJobs x.flows = 0 → (solve x).order = .nil ∧ (solve x).rounds = 0 := by sorry

theorem I1 : ∀ x : Input, A1 x → ∃ order rounds, (solve x).order = order ∧ (solve x).rounds = rounds := by sorry

theorem R1 : ∀ x : Input, solve x = solve x := by sorry

theorem E1 : ∀ x : Input, A1 x → ∃ order rounds, (solve x).order = order ∧ (solve x).rounds = rounds := by sorry

theorem A1_nonvacuous : ∃ x : Input, A1 x := by sorry

end G24
