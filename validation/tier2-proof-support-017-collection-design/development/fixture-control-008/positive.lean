import VeriSlopBridgeGoal
namespace VeriSlopBridgeProof
open VeriSlopBridgeGoal VSCore3.ProofSupport
set_option maxRecDepth 100000
set_option maxHeartbeats 20000000

theorem ref_map : Refines_shiftEnvelopes := by
  intro xs increment
  rw [Readable.source_eq_shiftEnvelopes]
  with_unfolding_all
    apply map_transport adapter_4 adapter_4
    intro e
    rfl

theorem ref_filter : Refines_keepParcel := by
  intro xs needle
  rw [Readable.source_eq_keepParcel]
  with_unfolding_all
    apply filter_transport adapter_4
    intro e
    simp only [VeriSlopReadableSource.helper_0_named, VeriSlopReadableSource.helper_0_run, VeriSlopReadableSource.helper_0_body, VeriSlopReadableSource.helper_1_named, VeriSlopReadableSource.helper_1_run, VeriSlopReadableSource.helper_1_body, VeriSlopReadableSource.helper_2_named, VeriSlopReadableSource.helper_2_run, VeriSlopReadableSource.helper_2_body, VeriSlopReadableSource.helper_3_named, VeriSlopReadableSource.helper_3_run, VeriSlopReadableSource.helper_3_body, VSCore3.envReverse, VSCore3.envReverseAux, Eq.mp, Eq.mpr, cast_eq]
    letI := VSCore3.denoteDecidableEq (.record "Parcel" ["shade", "n"] (.product (.enum "Shade" ["light", "dark", "neutral"]) (.product .nat .unit)))
    change decide (adapter_2.to e.parcel = adapter_2.to needle) = _
    apply Bool.eq_iff_iff.mpr
    simp only [decide_eq_true_eq, Bool.and_eq_true]
    change adapter_2.to e.parcel = adapter_2.to needle ↔ e.parcel.shade = needle.shade ∧ e.parcel.n = needle.n
    rw [to_eq_iff]
    constructor
    · intro h; cases h; exact ⟨rfl, rfl⟩
    · rintro ⟨hs, hn⟩
      cases e with
      | mk p active =>
        cases p with
        | mk shade n =>
          cases needle with
          | mk shade2 n2 => simp_all

theorem ref_fold : Refines_shadeTotal := by
  intro xs initial chosen
  rw [Readable.source_eq_shadeTotal]
  with_unfolding_all
    apply foldl_transport adapter_4 adapter_1
    intro z e
    cases e with
    | mk p active =>
      cases p with
      | mk shade n => cases shade <;> cases chosen <;> rfl

theorem ref_equality : Refines_sameShade := by
  intro x y
  rw [Readable.source_eq_sameShade]
  letI := VSCore3.denoteDecidableEq (.enum "Shade" ["light", "dark", "neutral"])
  with_unfolding_all
    exact decide_to_eq adapter_0 x y

theorem edge : EdgeProp := edge_of_refines ref_filter ref_equality ref_fold ref_map
end VeriSlopBridgeProof
