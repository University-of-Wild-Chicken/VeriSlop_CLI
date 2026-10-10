import Fixture
namespace GenericErgonomicsProbe
example (xs : List Bundle) : mapped xs = xs.map (fun x => x.payload.tint) := by
  simp only [mapped, VSCore3.listAdapter, bundleAdapter, capsuleAdapter,
    VSCore3.natAdapter, tintAdapter.from_to,
    VSCore3.ProofSupport.apply_ite, VSCore3.ProofSupport.apply_bool_ite,
    VSCore3.ProofSupport.ite_decide, VSCore3.ProofSupport.map_identity,
    VSCore3.ProofSupport.int_ofNat_eq_cast, VSCore3.ProofSupport.int_ofNat_add]
end GenericErgonomicsProbe
