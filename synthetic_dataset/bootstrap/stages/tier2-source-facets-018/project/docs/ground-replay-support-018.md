# Generic ground replay support 018

This change extends proof construction for the existing grounded proposition. A
probe still produces an observation only from a safe theorem of the original
closed `E` or `Not E`, independently replayed by the pinned Lean kernel, with
the existing exact source, reconstructed AST, statements, module inventory,
toolchain bytes, and axiom policy checks. No host evaluation supplies truth.

The frozen recipe sets `smartUnfolding false` locally, uses full transparency,
then `simp only` with `eq_self`, `true_implies`, `implies_true`, `and_true`,
`true_and`, `not_true_eq_false`, and `not_false_eq_true`, followed by
`all_goals decide +kernel`. It has the original shared 30 second deadline,
at most two polarity compiles, recursion depth 100000, and 2000000 heartbeats.
The negative attempt precedes the positive attempt. Failure never supplies a
polarity. Readable correspondence strategy S-GR-002 remains unavailable; S-GR-001
is selected before compilation and does not use a readable descriptor.

Every staged normative library, contract, goal, and probe is independently kernel
replayed. The kernel exports every declaration of the contract, goal, and probe;
their exported row counts must match the complete replay inventory counts.
The actual result dependency walk traverses these exported types, definition
values, and theorem constant references, including wrappers. It rejects accepted
guarantees and generated refinement, transfer, and candidate proof declarations
using exact Lean Name components, including flat quoted names containing dots,
hyphens, or colons.

Dependencies beyond those exports end at a recorded precontract frontier. This
is not a full normative declaration export or dependency walk. Registered
normative sources are compiled sequentially using only preceding normative
modules and the pinned toolchain. The current contract is staged afterwards.
The source/toolchain cache key, exact normative source and module parts hashes,
and prior-module build frontiers are recorded. These bound existing registered
library inputs cannot refer forward to a later contract or its proof oracles.
The kernel's actual result axiom closure remains complete and must satisfy the
unchanged policy. Development observations used `Classical.choice`, `Quot.sound`,
and `propext`; the tactic spelling does not establish an empty axiom inventory.

Polarity compiler attempts retain their source identity, polarity, exit code, process
output byte counts/hashes, and bounded diagnostic rows. Each row retains at most
512 UTF-8 bytes at a scalar boundary, with no ellipsis, and each attempt retains
at most eight rows. The whole canonical JSON list is capped at 16384 bytes,
including metadata and JSON escapes. Deterministic row omission enforces that
wire cap; original/retained row and byte counts and truncation flags remain
explicit. Prior failed attempts survive Unsupported and shared-deadline exits
in the ordinary supervisor receipt diagnostics string. The deadline is checked
after each retained attempt, including after the second ordinary failure.
Process output hashes
are not claims that uncaptured output bytes are available.

The unrelated finite corpus has four source/contract designs and two assignments
each. A reflexive bounded Nat residual genuinely failed both baseline proof
constructions with captured Decidable synthesis errors; the new recipe produced
an exact independent kernel theorem for it. This does not identify the cause of
the sealed release failure. An additional bounded comparison control still
fails both constructions and remains Unsupported. There is no claim of total
ground decision coverage, of inherent undecidability, or of a task repair.
The sealed release is not changed or rescored.

Run fresh qualification with:

```sh
PYTHONPATH=. python validation/tier2-ground-replay-support-018-design/qualification.py \
  --output NEW_OUTPUT_DIRECTORY \
  --source-freeze FROZEN_ROOT_LABEL \
  --source-manifest FILE_MAP_JSON
```

The file map is a JSON object mapping workspace-relative paths to `sha256:hex`,
optionally nested under `files`. The hook rehashes the supplied mapping and
mandatory relevant code, printer, library, specification, and verifier inputs
before and after execution. It binds the caller's root label; the caller owns
the unified whole-root freeze and audit. The hook independently executes the
preserved exact baseline, two current-source clean fixture builds, the actual
construction/kernel negative controls, oracle/type/axiom and quoted-name
controls, three real deadline controls, fifteen individually recorded unit
controls, and the existing nine
replay regressions. No previous PASS is imported. Ordinary library/contract
preparation uses the existing supervisor build cap; each prepared-library probe
uses its unchanged shared 30 second deadline. Cold-cache throughput is not
guaranteed by this finite qualification.

The original draft specification files remain historical PENDING drafts. The
activation, prospective recipe/frontier/control freezes and hook registration
identify the executed scope; only a fresh `report.json` and its bound evidence
can resolve the eight claims and sixteen controls. Any required failure or
frozen input mutation keeps qualification blocked.
