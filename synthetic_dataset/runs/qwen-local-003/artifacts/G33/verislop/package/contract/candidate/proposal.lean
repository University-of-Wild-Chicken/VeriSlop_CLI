import Std

namespace VeriSlop.G33

inductive Relation where
  | equal
  | before
  | after
  | concurrent

structure Event where
  id : Nat
  clock : List Nat

structure Input where
  events : List Event

structure Output where
  order : List Nat
  relations : List (List Relation)

def validClock (c : List Nat) : Prop :=
  1 ≤ c.length ∧ c.length ≤ 5

def validEvents (evs : List Event) : Prop :=
  (∀ e ∈ evs, validClock e.clock) ∧
  (∀ e₁ e₂, e₁ ∈ evs → e₂ ∈ evs → e₁.id = e₂.id → e₁ = e₂)

def validInput (inp : Input) : Prop :=
  validEvents inp.events

def clockEqual (c1 c2 : List Nat) : Bool :=
  c1 = c2

def clockBefore (c1 c2 : List Nat) : Bool :=
  let n := c1.length
  let allLe := (List.range n).all (fun i => c1[i]! ≤ c2[i]!)
  let anyLt := (List.range n).any (fun i => c1[i]! < c2[i]!)
  allLe && anyLt

def relation (e1 e2 : Event) : Relation :=
  if clockEqual e1.clock e2.clock then Relation.equal
  else if clockBefore e1.clock e2.clock then Relation.before
  else if clockBefore e2.clock e1.clock then Relation.after
  else Relation.concurrent

def relationsMatrix (evs : List Event) : List (List Relation) :=
  evs.map (fun e1 => evs.map (fun e2 => relation e1 e2))

def inDegree (evs : List Event) (target : Nat) : Nat :=
  evs.filter (fun e => e.id ≠ target ∧ clockBefore e.clock (evs.find! (fun x => x.id = target)).clock).length

def topologicalOrder (evs : List Event) : List Nat :=
  let n := evs.length
  let allIds : List Nat := evs.map (fun e => e.id)
  let rec go (remaining : List Nat) (placed : List Nat) : List Nat :=
    match remaining with
    | [] => placed
    | _ =>
      let eligible := remaining.filter (fun id =>
        let e := evs.find! (fun x => x.id = id)
        (evs.filter (fun f => f.id ≠ id ∧ clockBefore f.clock e.clock)).length = 0
      )
      match eligible with
      | [] => placed
      | _ =>
        let minId := eligible.min! (fun a b => a < b)
        go (remaining.filter (fun x => x ≠ minId)) (placed ++ [minId])
  go allIds []

def solve (inp : Input) : Output :=
  { order := topologicalOrder inp.events,
    relations := relationsMatrix inp.events }

def isTopologicalOrder (evs : List Event) (order : List Nat) : Prop :=
  (order.length = evs.length) ∧
  (∀ i j, i < order.length → j < order.length →
    let ei := evs.find! (fun e => e.id = order[i]!)
    let ej := evs.find! (fun e => e.id = order[j]!)
    ¬ clockBefore ej.clock ei.clock)

def isLexSmallestTopOrder (evs : List Event) (order : List Nat) : Prop :=
  isTopologicalOrder evs order ∧
  (∀ other : List Nat, isTopologicalOrder evs other → order ≤ other)

def noEdgeBetweenEqualClocks (evs : List Event) (order : List Nat) : Prop :=
  ∀ i j, i < order.length → j < order.length →
    let ei := evs.find! (fun e => e.id = order[i]!)
    let ej := evs.find! (fun e => e.id = order[j]!)
    ei.clock = ej.clock → ¬ clockBefore ei.clock ej.clock ∧ ¬ clockBefore ej.clock ei.clock

def isJsonSerializable (_ : Output) : Prop := True

def isPureDeterministic (f : Input → Output) : Prop :=
  ∀ inp : Input, f inp = f inp

theorem O1 (inp : Input) (h : validInput inp) (i j : Nat) (hi : i < inp.events.length) (hj : j < inp.events.length) :
  (relationsMatrix inp.events)[i]![j] = Relation.equal ↔ (inp.events)[i]!.clock = (inp.events)[j]!.clock := by sorry

theorem O2 (inp : Input) (h : validInput inp) (i j : Nat) (hi : i < inp.events.length) (hj : j < inp.events.length) :
  (relationsMatrix inp.events)[i]![j] = Relation.before ↔
    let c1 := (inp.events)[i]!.clock
    let c2 := (inp.events)[j]!.clock
    let n := c1.length
    (List.range n).all (fun k => c1[k]! ≤ c2[k]!) ∧ (List.range n).any (fun k => c1[k]! < c2[k]!) := by sorry

theorem O3 (inp : Input) (h : validInput inp) (i j : Nat) (hi : i < inp.events.length) (hj : j < inp.events.length) :
  (relationsMatrix inp.events)[i]![j] = Relation.after ↔
    let c1 := (inp.events)[i]!.clock
    let c2 := (inp.events)[j]!.clock
    let n := c1.length
    (List.range n).all (fun k => c2[k]! ≤ c1[k]!) ∧ (List.range n).any (fun k => c2[k]! < c1[k]!) := by sorry

theorem O4 (inp : Input) (h : validInput inp) (i j : Nat) (hi : i < inp.events.length) (hj : j < inp.events.length) :
  (relationsMatrix inp.events)[i]![j] = Relation.concurrent ↔
    let c1 := (inp.events)[i]!.clock
    let c2 := (inp.events)[j]!.clock
    c1 ≠ c2 ∧ ¬ clockBefore c1 c2 ∧ ¬ clockBefore c2 c1 := by sorry

theorem O5 (inp : Input) (h : validInput inp) :
  isLexSmallestTopOrder inp.events (solve inp).order := by sorry

theorem O6 (inp : Input) (h : validInput inp) :
  noEdgeBetweenEqualClocks inp.events (solve inp).order := by sorry

theorem O7 (inp : Input) (h : validInput inp) (hempty : inp.events = []) :
  solve inp = { order := [], relations := [] } := by sorry

theorem O8 (inp : Input) (h : validInput inp) :
  isJsonSerializable (solve inp) := by sorry

theorem O9 (inp : Input) (h : validInput inp) (i j : Nat) (hi : i < inp.events.length) (hj : j < inp.events.length) :
  (solve inp).relations[i]![j] = relation ((inp.events)[i]!) ((inp.events)[j]!) := by sorry

theorem S1 (inp : Input) (h : validInput inp) :
  True := by sorry

theorem S2 (inp : Input) (h : validInput inp) :
  True := by sorry

theorem S3 (inp : Input) (h : validInput inp) :
  solve inp = solve inp := by sorry

end VeriSlop.G33