# Proposed JSON schemas

These Draft 2020-12 schemas define version 0.1 interfaces. They are design artifacts, not executable verification services.

- `draft.schema.json`: ten required proposal categories and a category-review ledger.
- `obligation.schema.json`: tracked records with all eight milestone symbols; shared formal/source/dependency definitions.
- `accepted-ir.schema.json`: immutable semantic content reconstructed from the accepted formal environment. It intentionally excludes the mutable lifecycle overlay.
- `evidence.schema.json`: registered mechanical evidence bound to a root and verifier hash.
- `review-config.schema.json`: provider secret references, agent profiles, per-tier reviewer counts, consensus rules, and budgets.
- `review-ballot.schema.json`: an advisory reviewer ballot bound to one immutable review target.

Schemas added by the v0.1 implementation:

- `interpretation.schema.json`: interpretation ledger — clause dispositions, assumption suppliers, ambiguity decisions.
- `routing.schema.json`: classifier routing decision (advisory, never evidence).
- `formalization-candidate.schema.json`: untrusted obligation-to-Lean binding proposal.
- `claims.schema.json`: frozen contract-phase and implementation-phase claim inventories.
- `acceptance-certificate.schema.json`: immutable Lean acceptance certificate.
- `implementation-bindings.schema.json`: untrusted implementation binding proposal (python-v0_1).
- `report.schema.json`: authoritative run report.
- `consensus-certificate.schema.json`: review consensus certificate (a workflow claim, never proof).
- `endpoint-profiles.schema.json`: user-defined provider endpoint profiles.
- `event.schema.json`: JSON Lines progress events.
- `bridge-plan.schema.json`: proposed frozen bridge nodes, artifact slots, assigned claim checkers, premise graph and accepted-obligation coverage.
- `bridge-artifacts.schema.json`: artifact inventory bound to exact plan bytes, with relative paths, byte sizes and SHA-256 digests.
- `semantic-edge-certificate.schema.json`: proposed semantic edge bound to its plan, manifest, model/profile/relation identities, proof inventory and mechanical evidence. It contains no submitted outcome or lifecycle fields.
- `bridge-proposal.schema.json`: untrusted artifact and graph proposal; accepted identities, coverage hashes and verifier assignments are supplied by the supervisor.
- `bridge-preparation-certificate.schema.json`: supervisor output binding live structural evidence and replayed contract import to a frozen plan and manifest; semantic and E2E acceptance are explicitly false.
- `vscore-source.schema.json`: closed node shapes of VSCore 0.1 source programs. It is documentation only: the Lean decoder `VSCore.parseSource` is the normative interpretation of the exact bytes.
- `vscore-relation.schema.json`: untrusted relation descriptor naming `vscore.reference_refinement/0.1` and binding accepted symbols to entries one-to-one.
- `vscore-model.schema.json` and `vscore-profile.schema.json`: the registered VSCore semantic model and the representation profile derived from an accepted registry. Candidate copies must match the supervisor's derivation byte for byte.
- `vscore-implementation-ir.schema.json`: implementation IR re-exported by bounded constructor reification of the replayed goal declarations.
- `vscore-edge-certificate.schema.json`: output of the registered `verislop.vscore-checker` for one semantic edge, bound to its evidence record. It assigns no lifecycle milestone.

Schema validation can reject malformed records. It cannot establish proof validity, source/statement correspondence, honest evidence, correct state derivation, semantic dependency closure, or reviewer truthfulness. Registered validators must additionally check references, uniqueness, revisions, content hashes, graph invariants, capability support, configured voting rules, applicability, and lifecycle prerequisites.

The accepted IR schema contains formal references into the hashed expression package. The [expression specification](../docs/contract-ir.md) defines the typed v0.1 DSL, exact JSON node shapes, denotation, and opaque core-term references. The exporter reconstructs these packages from the certified environment, and the reifier checks their denotation in Lean. No arbitrary JSON object is treated as a proved formula.

The current draft fixture is deliberately at INTERPRETED. Compiling the accompanying Lean example does not retrospectively turn the fixture into an accepted VeriSlop run. No accepted-IR or closure report is committed to this repository; `verislop run` produces them in a run package from evidence it records.
