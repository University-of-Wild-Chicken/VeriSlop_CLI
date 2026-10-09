import Std

/-!
# Finite TESTED campaigns: proposed strict v0.2 design

This standalone model specifies a finite evidence judgment, not the current Python campaign
implementation. In particular, legacy sampled truth is not an exact residual-formula result.
Nothing here enables a backend, proves the host evaluator/harness correct, or assigns E2E.

Binding tokens stand for exact accepted predicate, target, campaign, checker and environment
identities. Token equality alone proves no hash, filesystem, isolation, freshness or external
identity fact. The soundness theorem exposes those facts as external premises. Values and
canonical outer assignments are abstractly represented by naturals; their real codecs and
assignment canonicalization belong to those premises.
-/

namespace TestingModel

abbrev CaseId := Nat
abbrev AtomId := Nat
abbrev CoverageId := Nat

structure Binding where
  target : Nat
  acceptedPredicates : Nat
  campaign : Nat
  checker : Nat
  environment : Nat
  deriving DecidableEq, Repr

/-- Identity of an obligation revision and one canonical outer-quantifier assignment.
Different arbitrary receipt IDs cannot make the same semantic key count twice. -/
structure CaseKey where
  obligation : Nat
  assignment : List Nat
  deriving DecidableEq, Repr

inductive CaseClass where
  | effectivePass | discard | unknown | indeterminate | timeout | counterexample
  deriving DecidableEq, Repr

/-- Only exactPass can discharge an effective case's accepted residual atoms.
An unbounded existential with no checked witness is unknown; samples cannot decide it false.
Samples of an inner universal likewise do not furnish an exactPass certificate. -/
inductive AtomOutcome where
  | exactPass | exactFail | unknown | sampledPass | sampledFail
  deriving DecidableEq, Repr

structure CallSpec where
  callId : Nat
  entry : Nat
  arguments : List Nat
  deriving DecidableEq, Repr

structure Invocation where
  call : CallSpec
  target : Nat
  output : Nat
  meteredCost : Nat
  deriving DecidableEq, Repr

structure AtomCheck where
  atom : AtomId
  outcome : AtomOutcome
  deriving DecidableEq, Repr

structure CasePlan where
  caseId : CaseId
  key : CaseKey
  mandatoryEffective : Bool
  requiredAtoms : List AtomId
  requiredCalls : List (AtomId × CallSpec)
  deriving DecidableEq, Repr

structure CaseRecord where
  caseId : CaseId
  key : CaseKey
  binding : Binding
  classification : CaseClass
  guardExactFalse : Bool
  atoms : List AtomCheck
  invocations : List Invocation
  coverage : List CoverageId
  deriving DecidableEq, Repr

structure Policy where
  binding : Binding
  plan : List CasePlan
  minEffective : Nat
  maxCases : Nat
  maxInvocations : Nat
  maxMeteredCost : Nat
  requiredCoverage : List CoverageId
  deriving DecidableEq, Repr

structure Campaign where
  binding : Binding
  evidenceToken : Nat
  records : List CaseRecord
  deriving DecidableEq, Repr

def Matches (s : CasePlan) (r : CaseRecord) : Prop :=
  r.caseId = s.caseId ∧ r.key = s.key

def effectiveRecords (c : Campaign) : List CaseRecord :=
  c.records.filter (fun r => r.classification == .effectivePass)

def effectiveKeys (c : Campaign) : List CaseKey := (effectiveRecords c).map (·.key)

def invocationInventory (c : Campaign) : List Invocation := c.records.flatMap (·.invocations)

def meteredCost (c : Campaign) : Nat :=
  ((invocationInventory c).map (·.meteredCost)).foldl (· + ·) 0

def effectiveCoverage (c : Campaign) : List CoverageId :=
  (effectiveRecords c).flatMap (·.coverage)

