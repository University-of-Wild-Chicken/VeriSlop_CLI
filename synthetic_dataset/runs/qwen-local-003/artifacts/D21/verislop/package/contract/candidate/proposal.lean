import Std

namespace VeriSlop.D21

inductive FillMode where
  | none
  | previous

structure Event where
  group : Nat
  time : Nat
  value : Option Nat

structure Input where
  events : List Event
  start : Nat
  end : Nat
  width : Nat
  fill : FillMode

structure Bucket where
  group : Nat
  start : Nat
  count : Nat
  value : Option Nat

def validStartEnd (inp : Input) : Prop := inp.start ≤ inp.end
def validWidth (inp : Input) : Prop := 0 < inp.width

def allGroups (inp : Input) : List Nat :=
  (List.map (fun e => e.group) inp.events)
    |>.toSet
    |>.toList
    |>.sort
    |>.dedup

def bucketStarts (inp : Input) : List Nat :=
  let rec gen (acc : List Nat) (s : Nat) : List Nat :=
    if s < inp.end then gen (acc ++ [s]) (s + inp.width) else acc
  gen [] inp.start

def bucketEnd (inp : Input) (b : Nat) : Nat := min (b + inp.width) inp.end

def inBucket (inp : Input) (e : Event) (b : Nat) : Prop :=
  e.time ≥ b ∧ e.time < bucketEnd inp b

def nonNullInBucket (inp : Input) (g : Nat) (b : Nat) : List Event :=
  List.filter (fun e => e.group = g ∧ inBucket inp e b ∧ e.value.isSome) inp.events

def bucketCount (inp : Input) (g : Nat) (b : Nat) : Nat :=
  (nonNullInBucket inp g b).length

def bucketSum (inp : Input) (g : Nat) (b : Nat) : Nat :=
  List.sum (List.map (fun e => e.value.getD 0) (nonNullInBucket inp g b))

def prevValue (inp : Input) (g : Nat) (b : Nat) : Option Nat :=
  let bs := bucketStarts inp
  let rec go (acc : Option Nat) (rest : List Nat) : Option Nat :=
    match rest with
    | [] => acc
    | x :: xs =>
      if x < b then
        let c := bucketCount inp g x
        if c > 0 then go (some (bucketSum inp g x)) xs else go acc xs
      else acc
  go none bs

def bucketValue (inp : Input) (g : Nat) (b : Nat) : Option Nat :=
  let c := bucketCount inp g b
  if c > 0 then some (bucketSum inp g b)
  else if inp.fill = FillMode.none then none
  else prevValue inp g b

def solve (inp : Input) : List Bucket :=
  let groups := allGroups inp
  let bs := bucketStarts inp
  let rec goG (acc : List Bucket) (gs : List Nat) : List Bucket :=
    match gs with
    | [] => acc
    | g :: rest =>
      let rec goB (acc2 : List Bucket) (bs2 : List Nat) : List Bucket :=
        match bs2 with
        | [] => acc2
        | b :: rest2 =>
          goB (acc2 ++ [⟨g, b, bucketCount inp g b, bucketValue inp g b⟩]) rest2
      goG (goB acc bs) rest
  goG [] groups

theorem O1_output_groups (inp : Input) :
  (List.map (fun b => b.group) (solve inp)) =
    (List.concat (List.map (fun g => List.replicate (List.length (bucketStarts inp)) g) (allGroups inp))) := by sorry

theorem O2_bucket_starts (inp : Input) (h1 : validStartEnd inp) (h2 : validWidth inp) :
  List.Pairwise (fun a b => a < b) (bucketStarts inp) ∧
  ∀ b ∈ bucketStarts inp, b < inp.end := by sorry

theorem O3_bucket_interval (inp : Input) (b : Nat) (hb : b ∈ bucketStarts inp) :
  ∀ e : Event, inBucket inp e b ↔ (e.time ≥ b ∧ e.time < min (b + inp.width) inp.end) := by sorry

theorem O4_bucket_value_sum (inp : Input) (g : Nat) (b : Nat) (hb : b ∈ bucketStarts inp) :
  bucketCount inp g b > 0 →
    (List.find? (fun x => x.group = g ∧ x.start = b) (solve inp)) =
      some ⟨g, b, bucketCount inp g b, some (bucketSum inp g b)⟩ := by sorry

theorem O5_bucket_count (inp : Input) (g : Nat) (b : Nat) (hb : b ∈ bucketStarts inp) :
  (List.find? (fun x => x.group = g ∧ x.start = b) (solve inp)) =
    some ⟨g, b, bucketCount inp g b, bucketValue inp g b⟩ := by sorry

theorem O6_nonempty_previous (inp : Input) (g : Nat) (b : Nat) (hb : b ∈ bucketStarts inp) :
  bucketCount inp g b > 0 →
    (List.find? (fun x => x.group = g ∧ x.start = b) (solve inp)) =
      some ⟨g, b, bucketCount inp g b, some (bucketSum inp g b)⟩ := by sorry

theorem O7_fill_none_empty (inp : Input) (g : Nat) (b : Nat) (hb : b ∈ bucketStarts inp) :
  inp.fill = FillMode.none → bucketCount inp g b = 0 →
    (List.find? (fun x => x.group = g ∧ x.start = b) (solve inp)) =
      some ⟨g, b, 0, none⟩ := by sorry

theorem O8_fill_previous_empty (inp : Input) (g : Nat) (b : Nat) (hb : b ∈ bucketStarts inp) :
  inp.fill = FillMode.previous → bucketCount inp g b = 0 →
    (List.find? (fun x => x.group = g ∧ x.start = b) (solve inp)) =
      some ⟨g, b, 0, prevValue inp g b⟩ := by sorry

theorem O11_output_order (inp : Input) :
  List.Pairwise (fun a b => a.group < b.group ∨ (a.group = b.group ∧ a.start < b.start)) (solve inp) := by sorry

theorem O12_zero_sum_and_duplicates (inp : Input) (g : Nat) (b : Nat) (hb : b ∈ bucketStarts inp) :
  (bucketCount inp g b > 0 ∧ bucketSum inp g b = 0) →
    (List.find? (fun x => x.group = g ∧ x.start = b) (solve inp)) =
      some ⟨g, b, bucketCount inp g b, some 0⟩ := by sorry

theorem O9_empty_no_reset (inp : Input) (g : Nat) (b : Nat) (hb : b ∈ bucketStarts inp) :
  bucketCount inp g b = 0 →
    prevValue inp g b = prevValue inp g (List.head! (bucketStarts inp)) := by sorry

theorem O10_before_start_no_seed (inp : Input) (g : Nat) (b : Nat) (hb : b ∈ bucketStarts inp) :
  (∀ e ∈ inp.events, e.group = g → e.time < inp.start → e.value.isSome → False) →
    prevValue inp g b = none := by sorry

theorem NV_A1_A2 : ∃ inp : Input, validStartEnd inp ∧ validWidth inp := by sorry

end VeriSlop.D21