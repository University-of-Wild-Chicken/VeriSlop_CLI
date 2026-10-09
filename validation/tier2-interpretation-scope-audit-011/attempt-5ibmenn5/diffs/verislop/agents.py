--- frozen010/verislop/agents.py
+++ current/verislop/agents.py
@@ -196,6 +196,15 @@
   clauses, copying its clause_id and omitting quote. Clauses are source coverage, not automatically separate obligations.
   Clause IDs refer only to THIS request; a document field with an ID, if included, must equal the current request ref.
   Do not mark behavior, input/output requirements, edge cases or examples as mere context to avoid specifying them.
+- Distinguish supervisor instructions about this verification run from requested implementation behavior by
+  their subject and provenance. Instructions about this run's proof, staged checking, review, endpoint selection,
+  contract registry maintenance or trust configuration are workflow context: cover their request clauses in the
+  ledger as context with explanatory notes. They do not add program guarantees or establish their satisfaction.
+  Supervisor-supplied program source policies still prescribe requirements of the delivered implementation.
+  A user-requested verifier, artifact checker, audit log or metadata-processing program still has software
+  requirements, even when it uses the same terminology. Preserve its source properties, functional safety,
+  invariants, branches, examples and complete input/output domains as obligations with source citations.
+  Never use this distinction to delete, downgrade or hide an unsupported user software requirement.
 - dependencies is an array of objects {{"id":"<existing obligation ID>","relation":"<allowed relation>"}}, never strings.
   Every dependency target must appear in your obligations array; never copy a sample ID that you did not declare.
   Use [] when independent. assumes may name only an assumption record; uses_definition names a declaration;
