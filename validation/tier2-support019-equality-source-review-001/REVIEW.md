# Equality candidate 019: independent source review

Status: SOURCE_REVIEW_COMPLETE_WITH_FINDINGS. This is a source review, not actual-Lean qualification or independent verification of the development process receipts. No repair has started under this review.

## Finding 1: a safe private equality definition blocks available deriving

Location: `validation/tier2-refutation-equality-support-019-implementation/contract_refutation_candidate.py:398-410`, with the resulting early return at `:434-437` and the existing name printer at `:35-39`.

The candidate considers every exact-type declaration in the full replayed Env. After `_enum_equality_declaration` accepts a definition, `_qualified(equality_name)` runs outside the `except reify.Unsupported` selection loop. A private declaration has a numeric component in its actual kernel name. `exprjson.parse_name` converts that component to an integer (`verislop/exprjson.py:59-62`), and `_qualified` rejects any non-string component. `_proof` consequently returns `{ok: false, reason: "unsupported Lean name component"}` before attempting a compile, rather than trying another printable definition or the safe deriving fallback.

Concrete fresh unrelated source witness, not executed by this review:

```lean
import Std
namespace RefutationEquality019
inductive Token where | amber | violet
private def hiddenEq : DecidableEq Token := fun a b => by
  cases a <;> cases b
  · exact isTrue rfl
  · exact isFalse (by intro h; cases h)
  · exact isFalse (by intro h; cases h)
  · exact isTrue rfl
def swap (t : Token) : Token :=
  match t with | .amber => .violet | .violet => .amber
theorem wrongToken (t : Token) : swap t = t := by sorry
end RefutationEquality019
```

Bind the public Token/swap declarations and the wrongToken guarantee in the ordinary generic formalization. Submit the amber concrete input, or call `_proof` for `Not (swap Token.amber = Token.amber)` with the accepted profile and actual base Env.

For module `VeriSlopContract`, the private equality name is `_private.VeriSlopContract.0.RefutationEquality019.hiddenEq`. Pinned Lean 4.34.1's `Lean/PrivateName.lean:18-30` explicitly defines this name shape using `Name.mkNum ... 0`. It has the exact exported nominal `DecidableEq.{1} Token` type. The hand-written body is monomorphic and safe, uses no sorry/choice/unsafe/partial machinery, and satisfies the existing equality audit when accompanied by its actual declaration/closure hashes. Full private inventory availability is part of the existing kernel API (`verislop/lean/VeriSlopKernel.lean:374-377`); this is not a forged Env or admission expansion.

The baseline deriving path remains available: Token has no deriving command, `hiddenEq` is an ordinary private definition rather than an attributed instance, and its name/body do not occupy `Token.ofNat`, `Token.ofNat_ctorIdx`, or the generated public equality-instance name. The baseline `_derivations` at `verislop/contract_refutation.py:393` ignores this private definition and emits the original derivation for the public finite enum. The closed inequality is then a legitimate proof-producing deriving/decide case. The new selection therefore introduces an availability regression without creating a false proof receipt. None of the 44 registered control labels covers a private equality name.

## Finding 2: two binding-negative assertions cannot detect removal of the binding guard

Location: `validation/tier2-refutation-equality-support-019-implementation/test_candidate_019.py:503-509`; guard claimed to be exercised: candidate `:523-525`.

The changed-source and forged-analysis subchecks prepare the true `rightToken` guarantee, pass no proposals, and assert only UNKNOWN with no receipts. The first source mutation adds a comment, which legitimately preserves the kernel-derived semantic Analysis identity. This review does not require comment-only changes to be rejected: the checker recompiles the exact fresh source and binds its new source hash. UNKNOWN is already the correct result for the original true guarantee, so this assertion cannot demonstrate the semantic binding guard.

