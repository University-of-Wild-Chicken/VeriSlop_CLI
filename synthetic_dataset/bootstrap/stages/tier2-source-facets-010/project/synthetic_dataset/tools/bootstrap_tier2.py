"""Write-once Tier 2 pure-data bootstrap, separate from historical Python runs.

Only public requests, sealed requirement identity metadata, generic current source
and registered native evidence are used. No dataset cases, oracle, Python grader,
positive candidate or previous model answer is an input to a new role.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

from synthetic_dataset.tools import bootstrap_tier2_transport as transport
from synthetic_dataset.tools import bootstrap_tier2_worker as worker
from verislop import canonical
from verislop.package import Package
from verislop.providers import config as provider_config

REPO = Path(__file__).resolve().parents[2]
FORMAT = "verislop.tier2-data-bootstrap/0.1"
CARRIER_FORMAT = "verislop.collaboration-carrier/0.1"
TASK_ORDER = ("A23", "D21")
PROFILES_INPUT = "provider-home/" + provider_config.DEFAULT_PROFILES_PATH
SOURCE_POLICY_FORMAT = "verislop.required-source-facets/0.1"
SOURCE_PROPERTIES = ("typed_total", "deterministic", "input_preserved", "no_external_io",
                     "no_floating_point", "pure_data", "restricted_runtime_only")
# Explicitly approved operational identities in the retained public task revision.
# Categories never determine whether a guarantee has a functional value facet.
SOURCE_ONLY_OPERATIONAL_IDS = {"A23": ("S1", "S2"), "D21": ("I1", "S1")}
STATUSES = ("VERIFIED", "BLOCKED", "INFRASTRUCTURE_FAILURE")
TRANSPORT_FILES = (
    "synthetic_dataset/__init__.py", "synthetic_dataset/tools/bootstrap_tier2.py",
    "synthetic_dataset/tools/bootstrap_tier2_worker.py",
    "synthetic_dataset/tools/bootstrap_tier2_transport.py")
BINDINGS = ("task", "arm", "supplemental_protocol_root", "source_root", "request_set_root",
            "spawn_message_sha256", "carrier_path", "carrier_sha256", "model_override", "fork_turns")
ENVELOPE_FIELDS = set(BINDINGS) | {"transport", "requested_model", "relay_mode", "request_id",
                                 "request_sha256", "agent_task_id", "text", "model_identity_attested"}
WITHHELD = ("withheld/", "synthetic_dataset/cases/", "data_pipeline_oracle", "expected_wire",
            "generate_algorithms.py", "generate_graph_systems.py", "generate_text_data.py",
            "PREREGISTRATION.json", "independent-oracle.json")

# Exact edits to the public language/delivery clauses. No functional algorithm,
# ordering, input domain or example is changed by these replacements.
DELIVERY_EDITS = (
    ("Implement solution.py with a single solve(data) function. data and the return value must be JSON-compatible. "
     "Use Python 3 standard library only; perform no external I/O and do not read benchmark files.",
     "Deliver program.vscore.json with one admitted typed entry named solve. Its typed input and result "
     "must represent the specified JSON input/output structure. Perform no external I/O and do not read benchmark files."),
    ("Implement solution.py with a pure solve(data) function. Input and output are JSON-compatible Python values. "
     "Use Python standard library only, no external I/O.",
     "Deliver program.vscore.json with one pure admitted typed entry named solve. Its typed input and result "
     "must represent the specified JSON input/output structure. Perform no external I/O."),
    ("Implement a pure deterministic Python 3 function solve(data) in solution.py. Use only the standard library, "
     "no external I/O. The function receives a JSON value and returns a JSON-serializable value. "
     "Preserve the specified input/output structure and exact ordering.",
     "Implement the solve entry as canonical vscore/0.3 source under normative Lean vscore-semantics/0.3 "
     "and the data-pipeline/0.3 serialization profile. Preserve the specified input/output structure and exact ordering. "
     "Admitted typed execution is total, pure and deterministic; input values are immutable, and the language has "
     "no external-effect constructors. Arithmetic uses unbounded mathematical integers without floating point. "
     "Strings contain Unicode scalar values and lexicographic order compares scalar codepoints. "
     "There are no additional input bounds or preconditions beyond the functional specification."),
    ("Public examples (additional held-out cases will be scored):",
     "Original public examples (preserved verbatim; universal refinement is required):"),
)


def load(path: Path, default: Any = None) -> Any:
    if not path.exists() and default is not None:
        return default
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"INPUT_MUTATION: expected a regular file: {path}")
    return canonical.load_file(path)


def write_bytes_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".publish-", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink()


def write_once(path: Path, value: Any) -> None:
    write_bytes_once(path, canonical.dumps(value))


def _regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.resolve() != path.absolute():
        raise ValueError(f"INPUT_MUTATION: nonregular or indirect input {path}")
    return path.read_bytes()


def validate_provider_inputs(configuration: Path, profiles: Path) -> None:
    """Use the production parsers/resolver, without constructing a provider call."""
    resolved = provider_config.resolve(provider_config.load(configuration),
                                       provider_config.load_user_profiles(profiles))
    blocking = [item.to_json() for item in resolved.diagnostics
                if item.severity in ("blocking", "infrastructure")]
    if blocking:
        raise ValueError("Frozen simulation configuration does not resolve: " + canonical.dumps(blocking).decode())


@contextmanager
def _frozen_provider_context(configuration: Path):
    """Select only authenticated cohort profiles for a read-only native observation."""
    configuration = Path(configuration).absolute()
    cohort = configuration.parent
    protocol_bytes = _regular(cohort / "protocol.json")
    protocol = canonical.loads(protocol_bytes)
    record = canonical.loads(_regular(cohort / "preregistration.json"))
    if (configuration.name != "config.json" or protocol.get("format") != FORMAT
            or record.get("format") != FORMAT
            or record.get("protocol_sha256") != canonical.digest(protocol_bytes)
            or any(not isinstance(protocol[key], str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", protocol[key])
                   for key in ("source_root", "input_root", "request_set_root"))
            or any(record.get(key) != protocol[key] for key in ("source_root", "input_root", "request_set_root"))
            or canonical.digest_json(protocol["input_files"]) != protocol["input_root"]
            or protocol.get("endpoint_profiles_path") != PROFILES_INPUT
            or protocol.get("endpoint_profiles_sha256") != protocol["input_files"].get(PROFILES_INPUT)
            or "config.json" not in protocol["input_files"] or PROFILES_INPUT not in protocol["input_files"]):
        raise ValueError("INPUT_MUTATION: frozen provider preregistration differs")
    for name, expected in protocol["input_files"].items():
        if not isinstance(name, str):
            raise ValueError("INPUT_MUTATION: frozen provider input path is invalid")
        path = Path(name)
        if (path.is_absolute() or not path.parts
                or any(part in (".", "..") for part in path.parts) or path.as_posix() != name
                or canonical.digest(_regular(cohort / path)) != expected):
            raise ValueError("INPUT_MUTATION: frozen provider input inventory differs")
    validate_provider_inputs(configuration, cohort / PROFILES_INPUT)
    key = "VERISLOP_CONFIG_HOME"
    previous = os.environ.get(key)
    os.environ[key] = str(cohort / "provider-home")
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


def source_inventory(repo: Path | None = None) -> dict[str, str]:
    repo = repo or REPO
    paths = set()
    for directory, suffixes in (("verislop", (".py", ".lean")), ("formal", (".lean",)), ("grammar", (".ebnf",)),
                                ("schemas", (".json",)), ("policies", (".json",)), ("docs", (".md",))):
        paths.update(path for path in (repo / directory).rglob("*") if path.suffix in suffixes)
    paths.update(repo / name for name in TRANSPORT_FILES)
    paths.update(repo / name for name in ("pyproject.toml", "lean-toolchain", "lakefile.lean", "lake-manifest.json")
                 if (repo / name).exists())
    if not (repo / "docs/bootstrap-tier2-data.md").is_file():
        raise ValueError("Tier 2 specification is missing")
    return {path.relative_to(repo).as_posix(): canonical.digest(_regular(path)) for path in sorted(paths)}


def snapshot(project: Path) -> dict:
    """Copy current generic inputs only; never copy a historical run or cases."""
    project = project.absolute()
    if project.exists():
        raise FileExistsError("The isolated project must be new")
    inventory = source_inventory()
    project.mkdir(parents=True)
    for name in inventory:
        write_bytes_once(project / name, _regular(REPO / name))
    if source_inventory(project) != inventory or source_inventory() != inventory:
        raise ValueError("INPUT_MUTATION: source changed during snapshot")
    record = {"format": FORMAT, "source_files": inventory, "source_root": canonical.digest_json(inventory),
              "historical_snapshots_modified": False, "cases_or_oracles_copied": False}
    write_once(project / "TIER2-SNAPSHOT.json", record)
    return record


def freeze_engineering(path: Path) -> dict:
    """Publish exact current sources BEFORE a fresh unrelated native gate."""
    files = source_inventory()
    record = {"format": "verislop.tier2-engineering-source-freeze/0.1", "source_files": files,
              "source_root": canonical.digest_json(files), "generation_started": False,
              "created_at_utc": datetime.now(timezone.utc).isoformat()}
    write_once(path, record)
    return record


def engineering_record(package: Path, source_freeze: Path) -> dict:
    """Construct observations from a current actual complete native fixture.

    This performs no kernel rerun and no model call. The registered validator
    checks both retained fresh-build bodies, evidence premises and exact hashes.
    A fixture is an engineering input; its source/proof never enters role packets.
    """
    from verislop.backends import vscore3, vscore3_closure
    from verislop import schemas

    frozen = load(source_freeze)
    files = source_inventory()
    if (frozen.get("format") != "verislop.tier2-engineering-source-freeze/0.1"
            or frozen.get("generation_started") is not False or frozen.get("source_files") != files
            or frozen.get("source_root") != canonical.digest_json(files)):
        raise ValueError("Engineering sources changed after the pre-execution freeze; run a new gate")
    pkg = Package(package.absolute(), resolve_root=False)
    if not pkg.exists() or list(pkg.root.rglob("transcripts/*.json")):
        raise ValueError("Engineering gate must be an unrelated authored fixture without live model transcripts")
    try:
        frozen_at = datetime.fromisoformat(frozen["created_at_utc"])
        created_at = datetime.fromisoformat(pkg.meta()["created_at"].replace("Z", "+00:00"))
        # Package timestamps have one-second resolution; no inference deadline
        # is inferred from this provenance check.
        if int(frozen_at.timestamp()) > int(created_at.timestamp()):
            raise ValueError("Native fixture package predates the engineering freeze; execute a fresh gate")
    except (KeyError, TypeError) as exc:
        raise ValueError("Engineering freeze/package creation provenance is missing") from exc
    report = load(pkg.path("report"))
    if (schemas.validate("run-report-v3", report) or report.get("terminal_status") != "VERIFIED"
            or report.get("mechanical_status") != "VERIFIED" or report.get("backend") != "verislop.backend.vscore/0.3"):
        raise ValueError("Final engineering gate has no successful registered VSCore 0.3 native report")
    snapshot = vscore3_closure.mechanical_snapshot(pkg)
    if snapshot is None or snapshot["mechanical_status"] != "VERIFIED":
        raise ValueError("Final engineering gate has no current complete mechanical publication")
    if (report["builds"] != snapshot["builds"] or report["determinism"] != snapshot["determinism"]
            or [build["build"] for build in snapshot["builds"]] != ["A", "B"]
            or not all(build["ok"] and not build["errors"] for build in snapshot["builds"])
            or snapshot["builds"][0]["outputs"] != snapshot["builds"][1]["outputs"]
            or snapshot["determinism"]["mismatches"] or any(c["required"] and c["outcome"] != "PASS" for c in snapshot["claims"])):
        raise ValueError("Actual engineering closure/build observations are incomplete or disagree")
    selected = vscore3.selection(pkg)
    source = pkg.path("implementation") / vscore3.SOURCE_FILE
    materialized = load(source.with_name(vscore3.INVENTORY_FILE))
    if (canonical.digest(_regular(source)) != materialized["source_hash"]
            or canonical.loads(_regular(source)) != materialized["program"]):
        raise ValueError("Engineering source bytes differ from actual accepted-AST reconstruction")
    members = {path.relative_to(pkg.root).as_posix(): canonical.digest(_regular(path))
               for path in sorted(pkg.root.rglob("*")) if (path.is_file() or path.is_symlink())
               and "__pycache__" not in path.parts and not path.name.endswith((".pyc", ".lock"))}
    return {"format": "verislop.tier2-engineering-validation/0.1", "status": "VERIFIED",
            "source_root": frozen["source_root"], "source_freeze": str(source_freeze.absolute()),
            "source_freeze_sha256": canonical.digest_file(source_freeze),
            "package": str(pkg.root), "package_files": members, "package_files_root": canonical.digest_json(members),
            "report_sha256": canonical.digest_file(pkg.path("report")), "closure_root": snapshot["closure_root"],
            "closure_id": snapshot["closure_id"], "mechanical_result": snapshot["mechanical_result_path"],
            "mechanical_result_sha256": members[snapshot["mechanical_result_path"]],
            "selected_inputs": selected["inputs"], "source_sha256": canonical.digest_file(source),
            "builds": snapshot["builds"], "determinism": snapshot["determinism"],
            "required_claim_observations": [c for c in snapshot["claims"] if c["required"]],
            "fresh_model_calls": 0, "fixture_only": True, "model_authoring_input": False,
            "scope": "current generic complete restricted-source engineering closure; no benchmark answer transfer"}


def verify_engineering_record(record: dict) -> None:
    """Reject invented/stale build booleans and changed actual fixture artifacts."""
    if not {"source_freeze", "source_freeze_sha256", "package", "package_files", "package_files_root"} <= set(record):
        raise ValueError("Actual engineering freeze/package/build provenance is required; booleans are insufficient")
    frozen = Path(record["source_freeze"])
    if canonical.digest(_regular(frozen)) != record["source_freeze_sha256"]:
        raise ValueError("Engineering pre-execution freeze receipt changed")
    actual = engineering_record(Path(record["package"]), frozen)
    if actual != record:
        raise ValueError("Engineering validation differs from actual current native closure observations")


def _sealed_metadata(original: Path, task: str, prompt: bytes) -> dict:
    """Read IDs/requiredness/spans only, never old statements or proof artifacts."""
    sealpath = original / "BOOTSTRAP-EVIDENCE-MANIFEST.json"
    if not sealpath.exists():
        sealpath = original / "EVIDENCE-MANIFEST.json"
    seal = load(sealpath)
    files = seal["files"]
    if (not isinstance(files, dict) or seal.get("files_root") != canonical.digest_json(files)
            or any(not isinstance(k, str) or not isinstance(v, str) for k, v in files.items())):
        raise ValueError("Original evidence seal has an invalid file inventory")
    prefixes = sorted(name.removesuffix("/package.json") for name in files
                      if re.fullmatch(rf"artifacts/{re.escape(task)}/verislop/package(?:-repair-\d+)?/package.json", name))
    if not prefixes:
        raise ValueError("Original seal has no package for the selected request")
    base = f"artifacts/{task}/verislop/package"
    if base not in prefixes:
        raise ValueError("Original request root package is missing from its seal")

    def metadata(name: str):
        data = _regular(original / name)
        if files.get(name) != canonical.digest(data):
            raise ValueError("Original public metadata differs from its retained seal")
        return canonical.loads(data)

    if files.get(base + "/request/prompt.txt") != canonical.digest(prompt):
        raise ValueError("Original public request hash differs from the sealed request")
    draft = metadata(base + "/draft.json")
    ledger = metadata(base + "/interpretation.json")
    if ledger["request"]["document_hash"] != canonical.digest(prompt):
        raise ValueError("Original identity spans refer to a different request")
    identities = []
    for category, entries in draft.items():
        if not isinstance(entries, list):
            continue
        for item in entries:
            if not isinstance(item, dict) or "id" not in item:
                continue
            spans = [{"start_byte": ref["start_byte"], "end_byte": ref["end_byte"]}
                     for ref in item["source_refs"]]
            if any(type(s[k]) is not int or not 0 <= s["start_byte"] < s["end_byte"] <= len(prompt)
                   for s in spans for k in ("start_byte", "end_byte")):
                raise ValueError("Original requirement metadata has invalid byte spans")
            identities.append({"id": item["id"], "role": item["role"], "kind": item["kind"],
                               "required": item["required"], "source_spans": spans})
    if not identities or len({row["id"] for row in identities}) != len(identities):
        raise ValueError("Original required identities are missing or duplicated")
    # Package roots are hashes of the ORIGINAL sealed inventory, not reopened old
    # candidate bytes. The controller/file-copy mechanism is an explicit TCB.
    packages = [{"path": prefix, "package_json_sha256": files[prefix + "/package.json"],
                 "sealed_package_root": canonical.digest_json({name[len(prefix) + 1:]: sha
                     for name, sha in files.items() if name.startswith(prefix + "/")})} for prefix in prefixes]
    protocol_hash = canonical.digest(_regular(original / "protocol.json"))
    if files.get("protocol.json") != protocol_hash:
        raise ValueError("Original protocol metadata differs from its retained seal")
    return {"original_request_sha256": canonical.digest(prompt), "original_cohort": str(original),
            "original_protocol_sha256": protocol_hash,
            "original_evidence_manifest_sha256": canonical.digest(_regular(sealpath)),
            "original_evidence_root": seal["files_root"], "original_packages": packages,
            "metadata_hashes": {name: files[name] for name in (base + "/draft.json", base + "/interpretation.json")},
            "identities": identities, "previous_python_assurance": "unchanged; no Tier 2 reinterpretation",
            "old_positive_candidate_bytes_read": False}


def source_policy(identities: list[dict], *, operational_ids: tuple[str, ...] = ()) -> dict:
    """Request constraints from sealed identities, never statements or candidates.

    Every required guarantee has a value facet by default, regardless of category.
    Only explicitly classified required operational guarantee IDs are source-only.
    This is specification metadata; accepted IR still comes from the Lean kernel.
    """
    ids = [row["id"] for row in identities]
    if len(ids) != len(set(ids)):
        raise ValueError("Required source policy cannot use duplicate original obligation IDs")
    operational = set(operational_ids)
    required_guarantees = {row["id"] for row in identities
                           if row["role"] == "guarantee" and row["required"] is True}
    if len(operational) != len(operational_ids) or not operational <= required_guarantees:
        raise ValueError("Explicit operational overrides must name unique original required guarantee IDs")
    policy = {"schema_version": "0.1", "format": SOURCE_POLICY_FORMAT,
            "obligations": {row["id"]: {"file": "program.vscore.json", "entry": "solve", "arity": 1,
                "properties": list(SOURCE_PROPERTIES), "value_required": row["id"] not in operational}
                for row in sorted(identities, key=lambda item: item["id"])
                if row["role"] == "guarantee" and row["required"] is True}}
    from verislop import source_policy as policy_backend
    problems = policy_backend.validate(policy)
    if problems:
        raise ValueError("Required source policy does not satisfy the native closed request schema: " +
                         canonical.dumps([item.to_json() for item in problems]).decode())
    return policy


def revise_prompt(original: bytes, identities: list[dict], *, operational_ids: tuple[str, ...] = ()) -> tuple[bytes, dict]:
    original.decode("utf-8", errors="strict")
    edits = []
    for before, after in DELIVERY_EDITS:
        needle, replacement = before.encode(), after.encode()
        at = original.find(needle)
        if at >= 0:
            if original.find(needle, at + len(needle)) >= 0:
                raise ValueError("Delivery clause is ambiguous or repeated")
            edits.append({"original_start_byte": at, "original_end_byte": at + len(needle),
                          "before": before, "after": after})
    edits.sort(key=lambda row: row["original_start_byte"])
    if len(edits) != 3 or any(a["original_end_byte"] > b["original_start_byte"] for a, b in zip(edits, edits[1:])):
        raise ValueError("Explicit public delivery revision requires exactly one entry clause, common clause and example header")
    chunks, cursor, length, segments = [], 0, 0, []
    for edit in edits:
        start, end = edit["original_start_byte"], edit["original_end_byte"]
        unchanged = original[cursor:start]
        chunks.append(unchanged)
        segments.append({"original_start_byte": cursor, "original_end_byte": start,
                         "revised_start_byte": length, "revised_end_byte": length + len(unchanged),
                         "kind": "preserved", "sha256": canonical.digest(unchanged)})
        length += len(unchanged)
        replacement = edit["after"].encode()
        edit.update(revised_start_byte=length, revised_end_byte=length + len(replacement))
        chunks.append(replacement)
        segments.append({**{k: edit[k] for k in ("original_start_byte", "original_end_byte", "revised_start_byte", "revised_end_byte")},
                         "kind": "explicit_delivery_revision"})
        length += len(replacement)
        cursor = end
    chunks.append(original[cursor:])
    segments.append({"original_start_byte": cursor, "original_end_byte": len(original),
                     "revised_start_byte": length, "revised_end_byte": length + len(original[cursor:]),
                     "kind": "preserved", "sha256": canonical.digest(original[cursor:])})
    revised = b"".join(chunks)
    if b"Python" in revised or b"solution.py" in revised:
        raise ValueError("Unrevised native delivery language requires an explicit new revision")
    marker = b"Public examples (additional held-out cases will be scored):\n"
    example_data = original.split(marker, 1)
    if len(example_data) != 2 or not example_data[1].strip():
        raise ValueError("Public examples are missing")
    canonical.loads(example_data[1])
    if not revised.endswith(example_data[1]):
        raise ValueError("Public examples changed")

    def mapped_span(span):
        start, end = span["start_byte"], span["end_byte"]
        overlap = [s for s in segments if s["original_start_byte"] < end and start < s["original_end_byte"]]
        if not overlap:
            raise ValueError("Requirement identity has no mapped public clause")
        first, last = overlap[0], overlap[-1]
        rstart = (first["revised_start_byte"] + start - first["original_start_byte"]
                  if first["kind"] == "preserved" else first["revised_start_byte"])
        rend = (last["revised_start_byte"] + end - last["original_start_byte"]
                if last["kind"] == "preserved" else last["revised_end_byte"])
        return {"original_start_byte": start, "original_end_byte": end,
                "revised_start_byte": rstart, "revised_end_byte": rend,
                "delivery_revised": any(s["kind"] != "preserved" for s in overlap)}

    mapping = [{**{k: row[k] for k in ("id", "role", "kind", "required")},
                "source_mappings": [mapped_span(span) for span in row["source_spans"]]} for row in identities]
    request_metadata = [{**{k: row[k] for k in ("id", "role", "kind", "required")},
                         "revised_clause_spans": [{"start_byte": s["revised_start_byte"], "end_byte": s["revised_end_byte"]}
                                                 for s in row["source_mappings"]],
                         "delivery_revised": any(s["delivery_revised"] for s in row["source_mappings"])} for row in mapping]
    revision_note = ("\n\nExplicit delivery revision and requirement identity metadata:\n"
        "This is a new canonical restricted-source delivery request. The functional clauses, stated domains and "
        "public example values above retain their original meaning. Preserve these requirement IDs, roles and "
        "required flags in the interpretation. IDs mapped across a delivery revision now state the specified "
        "typed pure source properties; their previous delivery assurance is unchanged. Each functional guarantee "
        "requires its complete mathematical statement and universal implementation refinement; illustrative "
        "examples do not replace it. The clause offsets below refer to the revised text above.\n" +
        canonical.dumps(request_metadata).decode() +
        "\nRequested endpoint: Tier 2 / restricted_source, backend vscore/0.3, END_TO_END_VERIFIED. "
        "Runtime campaigns are not requested. This request claims normative restricted-source execution only, "
        "with natural-language correspondence, host tooling, the pinned Lean kernel, hashing and OS/hardware "
        "explicitly trusted. No machine-code, compiler, runtime or physical-resource assurance is claimed.\n")
    required_source = source_policy(identities, operational_ids=operational_ids)
    classification = {"value_required_default": True, "source_only_operational_ids": sorted(operational_ids)}
    policy_note = ("\nMandatory requested source-facet specification:\n"
        "This is a frozen request constraint, not accepted obligation IR or proof evidence. Every listed original "
        "required guarantee retains the globally requested source delivery: canonical file program.vscore.json, "
        "one typed entry solve of arity 1, and all seven closed source properties below. Include the exact source "
        "requirements in its formal contract; a mathematical result-existence or equality theorem cannot replace "
        "entry identity, purity, input preservation, effect restrictions or exact non-floating-point semantics. "
        "For every value_required=true row also preserve the complete functional formula and universal source "
        "implementation refinement as a mixed source/value guarantee, including functional safety properties and "
        "invariants. Value facets are required by default regardless of category. Only the explicitly classified "
        "operational IDs below are source-only, retaining their source requirements rather than being replaced "
        "by value equalities. Assumptions, exclusions and "
        "separate non-vacuity witnesses are not source-policy rows. These constraints will be independently "
        "checked against kernel-reconstructed contract facets before proof, after acceptance and at closure.\n" +
        canonical.dumps(classification).decode() + "\n" + canonical.dumps(required_source).decode() + "\n")
    final = revised + revision_note.encode() + policy_note.encode()
    return final, {"format": "verislop.delivery-revision/0.1", "original_request_sha256": canonical.digest(original),
                   "revised_request_sha256": canonical.digest(final), "edits": edits, "segments": segments,
                   "identity_mapping": mapping, "public_examples_sha256": canonical.digest(example_data[1]),
                   "source_policy_format": SOURCE_POLICY_FORMAT, "source_policy_sha256": canonical.digest_json(required_source),
                   "source_policy_classification": classification,
                   "functional_bytes_preserved": True, "old_delivery_assurance_relabelled": False}


def prepare(cohort: Path, stage: str, original_cohorts: dict[str, Path], *,
            prompts: dict[str, Path] | None = None, engineering_record: Path | None = None) -> dict:
    cohort = cohort.absolute()
    selected = [task for task in TASK_ORDER if task in original_cohorts]
    if not selected or set(selected) != set(original_cohorts) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", stage):
        raise ValueError("Select A23 before D21 and provide a unique stage name")
    if cohort.exists():
        raise FileExistsError("A cohort is write-once; select a new stage")
    source = source_inventory()
    source_root = canonical.digest_json(source)
    if engineering_record is None:
        raise ValueError("A pre-live generic engineering validation record is required")
    engineering = canonical.loads(_regular(engineering_record.absolute()))
    if (engineering.get("format") != "verislop.tier2-engineering-validation/0.1"
            or engineering.get("status") != "VERIFIED" or engineering.get("source_root") != source_root
            or [b.get("build") for b in engineering.get("builds", [])] != ["A", "B"]
            or not all(b.get("ok") is True for b in engineering["builds"])
            or engineering.get("determinism", {}).get("mismatches") != []
            or engineering.get("fresh_model_calls") != 0):
        raise ValueError("Pre-live engineering gate is missing, stale or incomplete")
    verify_engineering_record(engineering)
    # Validate the actual file schemas and resolver before any cohort publication.
    with tempfile.TemporaryDirectory(prefix="tier2-provider-preflight-") as temporary:
        staged = Path(temporary)
        write_once(staged / "config.json", transport.configuration())
        write_once(staged / provider_config.DEFAULT_PROFILES_PATH, transport.endpoint_profiles())
        validate_provider_inputs(staged / "config.json", staged / provider_config.DEFAULT_PROFILES_PATH)
    planned = []
    for task in selected:
        prompt_path = (prompts or {}).get(task, REPO / "synthetic_dataset/tasks" / task / "prompt.txt").absolute()
        prompt = _regular(prompt_path)
        provenance = _sealed_metadata(original_cohorts[task].absolute(), task, prompt)
        revised, revision = revise_prompt(prompt, provenance["identities"],
                                          operational_ids=SOURCE_ONLY_OPERATIONAL_IDS[task])
        planned.append((task, prompt, provenance, revised, revision))
    # All preconditions and revisions are resolved before publishing anything.
    cohort.mkdir(parents=True)
    for name in source:
        write_bytes_once(cohort / "execution-source" / name, _regular(REPO / name))
    input_names = ["config.json", PROFILES_INPUT, "engineering-validation.json"]
    write_once(cohort / "config.json", transport.configuration())
    write_once(cohort / PROFILES_INPUT, transport.endpoint_profiles())
    write_once(cohort / "engineering-validation.json", engineering)
    tasks = []
    for task, prompt, provenance, revised, revision in planned:
        base = f"requests/{task}"
        for name, data in (("original-prompt.txt", prompt), ("revised-prompt.txt", revised)):
            write_bytes_once(cohort / base / name, data)
            input_names.append(base + "/" + name)
        required_source = source_policy(provenance["identities"], operational_ids=SOURCE_ONLY_OPERATIONAL_IDS[task])
        for name, obj in (("original-metadata.json", provenance), ("delivery-revision.json", revision),
                          ("source-policy.json", required_source)):
            write_once(cohort / base / name, obj)
            input_names.append(base + "/" + name)
        tasks.append({"id": task, "revised_prompt_path": base + "/revised-prompt.txt",
                      "revised_request_ref": f"tier2:{stage}:{task}",
                      "original_request_sha256": canonical.digest(prompt), "revised_request_sha256": canonical.digest(revised),
                      "source_policy_path": base + "/source-policy.json", "source_policy_sha256": canonical.digest_json(required_source),
                      "source_policy_classification": revision["source_policy_classification"],
                      "revision_path": base + "/delivery-revision.json", "metadata_path": base + "/original-metadata.json"})
    inputs = {name: canonical.digest(_regular(cohort / name)) for name in sorted(input_names)}
    protocol = {"format": FORMAT, "stage": stage, "generation_started": False,
        "tasks": tasks, "task_order": selected, "pair_order": [{"task": task, "arm": "verislop", "pair_index": i}
                                                               for i, task in enumerate(selected)],
        "project_path": str(REPO), "source_files": source, "source_root": source_root, "input_files": inputs,
        "request_set_root": canonical.digest_json({task["id"]: task["revised_request_sha256"] for task in tasks}),
        "input_root": canonical.digest_json(inputs), "specifications": {name: sha for name, sha in source.items() if name.startswith("docs/")},
        "configuration_sha256": inputs["config.json"], "endpoint_profiles_path": PROFILES_INPUT,
        "endpoint_profiles_sha256": inputs[PROFILES_INPUT],
        "tier": 2, "target": "vscore", "backend_version": "0.3", "language": "vscore/0.3",
        "semantics": "vscore-semantics/0.3", "profile": "data-pipeline/0.3", "endpoint": "restricted_source",
        "require_state": "END_TO_END_VERIFIED", "policy": "strict", "runtime_campaign_requested": False,
        "native_cli_required": True, "positive_candidate_arguments": [], "hidden_cases_loaded": False,
        "python_grader_invoked": False, "task_oracle_invoked": False, "independent_clean_builds": 2,
        "transport": "collaboration-agent-simulation", "requested_model": transport.MODEL,
        "relay_mode": "file", "carrier_format": CARRIER_FORMAT, "fork_turns": "none", "fresh_agent_per_request": True,
        "max_calls_per_task": transport.MAX_CALLS, "max_calls_per_instance": 24, "contract_repair_rounds": 2,
        "model_generation_deadline": None, "proof_search_deadline": None, "review_tier_deadline": None,
        "model_identity_attested": False, "input_tokens": None, "output_tokens": None,
        "trust": ["natural-language correspondence", "controller and exact file-copy transport",
                  "host Python/tooling", "pinned Lean kernel/toolchain", "SHA-256", "OS/hardware"],
        "excluded": ["previous Python packages and runtime assurance", "hidden-case correctness",
                     "machine-code/compiler/runtime semantics", "physical resource bounds", "unlisted or future claims"]}
    write_once(cohort / "protocol.json", protocol)
    write_once(cohort / "preregistration.json", {"format": FORMAT, "generation_started": False,
        "protocol_sha256": canonical.digest_file(cohort / "protocol.json"), "source_root": source_root,
        "input_root": protocol["input_root"], "request_set_root": protocol["request_set_root"]})
    verify_inputs(cohort)
    return protocol


def verify_inputs(cohort: Path) -> dict:
    protocol = load(cohort / "protocol.json")
    record = load(cohort / "preregistration.json")
    if (protocol.get("format") != FORMAT or record.get("format") != FORMAT
            or record.get("protocol_sha256") != canonical.digest_file(cohort / "protocol.json")
            or record.get("source_root") != protocol.get("source_root")
            or record.get("input_root") != protocol.get("input_root")
            or record.get("request_set_root") != protocol.get("request_set_root")
            or protocol.get("project_path") != str(REPO)
            or canonical.digest_json(protocol["source_files"]) != protocol["source_root"]
            or canonical.digest_json(protocol["input_files"]) != protocol["input_root"]):
        raise ValueError("INPUT_MUTATION: protocol/preregistration binding differs")
    if source_inventory() != protocol["source_files"]:
        raise ValueError("INPUT_MUTATION: current generic source/specification differs from freeze")
    frozen = {name: canonical.digest(_regular(cohort / "execution-source" / name)) for name in protocol["source_files"]}
    actual_paths = {path.relative_to(cohort / "execution-source").as_posix() for path in (cohort / "execution-source").rglob("*") if path.is_file()}
    if frozen != protocol["source_files"] or actual_paths != set(frozen):
        raise ValueError("INPUT_MUTATION: exact retained source inventory differs")
    if {name: canonical.digest(_regular(cohort / name)) for name in protocol["input_files"]} != protocol["input_files"]:
        raise ValueError("INPUT_MUTATION: original/revised public request, config or engineering input changed")
    if (protocol.get("endpoint_profiles_path") != PROFILES_INPUT
            or protocol.get("endpoint_profiles_sha256") != protocol["input_files"].get(PROFILES_INPUT)
            or load(cohort / "config.json") != transport.configuration()
            or load(cohort / PROFILES_INPUT) != transport.endpoint_profiles()):
        raise ValueError("INPUT_MUTATION: configuration differs from generic Tier 2 transport")
    validate_provider_inputs(cohort / "config.json", cohort / PROFILES_INPUT)
    if (protocol["task_order"] != [task for task in TASK_ORDER if task in protocol["task_order"]]
            or protocol["task_order"] != [row["id"] for row in protocol["tasks"]]
            or protocol["pair_order"] != [{"task": task, "arm": "verislop", "pair_index": i} for i, task in enumerate(protocol["task_order"])]) :
        raise ValueError("INPUT_MUTATION: task order/selection differs")
    if (protocol["requested_model"] != transport.MODEL or protocol["tier"] != 2
            or protocol["target"] != "vscore" or protocol["backend_version"] != "0.3"
            or protocol["endpoint"] != "restricted_source" or protocol["require_state"] != "END_TO_END_VERIFIED"
            or protocol["relay_mode"] != "file" or protocol["fork_turns"] != "none"
            or protocol["positive_candidate_arguments"] != [] or protocol["runtime_campaign_requested"] is not False):
        raise ValueError("INPUT_MUTATION: protocol no longer selects the preregistered Tier 2 surface")
    for task in protocol["tasks"]:
        original = _regular(cohort / "requests" / task["id"] / "original-prompt.txt")
        metadata = load(cohort / task["metadata_path"])
        revised, revision = revise_prompt(original, metadata["identities"],
                                          operational_ids=SOURCE_ONLY_OPERATIONAL_IDS[task["id"]])
        required_source = source_policy(metadata["identities"], operational_ids=SOURCE_ONLY_OPERATIONAL_IDS[task["id"]])
        policy_path = "requests/" + task["id"] + "/source-policy.json"
        if (task.get("source_policy_classification") != revision["source_policy_classification"]
                or task.get("source_policy_path") != policy_path
                or task.get("source_policy_sha256") != canonical.digest_json(required_source)
                or protocol["input_files"].get(policy_path) != canonical.digest_json(required_source)
                or _regular(cohort / policy_path) != canonical.dumps(required_source)
                or revised != _regular(cohort / task["revised_prompt_path"])
                or revision != load(cohort / task["revision_path"])
                or task["original_request_sha256"] != canonical.digest(original)
                or task["revised_request_sha256"] != canonical.digest(revised)):
            raise ValueError("INPUT_MUTATION: public delivery revision/source policy no longer reconstructs exactly")
    if protocol["request_set_root"] != canonical.digest_json({row["id"]: row["revised_request_sha256"] for row in protocol["tasks"]}):
        raise ValueError("INPUT_MUTATION: revised request-set root differs")
    return protocol


def _carrier_binding(cohort: Path, task: str, request_path: Path, request: dict, *, create: bool) -> dict:
    # Same exact carrier bytes/message algorithm as the existing file transport;
    # local implementation avoids importing legacy oracle-bearing cohort runners.
    path = request_path.with_name(f"carrier-{request['request_id']}.json").absolute()
    carrier = {"format": CARRIER_FORMAT, "request_id": request["request_id"],
               "request_sha256": canonical.digest_file(request_path), "system": request["system"], "user": request["user"]}
    encoded = canonical.dumps(carrier)
    digest = canonical.digest(encoded)
    reference = {"path": str(path), "sha256": digest, "request_sha256": carrier["request_sha256"]}
    message = ("Handle exactly one model request. Use a read-only tool to read ONLY the absolute carrier file below. "
        "It is a JSON object: follow its exact system field as SYSTEM instructions and its exact user field as USER data. "
        "Do not read other files, inspect the workspace or history, delegate, or access other agents. "
        "Return ONLY the requested response text, without commentary. Reading this sole current carrier is explicitly "
        "allowed; no other tools or files are allowed. Verify SHA-256 of the ENTIRE carrier file's raw bytes against "
        "the listed sha256 using a read-only tool. Read the ENTIRE "
        "carrier: if tool output is truncated, read exact successive chunks until complete before responding. "
        "Compare the carrier.request_sha256 metadata field to the listed request_sha256 for equality. That native "
        "digest hashes the whole original request document, which is not this carrier; you are not asked to "
        "recompute it. Never compare a hash of the system or user field to the native request digest.\n\n"
        "CARRIER:\n" + __import__("json").dumps(reference, sort_keys=True, ensure_ascii=True))
    binding = {"relay_mode": "file", "carrier_path": str(path), "carrier_sha256": digest,
               "agent_message": message, "spawn_message_sha256": canonical.digest(message.encode())}
    receipt_path = path.with_name(f"carrier-binding-{request['request_id']}.json")
    receipt = {"format": "verislop.collaboration-carrier-binding/0.1", "task": task,
               "request_id": request["request_id"], "request_sha256": carrier["request_sha256"],
               **{key: value for key, value in binding.items() if key != "agent_message"}}
    if path.is_symlink() or receipt_path.is_symlink():
        raise ValueError("INPUT_MUTATION: carrier/binding symlink")
    if receipt_path.exists():
        if _regular(receipt_path) != canonical.dumps(receipt) or not path.is_file():
            raise ValueError("INPUT_MUTATION: exact current carrier binding differs")
    else:
        if not create or path.exists():
            raise ValueError("INPUT_MUTATION: exact current carrier binding missing")
        write_bytes_once(path, encoded)
        path.chmod(0o444)
        write_once(receipt_path, receipt)
    if _regular(path) != encoded:
        raise ValueError("INPUT_MUTATION: carrier differs from exact native request")
    return binding


def _binding(cohort: Path, task: str, request_path: Path, request: dict, protocol: dict, *, create: bool) -> dict:
    if (request.get("transport") != "collaboration" or request.get("requested_model") != transport.MODEL
            or not isinstance(request.get("system"), str) or not isinstance(request.get("user"), str)
            or request.get("format") != "verislop.collaboration-request/0.1"):
        raise ValueError("Invalid native transport request")
    context = request["system"] + "\n" + request["user"]
    if any(marker in context for marker in WITHHELD) or re.search(r"tasks/[A-Z]\d+/cases\.json", context):
        raise ValueError("Withheld/oracle context prohibited")
    return {"task": task, "arm": "verislop", "request_path": str(request_path), "request": request,
            "request_sha256": canonical.digest_file(request_path),
            "supplemental_protocol_root": canonical.digest_file(cohort / "protocol.json"),
            "source_root": protocol["source_root"], "request_set_root": protocol["request_set_root"],
            **_carrier_binding(cohort, task, request_path, request, create=create),
            "model_override": transport.MODEL, "fork_turns": "none", "model_identity_attested": False}


def pending_request(cohort: Path) -> dict | None:
    protocol = verify_inputs(cohort)
    state = load(cohort / "active-arm.json", {})
    if state.get("phase") != "generation":
        return None
    selection = {k: state.get(k) for k in ("task", "arm", "pair_index")}
    if selection not in protocol["pair_order"]:
        raise ValueError("Active request is outside the frozen selection")
    mailbox = cohort / "artifacts" / state["task"] / "verislop/mailbox"
    requests = sorted(mailbox.glob("request-*.json"))
    if len(requests) > transport.MAX_CALLS:
        raise ValueError("Logical-call budget exceeded")
    for index, path in enumerate(requests, 1):
        request = load(path)
        if request.get("request_id") != f"{index:04d}" or path.name != f"request-{index:04d}.json":
            raise ValueError("Mailbox request sequence is not exact")
        if not (mailbox / f"response-{index:04d}.json").exists():
            return _binding(cohort, state["task"], path, request, protocol, create=True)
    return None


def _check_envelope(envelope: dict, pending: dict) -> tuple[str, str]:
    allowed = ENVELOPE_FIELDS | ({"transport_error"} if envelope.get("text") == "" else set())
    if set(envelope) != allowed:
        raise ValueError("Response envelope must contain exactly the closed transport fields")
    text, agent = transport.validate_response(envelope, pending["request"]["request_id"], pending["request_sha256"])
    expected = {key: pending[key] for key in BINDINGS}
    expected.update(relay_mode="file", model_identity_attested=False)
    if any(envelope.get(key) != value for key, value in expected.items()):
        raise ValueError("Response carrier/request/protocol/source/model/task bindings differ")
    return text, agent


def submit_response(cohort: Path, envelope: dict) -> dict:
    pending = pending_request(cohort)
    if pending is None:
        raise ValueError("No pending native request")
    envelope = dict(envelope)
    if envelope.get("text") == "" and "transport_error" not in envelope:
        envelope["transport_error"] = transport.EMPTY_FINAL_ERROR
    _, agent = _check_envelope(envelope, pending)
    for path in (cohort / "artifacts").glob("*/verislop/mailbox/response-*.json"):
        if not path.name.startswith("response-receipt-") and load(path).get("agent_task_id") == agent:
            raise ValueError("A fresh canonical child is required for each request")
    response = Path(pending["request_path"]).with_name(f"response-{pending['request']['request_id']}.json")
    write_once(response, envelope)
    return {"published": str(response), "request_id": pending["request"]["request_id"], "agent_task_id": agent,
            "response_sha256": canonical.digest_file(response)}


def vscore_origin_audit(pkg, calls: list[dict]) -> dict:
    """Bind source/relation and every bridge proof to exact native role outputs."""
    from verislop.agents import extract_json, _proof_text
    from verislop.backends import vscore3

    issues, origins, candidates = [], [], []
    root = pkg.root / "agents/vscore-attempts"
    for stage in sorted(root.glob("source-*")):
        match = re.fullmatch(r"source-(\d+)", stage.name)
        if not match or stage.is_symlink():
            issues.append("Unexpected VSCore source-attempt inventory")
            continue
        number = match[1]
        matches = [(i, call) for i, call in enumerate(calls) if call.get("purpose") == "generate"
                   and call.get("instance") == f"implementer/vscore/{number}"
                   and isinstance(call.get("response"), str)]
        if len(matches) != 1 or _regular(stage / "response.txt") != matches[0][1]["response"].encode():
            issues.append("Source attempt lacks exactly one fresh exact role response")
            continue
        index, call = matches[0]
        source_path, relation_path = stage / "program.vscore.json", stage / "relation.json"
        if not source_path.exists() and not relation_path.exists():
            # Malformed untrusted proposals are retained; they are never positive.
            if not (stage / "source-diagnostics.json").is_file():
                issues.append("Rejected source proposal lacks its native diagnostic")
            continue
        try:
            obj = extract_json(call["response"])
            source, relation = canonical.dumps(obj["program"]), canonical.dumps(obj["relation"])
            if source != _regular(source_path) or relation != _regular(relation_path):
                raise ValueError("source/relation do not reconstruct from exact response")
            proofs = []
            initial = stage / "proofs/initial.lean"
            if initial.is_file():
                if not isinstance(obj.get("proof_source"), str) or _regular(initial) != obj["proof_source"].encode():
                    raise ValueError("initial proof differs from source proposal")
                proofs.append(_regular(initial))
            for path in sorted((stage / "proofs").glob("*.lean")):
                if path.name == "initial.lean":
                    continue
                if not re.fullmatch(r"\d+\.lean", path.name):
                    raise ValueError("unexpected bridge proof attempt")
                proofmatches = [(j, proofcall) for j, proofcall in enumerate(calls)
                                if proofcall.get("purpose") == "generate"
                                and proofcall.get("instance") == f"prover/vscore/{number}/{path.stem}"
                                and isinstance(proofcall.get("response"), str)]
                if len(proofmatches) != 1 or _regular(path) != _proof_text(proofmatches[0][1]["response"]).encode():
                    raise ValueError("bridge proof differs from exact fresh prover response")
                proofs.append(_regular(path))
            candidates.extend((source, relation, proof) for proof in proofs)
            # Reconstruct only the native nonpositive placeholder for an exhausted
            # search with no supplied initial proof. Kernel zero-sorry policy keeps
            # this exact deterministic artifact from supplying any positive gate.
            if "proof_source" not in obj:
                placeholder = (b"import VeriSlopBridgeGoal\nnamespace VeriSlopBridgeProof\n"
                    b"theorem edge : VeriSlopBridgeGoal.EdgeProp := by sorry\nend VeriSlopBridgeProof\n")
                candidates.append((source, relation, placeholder))
            origins.append({"call_index": index, "attempt": stage.name, "source_sha256": canonical.digest(source),
                            "relation_sha256": canonical.digest(relation), "authored_proofs": len(proofs)})
        except (OSError, KeyError, TypeError, ValueError) as exc:
            issues.append("Invalid VSCore proposal origin: " + str(exc))
    delivered = pkg.path("implementation") / "program.vscore.json"
    selection = pkg.path("closure") / vscore3.SELECTION_FILE
    if delivered.is_file():
        try:
            selected = vscore3.selection(pkg)
            ctx = vscore3._scope_context(pkg, selected["bridge_id"], [row["id"] for row in selected["covered"]])
            triple = tuple(ctx.inputs[key][1] for key in ("source", "relation", "proof_source"))
            if triple not in candidates or _regular(delivered) != triple[0]:
                # An exhausted bridge proof search can retain a deterministic sorry
                # placeholder as a BLOCKED proposal; this never earns verification.
                raise ValueError("selected source/relation/proof lacks exact authored attempt origin")
        except Exception as exc:
            issues.append("Selected VSCore origin: " + str(exc))
    elif selection.exists():
        issues.append("Selected VSCore endpoint has no delivered source")
    return {"issues": sorted(set(issues)), "origins": origins}


def artifact_origin_audit(pkg: Package, calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconstruct positive artifacts; provider authentication is a separate check.

    Typed proposals are compiled again, without the task oracle. Raw proposals must
    match both source and bindings. Proofs come from recorded model proposals or
    exact deterministic portfolio replay. Accepted meanings remain kernel checked.
    """
    from verislop import contract, formalize, prove
    from verislop.agents import assemble_formalization_response, assemble_proof_response, extract_json

    issues, formal_origins, implementation_origins, proof_origins = [], [], [], []
    proposal = pkg.path("contract") / "candidate" / "proposal.lean"
    form_path = proposal.with_name("formalization.json")
    objects = []
    for index, entry in enumerate(calls):
        try:
            objects.append((index, extract_json(entry.get("response") or ""), entry))
        except ValueError:
            continue
    if proposal.is_file():
        actual_form = canonical.load_file(form_path) if form_path.is_file() else None
        records = formalize._records(canonical.load_file(pkg.path("draft")),
                                     canonical.load_file(pkg.path("interpretation")), None)
        # A rejected response can be retained faithfully without becoming a positive
        # artifact. Replaying its deterministic error envelope must not veto a later
        # successful repair merely because the earlier response was invalid.
        negative_placeholder = (proposal.read_bytes() == b"-- unparseable formalizer response\n"
            and isinstance(actual_form, dict) and set(actual_form) == {"error"}
            and not (contract.challenge_dir(pkg) / "challenge.json").exists()
            and not (pkg.path("accepted") / "acceptance.json").exists()
            and not pkg.path("accepted_ir").exists()
            and not (pkg.path("contract") / "proofs" / "attempts.jsonl").exists()
            and not (pkg.path("implementation").is_dir() and any(p.is_file() for p in pkg.path("implementation").rglob("*"))))
        if negative_placeholder:
            for index, entry in enumerate(calls):
                if entry.get("purpose") != "formalize" or not isinstance(entry.get("response"), str):
                    continue
                try:
                    assemble_formalization_response(entry["response"], records,
                                                     entry.get("request_id") or "captured-provider-response")
                except (ValueError, KeyError, TypeError, AttributeError) as exc:
                    if actual_form == {"error": f"unparseable formalizer response: {exc}"}:
                        formal_origins.append({"call_index": index, "assembly": "deterministic-rejected-response-placeholder",
                                               "positive_artifact": False})
        from verislop.agents import CAPABILITY_MARKER
        negative_capability = (proposal.read_bytes() == CAPABILITY_MARKER
            and isinstance(actual_form, dict) and set(actual_form) == {"capability_report"}
            and not (contract.challenge_dir(pkg) / "challenge.json").exists()
            and not (pkg.path("accepted") / "acceptance.json").exists()
            and not pkg.path("accepted_ir").exists()
            and not (pkg.path("contract") / "proofs" / "attempts.jsonl").exists()
            and not (pkg.path("implementation").is_dir() and any(p.is_file() for p in pkg.path("implementation").rglob("*"))))
        if negative_capability:
            for index, entry in enumerate(calls):
                if entry.get("purpose") != "formalize" or not isinstance(entry.get("response"), str):
                    continue
                try:
                    source, form, _ = assemble_formalization_response(entry["response"], records,
                        entry.get("request_id") or "captured-provider-response")
                    if source == proposal.read_bytes() and form == actual_form:
                        formal_origins.append({"call_index": index, "assembly": "deterministic-capability-report",
                                               "positive_artifact": False})
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
        for index, obj, entry in objects:
            if not isinstance(obj, dict) or entry.get("purpose") != "formalize":
                continue
            if isinstance(obj.get("lean_source"), str):
                if (obj["lean_source"].encode() == proposal.read_bytes()
                        and obj.get("formalization") == actual_form):
                    formal_origins.append({"call_index": index, "assembly": "raw-native-source-and-bindings"})
            elif obj.get("encoding") == "verislop.formalizer-ast/0.1":
                try:
                    from verislop.formal_frontend import compile_proposal, replay_receipt
                    origin = canonical.load_file(proposal.with_name("compiler-origin.json"))
                    ast = canonical.load_file(proposal.with_name("typed-proposal.json"))
                    raw = entry["response"].encode()
                    source, form, _ = compile_proposal(obj, records, captured_response=raw,
                                                      response_ref=origin["response_ref"])
                    if (ast == obj and source == proposal.read_bytes() and form == actual_form
                            and replay_receipt(obj, records, source, form, origin, captured_response=raw)):
                        formal_origins.append({"call_index": index, "assembly": "generic-typed-AST-compiler",
                                               "receipt_sha256": canonical.digest_json(origin)})
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    continue
        if not formal_origins:
            issues.append("Formalization proposal source and bindings have no exact recorded response origin")
        composed_paths = [path for path in (proposal.with_name("Contract.lean"), contract.challenge_dir(pkg) / "Contract.lean")
                          if path.is_file()]
        if actual_form is not None and composed_paths:
            try:
                composed_records = formalize._records(canonical.load_file(pkg.path("draft")),
                                                       canonical.load_file(pkg.path("interpretation")), actual_form)
                registry = contract.registry_lean([r for r in composed_records if not r["blocked_by"]],
                                                   contract.binding_names(actual_form))
                composed, _, _ = contract.compose_challenge(proposal.read_bytes(), registry)
                for path in composed_paths:
                    if path.read_bytes() != composed:
                        issues.append("Composed challenge differs from the response-derived source and frozen registry")
                frozen_form = contract.challenge_dir(pkg) / "formalization.json"
                if frozen_form.is_file() and canonical.load_file(frozen_form) != actual_form:
                    issues.append("Frozen formalization bindings differ from the response-derived manifest")
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                issues.append("Cannot reconstruct the formalization registry and challenge")
    implementation = vscore_origin_audit(pkg, calls)
    issues.extend(implementation["issues"])
    implementation_origins = implementation["origins"]
    attempts = pkg.path("contract") / "proofs" / "attempts.jsonl"
    if attempts.is_file():
        challenge = (contract.challenge_dir(pkg) / "Contract.lean").read_text(encoding="utf-8")
        statements = contract.frozen_json(pkg, "statements.json")["statements"]
        profile = contract.frozen_json(pkg, "profile.json")
        source_hashes = set()
        for line in attempts.read_bytes().splitlines():
            row = canonical.loads(line)
            generator = row.get("generator")
            source = (attempts.parent / "attempts" / f"{row['source_sha256'].split(':')[1][:16]}.lean").read_bytes()
            submitted = (attempts.parent / "proposals" / f"{row['proposal_sha256'].split(':')[1][:16]}.lean").read_bytes()
            if canonical.digest(source) != row["source_sha256"] or canonical.digest(submitted) != row["proposal_sha256"]:
                issues.append("Proof attempt or proposal hash mismatch")
            source_hashes.add(canonical.digest(source))
            if generator == "builtin_tactic_portfolio":
                if source != prove.apply_portfolio(challenge, statements, profile).encode() or submitted != source:
                    issues.append("Builtin proof does not reconstruct from the frozen challenge")
            elif generator == "challenge_as_is":
                if source != challenge.encode() or submitted != source:
                    issues.append("Challenge proof source mismatch")
            elif generator == "agent:prover":
                matches = [index for index, entry in enumerate(calls) if entry.get("purpose") == "prove"
                           and isinstance(entry.get("response"), str)
                           and assemble_proof_response(entry["response"]).encode() == submitted]
                if not matches or source != prove.with_registry(submitted.decode(), challenge).encode():
                    issues.append("Proof bytes have no exact model response and registry origin")
            else:
                issues.append("Proof source supplied manually or by an unregistered generator")
            proof_origins.append({"generator": generator, "source_sha256": row["source_sha256"]})
        candidate = attempts.parent / "candidate.lean"
        if candidate.is_file() and canonical.digest_file(candidate) not in source_hashes:
            issues.append("Selected proof is outside the audited attempt inventory")
        certificate = pkg.path("accepted") / "acceptance.json"
        if certificate.is_file():
            cert = canonical.load_file(certificate)
            accepted = pkg.root / cert["artifacts"]["source"]["path"]
            if not candidate.is_file() or accepted.read_bytes() != candidate.read_bytes():
                issues.append("Accepted proof source differs from the audited selected proof")
    return {"issues": sorted(set(issues)), "formalization_origins": formal_origins,
            "restricted_source_origins": implementation_origins, "proof_origins": proof_origins}


