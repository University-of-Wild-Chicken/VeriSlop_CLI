/-!
# Deterministic review projection and review target

Milestone §10. A normalized envelope has `record`, `raw` and `execution` objects. Exactly ten
JSON Pointer paths are execution metadata; everything else is semantic and stays in the
projection. Nothing is dropped by field name recursively. The review target hashes the
checkpoint, closure root, projection hash, reviewer configuration and the frozen
model-resolution manifest. Ballots, transcripts and raw-inventory digests are not inputs to it.
Python mirror: `verislop/review_projection.py`.
-/

namespace ClosureModel

abbrev Path := List String

inductive Leaf where
  | str (s : String) | nat (n : Nat) | bool (b : Bool) | null
  deriving DecidableEq, Repr

/-- A normalized envelope flattened to its leaves (paths are JSON Pointer token lists). -/
abbrev Envelope := List (Path × Leaf)

def executionFields : List String := ["attempt_id", "started_at", "finished_at", "wall_ms", "work_directory"]

def excludedPaths : List Path :=
  [["record", "evidence_id"], ["record", "raw_result_ref"], ["record", "raw_result_hash"],
   ["raw", "sequence"], ["raw", "recorded_at"]] ++ executionFields.map (["execution", ·])

def excluded (p : Path) : Bool := excludedPaths.contains p

/-- Closed shape: every leaf lies below `record` or `raw`, or is one of the five execution fields. -/
def leafShaped : Path → Bool
  | ["execution", f] => executionFields.contains f
  | "record" :: _ :: _ => true
  | "raw" :: _ :: _ => true
  | _ => false

def wellShaped (e : Envelope) : Bool := e.all fun pv => leafShaped pv.1

def project (e : Envelope) : Envelope := e.filter (fun pv => !excluded pv.1)

theorem project_keeps (e : Envelope) (pv : Path × Leaf) (h : pv ∈ e) (hx : excluded pv.1 = false) :
    pv ∈ project e := by
  simp [project, h, hx]

theorem project_drops_only_excluded (e : Envelope) (pv : Path × Leaf) (h : pv ∈ e) (hn : pv ∉ project e) :
    excluded pv.1 = true := by
  cases hx : excluded pv.1
  · exact absurd (project_keeps e pv h hx) hn
  · rfl

theorem project_subset (e : Envelope) (pv : Path × Leaf) (h : pv ∈ project e) : pv ∈ e := by
  simp only [project, List.mem_filter] at h; exact h.1

theorem execution_leaf_excluded (p : Path) (hs : leafShaped p = true) (hh : p.head? = some "execution") :
    excluded p = true := by
  cases p with
  | nil => simp at hh
  | cons a rest =>
    have ha : a = "execution" := by simpa using hh
    subst ha
    cases rest with
    | nil => simp [leafShaped] at hs
    | cons f rest2 =>
      cases rest2 with
      | nil =>
        simp only [leafShaped, executionFields, List.contains_cons, List.contains_nil, Bool.or_false,
          Bool.or_eq_true, beq_iff_eq] at hs
        rcases hs with h | h | h | h | h <;> subst h <;> decide
      | cons _ _ => simp [leafShaped] at hs

