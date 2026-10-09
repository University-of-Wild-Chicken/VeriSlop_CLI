import Std
namespace RecordFoldFixture
structure Packet where
  amount : Int
  label : String
def transformed (offset : Int) (xs : List Packet) : List Packet :=
  xs.map (fun x => { amount := x.amount + offset, label := x.label })
def selected (limit : Int) (xs : List Packet) : List Packet :=
  xs.filter (fun x => decide (x.amount < limit))
def folded (initial : Int) (xs : List Packet) : Int :=
  xs.foldl (fun acc x => acc + x.amount) initial
def transformed_fold (offset initial : Int) (xs : List Packet) : Int :=
  (xs.map (fun x : Packet => { amount := x.amount + offset, label := x.label })).foldl
    (fun acc x => acc + x.amount) initial
theorem transformed_contract : forall offset xs, transformed offset xs =
  xs.map (fun x => { amount := x.amount + offset, label := x.label }) := by intros; rfl
theorem selected_contract : forall limit xs, selected limit xs =
  xs.filter (fun x => decide (x.amount < limit)) := by intros; rfl
theorem folded_contract : forall initial xs, folded initial xs =
  xs.foldl (fun acc x => acc + x.amount) initial := by intros; rfl
theorem transformed_fold_contract : forall offset initial xs, transformed_fold offset initial xs =
  (xs.map (fun x : Packet => { amount := x.amount + offset, label := x.label })).foldl
    (fun acc x => acc + x.amount) initial := by intros; rfl
end RecordFoldFixture
