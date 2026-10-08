# Sealed expanded-domain follow-up

Native Qwen cohort005 completed all three fixed tasks on 2026-10-08. P01 completed the
ordinary strict CLI with PASS and exit0: eight required guarantees/invariants reached
TESTED, both review checkpoints accepted, and two clean builds verified closure.
All160 independent numeric cases passed in two fresh isolated harnesses (320
observations). The complete generated [solve.py](cohorts/cohort-005/P01-numeric-batch/runs/p01-numeric-batch-repair-01/implementation/solve.py)
matches a captured native Qwen response. Its [report](cohorts/cohort-005/P01-numeric-batch/runs/p01-numeric-batch-repair-01/report.json)
and [independent receipt](cohorts/cohort-005/P01-numeric-batch/independent-oracle.json)
preserve these facts.

The original experiment supervisor nevertheless records0/3. Its frozen checker
compared the report's tier object to integer0, falsely rejecting P01 after every
other gate and case passed. The [separate audit](accounting-audit-attempt.md) explains
the defect. Original result and oracle receipts remain byte-for-byte unchanged;
no historical score is promoted. A newly measured qualification with the fixed
checker would require a new whole cohort.

P02 exhausted formalization repairs and ended with a premature provider completion:
INFRASTRUCTURE_FAILURE,10calls,no implementation. P03 used its final proof budget
and remained BLOCKED,15calls,no implementation. Its model-generated theorem equates
prefixed labels with unprefixed filtered labels, which is false for labels=["x"],
prefix="p". P01 used10calls. All three origin audits pass, including unsuccessful
repair packages. No generation timeout or selective extra attempt was added.

Luna simulation cohort003 sealed normally with0/3 and17calls (3/10/4). Its numeric
and Unicode tasks stopped at incomplete review; row formalization exhausted repairs.
No implementation or execution observations exist. Unicode review identified a
concrete natural-language mismatch, but its proof-failure probe could not reproduce
that semantic mismatch. Actual model identity, token usage and read/tool restrictions
remain unattested. These simulations do not support an equal-compute comparison.

The same three natural-language prompts and480 distinct withheld cases were fixed
before generation. The runtime and effective32768-token context configuration were
frozen. No positive source/proof was hand edited and no withheld output was fed back
to model agents. Every completed response, failed repair, source snapshot and origin
receipt is retained. Authored mock regressions and diagnostic mutants are excluded
from model results. The host, transport, hashing and isolation remain trusted.

After native005 sealed, three [fixes](post-seal-fixes/SOURCE_RECORD.json) corrected
report accounting, rejected-response feedback and reconstruction of bound underscore
names. [All66 selected regressions passed](post-seal-fixes/REGRESSIONS.json). These are
implementation checks, not additional model-positive tasks. An additional existing
[Tier2 certificate/full-rebuild compatibility check passed](post-seal-fixes/COMPATIBILITY.json).
Tier0 TESTED is finite;
END_TO_END_VERIFIED remains unsupported.

The manifest hashes all files in this follow-up except itself. Archived original
absolute paths are preserved; audit historical behavior with that cohort's frozen
execution-source. [Overall results](../OVERALL.md) retain earlier failed cohorts too.
