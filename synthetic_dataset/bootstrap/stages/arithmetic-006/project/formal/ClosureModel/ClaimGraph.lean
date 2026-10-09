import ClosureModel.Lifecycle

/-!
# The frozen claim graph

Milestone §5. The supervisor derives every claim, its assigned verifier, typed predicate and
premise edges before execution. The graph contains the contract milestone claims, the
implementation milestone claims (including interface declarations), the structural preparation
claim, the selected semantic edge and the four final closure claims.

Phase order is a rank: every premise has a strictly smaller rank than the claim that uses it.
The final closure claims and the end-to-end claims are terminal: `CLOSURE:provenance` uses only
non-final claims, and no claim uses an end-to-end claim. A frozen inventory is accepted only if
its IDs are unique, its premises exist and respect the rank, which rules out cycles.
Python mirror: `verislop/claimgraph.py`.
-/

namespace ClosureModel

inductive ClaimKind where
  | milestone (m : Milestone) (o : Nat)
  | structural
  | semanticEdge
  | cleanBuilds | determinism | provenance | endpoint
  deriving DecidableEq, Repr

namespace ClaimKind

/-- Terminal-phase claims: the four `CLOSURE:*` claims and the end-to-end claims. -/
def final : ClaimKind → Bool
  | .milestone .endToEnd _ => true
  | .cleanBuilds | .determinism | .provenance | .endpoint => true
  | _ => false

def rank : ClaimKind → Nat
  | .milestone .endToEnd _ => 10
  | .milestone m _ => m.rank
  | .structural => 5
  | .semanticEdge => 6
  | .cleanBuilds => 7
  | .endpoint => 7
  | .determinism => 8
  | .provenance => 9

theorem rank_le (k : ClaimKind) : k.rank ≤ 10 := by
  cases k with
  | milestone m o => cases m <;> simp [rank, Milestone.rank]
  | _ => simp [rank]

theorem nonfinal_rank (k : ClaimKind) (h : k.final = false) : k.rank ≤ 6 := by
  cases k with
  | milestone m o => cases m <;> simp_all [final, rank, Milestone.rank]
  | _ => simp_all [final, rank]

end ClaimKind

/-- Verifier assignment. Backend operations never choose it. -/
inductive Verifier where
  | interpretationRecorder | formalStatementChecker | leanAcceptance
  | vscoreMaterializer | vscoreLinker | campaign
  | bridgePreparation | vscoreChecker | closure
  deriving DecidableEq, Repr

/-- Typed result predicates. The generic milestone predicate is kept only for the unchanged
contract-phase claims; no implementation, bridge or closure claim can be discharged by it. -/
inductive Predicate where
  | interpretationCoverage | milestonePass
  | vscoreMaterialized | vscoreLinked | campaign
  | bridgeStructural | bridgeSemanticEdge
  | closureCleanBuilds | closureDeterminism | closureProvenance | closureEndpoint
  | endToEnd
  deriving DecidableEq, Repr

def verifierOf : ClaimKind → Verifier
  | .milestone .interpreted _ => .interpretationRecorder
  | .milestone .formalized _ => .formalStatementChecker
  | .milestone .typechecked _ => .leanAcceptance
  | .milestone .proved _ => .leanAcceptance
  | .milestone .implemented _ => .vscoreMaterializer
  | .milestone .linked _ => .vscoreLinker
  | .milestone .tested _ => .campaign
  | .milestone .endToEnd _ => .closure
  | .structural => .bridgePreparation
  | .semanticEdge => .vscoreChecker
  | _ => .closure

def predicateOf : ClaimKind → Predicate
  | .milestone .interpreted _ => .interpretationCoverage
  | .milestone .formalized _ => .milestonePass
  | .milestone .typechecked _ => .milestonePass
  | .milestone .proved _ => .milestonePass
  | .milestone .implemented _ => .vscoreMaterialized
  | .milestone .linked _ => .vscoreLinked
  | .milestone .tested _ => .campaign
  | .milestone .endToEnd _ => .endToEnd
  | .structural => .bridgeStructural
  | .semanticEdge => .bridgeSemanticEdge
  | .cleanBuilds => .closureCleanBuilds
  | .determinism => .closureDeterminism
  | .provenance => .closureProvenance
  | .endpoint => .closureEndpoint

