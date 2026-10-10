import ClosureModel.ClaimGraph

/-!
# Terminal evaluation, the mechanical decision and release finalization

Milestone §5, §7 and §10. Non-final claims are evaluated from current evidence. The four final
closure outcomes are computed from checked build observations and those non-final outcomes,
then each end-to-end outcome from its exact premises. The mechanical decision applies the
frozen order and staged end-to-end PASS records are published only with `VERIFIED`. Release
review is evaluated afterwards and never rewrites mechanical evidence.

No stage consumes its own outcome: final and end-to-end records already present in the evidence
store, or supplied by a package, are ignored. Python mirror: `verislop/finalize.py`.
-/

namespace ClosureModel

/-- Checked observations of the two complete clean builds and the closure checks. -/
structure Observations where
  infrastructure : Bool
  buildA : Bool
  buildB : Bool
  outputsPresent : Bool
  buildsAgree : Bool
  matchesAccepted : Bool
  undeclaredDependency : Bool
  correspondenceResolved : Bool
  witnessesValid : Bool
  plannedProvenanceComplete : Bool
  endpointEstablished : Bool
  deriving DecidableEq, Repr

def passIf (b : Bool) : Outcome := if b then .pass else .fail

def cleanBuildsOutcome (o : Observations) : Outcome := passIf (o.buildA && o.buildB)

def determinismOutcome (o : Observations) : Outcome :=
  passIf (o.buildA && o.buildB && o.outputsPresent && o.buildsAgree && o.matchesAccepted)

def provenanceOutcome (o : Observations) (nonFinal : List Outcome) : Outcome :=
  passIf (nonFinal.all (· == .pass) && o.plannedProvenanceComplete && !o.undeclaredDependency)

def endpointOutcome (o : Observations) : Outcome :=
  passIf (o.endpointEstablished && o.correspondenceResolved)

/-- The end-to-end verifier computes its outcome from prerequisite outcomes only. -/
def endToEndOutcome (prereqs : List Outcome) : Outcome :=
  if prereqs.all (· == .pass) then .pass
  else if prereqs.any (· == .unsupported) then .unsupported
  else .fail

inductive MechStatus where
  | verified | blocked | infrastructureFailure
  deriving DecidableEq, Repr

inductive BlockReason where
  | requiredClaim | undeclaredDependency | unresolvedCorrespondence | witness
  | cleanBuild | nondeterminism | provenance
  deriving DecidableEq, Repr

/-- §7: infrastructure failure; any required claim not PASS; undeclared dependency; unresolved
correspondence; invalid/missing witness; failed clean build; nondeterminism; incomplete
provenance; otherwise VERIFIED. -/
def mechanicalDecision (o : Observations) (required : List Outcome) : MechStatus × Option BlockReason :=
  if o.infrastructure then (.infrastructureFailure, none)
  else if !(required.all (· == .pass)) then (.blocked, some .requiredClaim)
  else if o.undeclaredDependency then (.blocked, some .undeclaredDependency)
  else if !o.correspondenceResolved then (.blocked, some .unresolvedCorrespondence)
  else if !o.witnessesValid then (.blocked, some .witness)
  else if !(o.buildA && o.buildB) then (.blocked, some .cleanBuild)
  else if !(o.outputsPresent && o.buildsAgree && o.matchesAccepted) then (.blocked, some .nondeterminism)
  else if !o.plannedProvenanceComplete then (.blocked, some .provenance)
  else (.verified, none)

theorem mechanicalDecision_verified_iff (o : Observations) (required : List Outcome) :
    (mechanicalDecision o required).1 = .verified ↔
      o.infrastructure = false ∧ required.all (· == .pass) = true ∧ o.undeclaredDependency = false ∧
      o.correspondenceResolved = true ∧ o.witnessesValid = true ∧ o.buildA = true ∧ o.buildB = true ∧
      o.outputsPresent = true ∧ o.buildsAgree = true ∧ o.matchesAccepted = true ∧
      o.plannedProvenanceComplete = true := by
  unfold mechanicalDecision
  cases o.infrastructure <;> cases h : required.all (· == .pass) <;> cases o.undeclaredDependency <;>
    cases o.correspondenceResolved <;> cases o.witnessesValid <;> cases o.buildA <;> cases o.buildB <;>
    cases o.outputsPresent <;> cases o.buildsAgree <;> cases o.matchesAccepted <;>
    cases o.plannedProvenanceComplete <;> simp

