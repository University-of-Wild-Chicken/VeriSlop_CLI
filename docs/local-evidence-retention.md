# Local bootstrapping evidence

Git tracks the CLI, formal libraries, schemas, tests, examples, documentation,
benchmark harness, and fixed synthetic task corpus. Generated execution evidence
stays on the machine that produced it and is excluded from the current Git tree:

- `validation/`: build captures, qualification runs, model transport, controllers,
  and checkpoints.
- `bootstrap_ledger/` and `BOOTSTRAP_LEDGER.json`: local evidence retention and
  continuation records.
- `synthetic_dataset/runs/`, `diagnostics/`, `bootstrap/`, `pilot/`,
  `comparison-*/`, and top-level experiment logs.

Four static source/fixture files under `validation/` remain tracked because the
test suite uses them. The exact exceptions are in `.gitignore`; copied source
trees inside generated runs do not become exceptions.

Removing an index entry leaves its local file intact. Historical report links
into these directories refer to local evidence; a fresh clone does not include
that evidence and cannot replay an old qualification without its original frozen
inputs and artifacts. A retention ledger records storage operations, not proof
acceptance. Run future experiments into fresh output directories.

The stopped Q015 evidence and frozen inputs remain available locally. Legacy
Q008, Q009, and Q014 runs are archival after redundant snapshot pruning; their
file-count checkpoint writer must not be resumed. A newly authorized iteration
should use the compact controller.

Untracking removes traces from the current branch tree. It does not erase blobs
from published Git history. Local backup references must not be pushed when
synchronizing the source branch.
