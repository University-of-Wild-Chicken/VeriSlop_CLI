# VeriSlop Workbench MVP

Start from the repository root with `bin/verislop ui`, then open
<http://127.0.0.1:8765>. `python -m verislop.web` and the installed `verislop-ui`
entry point are equivalent. Use `--workspace PATH` and optionally `--port PORT`;
the HTTP server accepts loopback addresses only. No Node build or pip dependency
installation is required. The CLI's existing Lean/Linux prerequisites still
apply to native execution.

Keep the server terminal open while using the app. Closing the terminal stops
the app and interrupts its owned runs. If the port is occupied, use a different
one, such as `bin/verislop ui --port 8766`. Only one workbench server may own a
workspace at a time; another instance fails explicitly rather than sharing
mutable request and process state.

Choose **Add request**, enter your software specification, and select **Save
request**. Provider configuration is optional until launch. Saved requests appear
above the run list and survive page reloads and server restarts. Open one to edit
it, select a workspace-relative provider configuration, then **Save & launch**.
Saving alone never calls a model or starts a run. Launch preserves the exact saved
prompt in the run package; later edits do not change existing run evidence.

Credentials and environment model references are inherited from the terminal
that launched the server. Choose **Offline example** for the exact bundled
handwritten Tier 0 candidates. That preset fixes its request and target and
performs real native checks without LLMs.

For a model-driven run from a checkout, open **Local setup**, then choose **Use**
beside a configuration. The request form adopts that file's declared tier and
shows a warning if you subsequently choose a different target. This is a local
structural check; model access and credentials are checked when the CLI runs.
For example, the Tier 2 Ollama configuration uses `OLLAMA_MODEL`:

```bash
export OLLAMA_MODEL='your-installed-model-name'
bin/verislop providers check --config examples/ollama-review-config.json
bin/verislop ui --port 8766
```

Set environment references **before** starting the server. A wheel installation
includes the offline example; for live providers, put your own provider JSON in
the selected workspace and enter its path. Agent roles, proof routing, fallback
models, and adversarial-review tiers remain explicit configuration; the UI does
not silently change those policies.

Use **Open package** for retained packages outside the default runs directory.
Artifacts are read-only previews with explicit size limits. The app never calls
the mutating CLI `status` command during inspection. Only one new owned run can be
active at once. **Stop run** interrupts it; Ctrl+C closes the server and interrupts
its owned processes. Neither action touches independently launched CLI processes.

## Implementation contract

The workbench is a local, standard-library web application for launching and
inspecting CLI runs. The CLI remains the only execution and assurance authority.
Opening a package reads retained artifacts; it does not reverify or modify them.
Recorded results are labeled as historical. Process status, mechanical closure,
release status, and individual obligation milestones remain distinct.

The first version provides:

- A run list, search/filter controls, live event polling, and cancellation of
  processes started by this workbench only.
- A natural-language run form using an existing provider configuration, plus the
  bundled offline Python example. Launch requires an explicit user action.
- Persisted, editable request drafts with optional model configuration until
  launch, separate from run packages and verification outcomes. Saved requests
  are not an automatic execution queue and carry no assurance milestone.
- Tier 0 Python testing, Tier 1 Python runtime contracts, and Tier 2 VSCore 0.3
  source verification. Unsupported tiers cannot silently downgrade.
- Read-only opening of existing workspace packages, including the active repair
  package reported by a completed CLI run.
- Obligation outcomes, report details, activity, and bounded JSON/Lean/source
  artifact previews. Missing or partial files are displayed as unavailable.
- Loopback-only serving, same-origin mutation requests, a per-server request
  token, confined paths, bounded reads, and argument-list subprocess execution.

MVP acceptance requires a usable checkout and installed distribution, persistence
across restarts, exact saved-request launch snapshots, cancellation of owned
processes even if bookkeeping fails, and independent access to run evidence
when a request draft is unreadable. The release checks use deterministic fixtures;
they do not certify live model quality. This is a single-user Linux application,
not a hosted service or a guarantee that arbitrary prompts will verify.

No model is contacted by opening the application. API credentials stay in the
CLI's configured environment or credential store. There is no browser credential
storage, evidence promotion, automatic experiment resumption, or hosted service.

## Local API

All routes return JSON except static assets. Errors use `{ "error": "..." }`.
POST requests send JSON and the `X-VeriSlop-Token` from `/api/meta`.

- `GET /api/meta`: `workspace`, `runs_dir`, `token`, `version`, `example_prompt`,
  `configs` (relative configuration paths), `tiers` (id, label, target, endpoint,
  require_state), `config_details` (path, structural validity, tier, endpoint),
  and basic local `environment` information. Configuration summaries never
  contain credential values or resolved environment variables.
