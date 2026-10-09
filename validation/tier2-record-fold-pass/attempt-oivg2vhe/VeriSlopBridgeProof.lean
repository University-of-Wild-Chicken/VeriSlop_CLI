import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
open VeriSlopBridgeGoal RecordFoldFixture
theorem edge : EdgeProp := by
  apply edge_of_refines
  · intro offset xs
    with_unfolding_all
      change ((xs.map adapter_2.to).map (fun x => (x.1 + offset, (x.2.1, ())))).map adapter_2.inv =
        xs.map (fun x => { amount := x.amount + offset, label := x.label })
    simp only [List.map_map]
    with_unfolding_all rfl
  · intro limit xs
    with_unfolding_all
      change ((xs.map adapter_2.to).filter (fun x => decide (x.1 < limit))).map adapter_2.inv =
        xs.filter (fun x => decide (x.amount < limit))
    rw [List.filter_map, List.map_map]
    with_unfolding_all
      change (xs.filter (fun x => decide (x.amount < limit))).map (fun x => adapter_2.inv (adapter_2.to x)) = _
    simp only [adapter_2.from_to, List.map_id']
  · intro initial xs
    with_unfolding_all
      change (xs.map adapter_2.to).foldl (fun acc x => acc + x.1) initial =
        xs.foldl (fun acc x => acc + x.amount) initial
    rw [List.foldl_map]
    with_unfolding_all rfl
  · intro offset initial xs
    with_unfolding_all
      change ((xs.map adapter_2.to).map (fun x => (x.1 + offset, (x.2.1, ())))).foldl (fun acc x => acc + x.1) initial =
        (xs.map (fun x : Packet => Packet.mk (x.amount + offset) x.label)).foldl (fun acc x => acc + x.amount) initial
    simp only [List.foldl_map]
    with_unfolding_all rfl
end VeriSlopBridgeProof
