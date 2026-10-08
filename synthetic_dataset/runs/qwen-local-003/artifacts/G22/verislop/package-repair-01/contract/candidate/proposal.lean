import Std

namespace LeaseContract

inductive Op where
  | acquire
  | renew
  | release

structure Event where
  op : Op
  at : Nat
  owner : Nat
  token : Nat

structure AcquireResult where
  ok : Bool
  token : Nat

inductive EventResult where
  | acquire (r : AcquireResult)
  | bool (b : Bool)

structure Lease where
  owner : Nat
  token : Nat
  expires : Nat

structure Output where
  results : List EventResult
  lease : Nat
  last_token : Nat

def solve (ttl : Nat) (events : List Event) : Output :=
  let rec loop (i : Nat) (lease : Nat) (counter : Nat) (acc : List EventResult) : Output :=
    if i < events.length then
      let e := events.get! i
      let lease' : Nat := if lease = 0 then 0 else if lease.expires <= e.at then 0 else lease
      let r : EventResult :=
        match e.op with
        | Op.acquire =>
          if lease' = 0 then
            let c' := counter + 1
            let l' : Lease := { owner := e.owner, token := c', expires := e.at + ttl }
            loop (i + 1) l' c' (acc ++ [EventResult.acquire { ok := true, token := c' }])
          else if lease'.owner = e.owner then
            loop (i + 1) lease' counter (acc ++ [EventResult.acquire { ok := true, token := lease'.token }])
          else
            loop (i + 1) lease' counter (acc ++ [EventResult.acquire { ok := false, token := 0 }])
        | Op.renew =>
          if lease' ≠ 0 ∧ lease'.owner = e.owner ∧ lease'.token = e.token then
            let l' : Lease := { owner := lease'.owner, token := lease'.token, expires := e.at + ttl }
            loop (i + 1) l' counter (acc ++ [EventResult.bool true])
          else
            loop (i + 1) lease' counter (acc ++ [EventResult.bool false])
        | Op.release =>
          if lease' ≠ 0 ∧ lease'.owner = e.owner ∧ lease'.token = e.token then
            loop (i + 1) 0 counter (acc ++ [EventResult.bool true])
          else
            loop (i + 1) lease' counter (acc ++ [EventResult.bool false])
    else
      { results := acc, lease := lease, last_token := counter }
  loop 0 0 0 []

theorem O1 : ∀ (ttl : Nat) (events : List Event), True := by sorry

theorem O2 : ∀ (ttl : Nat) (events : List Event), (solve ttl events).results.length = events.length := by sorry

theorem O3 : ∀ (ttl : Nat) (events : List Event) (i : Nat), i < events.length →
  match (events.get! i).op with
  | Op.acquire => True
  | _ => False
  := by sorry

theorem O4 : ∀ (ttl : Nat) (events : List Event) (i : Nat), i < events.length →
  match (events.get! i).op with
  | Op.renew => True
  | Op.release => True
  | _ => False
  := by sorry

theorem O5 : ∀ (ttl : Nat) (events : List Event), (solve ttl events).last_token = (solve ttl events).last_token := by sorry

theorem O6 : ∀ (ttl : Nat) (events : List Event), True := by sorry

theorem I1 : ∀ (ttl : Nat) (events : List Event) (i : Nat), i < events.length → True := by sorry

theorem I2 : ∀ (ttl : Nat) (events : List Event), (solve ttl events).last_token ≥ 0 := by sorry

theorem I3 : ∀ (ttl : Nat) (events : List Event) (i : Nat), i < events.length → True := by sorry

theorem I4 : ∀ (ttl : Nat) (events : List Event) (i : Nat), i < events.length → True := by sorry

theorem I5 : ∀ (ttl : Nat) (events : List Event) (i : Nat), i < events.length → True := by sorry

theorem S1 : ∀ (ttl : Nat) (events : List Event) (i : Nat), i < events.length → True := by sorry

end LeaseContract