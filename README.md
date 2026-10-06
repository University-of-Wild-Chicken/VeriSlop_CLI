# VeriSlop CLI — Verify the Slop

VeriSlop turns a software request into explicit obligations, proves a selected formal contract in Lean 4, reconstructs downstream obligations from the accepted formal artifact, and binds generated implementations to that contract at a declared assurance tier.

This repository contains the **design specification** and a **working implementation of the `verislop` CLI** (v0.1). Generators propose; registered verifiers decide. Obligation milestones come from immutable evidence bound to the exact bytes it checked.

- [Specification](docs/specification.md), [contract expression IR](docs/contract-ir.md), [obligation states](docs/obligation-states.md), [providers and adversarial review](docs/providers-and-review.md): the normative design.
- [Implementation notes](docs/implementation.md): how the CLI realises the specification, artifact by artifact, and where it stops.
- [Tier 2–4 specification and implementation outline](docs/tier-2-4.md): proposed source, extraction and machine-code backends, with proof obligations and release gates.
- [Schemas](schemas/): JSON interfaces. Schema validity is structure only; semantic validators check the rest.
- [Examples](examples/): the bounded-increment request with a candidate draft, ledger, formalization, Lean fixture and Python implementation.

Every obligation carries these symbols:

```text
INTERPRETED  FORMALIZED  TYPECHECKED  PROVED
IMPLEMENTED  LINKED  TESTED  END_TO_END_VERIFIED
```

They are evidence milestones, not interchangeable claims. Tests do not establish a proof, and proving a Lean model does not establish correctness of an independently generated program.

## Requirements

- Python ≥ 3.10 (standard library only; no third-party packages).
- Lean toolchain `leanprover/lean4:v4.34.1` installed with elan (VeriSlop never downloads toolchains during verification; `VERISLOP_LEAN_PREFIX` can point at a toolchain directory).
- Linux with bubblewrap (`bwrap`) and unprivileged user/network namespaces (`unshare -rn`). Candidate builds and tests require filesystem and network containment; missing containment fails closed.

Run `bin/verislop doctor` to check these prerequisites. Install with `pip install -e .` (editable, so the bundled schemas are found), or run `bin/verislop` from the checkout.

## Quickstart (offline, with the bundled candidates)

Every generator stage accepts either an LLM agent (`--config`) or a pre-authored candidate. The example candidates make the whole pipeline reproducible without credentials:

```bash
bin/verislop run --prompt-file examples/request.txt --mode auto --tier 0 --target python \
  --draft-candidate examples/draft.json --ledger-candidate examples/interpretation.json \
  --formalization-candidate examples/formalization \
  --implementation-candidate examples/python --non-interactive
```

About 15 seconds later the run package `.verislop/runs/<run-id>/` holds `report.json` and the terminal shows:

```text
RESULT: VERIFIED closure; implementation assurance: TESTED (Tier 0)
         INTE FORM TYPE PROV IMPL LINK TEST END_
  E1     ✓    ✓    ✓    ✓    ✓    ✓    ✓    u    guarantee, state TESTED
         proof boundary: PROVED PASS: Lean reference-model theorem …error_iff_at_limit (hypotheses: A3); proves the model, not the implementation
         implementation: TESTED (Tier 0 campaign seed …, 300 effective cases; finite sampling, not proof)
clean builds: 2; reproducible outputs compared: olean, environment_export, accepted_ir, pyc, tests; mismatches: 0
end-to-end: No END_TO_END_VERIFIED claim: Tiers 0 and 1 are ineligible …
remaining trust (TCB): …
```

The same pipeline stage by stage. Each command reads and writes the run package given by `--package` (default: the current directory):

```bash
P=build/demo; mkdir -p $P
bin/verislop interpret --package $P --prompt-file examples/request.txt \
  --candidate examples/draft.json --ledger examples/interpretation.json
bin/verislop formalize --package $P --candidate examples/formalization   # statement check + freeze
bin/verislop prove     --package $P                    # untrusted: built-in tactic portfolio
bin/verislop accept    --package $P --policy strict    # kernel replay, axiom/statement/witness audit
bin/verislop export    --package $P                    # accepted-ir.json from the certified environment
bin/verislop generate  --package $P --tier 0 --target python --candidate examples/python
bin/verislop link      --package $P
bin/verislop test      --package $P
bin/verislop verify    --package $P                    # two clean builds, provenance, report.json
bin/verislop inspect obligation E1 --package $P
bin/verislop explain-block --package $P
```