def lookup (env : List (ClaimKind × Outcome)) (k : ClaimKind) : Outcome :=
  match env.find? (·.1 == k) with
  | some (_, x) => x
  | none => .pending

structure Evaluation where
  finals : List (ClaimKind × Outcome)
  endToEnd : List (Nat × Outcome)
  required : List Outcome
  status : MechStatus
  reason : Option BlockReason
  published : List (Nat × Outcome)
  deriving DecidableEq, Repr

/-- Terminal evaluation. `nonFinal` are the current authorized outcomes of the non-final claims;
any final or end-to-end entry in it is discarded, and `_previous` (stored end-to-end records of
earlier executions) is never consulted. -/
def evaluate (ctx : Context) (obs : Observations) (nonFinal : List (ClaimKind × Outcome))
    (_previous : List (Nat × Outcome)) : Evaluation :=
  let base := nonFinal.filter (fun e => !e.1.final)
  let requiredNonFinal := (ctx.inventory.filter fun k => !k.final && ctx.required k).map (lookup base)
  let finalsEnv : List (ClaimKind × Outcome) :=
    [(.cleanBuilds, cleanBuildsOutcome obs), (.determinism, determinismOutcome obs),
     (.provenance, provenanceOutcome obs requiredNonFinal), (.endpoint, endpointOutcome obs)]
  let env := base ++ finalsEnv
  let e2e := ctx.covered.map fun o =>
    (o, endToEndOutcome ((ctx.premisesOf (.milestone .endToEnd o)).map (lookup env)))
  let required := requiredNonFinal ++ finalsEnv.map (·.2) ++ e2e.map (·.2)
  let d := mechanicalDecision obs required
  { finals := finalsEnv, endToEnd := e2e, required := required, status := d.1, reason := d.2,
    published := if d.1 == .verified then e2e.filter (·.2 == .pass) else [] }

theorem endToEnd_pass_iff (prereqs : List Outcome) :
    endToEndOutcome prereqs = .pass ↔ ∀ x ∈ prereqs, x = .pass := by
  unfold endToEndOutcome
  constructor
  · intro h
    split at h
    · rename_i hall
      simpa using hall
    · split at h <;> cases h
  · intro h
    have : prereqs.all (· == .pass) = true := by simpa using h
    simp [this]

/-- Staged end-to-end PASS records are published only with a `VERIFIED` mechanical result. -/
theorem published_implies_verified (ctx obs nf prev) (x : Nat × Outcome)
    (h : x ∈ (evaluate ctx obs nf prev).published) : (evaluate ctx obs nf prev).status = .verified := by
  simp only [evaluate] at h ⊢
  split at h
  · rename_i hv; simpa using hv
  · cases h

theorem published_are_pass (ctx obs nf prev) (x : Nat × Outcome)
    (h : x ∈ (evaluate ctx obs nf prev).published) : x.2 = .pass := by
  simp only [evaluate] at h
  split at h
  · simp only [List.mem_filter, beq_iff_eq] at h; exact h.2
  · cases h

/-- `VERIFIED` requires every required claim, including every end-to-end claim, to pass. -/
theorem verified_all_required_pass (ctx obs nf prev) (h : (evaluate ctx obs nf prev).status = .verified) :
    ∀ x ∈ (evaluate ctx obs nf prev).required, x = .pass := by
  have hd := (mechanicalDecision_verified_iff obs (evaluate ctx obs nf prev).required).1 (by simpa [evaluate] using h)
  intro x hx
  have := List.all_eq_true.1 hd.2.1 x hx
  simpa using this

theorem verified_all_endToEnd_pass (ctx obs nf prev) (h : (evaluate ctx obs nf prev).status = .verified) :
    ∀ x ∈ (evaluate ctx obs nf prev).endToEnd, x.2 = .pass := by
  intro x hx
  apply verified_all_required_pass ctx obs nf prev h
  simp only [evaluate, List.mem_append, List.mem_map] at hx ⊢
  exact Or.inr ⟨x, hx, rfl⟩

/-- Infrastructure failure decides the terminal status but never rewrites a claim outcome:
an observed failure remains a failure. -/
theorem infrastructure_does_not_rewrite_claims (ctx obs nf prev) :
    (evaluate ctx { obs with infrastructure := true } nf prev).finals = (evaluate ctx obs nf prev).finals ∧
    (evaluate ctx { obs with infrastructure := true } nf prev).endToEnd = (evaluate ctx obs nf prev).endToEnd :=
  ⟨rfl, rfl⟩