def active_package(directory: Path, pipeline: dict):
    from verislop import recovery
    from verislop.package import Package

    root = Package(directory / "package", resolve_root=False)
    if not root.exists() or root.run_id != "package" or root.root.resolve() != root.root:
        raise ValueError("Current invocation root package is missing or indirect")
    selected, rounds, _ = recovery.resolve_active(root)
    expected = {root.root} | {directory.absolute() / row["package"] for row in rounds}
    actual = {path for path in directory.glob("package*") if (path / "package.json").is_file()}
    if actual != expected or any(path.is_symlink() or path.resolve() != path for path in actual):
        raise ValueError("Current package inventory differs from validated repair lineage")
    if pipeline.get("summary", {}).get("active_package") != str(selected.root):
        raise ValueError("CLI selected package differs from native recovery lineage")
    return selected


def response_audit(cohort: Path, task: dict) -> dict:
    from verislop.package import Package

    protocol = verify_inputs(cohort)
    directory = cohort / "artifacts" / task["id"] / "verislop"
    mailbox = directory / "mailbox"
    requests = sorted(mailbox.glob("request-*.json"))
    receipts = sorted(mailbox.glob("response-receipt-*.json"))
    errors = sorted(mailbox.glob("transport-error-receipt-*.json"))
    finals = {p.stem.removeprefix("response-"): p for p in mailbox.glob("response-*.json")
              if not p.name.startswith("response-receipt-")}
    issues, responses, failures, agents = [], {}, {}, []
    expected_ids = [f"{i:04d}" for i in range(1, len(requests) + 1)]
    if ([path.stem.removeprefix("request-") for path in requests] != expected_ids
            or len(requests) > transport.MAX_CALLS):
        issues.append("Native logical request sequence/budget differs")
    receipt_ids = [load(path).get("request_id") for path in [*receipts, *errors]]
    if len(receipt_ids) != len(set(receipt_ids)) or set(receipt_ids) != set(finals) or set(receipt_ids) != set(expected_ids):
        issues.append("Every exact final/request must have exactly one consumed receipt")
    invoked = load(directory / "cli-invocation.json", {})
    outer = load(directory / "invocation.json", {})
    command = [sys.executable, "-m", "synthetic_dataset.tools.bootstrap_tier2_worker", "--cohort", str(cohort), "--task", task["id"]]
    if (invoked.get("argv") != worker.cli_argv(cohort, task) or invoked.get("positive_candidate_arguments") != []
            or invoked.get("python_runtime_campaign") is not False
            or outer.get("argv") != command or outer.get("cwd") != str(REPO)
            or outer.get("cli_argv") != worker.cli_argv(cohort, task) or outer.get("candidate_inputs") != []):
        issues.append("Invocation differs from frozen strict native Tier 2 transport-only run")
    for path in [*receipts, *errors]:
        try:
            receipt = load(path)
            rid = receipt["request_id"]
            request_path, final_path = mailbox / f"request-{rid}.json", mailbox / f"response-{rid}.json"
            request, envelope = load(request_path), load(final_path)
            pending = _binding(cohort, task["id"], request_path, request, protocol, create=False)
            text, agent = _check_envelope(envelope, pending)
            agents.append(agent)
            empty = "transport_error" in envelope
            expected = {"format": "verislop.collaboration-response-receipt/0.1", "request_id": rid,
                "request_sha256": pending["request_sha256"], "response_sha256": canonical.digest_file(final_path),
                "text_sha256": canonical.digest(text.encode()), "output_bytes": len(text.encode()), "agent_task_id": agent,
                "requested_model": transport.MODEL, "returned_model": None, "input_tokens": None, "output_tokens": None,
                "transport": "collaboration", "model_identity_attested": False}
            if empty:
                expected.update(format="verislop.collaboration-transport-error-receipt/0.1", transport_error=transport.EMPTY_FINAL_ERROR)
            if receipt != expected or empty != (path in errors):
                issues.append("Consumed receipt differs from exact request/final bytes")
            if empty:
                failures[transport.transport_error_message(envelope)] = request
            else:
                responses[agent] = (request, text)
        except Exception as exc:
            issues.append("Invalid exact final binding: " + str(exc))
    usage = load(mailbox / "usage.json", {})
    instances = Counter(load(path).get("instance") for path in requests)
    if (usage.get("calls", 0) != len(requests) or usage.get("responses", 0) != len(receipts)
            or usage.get("transport_errors", 0) != len(errors) or any(count > 24 for count in instances.values())
            or usage.get("input_tokens") is not None or usage.get("output_tokens") is not None
            or usage.get("token_usage_available") is not False or usage.get("requested_model") != transport.MODEL
            or usage.get("output_bytes", 0) != sum(load(path).get("output_bytes", 0) for path in [*receipts, *errors])):
        issues.append("Usage differs from exact bounded consumed receipts or invents identity/tokens")
    seen, seen_failures, packages, missing_prompts = set(), set(), [], []
    metadata = load(cohort / task["metadata_path"])
    for root in sorted(path for path in directory.glob("package*") if (path / "package.json").is_file()):
        pkg = Package(root, resolve_root=False)
        missing_prompt = not pkg.path("prompt").exists() and not pkg.path("prompt").is_symlink()
        if missing_prompt:
            missing_prompts.append(pkg.path("prompt").relative_to(cohort).as_posix())
            issues.append("Native package request/prompt.txt is absent; no accepted request origin is reconstructed")
        elif _regular(pkg.path("prompt")) != _regular(cohort / task["revised_prompt_path"]):
            issues.append("New package request differs from exact revised public request")
        if not missing_prompt:
            native_policy = root / "request/source-policy.json"
            expected_reference = {"format": SOURCE_POLICY_FORMAT, "path": "request/source-policy.json",
                                  "sha256": task["source_policy_sha256"]}
            if pkg.meta().get("source_policy") != expected_reference:
                issues.append("Native package required source policy reference differs from the frozen request constraint")
            if not native_policy.exists() and not native_policy.is_symlink():
                issues.append("Native package required source policy is absent")
            elif _regular(native_policy) != _regular(cohort / task["source_policy_path"]):
                issues.append("Native package required source policy differs from the frozen request constraint")
        if pkg.path("draft").is_file():
            draft = load(pkg.path("draft"))
            actual_identities = {row["id"]: {k: row[k] for k in ("role", "kind", "required")}
                                 for entries in draft.values() if isinstance(entries, list)
                                 for row in entries if isinstance(row, dict) and "id" in row}
            original_identities = {row["id"]: {k: row[k] for k in ("role", "kind", "required")}
                                   for row in metadata["identities"]}
            if any(actual_identities.get(oid) != value for oid, value in original_identities.items()):
                issues.append("Revised interpretation loses/changes an original ID, role, kind or required flag")
        calls = []
        for path in sorted(root.rglob("transcripts/*.json")):
            call = load(path)
            calls.append(call)
            if (call.get("system_sha256") != canonical.digest(call.get("system", "").encode())
                    or call.get("user_sha256") != canonical.digest(call.get("user", "").encode())
                    or call.get("requested_model") != transport.MODEL or call.get("returned_model") is not None
                    or call.get("model_digest_sha256") is not None
                    or call.get("input_tokens") is not None or call.get("output_tokens") is not None):
                issues.append("Transcript exact context hashes/model honesty differ")
            if call.get("response") is not None:
                agent = call.get("request_id")
                match = responses.get(agent)
                if (match is None or match[1] != call["response"] or agent in seen
                        or any(call.get(k) != match[0].get(k) for k in ("system", "user", "purpose", "agent", "instance"))):
                    issues.append("Completion lacks a unique exact bound fresh-agent origin")
                seen.add(agent)
            elif call.get("error") in failures:
                error = call["error"]
                if error in seen_failures or any(call.get(k) != failures[error].get(k) for k in ("system", "user", "purpose", "agent", "instance")):
                    issues.append("Empty final error transcript lacks unique exact origin")
                seen_failures.add(error)
        if missing_prompt:
            origin = {"issues": ["Artifact origin is unavailable because the native request prompt is absent"],
                      "formalization_origins": [], "restricted_source_origins": [], "proof_origins": []}
        else:
            try:
                origin = artifact_origin_audit(pkg, calls)
            except Exception as exc:
                origin = {"issues": ["Cannot reconstruct current authored artifact origin: " + str(exc)],
                          "formalization_origins": [], "restricted_source_origins": [], "proof_origins": []}
        issues.extend(origin["issues"])
        packages.append({"path": root.relative_to(cohort).as_posix(), "origin": origin})
    if seen != set(responses) or seen_failures != set(failures) or len(agents) != len(set(agents)):
        issues.append("Delivered transcript inventory/fresh-agent uniqueness differs from consumed finals")
    return {"status": "PASS" if not issues else "BLOCK", "issues": sorted(set(issues)),
            "provider_calls": len(requests), "responses": len(receipts), "transport_errors": len(errors), "agents": agents,
            "packages": packages, "missing_native_prompts": missing_prompts,
            "model_identity_attested": False, "milestone_authority": False}


