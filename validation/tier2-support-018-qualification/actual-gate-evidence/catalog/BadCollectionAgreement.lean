import VSCore3
example (xs : List Nat) :
    (VSCore3.listAdapter VSCore3.natAdapter).inv
      (List.map (fun n => n + 1) ((VSCore3.listAdapter VSCore3.natAdapter).to xs)) = xs := by
  simpa only [VSCore3.ProofSupport.map_identity] using
    (VSCore3.ProofSupport.map_transport VSCore3.natAdapter VSCore3.natAdapter
      (fun n => n) (fun n => n + 1) (by intro n; rfl) xs)