/-- Complete exact checks and target-call coverage, not just one unrelated call receipt.
Every declared required atom has a nonempty call footprint. Shared calls can discharge
several atoms; distinct invocation IDs cannot alias separate receipts. -/
structure EffectiveChecked (p : Policy) (s : CasePlan) (r : CaseRecord) : Prop where
  binding : r.binding = p.binding
  nonemptyAtoms : s.requiredAtoms ≠ []
  atomsDistinct : (r.atoms.map (·.atom)).Nodup
  allAtomChecksExact : ∀ a ∈ r.atoms, a.outcome = .exactPass
  requiredAtomsChecked : ∀ a ∈ s.requiredAtoms,
    ∃ check ∈ r.atoms, check.atom = a ∧ check.outcome = .exactPass
  atomFootprintPositive : ∀ a ∈ s.requiredAtoms,
    ∃ call, (a, call) ∈ s.requiredCalls
  footprintAtomsRequired : ∀ ac ∈ s.requiredCalls, ac.1 ∈ s.requiredAtoms
  callsCovered : ∀ ac ∈ s.requiredCalls,
    ∃ inv ∈ r.invocations, inv.call = ac.2
  noUnplannedCalls : ∀ inv ∈ r.invocations,
    ∃ ac ∈ s.requiredCalls, inv.call = ac.2
  targetBound : ∀ inv ∈ r.invocations, inv.target = p.binding.target

/-- All selected planned cases are required to have a resolved terminal classification.
A checked false antecedent may discard a non-mandatory case, but it cannot count effective.
Mandatory boundary/witness cases must be effective and cannot be silently discarded. -/
def ResolvedCase (p : Policy) (s : CasePlan) (r : CaseRecord) : Prop :=
  (r.classification = .effectivePass ∧ EffectiveChecked p s r) ∨
  (r.classification = .discard ∧ r.guardExactFalse = true ∧
    s.mandatoryEffective = false ∧ r.binding = p.binding ∧
    ∀ inv ∈ r.invocations, inv.target = p.binding.target)

/-- Finite strict campaign acceptance. These are checks of the finite record, not a
quantification over all possible target inputs. The evidence and real-execution meaning of
the fields are deliberately absent from this data judgment and explicit in soundness.
Budget units are declared by the campaign: Nat bookkeeping is no wall-clock/resource proof.
Coverage tokens require an external faithful measurement premise as well. -/
structure Tested (p : Policy) (c : Campaign) : Prop where
  binding : c.binding = p.binding
  planIdsDistinct : (p.plan.map (·.caseId)).Nodup
  planKeysDistinct : (p.plan.map (·.key)).Nodup
  recordIdsDistinct : (c.records.map (·.caseId)).Nodup
  recordKeysDistinct : (c.records.map (·.key)).Nodup
  effectiveKeysDistinct : (effectiveKeys c).Nodup
  invocationIdsDistinct : ((invocationInventory c).map (·.call.callId)).Nodup
  completePlan : ∀ s ∈ p.plan, ∃ r ∈ c.records, Matches s r
  noUnplannedRecords : ∀ r ∈ c.records, ∃ s ∈ p.plan, Matches s r
  resolved : ∀ s ∈ p.plan, ∀ r ∈ c.records, Matches s r → ResolvedCase p s r
  positiveMinimum : 0 < p.minEffective
  enoughEffective : p.minEffective ≤ (effectiveKeys c).length
  caseBudget : c.records.length ≤ p.maxCases
  invocationBudget : (invocationInventory c).length ≤ p.maxInvocations
  costBudget : meteredCost c ≤ p.maxMeteredCost
  coverageComplete : ∀ label ∈ p.requiredCoverage, label ∈ effectiveCoverage c

theorem effective_checked (p : Policy) (c : Campaign) (h : Tested p c)
    (s : CasePlan) (hs : s ∈ p.plan) (r : CaseRecord) (hr : r ∈ c.records)
    (hm : Matches s r) (he : r.classification = .effectivePass) : EffectiveChecked p s r := by
  rcases h.resolved s hs r hr hm with hp | hd
  · exact hp.2
  · rw [he] at hd
    cases hd.1