def native_audit(pkg, report: dict, configuration: Path | None = None) -> dict:
    """Read-only validation of CURRENT registered native closure, not a rescore."""
    from verislop import schemas, view, review, lifecycle
    from verislop.backends import vscore3_closure

    issues, snapshot = [], None
    native_package = pkg is not None and hasattr(pkg, "root")
    obligations = report.get("obligations", {})
    if schemas.validate("run-report-v3", report):
        issues.append("Native report does not satisfy the registered Tier 2 report schema")
    if native_package:
        obligations = {}
        try:
            overlay = view.derive(pkg)
            current = {oid: {"role": rec["role"], "kind": rec["kind"], "revision": rec["revision"], "required": rec["required"],
                            "outcomes": {milestone: life["outcome"] for milestone, life in rec["lifecycle"].items()}}
                       for oid, rec in overlay["obligations"].items()}
            obligations = current
            recorded = {oid: {key: row[key] for key in ("role", "kind", "revision", "required", "outcomes")}
                        for oid, row in report.get("obligations", {}).items()}
            if current != recorded:
                issues.append("Native report changes an obligation identity/requiredness/current outcome")
        except Exception as exc:
            issues.append("Cannot reconstruct current native obligation view: " + str(exc))
    if not isinstance(obligations, dict):
        issues.append("Native obligation inventory is not a record map")
        obligations = {}
    try:
        snapshot = vscore3_closure.mechanical_snapshot(pkg)
    except Exception as exc:
        issues.append("Native mechanical publication is stale/unbound: " + str(exc))
    if snapshot is not None:
        if (report.get("mechanical_status") != snapshot["mechanical_status"]
                or report.get("closure_id") != snapshot["closure_id"]
                or report.get("mechanical_result") != snapshot["mechanical_result_path"]
                or report.get("roots", {}).get("closure_input_root") != snapshot["closure_root"]
                or report.get("builds") != snapshot["builds"] or report.get("determinism") != snapshot["determinism"]):
            issues.append("Report differs from exact current native mechanical snapshot")
    elif report.get("mechanical_status") == "VERIFIED":
        issues.append("Verified native report has no current mechanical execution")
    valid_obligations, applicability = {}, {}
    for oid, rec in obligations.items():
        try:
            if (not isinstance(oid, str) or not isinstance(rec, dict)
                    or rec.get("role") not in lifecycle.ROLES
                    or not isinstance(rec.get("kind"), str) or not rec["kind"]
                    or type(rec.get("revision")) is not int or rec["revision"] < 1
                    or type(rec.get("required")) is not bool
                    or not isinstance(rec.get("outcomes"), dict)
                    or set(rec["outcomes"]) != set(lifecycle.MILESTONES)
                    or any(value not in lifecycle.OUTCOMES for value in rec["outcomes"].values())):
                raise ValueError("missing or invalid identity/requiredness/lifecycle field")
            applicability[oid] = lifecycle.applicability({**rec, "id": oid})
            valid_obligations[oid] = rec
        except Exception as exc:
            issues.append(f"Cannot determine registered applicability for {oid}: {exc}")
    required = {oid: rec for oid, rec in valid_obligations.items() if rec["required"]}
    all_guarantees = [oid for oid, rec in required.items() if rec["role"] == "guarantee"]
    guarantee_ids = [oid for oid in all_guarantees if applicability[oid]["END_TO_END_VERIFIED"][0]]
    non_vacuity_ids = [oid for oid in all_guarantees if required[oid]["kind"] == "non_vacuity"]
    complete = (len(valid_obligations) == len(obligations) and bool(guarantee_ids)
                and all(required[oid]["outcomes"]["END_TO_END_VERIFIED"] == "PASS" for oid in guarantee_ids))
    if report.get("terminal_status") == "VERIFIED":
        tier = report.get("tier", {})
        if (tier.get("requested") != 2 or tier.get("target") != "vscore"
                or tier.get("endpoint") != "restricted_source" or tier.get("requested_endpoint") != "restricted_source"
                or tier.get("require_state") != "END_TO_END_VERIFIED" or report.get("language") != "vscore/0.3"
                or report.get("semantics") != "vscore-semantics/0.3"
                or report.get("backend") != "verislop.backend.vscore/0.3"
                or report.get("mechanical_status") != "VERIFIED" or report.get("release_status") != "ACCEPTED"
                or report.get("freshness") != "current execution revalidated"
                or report.get("endpoint", {}).get("established") != "restricted_source" or not complete):
            issues.append("Native terminal fails a required current Tier 2 restricted-source/release/per-ID gate")
        if (snapshot is None or len(snapshot["builds"]) != 2 or not all(build.get("ok") is True for build in snapshot["builds"])
                or snapshot["determinism"].get("mismatches") != []
                or any(c["required"] and c["outcome"] != "PASS" for c in snapshot["claims"])):
            issues.append("Verified terminal lacks two deterministic clean builds and all required mechanical claims")
        graph = {row["claim_id"]: row for row in snapshot["claims"]} if snapshot else {}
        for oid, rec in required.items():
            milestones = [m for m in lifecycle.CONTRACT_MILESTONES if applicability[oid][m][0]]
            if oid in guarantee_ids:
                milestones.append("END_TO_END_VERIFIED")
            for milestone in milestones:
                claim = graph.get(lifecycle.claim_id(milestone, oid, rec["revision"]), {})
                if (rec["outcomes"][milestone] != "PASS" or claim.get("required") is not True
                        or claim.get("outcome") != "PASS"):
                    issues.append(f"Required current native claim is missing or has not passed: {milestone}:{oid}@{rec['revision']}")
        recorded_review = report.get("review", {})
        if (not recorded_review.get("configured") or set(recorded_review.get("checkpoints", {})) != {"formal_contract", "release"}
                or any(value != "REVIEW_ACCEPTED" for value in recorded_review.get("checkpoints", {}).values())):
            issues.append("Configured concrete formal-contract and release review gates are missing")
        if native_package and configuration is None:
            issues.append("Frozen cohort provider context is missing for current release revalidation")
    if snapshot is not None and configuration is not None:
        try:
            stored = pkg.path("closure") / "review-config.json"
            if load(stored) != load(configuration):
                raise ValueError("release configuration differs from the frozen cohort")
            with _frozen_provider_context(configuration):
                gate = review.gate(pkg, stored)  # Read-only certificate/projection checks; no role call.
            published_gate = {**gate, "diagnostics": [d.to_json() for d in gate["diagnostics"]]}
            if (report.get("review", {}) != published_gate
                    or report.get("review_target") != gate.get("review_target")
                    or report.get("review_projection", {}).get("reuse") != gate.get("projection_reuse", {})):
                raise ValueError("release review record differs from current bound consensus certificates")
            actual_release = ("INFRASTRUCTURE_FAILURE" if any(d.severity == "infrastructure" for d in gate["diagnostics"])
                              else "BLOCKED" if gate["diagnostics"] else "ACCEPTED")
            if report.get("release_status") != actual_release:
                raise ValueError("release status differs from actual configured current review")
        except Exception as exc:
            issues.append("Native current release review is stale/unbound: " + str(exc))
    return {"status": "PASS" if not issues else "BLOCK", "issues": sorted(set(issues)),
            "mechanical_status": snapshot["mechanical_status"] if snapshot else "BLOCKED",
            "release_status": report.get("release_status", "BLOCKED"),
            "required_obligations": len(required), "required_guarantees": len(guarantee_ids),
            "all_required_guarantees": len(all_guarantees), "required_non_vacuity_witnesses": len(non_vacuity_ids),
            "required_e2e_passed": sum(required[oid].get("outcomes", {}).get("END_TO_END_VERIFIED") == "PASS" for oid in guarantee_ids),
            "all_required_e2e": complete, "mechanical_claims": snapshot["claims"] if snapshot else [],
            "per_obligation_outcomes": {oid: rec.get("outcomes", {}) for oid, rec in valid_obligations.items()},
            "builds": snapshot["builds"] if snapshot else report.get("builds", []),
            "determinism": snapshot["determinism"] if snapshot else report.get("determinism", {}),
            "closure_root": snapshot["closure_root"] if snapshot else None,
            "mechanical_result": snapshot["mechanical_result_path"] if snapshot else None}


