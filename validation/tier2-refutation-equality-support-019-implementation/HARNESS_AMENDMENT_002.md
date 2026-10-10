# Frozen harness correction amendment 019-002

Status DEVELOPMENT_ONLY. Run002 retained all actual outcomes; it is not rescored and cannot provide positive candidate evidence. Its authored Except derivation compiled and was replayed, but fixture preparation incorrectly audited every prefixed helper as if it were the equality definition (the prefix also includes theorem helpers). The frontend fixture incorrectly supplied unbound extra theorems, and the bad-helper fixture used an obsolete Classical API name. These are fixture/harness failures, not candidate correctness evidence.

Before the next fresh development run, select the actually replayed root generic Except equality definition and audit its whole closure, emit only the bound structured theorem, and author the noncomputable negative via the actual local primary API Classical.propDecidable. No candidate production-copy change, resource-limit change, policy change, rescore, or prior PASS reuse is authorized by this amendment.
