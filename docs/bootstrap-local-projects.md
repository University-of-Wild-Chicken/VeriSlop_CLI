# Local hybrid project coverage bootstrap

This specification precedes implementation of the project trial harness. This is
an adaptive engineering exercise on practical project components, not an unbiased
benchmark or a claim that an entire deployed project is verified. Historical
support019 and Python trials retain their original outcomes.

The first component is a pure inference-job memory admission planner, motivated
by the local inference workflow's GPU memory pressure. Follow-up components are
an inventory movement reconciler, a telemetry batch summary and a release manifest
planner using the separately specified Unicode String increment. Each starts with
an independent natural-language requirements file. No implementation, accepted
contract, proof, private case or previous successful model answer is supplied.

## Assurance and roles

The deliverable is `program.vscore.json`, version `vscore/0.3`, under normative
Lean `vscore-semantics/0.3`, profile `data-pipeline/0.3`. This explicitly targets
the pure component's restricted-source semantics. It excludes Python, device
allocation, service integration, performance, compilers and machine code. Natural
language interpretation remains trusted and subject to concrete adversarial review.

Qwen interprets, formalizes, implements, repairs and reviews. Unsolved proof jobs
first use three Pythagoras attempts, then three Qwen proof refinements, then the
explicit GPT-6.1 Sol proof fallback. The existing optional Sol autonomous-critic
protocol fallback remains available. A valid refutation is never overridden.
Absent API credentials, Sol uses a fresh-agent collaboration simulation whose
identity and usage are unattested. All local calls use pinned native Ollama models.

VSCore proof requests use purpose `prove-vscore` independently of complete-file
versus theorem-fragment response format. Fragment-mode agents retain the native
VSCore proof-environment guidance (including checked readable correspondence and
transport lemmas), while their output protocol remains theorem fragments only.
The old full-module output instruction is excluded from that guidance.

Run the ordinary strict CLI with Tier 2, backend 0.3, `restricted_source`, and
required `END_TO_END_VERIFIED` within that restricted-source boundary. Preserve
interpretation, formalization, Lean acceptance, accepted-AST reconstruction,
implementation refinement, linkage, two clean builds, determinism, closure and
configured concrete review gates. TESTED is a separate runtime milestone and is
not substituted for refinement. No fallback to Tier 0 is permitted.

## Frozen inputs and finite work

Extend the existing local hybrid harness with explicit Tier 2 project mode while
preserving its Tier 0 default. Freeze exact requirements, mode, configuration,
model pins, tokenizer inputs, grammar/specification, source archive and finite
call/repair budgets before inference. The invocation is derived from the frozen
mode. Unsupported mode/task combinations fail before dispatch. Sources changing
during a trial block it and require a new trial root. Never restart a partial
trial by resetting call counts.

Initial limits: 48 native calls and 8 simulated fallback calls per task, two
outer contract repair rounds, three initial and three refinement proof attempts
per proof job. Model calls have no hard wall deadline. Native checker limits
remain active. Full input plus output allowance must fit the role's pinned
context; do not truncate packets to fit. Byte-estimated native token admission
remains a soft resource policy, not a billing guarantee.

Use one compressed source snapshot per trial, the existing content-addressed
artifact memory and compact call records. Preserve exact rejected and accepted
JSON/Lean artifacts and diagnostic feedback. Keep generated traces local and
ignored. A compact ledger records trial roots, state and next gap; it grants no
proof authority. Do not resume legacy cumulative checkpoint writers.

## Mechanical predicates and reporting

The project trial succeeds only if the actual CLI exits zero, its current report
is VERIFIED with generation, contract, bridge, review and finalization stages PASS,
the requested Tier 2 endpoint is
established, required obligations attain END_TO_END_VERIFIED, configured release
review is accepted, and the existing VSCore 0.3 closure validator authenticates
the retained evidence, both clean builds and determinism. Empty, stale, malformed
or incomplete reports fail. The native pre-release verify row may be provisionally
BLOCKED while its mechanical status is VERIFIED, because release review has not
yet executed; only authenticated final closure and accepted release can resolve
that specific provisional state. No other failed stage is excused. No model
opinion may set these results.

Freeze each project's requirements before generation. Keep functional examples
public and separate from any later independent diagnostic cases. Record exactly
which constructor compositions are exercised by accepted implementation ASTs;
grammar availability alone is not demonstrated project coverage. A concrete
rejection may justify a generic grammar/compiler/prompt correction, but that
correction needs a separately frozen trial and regression before a new claim.