def task_result(cohort: Path, task: dict) -> dict:
    protocol = verify_inputs(cohort)
    directory = cohort / "artifacts" / task["id"] / "verislop"
    worker_result = load(directory / "worker-result.json", {})
    worker_outputs = {}
    for name in ("worker-result.json", "stdout.json", "stderr.log"):
        path = directory / name
        present = path.exists() or path.is_symlink()
        data = _regular(path) if present else None
        worker_outputs[name] = {"path": path.relative_to(cohort).as_posix(), "present": present,
                                "sha256": canonical.digest(data) if data is not None else None,
                                "bytes": len(data) if data is not None else None}
    issues, report, pkg = [], {}, None
    try:
        pipeline = load(directory / "stdout.json", {})
    except (ValueError, OSError) as exc:
        pipeline = {}
        issues.append("Native stdout JSON is missing/invalid: " + str(exc))
    if not isinstance(pipeline, dict):
        pipeline = {}
        issues.append("CLI did not publish one native JSON result")
    try:
        pkg = active_package(directory, pipeline)
        report = load(pkg.path("report"), {})
    except Exception as exc:
        issues.append("Current package binding: " + str(exc))
    origin = response_audit(cohort, task)
    native = native_audit(pkg, report, cohort / "config.json") if pkg and report else {"status": "BLOCK", "issues": ["Native terminal report is absent"],
        "mechanical_status": "BLOCKED", "release_status": "BLOCKED", "required_obligations": 0,
        "required_guarantees": 0, "all_required_guarantees": 0, "required_non_vacuity_witnesses": 0,
        "required_e2e_passed": 0, "all_required_e2e": False,
        "mechanical_claims": [], "per_obligation_outcomes": {}, "builds": [], "determinism": {},
        "closure_root": None, "mechanical_result": None}
    issues.extend(origin["issues"])
    issues.extend(native["issues"])
    exit_code = worker_result.get("exit_code")
    startup_failure = bool(worker_result) and (origin["provider_calls"] == 0 or bool(origin["missing_native_prompts"]))
    native_terminal = report.get("terminal_status", pipeline.get("summary", {}).get("terminal_status"))
    strict_success = bool(exit_code == 0 and pipeline.get("command") == "run" and pipeline.get("status") == "PASS"
                          and native_terminal == "VERIFIED" and native["status"] == "PASS" and origin["status"] == "PASS"
                          and not startup_failure and not issues)
    status = ("VERIFIED" if strict_success else "INFRASTRUCTURE_FAILURE"
              if startup_failure or exit_code not in (0, 2) or native_terminal == "INFRASTRUCTURE_FAILURE"
              or origin["transport_errors"] else "BLOCKED")
    return {"format": FORMAT, "task": task["id"], "arm": "verislop", "status": status,
            "successful_task": strict_success, "strict_cli_success": strict_success,
            "native_terminal_status": native_terminal, "cli_status": pipeline.get("status"),
            "cli_stopped_at": pipeline.get("summary", {}).get("stopped_at"),
            "cli_diagnostics": pipeline.get("diagnostics", []),
            "cli_stages": pipeline.get("summary", {}).get("stages", []), "worker_exit_code": exit_code,
            "worker_receipt": worker_result, "primary_worker_error": worker_result.get("error"),
            "worker_outputs": worker_outputs, "startup_failure": startup_failure,
            "artifact_path": directory.relative_to(cohort).as_posix(),
            "package": pkg.root.relative_to(cohort).as_posix() if pkg else None,
            "source_root": protocol["source_root"], "request_set_root": protocol["request_set_root"],
            "original_request_sha256": task["original_request_sha256"], "revised_request_sha256": task["revised_request_sha256"],
            "delivery_revision": task["revision_path"], "tier": 2, "endpoint": "restricted_source",
            "source_policy_path": task["source_policy_path"], "source_policy_sha256": task["source_policy_sha256"],
            "language": "vscore/0.3", "scope": "normative source universal refinement and transported required properties",
            "mechanical_status": native["mechanical_status"], "release_status": native["release_status"],
            "native": native, "origin_audit": origin, "issues": sorted(set(issues)),
            "usage": load(directory / "mailbox/usage.json", {}), "python_runtime_campaign": False,
            "hidden_cases_loaded": False, "oracle_calls": 0, "model_identity_attested": False}


