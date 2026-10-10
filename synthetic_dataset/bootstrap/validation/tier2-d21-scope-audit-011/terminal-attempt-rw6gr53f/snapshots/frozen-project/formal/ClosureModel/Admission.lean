import ClosureModel.Lifecycle

/-!
# Backend selection, implementation parameters and Tier 2 admission

Milestone §1, §2, §8 and §11. A backend is selected only by the frozen tuple
`(tier, target, endpoint, backend_version)`; unknown versions and incompatible tuples fail closed.
Test requirements are resolved before admission; a campaign that no registered backend can
run blocks admission rather than being dropped. The covered guarantee set is exactly the
required guarantees whose base lifecycle makes implementation milestones applicable, and every
one of them must have a supported transfer translation. Python mirror:
`verislop/backends/registry.py` and `verislop/backends/admission.py`.
-/

namespace ClosureModel

inductive Target where
  | python | vscore
  deriving DecidableEq, Repr

inductive Endpoint where
  | testCampaign | instrumentedRuntime | restrictedSource | proofBearingSource | extractedLanguage | nativeBinary
  deriving DecidableEq, Repr

/-- A registered backend descriptor. `version` is the minor of `<id>/0.<version>`. -/
structure Descriptor where
  tier : Nat
  target : Target
  endpoint : Endpoint
  version : Nat
  endToEndEligible : Bool
  testing : Bool
  deriving DecidableEq, Repr

/-- The supervisor-owned registry: Python Tier 0/1 adapters and `verislop.backend.vscore/0.1`. -/
def registry : List Descriptor :=
  [⟨0, .python, .testCampaign, 1, false, true⟩,
   ⟨1, .python, .instrumentedRuntime, 1, false, true⟩,
   ⟨2, .vscore, .restrictedSource, 1, true, false⟩]

def select (tier : Nat) (target : Target) (endpoint : Endpoint) (version : Nat) : Option Descriptor :=
  match registry.filter (fun d => d.tier == tier && d.target == target && d.endpoint == endpoint && d.version == version) with
  | [d] => some d
  | _ => none

theorem select_sound {tier target endpoint version d} (h : select tier target endpoint version = some d) :
    d ∈ registry ∧ d.tier = tier ∧ d.target = target ∧ d.endpoint = endpoint ∧ d.version = version := by
  unfold select at h
  split at h
  next heq =>
    cases h
    have hm : d ∈ registry.filter (fun d => d.tier == tier && d.target == target && d.endpoint == endpoint && d.version == version) := by
      rw [heq]; simp
    simp only [List.mem_filter, Bool.and_eq_true, beq_iff_eq] at hm
    exact ⟨hm.1, hm.2.1.1.1, hm.2.1.1.2, hm.2.1.2, hm.2.2⟩
  next => cases h

/-- Unknown versions and Tier 3/4 or native requests select nothing. -/
example : select 2 .vscore .restrictedSource 2 = none := by decide
example : select 2 .vscore .nativeBinary 1 = none := by decide
example : select 2 .python .restrictedSource 1 = none := by decide
example : select 3 .vscore .proofBearingSource 1 = none := by decide
example : select 4 .vscore .nativeBinary 1 = none := by decide
example : (select 2 .vscore .restrictedSource 1).isSome = true := by decide

inductive RequireState where
  | tested | endToEnd
  deriving DecidableEq, Repr

/-- `--require-tests`, `--no-tests` or neither (they are mutually exclusive flags). -/
inductive TestFlag where
  | omitted | requireTests | noTests
  deriving DecidableEq, Repr

inductive Code where
  | unsupportedCapability | configurationInvalid | orphanClaim
  deriving DecidableEq, Repr

/-- Missing Tier 2 `require_state` resolves to `END_TO_END_VERIFIED`. -/
def resolveState (tier : Nat) : Option RequireState → Option RequireState
  | none => if tier == 2 then some .endToEnd else none
  | s => s

/-- §8: Tier 0 tests are mandatory, Tier 1 keeps its default, Tier 2 defaults to no campaign;
`--require-state TESTED` requires tests and contradicts `--no-tests`. -/
def resolveTests (tier : Nat) (state : Option RequireState) (flag : TestFlag) : Except Code Bool :=
  match state, flag with
  | some .tested, .noTests => .error .configurationInvalid
  | _, .requireTests => .ok true
  | _, .noTests => .ok (tier == 0)
  | some .tested, .omitted => .ok true
  | _, .omitted => .ok (tier < 2)

structure Params where
  descriptor : Descriptor
  state : Option RequireState
  requireTests : Bool
  deriving DecidableEq, Repr

/-- Parameter resolution never downgrades: an unselectable tuple, an end-to-end request to an
ineligible backend, or a required campaign without a campaign backend all fail. -/
def resolveParams (tier : Nat) (target : Target) (endpoint : Endpoint) (version : Nat)
    (state : Option RequireState) (flag : TestFlag) : Except Code Params :=
  match resolveTests tier state flag with
  | .error e => .error e
  | .ok tests =>
    match select tier target endpoint version with
    | none => .error .unsupportedCapability
    | some d =>
      let s := resolveState tier state
      if s == some .endToEnd && !d.endToEndEligible then .error .unsupportedCapability
      else if tests && !d.testing then .error .unsupportedCapability
      else .ok ⟨d, s, tests⟩