The native closure's hashed claim graph, verifier registry, provenance and trust
declarations are authoritative. Trust includes Lean/kernel, exporter and host
tooling, Python, hashing, OS/filesystem/hardware and natural-language interpretation.
Final states are VERIFIED, BLOCKED or INFRASTRUCTURE_FAILURE; external interruption
is unfinished. A failed project remains unsuccessful and is retained as a source
of a concrete next coverage gap.

## Exact library projection for local bridge proof authors

This specification precedes the proof-context change. The current VSCore 0.3
prover packet includes about 112 KiB of complete verifier library source before
its generated goal and accepted contract. That exceeds the preferred local
prover's context allowance independently of the proof's difficulty.

For VSCore 0.3 only, retain the complete exact module-to-source mapping once per
source candidate in the existing content-addressed agent-memory store. Bind its
canonical digest, exact per-module UTF-8 byte sizes and hashes, toolchain pin and
relative snapshot reference. The proof-routing identity continues to hash the
original complete mapping. The complete library remains the compiler and kernel
input; storage and prompt selection assign no proof or lifecycle authority.

The model-facing `verifier_library` field contains the complete unchanged texts
of exactly `VSCore3.Typed` and `VSCore3.Transport`. These modules expose the
intrinsic carriers, environments, adapters and universal transport laws. The
closed projection contains no model-generated summary, extracted/reconstructed
Lean declaration or altered proposition. The existing exact proof-support
catalog remains alongside it. A bound reference explicitly identifies all
omitted modules and restores the complete mapping after context loss.

Keep every other existing context field unchanged, including source, relation,
generated goal, accepted reference/packages/profile, refinement inventory and
readable selection. Preserve version 0.1 packets unchanged. Reject missing,
unexpected, changed or non-text library modules, absent toolchain binding,
mutated CAS bytes or mismatched reference inventory. Restoration validates the
complete retained mapping and current memory journal; it does not substitute an
ambient library for a historical snapshot. The projection is not a guarantee of
fit: complete input/output preflight and explicit escalation still apply.

Regression checks cover exact full restoration, unchanged semantic fields and
input objects, fixed selection and meaningful size reduction, unchanged legacy
behavior, malformed inventories, changed sources and snapshot/blob tampering.
Projection is performed once before proof attempts, preserving their common
reference instead of appending a snapshot on each retry. Fragment-only proof
transport must also retain the VSCore role guidance as context while keeping its
registered fragment response grammar.

## Fallback response binding at consumption

This specification precedes the transport correction. A response publisher's
checks do not authorize the waiting worker to trust a directly written mailbox
file. The hybrid worker must revalidate each exact Sol response envelope before
accepting its text: frozen protocol and task, declared agent/purpose route,
unchanged request and carrier bytes, recorded carrier/spawn binding, requested
Sol model override, fresh-agent identity, `fork_turns=none`, and explicit absence
of model-identity attestation. Missing or mismatched bindings fail before a
completion or successful-response receipt is emitted. Responses remain retained
verbatim. A reusable optional mailbox validator preserves existing consumers'
behavior; the hybrid harness always installs it. These checks authenticate local
record correspondence, not actual remote model identity or compliance with the
carrier's tool restrictions.

## Running with user-selected models

`examples/local-hybrid-tier2-config.json` keeps model selection in
`VERISLOP_QWEN_MODEL` and `VERISLOP_PYTHAGORAS_MODEL`, and uses the explicit Sol
API fallback with `OPENAI_API_KEY`. Select the local endpoint in the provider
profiles. With those inputs configured, an ordinary invocation is:

```sh
python -m verislop run \
  --prompt-file examples/project-bootstrap/G01-inference-admission.txt \
  --runs-dir validation/project-runs --run-id inference-admission \
  --mode software --tier 2 --target vscore --backend-version 0.3 \
  --endpoint restricted_source --require-state END_TO_END_VERIFIED --no-tests \
  --policy strict --non-interactive --budget-seconds 0 --repair-rounds 2 \
  --config examples/local-hybrid-tier2-config.json
```

For the retained local evaluation, `synthetic_dataset.tools.run_local_hybrid
prepare --trial-mode tier2-project` freezes resolved model names/digests, the
endpoint profiles and tokenizer snapshots. Its default project selection is G01;
G02, G03 and G04 are independent selectable follow-ups. This harness's Sol mailbox is
explicitly simulated. Neither this example nor registration of a project is an
observed successful run.