/-- After projection nothing of the closed execution object remains. -/
theorem project_no_execution (e : Envelope) (hw : wellShaped e = true) (pv : Path × Leaf)
    (h : pv ∈ project e) : pv.1.head? ≠ some "execution" := by
  simp only [project, List.mem_filter, Bool.not_eq_true'] at h
  obtain ⟨hm, hx⟩ := h
  have hs := List.all_eq_true.1 hw pv hm
  intro hh
  have := execution_leaf_excluded pv.1 hs hh
  rw [hx] at this
  cases this

/-- A difference at any non-excluded leaf changes the projection. -/
theorem semantic_change_visible (e₁ e₂ : Envelope) (pv : Path × Leaf) (h₁ : pv ∈ e₁) (h₂ : pv ∉ e₂)
    (hx : excluded pv.1 = false) : project e₁ ≠ project e₂ := by
  intro heq
  have := project_keeps e₁ pv h₁ hx
  rw [heq] at this
  exact h₂ (project_subset e₂ pv this)

def setLeaf (e : Envelope) (p : Path) (v : Leaf) : Envelope :=
  e.map fun pv => if pv.1 == p then (p, v) else pv

/-- Fresh timestamps, attempt and evidence IDs leave the projection unchanged. -/
theorem metadata_does_not_change_projection (e : Envelope) (p : Path) (hp : excluded p = true) (v : Leaf) :
    project (setLeaf e p v) = project e := by
  unfold project setLeaf
  induction e with
  | nil => rfl
  | cons pv rest ih =>
    rw [List.map_cons, List.filter_cons, List.filter_cons, ih]
    by_cases h : (pv.1 == p) = true
    · have hpv : pv.1 = p := by simpa using h
      simp [hpv, hp]
    · simp [h]

/-- Nothing is dropped merely because it is named `id`, `time`, `sequence` or `path`. -/
example : excluded ["raw", "result", "id"] = false := by decide
example : excluded ["record", "scope", "time"] = false := by decide
example : excluded ["raw", "builds", "sequence"] = false := by decide
example : excluded ["raw", "artifact", "path"] = false := by decide
example : excluded ["record", "verifier_hash"] = false := by decide
example : excluded ["record", "execution_environment"] = false := by decide
example : excluded ["execution", "toolchain"] = false := by decide

theorem excluded_count : excludedPaths.length = 10 := rfl

/-! ## Registered normalizers -/

/-- A versioned, hashed normalizer of one raw result format: the complete set of field paths of
that format. Every raw field must be mapped; an unknown field blocks reuse. -/
structure Normalizer where
  known : List Path
  hash : String
  deriving DecidableEq, Repr

def normalize (n : Normalizer) (raw : Envelope) : Option Envelope :=
  if raw.all (fun pv => n.known.contains pv.1) then some raw else none

theorem unknown_field_blocks (n : Normalizer) (raw : Envelope) (pv : Path × Leaf) (h : pv ∈ raw)
    (hu : n.known.contains pv.1 = false) : normalize n raw = none := by
  unfold normalize
  have : raw.all (fun pv => n.known.contains pv.1) = false := by
    rw [List.all_eq_false]
    exact ⟨pv, h, by rw [hu]; decide⟩
  rw [this]; rfl

/-! ## Review target and model resolution -/

inductive Resolution where
  | pinned (model : String)
  | trustedAlias (alias : String)
  deriving DecidableEq, Repr

structure ModelPolicy where
  requireFixedSnapshot : Bool
  deriving DecidableEq, Repr

/-- Frozen before the target is generated or any ballot is requested. -/
def resolutionAdmitted (p : ModelPolicy) : Resolution → Bool
  | .pinned _ => true
  | .trustedAlias _ => !p.requireFixedSnapshot

def returnedModelValid : Resolution → String → Bool
  | .pinned m, returned => returned == m
  | .trustedAlias _, _ => true

theorem fixed_snapshot_rejects_alias (a : String) :
    resolutionAdmitted ⟨true⟩ (.trustedAlias a) = false := rfl

theorem pinned_requires_match (m r : String) (h : returnedModelValid (.pinned m) r = true) : r = m := by
  simpa [returnedModelValid] using h

structure TargetInputs where
  checkpoint : String
  closureRoot : String
  projectionHash : String
  reviewerConfigurationHash : String
  modelResolutionHash : String
  deriving DecidableEq, Repr

structure Ballot where
  slot : String
  verdict : String
  returnedModel : String
  deriving DecidableEq, Repr

structure Campaign where
  inputs : TargetInputs
  rawInventoryDigest : String
  ballots : List Ballot
  deriving DecidableEq, Repr

/-- The review target hashes exactly the five frozen components. -/
def reviewTarget (H : TargetInputs → String) (c : Campaign) : String := H c.inputs

/-- Returned model identities and other ballot data never enter their own target; the raw
inventory digest is audit provenance only. -/
theorem target_ignores_ballots (H : TargetInputs → String) (c : Campaign) (bs : List Ballot) (d : String) :
    reviewTarget H { c with ballots := bs, rawInventoryDigest := d } = reviewTarget H c := rfl

/-- With an injective target hash, any change of projection, configuration, model resolution,
closure root or checkpoint changes the target. -/
theorem target_changes (H : TargetInputs → String) (hH : ∀ a b, H a = H b → a = b)
    (c₁ c₂ : Campaign) (h : c₁.inputs ≠ c₂.inputs) : reviewTarget H c₁ ≠ reviewTarget H c₂ :=
  fun heq => h (hH _ _ heq)

/-! ## Consensus reuse -/

structure Execution where
  rawInventoryValid : Bool
  fresh : Bool
  projection : Envelope
  normalizerHash : String
  deriving DecidableEq, Repr

/-- Reuse of a consensus needs both exact inventories to validate, a fresh registered execution
for the current result, and byte-equal projections under the same normalizer. -/
def reuseAllowed (original current : Execution) : Bool :=
  original.rawInventoryValid && current.rawInventoryValid && current.fresh &&
    original.projection == current.projection && original.normalizerHash == current.normalizerHash

theorem reuse_sound (o c : Execution) (h : reuseAllowed o c = true) :
    c.fresh = true ∧ o.rawInventoryValid = true ∧ c.rawInventoryValid = true ∧
      o.projection = c.projection ∧ o.normalizerHash = c.normalizerHash := by
  simp only [reuseAllowed, Bool.and_eq_true, beq_iff_eq] at h
  exact ⟨h.1.1.2, h.1.1.1.1, h.1.1.1.2, h.1.2, h.2⟩

theorem reuse_preserves_semantics (o c : Execution) (h : reuseAllowed o c = true) (pv : Path × Leaf)
    (hm : pv ∈ o.projection) : pv ∈ c.projection := by
  rw [← (reuse_sound o c h).2.2.2.1]; exact hm

end ClosureModel