/-- Result formats produced by registered verifiers, and the predicates each can satisfy. -/
inductive ResultFormat where
  | milestoneResult | interpretationResult | materializationResult | linkResult | campaignResult
  | structuralResult | semanticEdgeResult | closureFinalResult (p : Predicate) | endToEndResult
  deriving DecidableEq, Repr

def satisfies : Predicate → ResultFormat → Bool
  | .interpretationCoverage, .interpretationResult => true
  | .milestonePass, .milestoneResult => true
  | .vscoreMaterialized, .materializationResult => true
  | .vscoreLinked, .linkResult => true
  | .campaign, .campaignResult => true
  | .bridgeStructural, .structuralResult => true
  | .bridgeSemanticEdge, .semanticEdgeResult => true
  | p, .closureFinalResult q => p == q &&
      (p == .closureCleanBuilds || p == .closureDeterminism || p == .closureProvenance || p == .closureEndpoint)
  | .endToEnd, .endToEndResult => true
  | _, _ => false

/-- A structural PASS cannot satisfy the semantic-edge predicate, and a generic milestone PASS
cannot discharge any implementation, bridge, closure or end-to-end predicate. -/
theorem structural_not_semantic : satisfies (predicateOf .semanticEdge) .structuralResult = false := rfl

theorem generic_pass_only_contract (k : ClaimKind)
    (h : satisfies (predicateOf k) .milestoneResult = true) :
    ∃ m o, k = .milestone m o ∧ m ∈ [.formalized, .typechecked, .proved] := by
  cases k with
  | milestone m o => cases m <;> simp_all [predicateOf, satisfies]
  | _ => simp_all [predicateOf, satisfies]

theorem closure_result_matches_own_claim (k : ClaimKind) (p : Predicate)
    (h : satisfies (predicateOf k) (.closureFinalResult p) = true) : predicateOf k = p := by
  cases k with
  | milestone m o => cases m <;> simp_all [predicateOf, satisfies]
  | _ => simp_all [predicateOf, satisfies]

/-! ## Derivation -/

structure Record where
  id : Nat
  role : Role
  kind : Kind
  required : Bool
  deriving DecidableEq, Repr

structure Context where
  records : List Record
  /-- The admitted covered guarantees (end-to-end claims are required for exactly these). -/
  covered : List Nat
  /-- Required declarations that participate in the interface. -/
  interface : List Nat
  /-- Whether the frozen test policy requires a campaign. -/
  tests : Bool
  deriving DecidableEq, Repr

def finals : List ClaimKind := [.cleanBuilds, .determinism, .provenance, .endpoint]

def Context.applicableFor (ctx : Context) (o : Nat) (m : Milestone) : Bool :=
  match ctx.records.find? (·.id == o) with
  | some r => applicable r.role r.kind m
  | none => false

def Context.milestoneClaims (ctx : Context) : List ClaimKind :=
  ctx.records.flatMap fun r => (Milestone.all.filter (applicable r.role r.kind)).map (.milestone · r.id)

def Context.inventory (ctx : Context) : List ClaimKind :=
  ctx.milestoneClaims ++ [.structural, .semanticEdge] ++ finals

def Context.required (ctx : Context) : ClaimKind → Bool
  | .milestone .endToEnd o => ctx.covered.contains o
  | .milestone .tested o => ctx.tests && ctx.covered.contains o
  | .milestone m o =>
      (ctx.records.find? (·.id == o)).any (fun r => r.required && applicable r.role r.kind m)
  | _ => true