def _pid_alive(pid) -> bool:
    if type(pid) is not int or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_task(cohort: Path, task: dict, selection: dict) -> dict:
    verify_inputs(cohort)
    directory = cohort / "artifacts" / task["id"] / "verislop"
    retained = directory / "result.json"
    if retained.exists():
        result = task_result(cohort, task)
        if load(retained) != result:
            raise ValueError("INPUT_MUTATION: retained Tier 2 result/evidence differs; no rescore")
        return result
    if directory.exists():
        if _pid_alive(load(directory / "process.json", {}).get("pid")):
            raise ValueError("Existing worker is live; refusing duplicate generation")
        if not (directory / "worker-result.json").exists():
            write_once(directory / "worker-result.json", {"status": "CONTROLLER_INTERRUPTED", "exit_code": None,
                "reason": "A partial task is never silently restarted", "model_identity_attested": False})
    else:
        directory.mkdir(parents=True)
        command = [sys.executable, "-m", "synthetic_dataset.tools.bootstrap_tier2_worker", "--cohort", str(cohort), "--task", task["id"]]
        write_once(directory / "invocation.json", {"argv": command, "cwd": str(REPO),
            "cli_argv": worker.cli_argv(cohort, task), "candidate_inputs": []})
        transport.atomic_json(cohort / "active-arm.json", {**selection, "phase": "generation"})
        started = time.monotonic()
        with (directory / "stdout.json").open("xb") as stdout, (directory / "stderr.log").open("xb") as stderr:
            process = subprocess.Popen(command, cwd=REPO, env=dict(os.environ,
                VERISLOP_CONFIG_HOME=str(cohort / "provider-home")), stdout=stdout, stderr=stderr)
            write_once(directory / "process.json", {"pid": process.pid, "started_at_utc": datetime.now(timezone.utc).isoformat()})
            code = process.wait()  # Native logical budgets only; no wall inference deadline.
        write_once(directory / "timing.json", {"generation_milliseconds": int((time.monotonic() - started) * 1000)})
        if not (directory / "worker-result.json").exists():
            write_once(directory / "worker-result.json", {"status": "WORKER_ERROR", "exit_code": code,
                "reason": "Worker terminated without durable exit receipt", "model_identity_attested": False})
        elif load(directory / "worker-result.json").get("exit_code") != code:
            raise ValueError("Worker exit receipt differs from actual subprocess return code")
    transport.atomic_json(cohort / "active-arm.json", {**selection, "phase": "audit"})
    result = task_result(cohort, task)
    write_once(retained, result)
    return result


