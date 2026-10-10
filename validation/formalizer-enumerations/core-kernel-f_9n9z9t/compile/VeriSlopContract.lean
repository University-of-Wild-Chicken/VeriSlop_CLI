import Std
namespace EnumEqualityCore
inductive Alpha where | first | second deriving DecidableEq
inductive Beta where | first | second | third deriving DecidableEq
structure Packet where
  kind : Alpha
  values : List Alpha
def equalAlpha (a b : Alpha) : Bool := @Decidable.decide (a = b) (instDecidableEqAlpha a b)
def equalBeta (a b : Beta) : Bool := @Decidable.decide (a = b) (instDecidableEqBeta a b)
def dispatch (p : Packet) : Nat := cond (decide (p.kind = Alpha.first)) 7 11
def filtered (p : Packet) : List Alpha := p.values.filter (fun x => decide (x = p.kind))
def mapped (p : Packet) : List Bool := p.values.map (fun x => decide (x = p.kind))
def folded (p : Packet) : Nat := p.values.foldl (fun acc x => cond (decide (x = p.kind)) (acc + 1) acc) 0
def compound (a : Alpha) : Bool := decide (a = Alpha.first ∧ ¬ a = Alpha.second)
theorem alpha_contract (a b : Alpha) : equalAlpha a b = decide (a = b) := rfl
theorem beta_contract (a b : Beta) : equalBeta a b = decide (a = b) := rfl
theorem dispatch_contract (p : Packet) : dispatch p = cond (decide (p.kind = Alpha.first)) 7 11 := rfl
theorem filtered_contract (p : Packet) : filtered p = p.values.filter (fun x => decide (x = p.kind)) := rfl
theorem mapped_contract (p : Packet) : mapped p = p.values.map (fun x => decide (x = p.kind)) := rfl
theorem folded_contract (p : Packet) : folded p = p.values.foldl (fun acc x => cond (decide (x = p.kind)) (acc + 1) acc) 0 := rfl
theorem compound_contract (a : Alpha) : compound a = decide (a = Alpha.first ∧ ¬ a = Alpha.second) := rfl
theorem primitive_contract (a b : Nat) : decide (a = b) = decide (a = b) := rfl
end EnumEqualityCore