theorem mandatory_effective (p : Policy) (c : Campaign) (h : Tested p c)
    (s : CasePlan) (hs : s ∈ p.plan) (hm : s.mandatoryEffective = true) :
    ∃ r ∈ c.records, Matches s r ∧ r.classification = .effectivePass ∧ EffectiveChecked p s r := by
  obtain ⟨r, hr, matchCase⟩ := h.completePlan s hs
  rcases h.resolved s hs r hr matchCase with hp | hd
  · exact ⟨r, hr, matchCase, hp.1, hp.2⟩
  · rw [hm] at hd
    cases hd.2.2.1

/-- Unknown, indeterminate, timeout and counterexample classifications cannot be hidden by
other passing cases, coverage or remaining budget. -/
theorem bad_terminal_blocks (p : Policy) (c : Campaign) (r : CaseRecord) (hr : r ∈ c.records)
    (bad : r.classification ≠ .effectivePass ∧ r.classification ≠ .discard) : ¬ Tested p c := by
  intro h
  obtain ⟨s, hs, hm⟩ := h.noUnplannedRecords r hr
  rcases h.resolved s hs r hr hm with hp | hd
  · exact bad.1 hp.1
  · exact bad.2 hd.1

theorem unknown_blocks (p : Policy) (c : Campaign) (r : CaseRecord) (hr : r ∈ c.records)
    (hk : r.classification = .unknown) : ¬ Tested p c := by
  apply bad_terminal_blocks p c r hr
  simp [hk]

theorem indeterminate_blocks (p : Policy) (c : Campaign) (r : CaseRecord) (hr : r ∈ c.records)
    (hk : r.classification = .indeterminate) : ¬ Tested p c := by
  apply bad_terminal_blocks p c r hr
  simp [hk]

theorem timeout_blocks (p : Policy) (c : Campaign) (r : CaseRecord) (hr : r ∈ c.records)
    (hk : r.classification = .timeout) : ¬ Tested p c := by
  apply bad_terminal_blocks p c r hr
  simp [hk]

theorem counterexample_blocks (p : Policy) (c : Campaign) (r : CaseRecord) (hr : r ∈ c.records)
    (hk : r.classification = .counterexample) : ¬ Tested p c := by
  apply bad_terminal_blocks p c r hr
  simp [hk]

theorem nonexact_atom_blocks_effective (p : Policy) (c : Campaign) (r : CaseRecord)
    (hr : r ∈ c.records) (he : r.classification = .effectivePass)
    (a : AtomCheck) (ha : a ∈ r.atoms) (hn : a.outcome ≠ .exactPass) : ¬ Tested p c := by
  intro h
  obtain ⟨s, hs, hm⟩ := h.noUnplannedRecords r hr
  exact hn ((effective_checked p c h s hs r hr hm he).allAtomChecksExact a ha)

theorem positive_effective_nonvacuity (p : Policy) (c : Campaign) (h : Tested p c) :
    ∃ r ∈ c.records, r.classification = .effectivePass := by
  have positive : 0 < (effectiveKeys c).length := Nat.lt_of_lt_of_le h.positiveMinimum h.enoughEffective
  have nonempty : effectiveRecords c ≠ [] := by
    intro empty
    simp [effectiveKeys, empty] at positive
  cases hs : effectiveRecords c with
  | nil => exact False.elim (nonempty hs)
  | cons r rest =>
    have member : r ∈ effectiveRecords c := by rw [hs]; exact List.mem_cons_self
    have selected := List.mem_filter.mp member
    exact ⟨r, selected.1, by simpa using selected.2⟩

/-- A positive recorded target receipt. Its actual execution and relevance require the
external premises in positive_actual_target_observation below. -/
theorem positive_target_observation (p : Policy) (c : Campaign) (h : Tested p c) :
    ∃ r ∈ c.records, r.classification = .effectivePass ∧
      ∃ inv ∈ r.invocations, inv.target = p.binding.target := by
  obtain ⟨r, hr, he⟩ := positive_effective_nonvacuity p c h
  obtain ⟨s, hs, hm⟩ := h.noUnplannedRecords r hr
  have checks := effective_checked p c h s hs r hr hm he
  cases hatoms : s.requiredAtoms with
  | nil => exact False.elim (checks.nonemptyAtoms hatoms)
  | cons a rest =>
    have ha : a ∈ s.requiredAtoms := by rw [hatoms]; exact List.mem_cons_self
    obtain ⟨call, hc⟩ := checks.atomFootprintPositive a ha
    obtain ⟨inv, hi, _⟩ := checks.callsCovered (a, call) hc
    exact ⟨r, hr, he, inv, hi, checks.targetBound inv hi⟩