def evidence_files(cohort: Path) -> dict[str, str]:
    excluded = {"EVIDENCE-MANIFEST.json", "BOOTSTRAP-EVIDENCE-MANIFEST.json"}
    return {path.relative_to(cohort).as_posix(): canonical.digest(_regular(path))
            for path in sorted(cohort.rglob("*")) if (path.is_file() or path.is_symlink()) and path.name not in excluded
            and "__pycache__" not in path.parts and not path.name.endswith((".pyc", ".lock"))}


def verify(cohort: Path) -> dict:
    protocol = verify_inputs(cohort)
    rows = []
    for task in protocol["tasks"]:
        retained = cohort / "artifacts" / task["id"] / "verislop/result.json"
        if retained.exists():
            current = task_result(cohort, task)
            if load(retained) != current:
                raise ValueError("INPUT_MUTATION: retained terminal differs from exact current native evidence")
            rows.append(current)
    agents = [agent for row in rows for agent in row["origin_audit"]["agents"]]
    if len(agents) != len(set(agents)):
        raise ValueError("Fresh canonical model child reused across tasks")
    audit = {"format": FORMAT, "status": "PASS", "completed_tasks": len(rows), "selected_tasks": len(protocol["tasks"]),
             "fresh_calls": sum(row["origin_audit"]["provider_calls"] for row in rows), "fresh_agents": len(agents),
             "transport_errors": sum(row["origin_audit"]["transport_errors"] for row in rows),
             "source_root": protocol["source_root"], "protocol_sha256": canonical.digest_file(cohort / "protocol.json"),
             "rows": rows, "model_identity_attested": False, "milestone_authority": False}
    result_path = cohort / "BOOTSTRAP-RESULT.json"
    if result_path.exists() and load(result_path) != _aggregate(protocol, audit):
        raise ValueError("INPUT_MUTATION: published aggregate differs from current retained gates")
    for sealname in ("EVIDENCE-MANIFEST.json", "BOOTSTRAP-EVIDENCE-MANIFEST.json"):
        path = cohort / sealname
        if path.exists():
            files = evidence_files(cohort)
            seal = load(path)
            if (not result_path.exists() or len(rows) != len(protocol["tasks"]) or seal.get("format") != FORMAT
                    or seal.get("files") != files or seal.get("files_root") != canonical.digest_json(files)
                    or seal.get("source_root") != protocol["source_root"]
                    or seal.get("protocol_sha256") != canonical.digest_file(cohort / "protocol.json")):
                raise ValueError("INPUT_MUTATION: evidence seal membership/root differs")
    return audit