theorem infrastructure_dominates (ctx obs nf prev) (h : obs.infrastructure = true) :
    (evaluate ctx obs nf prev).status = .infrastructureFailure := by
  simp [evaluate, mechanicalDecision, h]

/-- Pre-existing end-to-end records are never consulted. -/
theorem ignores_previous (ctx obs nf p q) : evaluate ctx obs nf p = evaluate ctx obs nf q := rfl

/-- Package-supplied final or end-to-end outcomes cannot change the evaluation. -/
theorem ignores_supplied_terminal (ctx obs nf prev) (s : List (ClaimKind × Outcome))
    (hs : ∀ e ∈ s, e.1.final = true) : evaluate ctx obs (nf ++ s) prev = evaluate ctx obs nf prev := by
  have : (nf ++ s).filter (fun e => !e.1.final) = nf.filter (fun e => !e.1.final) := by
    rw [List.filter_append]
    have : s.filter (fun e => !e.1.final) = [] := by
      rw [List.filter_eq_nil_iff]; intro e he; simp [hs e he]
    rw [this, List.append_nil]
  simp only [evaluate, this]

/-! ## Release finalization -/

inductive CheckpointState where
  | accepted | rejected | notRun | stale | unavailable
  deriving DecidableEq, Repr

inductive ReleaseStatus where
  | notRequired | accepted | blocked | infrastructureFailure
  deriving DecidableEq, Repr

def releaseStatus (cs : List CheckpointState) : ReleaseStatus :=
  if cs.isEmpty then .notRequired
  else if cs.any (· == .unavailable) then .infrastructureFailure
  else if cs.all (· == .accepted) then .accepted
  else .blocked

inductive Terminal where
  | verified | blocked | infrastructureFailure
  deriving DecidableEq, Repr

def terminal (m : MechStatus) (r : ReleaseStatus) : Terminal :=
  if m == .infrastructureFailure || r == .infrastructureFailure then .infrastructureFailure
  else if m == .verified && (r == .accepted || r == .notRequired) then .verified
  else .blocked

structure Finalized where
  mechanical : Evaluation
  release : ReleaseStatus
  terminal : Terminal
  deriving DecidableEq, Repr

def finalize (e : Evaluation) (cs : List CheckpointState) : Finalized :=
  ⟨e, releaseStatus cs, terminal e.status (releaseStatus cs)⟩

theorem terminal_verified_iff (m : MechStatus) (r : ReleaseStatus) :
    terminal m r = .verified ↔ m = .verified ∧ (r = .accepted ∨ r = .notRequired) := by
  cases m <;> cases r <;> decide

/-- Review cannot fix a mechanical failure, whatever the votes. -/
theorem review_cannot_fix_mechanics (e : Evaluation) (cs : List CheckpointState)
    (h : e.status ≠ .verified) : (finalize e cs).terminal ≠ .verified := by
  intro ht
  exact h ((terminal_verified_iff _ _).1 ht).1

/-- A mechanical success survives review rejection as a mechanical fact while release is blocked. -/
theorem rejection_keeps_mechanical_fact (e : Evaluation) (cs : List CheckpointState)
    (hv : e.status = .verified) (hr : CheckpointState.rejected ∈ cs) (hu : CheckpointState.unavailable ∉ cs) :
    (finalize e cs).mechanical = e ∧ (finalize e cs).release = .blocked ∧ (finalize e cs).terminal = .blocked := by
  have hne : cs.isEmpty = false := by
    cases cs with
    | nil => simp at hr
    | cons _ _ => rfl
  have hany : cs.any (· == .unavailable) = false := by
    rw [List.any_eq_false]; intro x hx hxe; simp at hxe; subst hxe; exact hu hx
  have hall : cs.all (· == .accepted) = false := by
    rw [List.all_eq_false]; exact ⟨.rejected, hr, by decide⟩
  have hrel : releaseStatus cs = .blocked := by simp [releaseStatus, hne, hany, hall]
  refine ⟨rfl, hrel, ?_⟩
  simp [finalize, hrel, terminal, hv]

theorem no_review_configured (e : Evaluation) : (finalize e []).release = .notRequired := rfl

end ClosureModel