/-! ## Explicit external assumptions and finite soundness -/

structure Semantics where
  evidenceBound : Binding → Nat → Prop
  actualInvocation : Binding → CaseKey → Invocation → Prop
  guardTrue : CaseKey → List Invocation → Prop
  acceptedAtom : CaseKey → AtomId → List Invocation → Prop
  /-- The full accepted guarded instance A ∧ P, not a selected subset of its atoms. -/
  effectivePredicate : CaseKey → List Invocation → Prop
  referencedCall : CaseKey → AtomId → CallSpec → Prop
  actualCoverage : CoverageId → Prop

def EvidenceBound (m : Semantics) (p : Policy) (c : Campaign) : Prop :=
  m.evidenceBound p.binding c.evidenceToken

/-- Includes exact execution/binding/freshness and canonical semantic key fidelity. These
facts require an external verifier; recorded target fields and distinct tokens do not prove them. -/
def ExecutionFaithful (m : Semantics) (p : Policy) (c : Campaign) : Prop :=
  ∀ r ∈ c.records, ∀ inv ∈ r.invocations, m.actualInvocation p.binding r.key inv

def CheckerSound (m : Semantics) (p : Policy) (c : Campaign) : Prop :=
  ∀ s ∈ p.plan, ∀ r ∈ c.records, Matches s r →
    ∀ a ∈ r.atoms, a.outcome = .exactPass →
      m.guardTrue s.key r.invocations ∧ m.acceptedAtom s.key a.atom r.invocations

def NegativeCheckerSound (m : Semantics) (p : Policy) (c : Campaign) : Prop :=
  ∀ s ∈ p.plan, ∀ r ∈ c.records, Matches s r →
    ∀ a ∈ r.atoms, a.outcome = .exactFail →
      m.guardTrue s.key r.invocations ∧ ¬ m.acceptedAtom s.key a.atom r.invocations

/-- Complete meaning-preserving atomization of the accepted guarded residual. This is an
external premise about the frozen accepted predicate, not a fact derived from a plan's list.
For example, selecting only one conjunct of a false conjunction cannot satisfy it. -/
def AtomizationAdequate (m : Semantics) (p : Policy) : Prop :=
  ∀ s ∈ p.plan, ∀ trace,
    (m.guardTrue s.key trace ∧ ∀ a ∈ s.requiredAtoms, m.acceptedAtom s.key a trace) ↔
      m.effectivePredicate s.key trace

/-- The required call list equals the actual accepted residual footprint in both directions.
Completeness alone would permit unrelated dummy calls. Nested/shared target calls and
memoized receipts must retain their actual identities. -/
def FootprintFaithful (m : Semantics) (p : Policy) : Prop :=
  ∀ s ∈ p.plan, ∀ a ∈ s.requiredAtoms, ∀ call,
    m.referencedCall s.key a call ↔ (a, call) ∈ s.requiredCalls

def DiscardSound (m : Semantics) (p : Policy) (c : Campaign) : Prop :=
  ∀ r ∈ c.records, r.binding = p.binding → r.guardExactFalse = true →
    ¬ m.guardTrue r.key r.invocations

def CoverageSound (m : Semantics) (c : Campaign) : Prop :=
  ∀ label ∈ effectiveCoverage c, m.actualCoverage label

