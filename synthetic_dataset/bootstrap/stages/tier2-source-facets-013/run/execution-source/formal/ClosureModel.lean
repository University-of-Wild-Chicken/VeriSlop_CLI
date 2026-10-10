import ClosureModel.Lifecycle
import ClosureModel.Admission
import ClosureModel.ClaimGraph
import ClosureModel.Decision
import ClosureModel.Projection
import ClosureModel.Roots

/-!
# Formal model of the Tier 2 restricted-source closure milestone

A design model of `docs/tier-2-closure-milestone.md`, written before the implementation.
`tests/test_closure_model.py` uses its admission and lifecycle definitions as a conformance
oracle on a finite set of Python inputs. The other modules state the intended claim graph,
terminal evaluation, release and review-projection rules; their theorems are proofs about
this model, not a proof of the Python implementation.

The model covers decisions, not bytes. Hashes are abstract functions, evidence is reduced to
outcomes, and the VSCore semantics and refinement proofs remain those of `verislop/lean/VSCore`.
Neither compiling the model nor passing its finite conformance checks establishes full
pipeline closure, verifier correctness, isolation, hash validity or artifact provenance.
-/