theorem noTests_with_tested_is_invalid (tier target endpoint version) :
    resolveParams tier target endpoint version (some .tested) .noTests = .error .configurationInvalid := by
  simp [resolveParams, resolveTests]

/-- A Tier 2 VSCore request that requires tests is rejected before any implementer runs. -/
theorem vscore_tests_required_rejected (state : Option RequireState) (flag : TestFlag)
    (h : resolveTests 2 state flag = .ok true) :
    resolveParams 2 .vscore .restrictedSource 1 state flag = .error .unsupportedCapability := by
  simp only [resolveParams, h]
  cases state with
  | none => rfl
  | some s => cases s <;> rfl

theorem vscore_tier2_default (flag : TestFlag) (hflag : flag ≠ .requireTests) :
    resolveParams 2 .vscore .restrictedSource 1 none flag =
      .ok ⟨⟨2, .vscore, .restrictedSource, 1, true, false⟩, some .endToEnd, false⟩ := by
  cases flag <;> simp_all <;> rfl

/-! ## Obligation admission -/

/-- The admission-relevant facts of one accepted record. For guarantees they describe its
accepted contract-DSL statement; for declarations whether every bound declaration lies in the
representable profile (Nat, Bool, Unit, finite enumerations, nested Result). -/
structure Obligation where
  id : Nat
  role : Role
  kind : Kind
  required : Bool
  contractDsl : Bool
  mentionsSymbol : Bool
  callInRangeBound : Bool
  representableSorts : Bool
  declRepresentable : Bool
  deriving DecidableEq, Repr

def Obligation.covered (o : Obligation) : Bool :=
  o.required && o.role == .guarantee && applicable o.role o.kind .endToEnd

/-- The existing transfer rule applies; liveness and physical-resource claims are never read as
arithmetic statements about a delivered source. -/
def Obligation.transferSupported (o : Obligation) : Bool :=
  o.contractDsl && o.mentionsSymbol && !o.callInRangeBound && o.representableSorts &&
    o.kind != .livenessProperty && o.kind != .resourceConstraint

def Obligation.interfaceDeclaration (o : Obligation) : Bool :=
  o.required && o.role == .declaration

def coveredSet (os : List Obligation) : List Nat := (os.filter Obligation.covered).map (·.id)

def unsupportedSet (os : List Obligation) : List Nat :=
  (os.filter fun o => (o.covered && !o.transferSupported) || (o.interfaceDeclaration && !o.declRepresentable)).map (·.id)

inductive Admission where
  | admitted (covered : List Nat)
  | rejected (code : Code) (obligations : List Nat)
  deriving DecidableEq, Repr

/-- Admission happens before any implementer runs. -/
def admit (tier : Nat) (state : Option RequireState) (flag : TestFlag) (os : List Obligation) : Admission :=
  match resolveParams tier .vscore .restrictedSource 1 state flag with
  | .error e => .rejected e []
  | .ok _ =>
    match unsupportedSet os with
    | [] => if coveredSet os = [] then .rejected .orphanClaim [] else .admitted (coveredSet os)
    | bad => .rejected .unsupportedCapability bad

theorem admit_exact {tier state flag os c} (h : admit tier state flag os = .admitted c) :
    c = coveredSet os := by
  unfold admit at h
  split at h
  · cases h
  · split at h
    · split at h
      · cases h
      · cases h; rfl
    · cases h

theorem admitted_no_unsupported {tier state flag os c} (h : admit tier state flag os = .admitted c) :
    unsupportedSet os = [] := by
  unfold admit at h
  split at h
  · cases h
  · split at h
    · assumption
    · cases h

/-- Every covered guarantee of an admitted request has a supported transfer translation. -/
theorem admitted_supported {tier state flag os c} (h : admit tier state flag os = .admitted c)
    (o : Obligation) (ho : o ∈ os) (hc : o.covered = true) : o.transferSupported = true := by
  have hu := admitted_no_unsupported h
  unfold unsupportedSet at hu
  rw [List.map_eq_nil_iff, List.filter_eq_nil_iff] at hu
  have := hu o ho
  simp_all

/-- Optional guarantees and non-vacuity witnesses never enter the implementation set. -/
theorem covered_required (o : Obligation) (h : o.covered = true) :
    o.required = true ∧ o.role = .guarantee ∧ o.kind ≠ .nonVacuity := by
  unfold Obligation.covered at h
  simp only [Bool.and_eq_true, beq_iff_eq] at h
  obtain ⟨⟨hr, hg⟩, ha⟩ := h
  refine ⟨hr, hg, ?_⟩
  intro hk
  rw [hg, hk] at ha
  simp [applicable, Milestone.implementation] at ha

/-- An unsupported required guarantee blocks admission (it stays applicable and UNSUPPORTED). -/
theorem unsupported_required_blocks {tier state flag os} (o : Obligation) (ho : o ∈ os)
    (hc : o.covered = true) (hu : o.transferSupported = false) :
    ∀ c, admit tier state flag os ≠ .admitted c := by
  intro c h
  have := admitted_supported h o ho hc
  rw [hu] at this
  cases this

/-- A selected bridge must cover the required guarantee set exactly. -/
def selectionMatches (selected : List Nat) (os : List Obligation) : Bool :=
  selected.mergeSort (· ≤ ·) == (coveredSet os).mergeSort (· ≤ ·)

end ClosureModel