/-- The result is deliberately finite: accepted ground residual atoms and faithful target
observations for this case. There is no all-input claim or E2E predicate in the conclusion. -/
def FiniteCaseSound (m : Semantics) (p : Policy) (s : CasePlan) (r : CaseRecord) : Prop :=
  m.guardTrue s.key r.invocations ∧
  (∀ a ∈ s.requiredAtoms, m.acceptedAtom s.key a r.invocations) ∧
  (∀ a ∈ s.requiredAtoms, ∀ call, m.referencedCall s.key a call →
    ∃ inv ∈ r.invocations, inv.call = call ∧ inv.target = p.binding.target ∧
      m.actualInvocation p.binding s.key inv) ∧
  (∀ a ∈ s.requiredAtoms, ∃ call inv, m.referencedCall s.key a call ∧
    inv ∈ r.invocations ∧ inv.call = call ∧ inv.target = p.binding.target ∧
      m.actualInvocation p.binding s.key inv)

theorem finite_acceptance_sound (m : Semantics) (p : Policy) (c : Campaign) (h : Tested p c)
    (evidence : EvidenceBound m p c) (execution : ExecutionFaithful m p c)
    (checker : CheckerSound m p c) (footprint : FootprintFaithful m p) :
    EvidenceBound m p c ∧
    (∀ s ∈ p.plan, ∀ r ∈ c.records, Matches s r →
      (s.mandatoryEffective = true ∨ r.classification = .effectivePass) →
      r.classification = .effectivePass ∧ FiniteCaseSound m p s r) := by
  refine ⟨evidence, ?_⟩
  intro s hs r hr hm required
  have he : r.classification = .effectivePass := by
    rcases h.resolved s hs r hr hm with hp | hd
    · exact hp.1
    · rcases required with mandatory | effective
      · rw [mandatory] at hd; cases hd.2.2.1
      · rw [effective] at hd; cases hd.1
  have checks := effective_checked p c h s hs r hr hm he
  refine ⟨he, ?_, ?_, ?_, ?_⟩
  · cases hatoms : s.requiredAtoms with
    | nil => exact False.elim (checks.nonemptyAtoms hatoms)
    | cons atom rest =>
      have ha : atom ∈ s.requiredAtoms := by rw [hatoms]; exact List.mem_cons_self
      obtain ⟨check, hc, _, hp⟩ := checks.requiredAtomsChecked atom ha
      exact (checker s hs r hr hm check hc hp).1
  · intro atom ha
    obtain ⟨check, hc, hatom, hp⟩ := checks.requiredAtomsChecked atom ha
    rw [← hatom]
    exact (checker s hs r hr hm check hc hp).2
  · intro atom ha call href
    obtain ⟨inv, hi, hcall⟩ := checks.callsCovered (atom, call)
      ((footprint s hs atom ha call).mp href)
    refine ⟨inv, hi, hcall, checks.targetBound inv hi, ?_⟩
    rw [← hm.2]
    exact execution r hr inv hi
  · intro atom ha
    obtain ⟨call, hc⟩ := checks.atomFootprintPositive atom ha
    obtain ⟨inv, hi, hcall⟩ := checks.callsCovered (atom, call) hc
    refine ⟨call, inv, (footprint s hs atom ha call).mpr hc,
      hi, hcall, checks.targetBound inv hi, ?_⟩
    rw [← hm.2]
    exact execution r hr inv hi

/-- Full accepted A ∧ P holds on every mandatory/effective observed case, conditionally on
faithful execution, exact checking, complete atomization and exact call-footprint premises.
This statement remains restricted to this finite campaign. -/
theorem finite_effective_predicate_sound (m : Semantics) (p : Policy) (c : Campaign)
    (h : Tested p c) (evidence : EvidenceBound m p c) (execution : ExecutionFaithful m p c)
    (checker : CheckerSound m p c) (footprint : FootprintFaithful m p)
    (atomization : AtomizationAdequate m p) :
    EvidenceBound m p c ∧
    (∀ s ∈ p.plan, ∀ r ∈ c.records, Matches s r →
      (s.mandatoryEffective = true ∨ r.classification = .effectivePass) →
      r.classification = .effectivePass ∧ m.effectivePredicate s.key r.invocations ∧
        FiniteCaseSound m p s r) := by
  refine ⟨evidence, ?_⟩
  intro s hs r hr hm required
  obtain ⟨he, sound⟩ :=
    (finite_acceptance_sound m p c h evidence execution checker footprint).2 s hs r hr hm required
  exact ⟨he, (atomization s hs r.invocations).mp ⟨sound.1, sound.2.1⟩, sound⟩

