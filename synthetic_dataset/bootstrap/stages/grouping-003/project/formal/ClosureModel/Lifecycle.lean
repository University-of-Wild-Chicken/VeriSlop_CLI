/-!
# Lifecycle vocabulary

The eight milestones, six outcomes, record roles and kinds of `docs/obligation-states.md`,
with the base applicability rule and the milestone prerequisite map. The Python mirror is
`verislop/lifecycle.py`; the closure milestone (`docs/tier-2-closure-milestone.md` §5) keeps
these rules unchanged. In particular `END_TO_END_VERIFIED` does not require `TESTED`.
-/

namespace ClosureModel

inductive Milestone where
  | interpreted | formalized | typechecked | proved
  | implemented | linked | tested | endToEnd
  deriving DecidableEq, Repr, Inhabited

namespace Milestone

def all : List Milestone :=
  [interpreted, formalized, typechecked, proved, implemented, linked, tested, endToEnd]

def contract : List Milestone := [interpreted, formalized, typechecked, proved]

def implementation : List Milestone := [implemented, linked, tested, endToEnd]

/-- Normative prerequisites (obligation-states §2). -/
def prerequisites : Milestone → List Milestone
  | interpreted => []
  | formalized => [interpreted]
  | typechecked => [formalized]
  | proved => [typechecked]
  | implemented => [interpreted]
  | linked => [typechecked, implemented]
  | tested => [implemented, typechecked]
  | endToEnd => [proved, implemented, linked]

end Milestone

inductive Outcome where
  | pass | pending | fail | stale | unsupported | notApplicable
  deriving DecidableEq, Repr, Inhabited

inductive Role where
  | guarantee | assumption | declaration | exclusion | openQuestion
  deriving DecidableEq, Repr, Inhabited

inductive Kind where
  | entity | precondition | postcondition | invariant | safetyProperty | livenessProperty
  | resourceConstraint | errorSemantics | explicitNonGoal | ambiguity | nonVacuity
  deriving DecidableEq, Repr, Inhabited

/-- Base applicability by frozen role and kind (`lifecycle.applicability`). Required guarantee
milestones are never made inapplicable to obtain a passing report. -/
def applicable : Role → Kind → Milestone → Bool
  | .guarantee, .nonVacuity, m => !(Milestone.implementation.contains m)
  | .guarantee, _, _ => true
  | .assumption, _, m => m != .proved && !(Milestone.implementation.contains m)
  | .declaration, _, m => m != .proved && m != .tested && m != .endToEnd
  | .exclusion, _, m => m != .proved && !(Milestone.implementation.contains m)
  | .openQuestion, _, m => m != .proved && !(Milestone.implementation.contains m)

/-! ## Facts the milestone relies on -/

/-- §5: `END_TO_END_VERIFIED` requires `PROVED`, `IMPLEMENTED` and `LINKED`, not `TESTED`. -/
theorem endToEnd_prerequisites :
    Milestone.prerequisites .endToEnd = [.proved, .implemented, .linked] := rfl

theorem tested_not_prerequisite_of_endToEnd :
    Milestone.tested ∉ Milestone.prerequisites .endToEnd := by decide

/-- Non-vacuity is a contract-only witness obligation: no implementation milestone applies. -/
theorem nonVacuity_contract_only (m : Milestone) (h : m ∈ Milestone.implementation) :
    applicable .guarantee .nonVacuity m = false := by
  simp [applicable, h]

/-- Every ordinary guarantee keeps all eight milestones applicable. -/
theorem guarantee_all_applicable (k : Kind) (hk : k ≠ .nonVacuity) (m : Milestone) :
    applicable .guarantee k m = true := by
  cases k <;> simp_all [applicable]

/-- Declarations keep their materialization and link milestones; `PROVED`, `TESTED` and the
end-to-end milestone stay not applicable as in the base lifecycle. -/
theorem declaration_interface (k : Kind) :
    applicable .declaration k .implemented = true ∧ applicable .declaration k .linked = true ∧
    applicable .declaration k .proved = false ∧ applicable .declaration k .tested = false ∧
    applicable .declaration k .endToEnd = false := by
  simp [applicable]

/-- Assumptions are hypotheses: never proved, never implemented. -/
theorem assumption_not_implemented (k : Kind) (m : Milestone) (h : m ∈ Milestone.implementation) :
    applicable .assumption k m = false := by
  simp [applicable, h]

/-- The prerequisite map only points backwards in this rank, so it is acyclic. -/
def Milestone.rank : Milestone → Nat
  | .interpreted => 0 | .formalized => 1 | .typechecked => 2 | .proved => 3
  | .implemented => 1 | .linked => 4 | .tested => 4 | .endToEnd => 5

theorem prerequisites_ranked (m p : Milestone) (h : p ∈ Milestone.prerequisites m) :
    p.rank < m.rank := by
  cases m <;> cases p <;> simp [Milestone.prerequisites, Milestone.rank] at h ⊢

end ClosureModel