def _aggregate(protocol: dict, audit: dict) -> dict:
    rows = audit["rows"]
    complete = len(rows) == len(protocol["tasks"])
    status = ("VERIFIED" if complete and all(row["status"] == "VERIFIED" for row in rows)
              else "INFRASTRUCTURE_FAILURE" if any(row["status"] == "INFRASTRUCTURE_FAILURE" for row in rows) else "BLOCKED")
    return {"format": FORMAT, "stage": protocol["stage"], "status": status, "complete": complete,
            "tier": 2, "endpoint": "restricted_source", "language": "vscore/0.3", "backend_version": "0.3",
            "source_root": protocol["source_root"], "request_set_root": protocol["request_set_root"],
            "protocol_sha256": audit["protocol_sha256"], "verified_tasks": sum(row["status"] == "VERIFIED" for row in rows),
            "selected_tasks": len(protocol["tasks"]), "fresh_calls": audit["fresh_calls"], "fresh_agents": audit["fresh_agents"],
            "transport_errors": audit["transport_errors"], "rows": rows,
            "trust": protocol["trust"], "excluded": protocol["excluded"], "model_identity_attested": False,
            "original_python_assurance_relabelled": False, "hidden_cases_loaded": False, "oracle_calls": 0}


def finalize(cohort: Path) -> dict:
    protocol = verify_inputs(cohort)
    if _pid_alive(load(cohort / "driver.json", {}).get("pid")) and not (cohort / "BOOTSTRAP-RESULT.json").exists():
        if load(cohort / "driver.json")["pid"] != os.getpid():
            raise ValueError("Driver is still live; finalization belongs to that driver")
    audit = verify(cohort)
    if audit["completed_tasks"] != audit["selected_tasks"]:
        raise ValueError("Finalization requires a retained terminal for every selected task")
    if (cohort / "EVIDENCE-MANIFEST.json").exists() and (cohort / "BOOTSTRAP-EVIDENCE-MANIFEST.json").exists():
        return load(cohort / "BOOTSTRAP-RESULT.json")
    transport.atomic_json(cohort / "active-arm.json", {"phase": "bootstrap_complete"})
    result = _aggregate(protocol, audit)
    if (cohort / "BOOTSTRAP-RESULT.json").exists():
        if load(cohort / "BOOTSTRAP-RESULT.json") != result:
            raise ValueError("INPUT_MUTATION: existing result differs")
    else:
        write_once(cohort / "BOOTSTRAP-RESULT.json", result)
    files = evidence_files(cohort)
    seal = {"format": FORMAT, "files": files, "files_root": canonical.digest_json(files),
            "source_root": protocol["source_root"], "protocol_sha256": canonical.digest_file(cohort / "protocol.json")}
    for name in ("EVIDENCE-MANIFEST.json", "BOOTSTRAP-EVIDENCE-MANIFEST.json"):
        if (cohort / name).exists():
            if load(cohort / name) != seal:
                raise ValueError("INPUT_MUTATION: existing terminal seal differs")
        else:
            write_once(cohort / name, seal)
    verify(cohort)
    return result