/-- Positive finite acceptance includes a target invocation actually referenced by a
required atom. Thus neither a dummy call nor a zero-call footprint establishes non-vacuity. -/
theorem positive_actual_target_observation (m : Semantics) (p : Policy) (c : Campaign)
    (h : Tested p c) (evidence : EvidenceBound m p c) (execution : ExecutionFaithful m p c)
    (footprint : FootprintFaithful m p) :
    EvidenceBound m p c ∧
    ∃ s ∈ p.plan, ∃ r ∈ c.records, ∃ a ∈ s.requiredAtoms, ∃ call inv,
      r.classification = .effectivePass ∧ m.referencedCall s.key a call ∧
      inv ∈ r.invocations ∧ inv.call = call ∧ inv.target = p.binding.target ∧
      m.actualInvocation p.binding s.key inv := by
  obtain ⟨r, hr, he⟩ := positive_effective_nonvacuity p c h
  obtain ⟨s, hs, hm⟩ := h.noUnplannedRecords r hr
  have checks := effective_checked p c h s hs r hr hm he
  cases hatoms : s.requiredAtoms with
  | nil => exact False.elim (checks.nonemptyAtoms hatoms)
  | cons a rest =>
    have ha : a ∈ s.requiredAtoms := by rw [hatoms]; exact List.mem_cons_self
    obtain ⟨call, hc⟩ := checks.atomFootprintPositive a ha
    obtain ⟨inv, hi, hcall⟩ := checks.callsCovered (a, call) hc
    refine ⟨evidence, s, hs, r, hr, a, ha, call, inv, he,
      (footprint s hs a ha call).mpr hc, hi, hcall, checks.targetBound inv hi, ?_⟩
    rw [← hm.2]
    exact execution r hr inv hi

theorem discarded_cases_sound (m : Semantics) (p : Policy) (c : Campaign)
    (h : Tested p c) (discard : DiscardSound m p c)
    (r : CaseRecord) (hr : r ∈ c.records) (hd : r.classification = .discard) :
    ¬ m.guardTrue r.key r.invocations := by
  obtain ⟨s, hs, hm⟩ := h.noUnplannedRecords r hr
  rcases h.resolved s hs r hr hm with hp | skipped
  · rw [hd] at hp; cases hp.1
  · exact discard r hr skipped.2.2.2.1 skipped.2.1

theorem coverage_sound (m : Semantics) (p : Policy) (c : Campaign)
    (h : Tested p c) (coverage : CoverageSound m c) :
    ∀ label ∈ p.requiredCoverage, m.actualCoverage label := by
  intro label required
  exact coverage label (h.coverageComplete label required)

/-! ## Concrete counterexamples and bounded adversarial review

A representation/ABI failure can be a verifier-owned atom only when its meaning is frozen
with the checked predicate/profile binding. A status string, suggested trigger or suspected
failure is not a negative certificate. The following judgment still requires external exact
negative-checker, complete footprint and faithful replay premises.
-/

structure ConfirmedReplayData (p : Policy) (s : CasePlan) (r : CaseRecord)
    (negative : AtomCheck) : Prop where
  matchingCase : Matches s r
  binding : r.binding = p.binding
  counterexample : r.classification = .counterexample
  recorded : negative ∈ r.atoms
  required : negative.atom ∈ s.requiredAtoms
  exactNegative : negative.outcome = .exactFail
  positiveFootprint : ∃ call, (negative.atom, call) ∈ s.requiredCalls
  callsCovered : ∀ ac ∈ s.requiredCalls, ∃ inv ∈ r.invocations, inv.call = ac.2
  targetBound : ∀ inv ∈ r.invocations, inv.target = p.binding.target

