import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
theorem edge : VeriSlopBridgeGoal.EdgeProp := by
  apply VeriSlopBridgeGoal.edge_of_refines
  · intro offset xs
    with_unfolding_all
      change ((xs.map (fun x : Int => x)).map (fun x => x + offset)).map (fun x => x) = xs.map (fun x => x + offset)
    simp
  · intro limit xs
    with_unfolding_all
      change ((xs.map (fun x : Int => x)).filter (fun x => decide (x < limit))).map (fun x => x) = xs.filter (fun x => decide (x < limit))
    simp
  · intro limit xs
    with_unfolding_all
      change (((xs.map (fun x : Int => x)).filter (fun x => decide (x < limit))).map (fun x => x + limit)).sum =
        ((xs.filter (fun x => decide (x < limit))).map (fun x => x + limit)).sum
    simp
end VeriSlopBridgeProof