- `GET /api/runs`: `{ runs: [...] }`. Each summary contains `id`, `run_id`,
  `path`, `created_at`, `status`, `process_status`, `tier`, `target`, `prompt`,
  `mechanical_status`, `release_status`, `require_state`, `endpoint`, `owned`,
  `historical`, `exit_code`, `mode`, and `phase`. Targets come from recorded
  metadata; a tier number does not imply a missing target or assurance claim.
- `GET /api/requests`: `{ requests: [...] }`, bounded request summaries with a
  prompt preview, timestamps, target tier, configuration path, and last run ID.
- `GET /api/requests/<id>`: the complete saved request with exact prompt text.
- `POST /api/requests` and `POST /api/requests/<id>`: create or update a request
  using `{ prompt, config: "", tier: 0, budget_seconds: 0, repair_rounds: 2 }`.
  Prompts must be nonblank and at most 64000 UTF-8 bytes. Saving accepts an empty
  configuration; launch validates it with the ordinary CLI launch checks.
- `POST /api/requests/<id>/launch`: launch the exact saved request and return its
  run summary. Requests are retained if validation or launch fails.
- `POST /api/runs`: `{ mode: "example" | "agents", prompt, config, tier,
  budget_seconds: 0, repair_rounds: 2 }`. Returns a summary with `id`.
  Example mode uses the exact bundled request/candidates and Tier 0.
- `POST /api/runs/open`: `{ path }` registers an existing workspace package for
  read-only inspection and returns its summary.
- `GET /api/runs/<id>`: `{ run, report, obligations, events, artifacts, prompt,
  stdout, stderr, command, warnings }`. Obligations are an array with `id` plus
  recorded fields, normalized `outcomes`, and statement text when available.
  Artifact entries have `path`, `size`, and decimal-string `mtime_ns` for preview
  invalidation; previews are bounded and text-only.
- `GET /api/runs/<id>/artifact?path=...`: `{ path, content, truncated, size }`.
- `POST /api/runs/<id>/cancel`: interrupt only a currently owned process group.

The UI polls while visible and keeps browser-selected navigation independent
from persisted CLI state. Requests live under `.verislop/workbench/requests`.
Workbench bookkeeping lives under `.verislop/workbench`;
new native packages live under `.verislop/runs`.

## Validation boundary

Backend tests cover actual HTTP routes, command construction, cancellation,
read-only inspection, malformed/partial artifacts, and path/origin boundaries.
Frontend verification covers navigation, run-form validation, launch/inspection,
artifact viewing, responsive layout, and accessible dialog controls. Any offline
example used for validation is explicitly labeled as a handwritten fixture;
it is not a model-generated benchmark result.

The 2026-10-31 validation passed all 19 workbench tests on Python 3.10 and 3.12,
including actual HTTP requests and graceful termination of an owned subprocess.
Browser checks covered launch, read-only package opening, search/status filters,
obligation details, source previews, and a 390-pixel mobile viewport. A browser-
launched bundled example completed two clean builds and reported
`VERIFIED closure; implementation assurance: TESTED (Tier 0)`. Live provider
calls were not exercised. Local screenshots and test logs are retained under
the ignored `validation/workbench-20261031-001/` directory.

The saved-request follow-up passed all 24 workbench tests on Python 3.10 and
3.12. Coverage includes exact prompt persistence, edits and restart recovery,
failed launches preserving requests, immutable launch snapshots, and persistence
failure preventing a subprocess from starting. Browser checks saved and edited
a Unicode request without configuration, reopened it after reload and server
restart, and confirmed configuration errors retain the request. Checks used an
isolated workspace; no live models or new Lean runs were invoked. Evidence is
retained under the ignored `validation/workbench-requests-20261031/` directory.

The 2026-11-01 MVP check passed 55 selected regression tests on each of Python
3.10 and 3.12, including 29 workbench tests. A source-distribution-to-wheel test
confirmed exact packaged schemas, examples, and web assets from a fresh
installation outside the checkout. A browser launch from that installed wheel
also completed the bundled offline example with two clean Lean builds and
`TESTED` implementation assurance. Browser checks additionally covered selecting
a configuration, tier mismatch warnings, and inspecting a run while a saved
request was malformed. No live model calls were made. Local evidence remains
under ignored `validation/workbench-mvp-20261101/`; CI runs the selected Python
regressions, JavaScript syntax, and distribution check without Lean or credentials.
