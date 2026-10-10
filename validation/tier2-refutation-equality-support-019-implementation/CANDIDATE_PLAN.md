# Candidate implementation plan 019

Status: DEVELOPMENT_ONLY. This candidate and its actual generic test evidence are not production changes, native task work, or ROOT003 qualification.

The frozen design is validation/tier2-refutation-equality-support-019-design/SPEC.md (SHA-256 a17ed1183760e4d2cd33005582962689ab9b9871666507018f5758552a7bfbc0). In its direct negative fixture shorthand, negate the instantiated theorem type, e.g. Not (swap (swap amber) = amber), never the proof term.

Order fixed before implementation:
1. Copy the generic production contract_refutation.py into this directory, import it as verislop.contract_refutation_candidate, and change only equality preparation: expected-Env exact-type audited reuse, deterministic local alias hygiene, deriving fallback, and existing carrier dependency order.
2. Keep the theorem, compilation and kernel resource limits, original-declaration hashes, root safety/closure, exact defeq checks, receipts, and authority unchanged. No production/docs/tests writes are authorized.
3. Author fresh unrelated raw Lean and structured frontend fixtures in this directory. Positive behavior uses actual compiler/kernel calls. Boundary tampering is explicitly labeled and separate from actual positive evidence.
4. Instrument the existing sandbox/leanbridge calls observationally to retain complete compiler and kernel command/process/request/response receipts and fresh generated sources/modules/exports. No new timeouts, model calls, native task inputs, retained answers, or old probes.
5. Run the candidate fixture matrix, preserve all attempts and failures, and record numeric development results. Inspect source/diff and run only meaningful focused checks.
6. Freeze candidate, fixture source, review, run results and all actual evidence with hashes/read-only permissions. Report to root and stop. Production installation and ROOT003 qualification require separate authorization.