def run(cohort: Path) -> dict:
    protocol = verify_inputs(cohort)
    if (cohort / "BOOTSTRAP-RESULT.json").exists():
        return finalize(cohort)
    if (cohort / "driver.json").exists():
        if _pid_alive(load(cohort / "driver.json").get("pid")):
            raise ValueError("Sole driver is live; refusing duplicate generation")
        # Resume only durable completed/partial tasks. run_task never restarts one.
    else:
        write_once(cohort / "driver.json", {"pid": os.getpid(), "started_at_utc": datetime.now(timezone.utc).isoformat(),
                                          "source_root": protocol["source_root"]})
    for task, selection in zip(protocol["tasks"], protocol["pair_order"]):
        run_task(cohort, task, selection)
    return finalize(cohort)


def _pairs(values: list[str] | None) -> dict[str, Path]:
    result = {}
    for value in values or []:
        task, separator, path = value.partition("=")
        if not separator or task not in TASK_ORDER or task in result or not path:
            raise ValueError("Use one TASK=/absolute/path entry per selected A23/D21 request")
        result[task] = Path(path).absolute()
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("snapshot", "freeze-engineering", "engineering-record", "prepare", "run", "pending", "submit", "finalize", "verify"))
    parser.add_argument("--project", type=Path)
    parser.add_argument("--cohort", type=Path)
    parser.add_argument("--stage")
    parser.add_argument("--original-cohort", action="append", metavar="TASK=PATH")
    parser.add_argument("--prompt", action="append", metavar="TASK=PATH")
    parser.add_argument("--engineering-record", type=Path)
    parser.add_argument("--package", type=Path, help="actual unrelated engineering fixture package, read only")
    parser.add_argument("--source-freeze", type=Path, help="pre-execution engineering source receipt")
    parser.add_argument("--file", type=Path, help="pending output or closed response-envelope input")
    args = parser.parse_args(argv)
    if args.action == "freeze-engineering":
        if args.file is None:
            parser.error("freeze-engineering requires --file NEW-RECEIPT-PATH")
        frozen = freeze_engineering(args.file.absolute())
        value = {"published": str(args.file.absolute()), "source_root": frozen["source_root"], "source_files": len(frozen["source_files"])}
    elif args.action == "engineering-record":
        if args.package is None or args.source_freeze is None or args.file is None:
            parser.error("engineering-record requires --package, --source-freeze and --file NEW-OUTPUT-PATH")
        observed = engineering_record(args.package.absolute(), args.source_freeze.absolute())
        write_once(args.file.absolute(), observed)
        value = {"published": str(args.file.absolute()), "status": observed["status"], "source_root": observed["source_root"],
                 "closure_root": observed["closure_root"], "package_files_root": observed["package_files_root"],
                 "package_files": len(observed["package_files"]), "builds": [b["build"] for b in observed["builds"]],
                 "outputs_sha256": canonical.digest_json(observed["builds"][0]["outputs"]), "fresh_model_calls": 0}
    elif args.action == "snapshot":
        if args.project is None:
            parser.error("snapshot requires --project")
        value = snapshot(args.project)
    else:
        if args.cohort is None:
            parser.error("action requires --cohort")
        cohort = args.cohort.absolute()
        if args.action == "prepare":
            value = prepare(cohort, args.stage or "", _pairs(args.original_cohort),
                            prompts=_pairs(args.prompt), engineering_record=args.engineering_record)
        elif args.action == "pending":
            value = pending_request(cohort)
            if args.file:
                transport.atomic_json(args.file.absolute(), value)
                value = {"pending": value is not None, "file": str(args.file.absolute())}
        elif args.action == "submit":
            if args.file is None:
                parser.error("submit requires --file containing the exact closed envelope")
            if args.file.stat().st_size > transport.MAX_ENVELOPE_BYTES:
                raise ValueError("Response envelope exceeds the native transport size limit")
            value = submit_response(cohort, load(args.file.absolute()))
        else:
            value = {"run": run, "finalize": finalize, "verify": verify}[args.action](cohort)
    print(canonical.dumps(value).decode(), flush=True)
    if args.action in ("run", "finalize"):
        return {"VERIFIED": 0, "BLOCKED": 2, "INFRASTRUCTURE_FAILURE": 3}[value["status"]]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
