# Synthetic dataset validation

The frozen dataset contains **100 Python software engineering tasks**, with
**1,157 cases: 200 public examples and 957 held-out cases**. Each task asks for
a pure `solution.py::solve(data)` using the Python standard library. Prompts
state input domains, output ordering, tie breakers, and error behavior.

Dataset root:
`sha256:00e1b28846431c379cf8460d57d84897c5d0575ce49fa1481d7fb1ebc000c04e`.
The [manifest](manifest.json) binds the task files and generator sources. The
dataset and benchmark execution sources were frozen before the paired model
run. This document records dataset validation; it contains no model scores.

## Task groups and construction

- **A01–A33:** 33 algorithm tasks and 396 cases, covering dynamic programming,
  interval algorithms, exact arithmetic, optimization, graphs, and constraint
  solving. See [the algorithm generator](generate_algorithms.py).
- **D01–D33:** 33 text and data tasks and 421 cases, covering parsing, codecs,
  normalization, query processing, transactional edits, joins, migrations,
  versioning, and JSON deltas. See [the text/data generator](generate_text_data.py).
- **G01–G34:** 34 graph and system-state tasks and 340 cases, covering graph
  algorithms, dependency scheduling, caches, transactions, event streams,
  leases, rate limiting, channels, and timers. See
  [the graph/system generator](generate_graph_systems.py).

Tasks were authored locally through deterministic Python generators, without
using Qwen to generate their specifications or expected outputs. Every task
has two manually calculated public anchors and at least eight distinct hidden
inputs. Hidden cases include targeted boundaries, adversarial constructions,
and fixed-seed generated inputs. Generation checks reject duplicate inputs
within a task and verifies repeatable output. Candidate prompts contain the
specification and public examples; hidden cases and reference implementations
remain on the benchmark side.

## Oracle checks

All **200 public anchors** were checked against their reference implementations.
Additional checks use different formulations rather than the same oracle twice:

- G03: 300 Bellman–Ford outputs compared with Floyd–Warshall distance and
  negative-cycle propagation calculations.
- G07: 200 canonical Euler trails compared with edge-permutation enumeration.
- G08: 200 maximum-flow results and reported residual cuts checked by
  enumerating every source/sink cut.
- G09: 120 matching results checked against all feasible assignment vectors,
  including exact tie breaking.
- G14: 100 resource-constrained routes checked by enumerating walks that never
  repeat a `(vertex, resource-used)` state.
- Four additional literal checks cover transaction tombstone conflicts,
  semaphore deadline ordering, SemVer build ties, and timer replacement.
- D07 valid CSV cases compared with the standard-library CSV parser, accounting
  for the task's explicitly different blank-record representation.
- D14 UTF-8 text outputs compared with the standard-library replacement decoder.
- D33 generated patches applied through the separate D10 patch engine and
  checked to reconstruct their target documents.

The graph/system generator therefore runs **924 additional independent checks**.
A separate pre-freeze review also compared G07 with an exhaustive trail solver
on 1,280 seeded multigraphs and A22 with an independent recursive rational
expression evaluator on 2,000 expressions. These checks passed.

The persisted generator checks can be repeated without modifying the dataset:

```bash
PYTHONDONTWRITEBYTECODE=1 python synthetic_dataset/generate_algorithms.py
PYTHONDONTWRITEBYTECODE=1 python synthetic_dataset/generate_text_data.py
PYTHONDONTWRITEBYTECODE=1 python synthetic_dataset/generate_graph_systems.py --check
```

## Concrete corrections before freezing

- **A33 empty constraint system:** `{n:0,constraints:[]}` previously returned
  infeasible because a zero-iteration relaxation loop skipped its success
  return. It now returns `{feasible:true,potential:[]}`, with an independent
  empty-system anchor.
- **D04/D20/D26/D27 integer conversion bounds:** a valid-looking 4,301-digit
  numeric token exceeded Python's default conversion guard, contradicting the
  original unbounded prompts. The relevant numeric components now have an
  explicit 1,000-digit maximum. Each task includes an accepted 1,000-digit
  boundary case; expected integer values are independently checked as
  `10**1000 - 1` where applicable.
- **D32 unsupported comparison types:** boolean and list comparisons could
  follow Python ordering although the specification permits only integer and
  string ordering. They now produce unknown, with concrete held-out witnesses.
- **A30 task duplication:** the original SCC-condensation task duplicated G02.
  A30 was replaced with exact rational polynomial interpolation queries,
  including manually calculated anchors and bounded generated instances.

These checks validate the finite benchmark cases and their specified domains.
They do not establish general correctness of every oracle or candidate program;
the paired benchmark report records actual artifact execution and test scores.
