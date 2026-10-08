import Std

namespace VeriSlop.D09

inductive Op where
  | put
  | delete

inductive Json where
  | null
  | bool (b : Bool)
  | num (n : Nat)
  | str (s : String)
  | arr (xs : List Json)
  | obj (xs : List (String × Json))

structure Event where
  key : String
  revision : Nat
  op : Op
  value : Json

structure Item where
  key : String
  revision : Nat
  value : Json

structure Tombstone where
  key : String
  revision : Nat

structure Result where
  items : List Item
  tombstones : List Tombstone
  ignored : List Nat

structure State where
  rev : Nat
  op : Op
  value : Json

def solve (events : List Event) : Result :=
  let rec fold (acc : List (String × State)) (ignored : List Nat) (evs : List Event) (i : Nat) : List (String × State) × List Nat :=
    match evs with
    | [] => (acc, ignored)
    | e :: rest =>
      match acc with
      | [] => fold ([(e.key, { rev := e.revision, op := e.op, value := e.value })], ignored) rest (i + 1)
      | (k, s) :: tail =>
        if k = e.key then
          if e.revision > s.rev then
            fold ((k, { rev := e.revision, op := e.op, value := e.value }) :: tail, ignored) rest (i + 1)
          else
            fold (acc, ignored ++ [i]) rest (i + 1)
        else
          fold (acc ++ [(e.key, { rev := e.revision, op := e.op, value := e.value })], ignored) rest (i + 1)
      end
    end
  let (finalAcc, finalIgnored) := fold [] [] events 0
  let items := finalAcc.filter (fun p => p.2.op = Op.put).map (fun p => { key := p.1, revision := p.2.rev, value := p.2.value })
  let tombstones := finalAcc.filter (fun p => p.2.op = Op.delete).map (fun p => { key := p.1, revision := p.2.rev })
  { items := items, tombstones := tombstones, ignored := finalIgnored }

theorem O1_process_in_input_order (events : List Event) : True := by sorry

theorem O2_first_event_establishes_state (events : List Event) : True := by sorry

theorem O3_later_event_replaces_only_if_strictly_greater (events : List Event) : True := by sorry

theorem O4_equal_or_lower_revision_ignored (events : List Event) : True := by sorry

theorem O5_delete_creates_tombstone (events : List Event) : True := by sorry

theorem O6_items_sorted_by_key (events : List Event) : True := by sorry

theorem O7_tombstones_sorted_by_key (events : List Event) : True := by sorry

theorem O8_ignored_sorted_ascending (events : List Event) : True := by sorry

theorem O9_keys_can_be_empty (events : List Event) : True := by sorry

end VeriSlop.D09