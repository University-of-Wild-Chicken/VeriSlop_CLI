# Metadata-only bridge preparation example

This proposal accompanies the repository's bounded-increment contract. It covers
the implementation guarantees `O17` (success is the successor), `I2` (success
preserves the bound), and `E1` (error semantics). The contract's non-vacuity witness
`W1` remains a formal prerequisite, not an implementation transfer obligation.

Use `proposal.json` with a freshly accepted and exported bounded-increment run.
Artifact paths are relative to this directory. The preparation supervisor injects
the accepted contract, derives obligation revisions and accepted statement hashes,
and computes the artifact manifest. No accepted IR, acceptance certificate,
artifact size, verifier assignment, or verification outcome is supplied here.

The candidate files are deliberately **metadata only**. They supply no executable
implementation, Lean semantics, theorem, or proof. The proposed goal hash names the
exact bytes of `candidate/goal.txt`; it is not an accepted Lean proposition hash.
The preparation stage can check this proposal's structure and file integrity.
It cannot establish the proposed relation or any implementation milestone.

A generated preparation certificate records that limited preparation result.
The refinement claim remains pending; semantic acceptance and
`END_TO_END_VERIFIED` remain unavailable. The example's `restricted_source`
endpoint is a requested endpoint, not an assurance already achieved.
