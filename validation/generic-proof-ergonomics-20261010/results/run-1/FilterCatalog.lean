import Fixture
namespace GenericErgonomicsProbe
example (xs : List Bundle) : filtered xs = xs.filter (fun x => ordinaryIvory x.payload.tint) := by
  simp only [filtered, VSCore3.listAdapter, bundleAdapter, capsuleAdapter,
    VSCore3.natAdapter, bundleAdapter.from_to, capsuleAdapter.from_to, tintAdapter.from_to,
    VSCore3.ProofSupport.apply_ite, VSCore3.ProofSupport.apply_bool_ite,
    VSCore3.ProofSupport.ite_decide, VSCore3.ProofSupport.map_identity,
    VSCore3.ProofSupport.int_ofNat_eq_cast, VSCore3.ProofSupport.int_ofNat_add]
end GenericErgonomicsProbe