/-- The premise edges the supervisor freezes. -/
def Context.premisesOf (ctx : Context) : ClaimKind → List ClaimKind
  | .milestone .endToEnd o =>
      [.milestone .proved o, .milestone .implemented o, .milestone .linked o]
      ++ ctx.interface.flatMap (fun d => [.milestone .implemented d, .milestone .linked d])
      ++ [.semanticEdge] ++ finals
      ++ (if ctx.tests then [.milestone .tested o] else [])
  | .milestone m o => ((Milestone.prerequisites m).filter (ctx.applicableFor o)).map (.milestone · o)
  | .structural => []
  | .semanticEdge => [.structural]
  | .cleanBuilds => []
  | .determinism => [.cleanBuilds]
  | .endpoint => [.semanticEdge]
  | .provenance => ctx.inventory.filter (fun k => !k.final && ctx.required k)

theorem premises_ranked (ctx : Context) (k p : ClaimKind) (h : p ∈ ctx.premisesOf k) :
    p.rank < k.rank := by
  cases k with
  | milestone m o =>
    cases m
    case endToEnd =>
      simp only [Context.premisesOf, List.mem_append, List.mem_flatMap, finals] at h
      rcases h with ((((h | h) | h) | h) | h)
      · simp at h; rcases h with h | h | h <;> subst h <;> simp [ClaimKind.rank, Milestone.rank]
      · obtain ⟨d, _, hd⟩ := h; simp at hd
        rcases hd with hd | hd <;> subst hd <;> simp [ClaimKind.rank, Milestone.rank]
      · simp at h; subst h; simp [ClaimKind.rank]
      · simp at h; rcases h with h | h | h | h <;> subst h <;> simp [ClaimKind.rank]
      · split at h <;> simp at h; subst h; simp [ClaimKind.rank, Milestone.rank]
    all_goals
      simp only [Context.premisesOf, List.mem_map, List.mem_filter] at h
      obtain ⟨q, ⟨hq, _⟩, rfl⟩ := h
      cases q <;> simp_all [ClaimKind.rank, Milestone.rank, Milestone.prerequisites]
  | structural => simp [Context.premisesOf] at h
  | semanticEdge => simp [Context.premisesOf] at h; subst h; simp [ClaimKind.rank]
  | cleanBuilds => simp [Context.premisesOf] at h
  | determinism => simp [Context.premisesOf] at h; subst h; simp [ClaimKind.rank]
  | endpoint => simp [Context.premisesOf] at h; subst h; simp [ClaimKind.rank]
  | provenance =>
    simp only [Context.premisesOf, List.mem_filter, Bool.and_eq_true, Bool.not_eq_true'] at h
    have := ClaimKind.nonfinal_rank p h.2.1
    show p.rank < 9
    omega

theorem no_self_premise (ctx : Context) (k : ClaimKind) : k ∉ ctx.premisesOf k := by
  intro h
  exact Nat.lt_irrefl _ (premises_ranked ctx k k h)

/-- No claim consumes an end-to-end claim, so end-to-end outcomes are always computed last. -/
theorem endToEnd_never_premise (ctx : Context) (k : ClaimKind) (o : Nat) :
    ClaimKind.milestone .endToEnd o ∉ ctx.premisesOf k := by
  intro h
  have h1 := premises_ranked ctx k _ h
  have h2 := ClaimKind.rank_le k
  have h3 : (ClaimKind.milestone .endToEnd o).rank = 10 := rfl
  omega

/-- `CLOSURE:provenance` validates planned edges of non-final claims only: it never requires the
not-yet-produced end-to-end records or its own record. -/
theorem provenance_premises_nonfinal (ctx : Context) (p : ClaimKind)
    (h : p ∈ ctx.premisesOf .provenance) : p.final = false := by
  simp only [Context.premisesOf, List.mem_filter, Bool.and_eq_true, Bool.not_eq_true'] at h
  exact h.2.1

/-- Each end-to-end claim depends on its exact accepted proof, its materialization and link
claims, those of the interface declarations, the selected semantic edge and all four final
closure claims (and a campaign only when the frozen policy requires one). -/
theorem endToEnd_premises_complete (ctx : Context) (o : Nat) :
    ClaimKind.milestone .proved o ∈ ctx.premisesOf (.milestone .endToEnd o) ∧
    ClaimKind.milestone .implemented o ∈ ctx.premisesOf (.milestone .endToEnd o) ∧
    ClaimKind.milestone .linked o ∈ ctx.premisesOf (.milestone .endToEnd o) ∧
    ClaimKind.semanticEdge ∈ ctx.premisesOf (.milestone .endToEnd o) ∧
    (∀ f ∈ finals, f ∈ ctx.premisesOf (.milestone .endToEnd o)) ∧
    (∀ d ∈ ctx.interface, ClaimKind.milestone .implemented d ∈ ctx.premisesOf (.milestone .endToEnd o) ∧
       ClaimKind.milestone .linked d ∈ ctx.premisesOf (.milestone .endToEnd o)) := by
  refine ⟨by simp [Context.premisesOf], by simp [Context.premisesOf], by simp [Context.premisesOf],
    by simp [Context.premisesOf], ?_, ?_⟩
  · intro f hf
    simp only [finals, List.mem_cons, List.not_mem_nil, or_false] at hf
    simp only [Context.premisesOf, finals, List.mem_append, List.mem_cons]
    rcases hf with h | h | h | h <;> simp [h]
  · intro d hd
    constructor <;> simp only [Context.premisesOf, List.mem_append, List.mem_flatMap] <;>
      exact Or.inl (Or.inl (Or.inl (Or.inr ⟨d, hd, by simp⟩)))

theorem tested_premise_iff_policy (ctx : Context) (o : Nat) :
    ClaimKind.milestone .tested o ∈ ctx.premisesOf (.milestone .endToEnd o) ↔ ctx.tests = true := by
  simp only [Context.premisesOf, finals, List.mem_append, List.mem_cons, List.mem_flatMap]
  constructor
  · intro h
    rcases h with ((((h | h) | h) | h) | h)
    · simp at h
    · obtain ⟨d, _, hd⟩ := h; simp at hd
    · simp at h
    · simp at h
    · split at h
      · assumption
      · simp at h
  · intro h; simp [h]

/-! ## Validation of a frozen inventory -/

/-- Unique IDs, existing premises and rank-respecting edges. -/
def wellFormed (claims : List (ClaimKind × List ClaimKind)) : Bool :=
  (claims.map Prod.fst).Nodup ∧
  claims.all (fun c => c.2.all (fun p => claims.any (·.1 == p) && decide (p.rank < c.1.rank)))

def Edge (claims : List (ClaimKind × List ClaimKind)) (a b : ClaimKind) : Prop :=
  ∃ ps, (a, ps) ∈ claims ∧ b ∈ ps

theorem edge_decreases {claims} (h : wellFormed claims = true) {a b : ClaimKind}
    (e : Edge claims a b) : b.rank < a.rank := by
  obtain ⟨ps, hmem, hb⟩ := e
  simp only [wellFormed, Bool.and_eq_true, decide_eq_true_eq, List.all_eq_true] at h
  have := h.2 (a, ps) hmem b hb
  simp at this
  exact this.2

theorem path_decreases {claims} (h : wellFormed claims = true) {a b : ClaimKind}
    (p : Relation.TransGen (Edge claims) a b) : b.rank < a.rank := by
  induction p with
  | single e => exact edge_decreases h e
  | tail _ e ih => exact Nat.lt_trans (edge_decreases h e) ih

/-- A well-formed frozen inventory has no cyclic premises. -/
theorem acyclic {claims} (h : wellFormed claims = true) (a : ClaimKind) :
    ¬ Relation.TransGen (Edge claims) a a :=
  fun p => Nat.lt_irrefl _ (path_decreases h p)

/-- The derived inventory with its premises. -/
def Context.graph (ctx : Context) : List (ClaimKind × List ClaimKind) :=
  ctx.inventory.map fun k => (k, ctx.premisesOf k)

end ClosureModel