A concrete source mutant that replaces the fresh-versus-supplied Analysis identity comparison with `False`, preserving all other code, would still satisfy both subchecks. For forged-analysis, the candidate later scans `fresh.statements`; the fresh true rightToken formula yields no counterexample and no receipt even though the forged supplied Analysis was allowed through. For the comment-only change, the same true guarantee likewise returns UNKNOWN. The remaining invalid-wire assertions in this grouped control do not exercise the removed guard and remain unchanged. This witness follows directly from source; no mutant was created or executed.

This is a fixture assertion gap, not an acceptance bypass in the inspected candidate: the actual identity guard is present. The 44-control development summary therefore cannot substantiate semantic binding rejection through these two assertions alone. A discriminating control should use an otherwise refutable guarantee with genuinely mismatched semantic Analysis and check the binding diagnostic, absence of proof attempts/receipts, and the differing result when the identity guard is removed.

## Remaining inspected scope and limits

The actual candidate diff is confined to `_derivations` and its preparation call in `_proof`. Discovery uses the fresh independently replayed base Env obtained in `check` at `:514-525`, exact nominal `DecidableEq` type with universe `[1]`, sorted declaration names, and the unchanged existing audit. That audit checks safe monomorphic definition identity and the local semantic closure/hashes, rejecting forbidden/noncomputable machinery; rejected candidates fall through to deriving except for the printable-name failure above. The original nested record dependency walk is unchanged. The namespace-qualified generated alias collision guard is present. The final expression printer, source prefix concatenation, compiler/resource options, exact base-declaration hash checks, replay/defeq/root/axiom acceptance, and receipt construction are unchanged by the diff. No additional concrete defect was found in these paths.

Current fixture source defines 40 main control labels plus four supplementary labels, consistent with the 44 distinct latest labels in the development metadata. Positive fixture assertions require genuine receipts and inspect exact bindings, retained artifact hashes, base declaration hashes, safe roots, defeq, zero sorry dependencies, and receipt/proof hashes. Result-field positives explicitly add the disclosed Except equality prerequisite; the missing-prerequisite UNKNOWN case and preexisting all-profile derivation limitation are not production support claims. These observations concern what the source asserts; this review did not independently validate the 339 claimed actual process receipts or rerun any fixture.

Inspection read only the permitted generic code/design/fixture source and evidence metadata, plus necessary production and pinned Lean primary API source. An initial filename listing recursively included generic development-run filenames; no corresponding artifact contents were opened through that inventory. No current or historical native task/candidate/formula/proof/output contents were read. No tests, builds, native reruns, model calls, or task APIs were executed. Only this new review directory was written; production and all existing sealed roots were preserved.

## Exact reviewed identities

- Candidate: `37451a3ab0bad57a941acd32907dca89b75e1303c7bd41002b4ad4f765a0fcff`
- Candidate patch: `e0ac84daa693087dcb090d7179f5cd000337b29e1baa961465dcde3a09ffb5bc`
- Frozen design SPEC: `a17ed1183760e4d2cd33005582962689ab9b9871666507018f5758552a7bfbc0`
- Development review: `889014d45a6f4413c94d10245369f418dd25466f148e5ef3301e8c083e7b23b6`
- REVIEW_HANDOFF: `bb7036c1a8696f744a0358fde230bab3defedc25a5fd19d688251b1eeae71737`
- Implementation manifest: `cb5e7a79cde2ca5335f3cd6d557aea901ef28fe98966a834c2a6eecd30f6ef0b`
- Design manifest: `98f51e07e08f7e30c00dc48186101ba8473006e6df3379ddd1f7798bbad6d5a7`
- Main fixture source: `38a7e5733e269453bf80cafaec45f315e56b08f528d1166059ea63160df960ae`
- Supplementary fixture source: `ba385b85ba436270f8dc4009b78a179b31d462d763eee853ab6eddaf161353c3`
- Existing reify audit: `da2022fd61c95a3d09b8d59f6630a4492b4ef3d3170e82d479f712965e0733f4`
- Existing Expr/name API: `32cc06b49c5637206ab885b9aa2cf3c19f275cbf6b99946612a04f3b6f10d329`

STOP. Any fix requires a separate candidate revision and fresh unrelated control; this review grants no production installation or qualification authority.
