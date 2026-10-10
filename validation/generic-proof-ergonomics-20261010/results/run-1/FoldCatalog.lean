import Fixture
namespace GenericErgonomicsProbe
example (xs : List Bundle) : folded xs =
    xs.foldl (fun acc x => if ordinaryIvory x.payload.tint then acc + x.payload.depth else acc) 0 := by
  simp only [folded, VSCore3.listAdapter, bundleAdapter, capsuleAdapter,
    VSCore3.natAdapter, bundleAdapter.from_to, capsuleAdapter.from_to, tintAdapter.from_to,
    VSCore3.ProofSupport.apply_ite, VSCore3.ProofSupport.apply_bool_ite,
    VSCore3.ProofSupport.ite_decide, VSCore3.ProofSupport.map_identity,
    VSCore3.ProofSupport.int_ofNat_eq_cast, VSCore3.ProofSupport.int_ofNat_add]
end GenericErgonomicsProbe
