import Fixture
namespace GenericErgonomicsProbe
example (x : Tint) : representedIvory (tintAdapter.to x) = ordinaryIvory x := by
  simp only [representedIvory, ordinaryIvory, tintAdapter.from_to,
    VSCore3.ProofSupport.apply_ite, VSCore3.ProofSupport.apply_bool_ite,
    VSCore3.ProofSupport.ite_decide, VSCore3.ProofSupport.map_identity,
    VSCore3.ProofSupport.int_ofNat_eq_cast, VSCore3.ProofSupport.int_ofNat_add]
end GenericErgonomicsProbe