theorem confirmed_counterexample_sound (m : Semantics) (p : Policy) (c : Campaign)
    (s : CasePlan) (hs : s ∈ p.plan) (r : CaseRecord) (hr : r ∈ c.records)
    (negative : AtomCheck) (data : ConfirmedReplayData p s r negative)
    (evidence : EvidenceBound m p c) (execution : ExecutionFaithful m p c)
    (checker : NegativeCheckerSound m p c) (footprint : FootprintFaithful m p) :
    EvidenceBound m p c ∧ m.guardTrue s.key r.invocations ∧
    ¬ m.acceptedAtom s.key negative.atom r.invocations ∧
    (∃ call inv, m.referencedCall s.key negative.atom call ∧ inv ∈ r.invocations ∧
      inv.call = call ∧ inv.target = p.binding.target ∧ m.actualInvocation p.binding s.key inv) ∧
    (∀ call, m.referencedCall s.key negative.atom call →
      ∃ inv ∈ r.invocations, inv.call = call ∧ m.actualInvocation p.binding s.key inv) := by
  have checked := checker s hs r hr data.matchingCase negative data.recorded data.exactNegative
  refine ⟨evidence, checked.1, checked.2, ?_, ?_⟩
  · obtain ⟨call, hc⟩ := data.positiveFootprint
    obtain ⟨inv, hi, he⟩ := data.callsCovered (negative.atom, call) hc
    refine ⟨call, inv, (footprint s hs negative.atom data.required call).mpr hc,
      hi, he, data.targetBound inv hi, ?_⟩
    rw [← data.matchingCase.2]
    exact execution r hr inv hi
  · intro call href
    obtain ⟨inv, hi, he⟩ := data.callsCovered (negative.atom, call)
      ((footprint s hs negative.atom data.required call).mp href)
    refine ⟨inv, hi, he, ?_⟩
    rw [← data.matchingCase.2]
    exact execution r hr inv hi

/-- A faithfully replayed negative required atom refutes the full accepted guarded
instance only under complete atomization. A suggested input alone establishes neither fact. -/
theorem confirmed_counterexample_refutes_effective_predicate (m : Semantics) (p : Policy)
    (c : Campaign) (s : CasePlan) (hs : s ∈ p.plan) (r : CaseRecord) (hr : r ∈ c.records)
    (negative : AtomCheck) (data : ConfirmedReplayData p s r negative)
    (evidence : EvidenceBound m p c) (execution : ExecutionFaithful m p c)
    (checker : NegativeCheckerSound m p c) (footprint : FootprintFaithful m p)
    (atomization : AtomizationAdequate m p) :
    EvidenceBound m p c ∧ ¬ m.effectivePredicate s.key r.invocations := by
  have replay := confirmed_counterexample_sound m p c s hs r hr negative data
    evidence execution checker footprint
  refine ⟨replay.1, ?_⟩
  intro positive
  exact replay.2.2.1
    (((atomization s hs r.invocations).mpr positive).2 negative.atom data.required)

theorem sound_negative_cannot_be_invented_for_true_atom (m : Semantics) (p : Policy)
    (c : Campaign) (checker : NegativeCheckerSound m p c)
    (s : CasePlan) (hs : s ∈ p.plan) (r : CaseRecord) (hr : r ∈ c.records)
    (hm : Matches s r) (a : AtomCheck) (ha : a ∈ r.atoms)
    (correct : m.acceptedAtom s.key a.atom r.invocations) : a.outcome ≠ .exactFail := by
  intro falseReport
  exact (checker s hs r hr hm a ha falseReport).2 correct

inductive SearchConclusion where
  | confirmedCounterexample | noCounterexampleFound
  deriving DecidableEq, Repr

/-- Completion of a fixed bounded search is a workflow judgment only. In the confirmed
case, a separate sound replay certificate is required to establish a defect. The no-findings
case neither needs an invented counterexample nor entails program acceptance/universal truth.
Semantic search keys abstract the frozen recipe/scope; real completion needs external audit. -/
def BoundedSearchCompleted (planned attempted : List CaseKey) (budget : Nat)
    (_conclusion : SearchConclusion) : Prop :=
  planned ≠ [] ∧ planned.Nodup ∧ attempted = planned ∧ attempted.length ≤ budget