## What each stage establishes

| Stage | Proposes (untrusted) | Decides (registered verifier) | Milestones |
|---|---|---|---|
| `interpret` | interpreter agent or candidate draft + ledger | spans/hashes against the exact request bytes, IDs, roles, no claimed lifecycle, assumption suppliers, ambiguity decisions, mechanical clause coverage | INTERPRETED |
| `formalize` | formalizer agent or candidate Lean + bindings | sandboxed elaboration, kernel replay, generated typed registry, mechanical semantic profile, DSL reification, kernel defeq of every denotation, hypothesis/witness policy; then freezes the claims and challenge | FORMALIZED |
| `prove` | tactic portfolio, prover agent, or a candidate file | nothing (acceptance decides) | — |
| `accept` | — | isolated rebuild, `Kernel.Environment.replay`, identity of statements/definitions/registry, transitive axiom walk on the replayed environment, constructive witnesses read from proof terms | TYPECHECKED, PROVED |
| `export` | — | IR reconstructed only from the certificate's environment; round trip and defeq rechecked; byte-identical re-export | (reification evidence) |
| `generate` | implementer agent or existing code | capability check (no silent downgrade), frozen implementation claims, sandboxed byte compilation | IMPLEMENTED |
| `link` | binding proposal | unique structural bindings; coverage from the accepted semantic closure | LINKED |
| `test` | — | Tier 0 campaign on hash-verified target bytes in an isolated interpreter | TESTED |
| `verify` | — | two isolated clean builds, determinism, provenance of every required claim, endpoint, review gate | END_TO_END_VERIFIED (UNSUPPORTED at Tiers 0/1), closure claims |

Run status has exactly three terminal values (`VERIFIED`, `BLOCKED`, `INFRASTRUCTURE_FAILURE`), always qualified, as in `VERIFIED closure; implementation assurance: TESTED (Tier 0)`. Exit codes: `0` the command's gate passed (only `verify`/`run` assert closure), `2` blocked, `3` infrastructure failure, `64` invalid invocation, `130` interrupted. `--json` prints one result object on stdout with progress on stderr. `--events PATH` streams schema-versioned JSON Lines.

## Supported combinations (`verislop capabilities`)

| Tier | Target / endpoint | Status | Strongest implementation claim |
|---|---|---|---|
| 0 | Python, `python-v0_1` / `test_campaign` | supported | TESTED for the recorded campaign |
| 1 | Python / `instrumented_runtime` | supported | runtime detection (raise before return) + TESTED |
| 2 | VSCore `vscore/0.1` / `restricted_source` | **partial** | registered semantic-edge acceptance (`bridge accept`); runs stay blocked, no END_TO_END_VERIFIED yet |
| 3–4 | extraction, machine code | **unsupported** | capability diagnostic; never downgraded |

No supported combination yields `END_TO_END_VERIFIED`. Opaque Lean statements can be accepted and PROVED, but they get no fabricated test oracle or monitor. Liveness and physical-resource obligations are never discharged by finite campaigns.

The shared bridge certificate workflow prepares frozen inputs from an accepted run:

```bash
bin/verislop bridge prepare --package build/demo \
  --proposal examples/bridge-proposal/proposal.json --candidate-dir examples/bridge-proposal
bin/verislop bridge verify --package build/demo --bridge-id bounded-increment-metadata
bin/verislop bridge check --package build/demo/bridges/bounded-increment-metadata \
  --plan plan.json --artifacts artifacts.json --json
```

`prepare` independently replays the accepted Lean contract and reconstructs its IR, computes artifact hashes and obligation coverage, then publishes a new frozen bundle with registered structural evidence and a preparation certificate. The bundled proposal contains metadata examples; it is not a VSCore implementation or proof. Changed inputs require a new bridge ID. `verify` rechecks the frozen bundle and its import/evidence bindings. `check` remains a read-only envelope gate, with paths relative to its package root; repeat `--certificate PATH` to inspect proposed semantic-edge certificates.

A structural PASS assigns no obligation state and proves no implementation relation. Supplied semantic-edge envelope certificates always remain blocked. Add `--bridge-proposal PATH --bridge-candidate-dir DIR` to `run` for preparation after export; `resume` rechecks prepared inputs before skipping completed stages. See [implementation details](docs/implementation.md#shared-bridge-certificate-layer).

### Tier 2: VSCore restricted source

One registered relation template exists: `vscore.reference_refinement/0.1`, decided by `verislop.vscore-checker`. A candidate delivers a VSCore 0.1 program as canonical JSON bytes, binds accepted symbols to its entries, and proves one refinement theorem per symbol. Everything else is derived by the supervisor from the accepted run ([example](examples/vscore/README.md)):

```bash
bin/verislop vscore goal --package $P --source examples/vscore/program.vscore.json \
  --relation examples/vscore/relation.json --proof examples/vscore/Proof.lean \
  --out /tmp/vscore-candidate --bridge-id bounded-increment-vscore      # advisory: goal + proposition hash
bin/verislop bridge prepare --package $P --proposal /tmp/vscore-candidate/proposal.json \
  --candidate-dir /tmp/vscore-candidate
bin/verislop bridge accept --package $P --bridge-id bounded-increment-vscore   # two isolated kernel replays
bin/verislop bridge verify --package $P --bridge-id bounded-increment-vscore   # re-executes the checker
```

Acceptance requires all of the following:

- kernel-checked equations `parseSource sourceBytes = .ok rawProgram` (on the exact delivered bytes) and `checkProgram profile rawProgram = .ok signatures`;
- input coverage and extensional refinement against the accepted reference functions;
- the transfer of every covered accepted obligation, mechanically derived from its accepted DSL statement and proved from its accepted theorem;
- statement identity, an axiom audit, the frozen proposition hash, re-export of `implementation-ir.json` from the replayed goal declarations, and agreement between two isolated builds.

Certificate evidence binds the complete descriptor, including obligation revisions, theorem identities and every compiled module part. Verification checks these bindings independently; a full recheck must reproduce the complete descriptor and build artifacts.

The run pipeline does not dispatch to VSCore yet, so `END_TO_END_VERIFIED` is not assigned. See [the VSCore notes](docs/implementation.md#tier-2-vscore-01-restricted-source) and [the next milestone specification](docs/tier-2-closure-milestone.md).

Accepted runs must match the current verifier hashes. Regenerate a run after updating verifier code; preparation rejects stale certificates and evidence.

Lean 4.34.1 `module` files are supported, including public sections and private declarations. Acceptance stores all compiled module parts together and replays the complete private declaration environment, so hidden axioms or proof dependencies cannot disappear at the export boundary. Imports must still come from the pinned toolchain; Mathlib and other third-party libraries remain unsupported.

Candidate execution uses bubblewrap with a private filesystem view, PID/IPC namespaces, scrubbed environment and resource limits. The writable stage and explicit read-only runtime/toolchain mounts are accessible; other host paths are hidden. This still trusts the kernel, bubblewrap and mounted runtime contents, and does not provide seccomp filtering or aggregate cgroup limits.

## Providers, credentials and adversarial review

`verislop.json` follows [`schemas/review-config.schema.json`](schemas/review-config.schema.json) (see [`examples/review-config.json`](examples/review-config.json)). It assigns provider/model pairs to the interpreter, formalizer, prover, implementer and repairer roles, and configures any number of review tiers with per-tier reviewer counts and unanimous or quorum consensus.

```bash
bin/verislop auth add --provider anthropic --credential-id claude-review   # masked prompt -> OS keyring
bin/verislop providers check --config verislop.json            # no network requests
bin/verislop providers check --config verislop.json --live     # minimal authenticated check only
bin/verislop providers probe --config verislop.json --agent author --live \
  --max-output-tokens 128                                    # bounded inference; may incur charges
bin/verislop review --package $P --config verislop.json --checkpoint formal_contract
bin/verislop review tally --package $P                         # re-check stored ballots
bin/verislop verify --package $P --config verislop.json        # review is an additional release gate
```

- Secrets are never read from argv and never enter prompts, transcripts, packages or hashes. There is no silent plaintext fallback.
- Redirects are refused, so credentials are never forwarded to another origin.
- Only providers used by a role or review slot need credentials.
- The adapter families are OpenAI Responses, Chat Completions (DeepSeek, Qwen/DashScope, GLM, Kimi, Grok, OpenAI-compatible), Anthropic Messages and Gemini. They are implemented but **not conformance-tested against live services**. Vertex AI, and Meta Muse or DashScope without a user endpoint profile, are reported as configuration diagnostics.

`providers probe` requires explicit `--live` and sends one JSON echo challenge per selected `--agent` (repeat the flag to select more). It checks protocol parsing, the challenge, returned model metadata and token usage through the actual broker, with no retries, a maximum 30-second request timeout and bounded output. Probe responses are not saved as transcripts. A successful probe establishes that this call worked; agent reliability, model alias equivalence and formal correctness remain separate questions. Use `--endpoint-profiles PATH` for user-supplied Meta Muse and Qwen/DashScope regional endpoints.

Review consensus is deterministic over immutable ballots. Missing or malformed ballots never count. Blocking findings and failed mechanical checks veto acceptance. Acceptance escalates tier by tier, and changed artifacts invalidate old votes. Review never assigns a proof or bridge milestone.

## Tests

```bash
python3 -m unittest discover -s tests -v     # uses the real Lean toolchain and clean builds
```

282 tests cover the specification's twenty acceptance scenarios (§13), Lean module bundles and private dependencies, filesystem containment and cleanup, bounded provider probes, the shared bridge-certificate workflow and the Tier 2 VSCore bridge. VSCore tests evaluate the normative parser, type checker and evaluator in the kernel against a malformed and ill-typed source suite, audit the library's axioms, and accept the bounded-increment fixture through two builds and a re-executing verify. They also reject sorry, candidate axioms, `native_decide`, weaker statements, proofs for other programs, unsupported constructs, missing bindings, wrong enumeration mappings, wrong proposition hashes, native endpoints, source mutation, forged certificates, tampered IR and stale checkers. They include rejection of a changed definition or weakened theorem, `sorry`, hidden axioms and `native_decide`, false preconditions without witnesses, and draft mutation that cannot change the re-exported IR. Bridge tests replay real accepted contracts, reject hash-consistent forged compiled artifacts, reproduce preparation roots, check no-clobber publication and reject removed preparation indexes on resume. They also reject forged PASS certificates, stale roots, detached endpoints, premise cycles, unsafe files and excessive JSON complexity. Evidence tests require the assigned issuer and preserve infrastructure failures. Other checks cover opaque statements without oracles, stale evidence after a target change, empty campaigns, nondeterminism, orphan claims, crashed checkers and cancellation. Provider and review tests use loopback mock services across the four wire protocols; no real credentials or live-service conformance results are included.

The correctness regressions cover Unit results, reflexive and logical formulas, accepted predicate aliases, helper-name collisions, oversized numeric tokens, complete certificate metadata, module-part binding and disagreement between recorded builds. These include compiled candidate proofs, kernel replay and exact implementation-IR re-export.

## Repository layout

```text
docs/        normative specification + implementation notes
schemas/     JSON Schemas (design + implementation artifacts)
examples/    bounded-increment request and candidates
verislop/    the CLI (pure Python) and lean/VeriSlopKernel.lean (trusted kernel tool)
tests/       unit, acceptance-scenario and provider/review tests
bin/         source-checkout launcher
```

The Lean fixture `examples/lean/BoundedIncrement.lean` still compiles standalone (`cd examples/lean && lean BoundedIncrement.lean`). Inside VeriSlop it serves as a proof candidate for the frozen challenge built from `examples/formalization/`.