theorem bounded_search_may_finish_without_counterexample (planned : List CaseKey)
    (nonempty : planned ≠ []) (distinct : planned.Nodup)
    (budget : Nat) (withinBudget : planned.length ≤ budget) :
    BoundedSearchCompleted planned planned budget .noCounterexampleFound :=
  ⟨nonempty, distinct, rfl, withinBudget⟩

theorem empty_search_cannot_complete (attempted : List CaseKey) (budget : Nat)
    (conclusion : SearchConclusion) : ¬ BoundedSearchCompleted [] attempted budget conclusion := by
  intro completed
  exact completed.1 rfl

/-! ## Exactness discipline for sampled and existential formulas -/

def SampledUniversal (samples : List Nat) (body : Nat → Prop) : Prop :=
  ∀ n ∈ samples, body n

theorem sampled_universal_is_only_sampled (samples : List Nat) (body : Nat → Prop)
    (h : SampledUniversal samples body) (n : Nat) (hn : n ∈ samples) : body n := h n hn

theorem sampled_universal_not_universal :
    SampledUniversal [0, 1, 2] (fun n => n ≤ 100) ∧ ¬ (∀ n : Nat, n ≤ 100) := by
  constructor
  · intro n hn
    simp only [List.mem_cons, List.not_mem_nil, or_false] at hn
    rcases hn with rfl | rfl | rfl <;> decide
  · intro universal
    exact (by decide : ¬ (101 ≤ 100)) (universal 101)

/-- Passing concrete finite tests does not establish all-input refinement. -/
def faultyIncrement (x : Nat) : Nat := if x = 2 then 0 else x + 1

theorem finite_increment_tests_not_refinement :
    SampledUniversal [0, 1] (fun x => faultyIncrement x = x + 1) ∧
    faultyIncrement 2 ≠ 3 := by
  constructor
  · intro x hx
    simp only [List.mem_cons, List.not_mem_nil, or_false] at hx
    rcases hx with rfl | rfl <;> decide
  · decide

def FiniteExists {α : Type} (domain : List α) (body : α → Prop) : Prop :=
  ∃ x, x ∈ domain ∧ body x

/-- A positive existential requires a concrete checked witness, not failed witness search. -/
structure WitnessCertificate {α : Type} (body : α → Prop) where
  witness : α
  checked : body witness

theorem checked_witness_proves_exists {α : Type} {body : α → Prop}
    (certificate : WitnessCertificate body) : ∃ x, body x :=
  ⟨certificate.witness, certificate.checked⟩

theorem checked_finite_witness {α : Type} {domain : List α} {body : α → Prop}
    (certificate : WitnessCertificate body) (member : certificate.witness ∈ domain) :
    FiniteExists domain body := ⟨certificate.witness, member, certificate.checked⟩

/-- Finite existential false is sound exactly when every domain member has an exact-negative
body certificate. A sampled/unknown body is not such a certificate, even for a finite outer sort. -/
theorem finite_exists_negative_iff {α : Type} (domain : List α) (body : α → Prop) :
    ¬ FiniteExists domain body ↔ ∀ x ∈ domain, ¬ body x := by
  constructor
  · intro negative x member positive
    exact negative ⟨x, member, positive⟩
  · intro negatives positive
    obtain ⟨x, member, checked⟩ := positive
    exact negatives x member checked

theorem exact_finite_exists_true_has_witness {α : Type} (domain : List α) (body : α → Prop)
    (positive : FiniteExists domain body) : ∃ x, x ∈ domain ∧ body x := positive

/-- The counterexample to treating a sampled inner universal as exact true and propagating
its negation as exact false through a finite existential. This is a mathematical proposition,
not a theorem about the Python oracle, whose implementation remains unproved here. -/
theorem finite_bool_nested_universal_counterexample :
    (∃ _ : Bool, ¬ (∀ n : Nat, n ≤ 100)) ∧
    ¬ (∃ _ : Bool, ¬ SampledUniversal [0, 1, 2] (fun n => n ≤ 100)) := by
  refine ⟨⟨false, sampled_universal_not_universal.2⟩, ?_⟩
  intro sampledNegative
  obtain ⟨_, negative⟩ := sampledNegative
  exact negative sampled_universal_not_universal.1

end TestingModel
