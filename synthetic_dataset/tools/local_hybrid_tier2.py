"""Read-only terminal validation for the frozen hybrid project trial.

No report label or stage-history row is evidence by itself. The existing native
VSCore closure validator authenticates retained claims, artifacts and clean builds.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import os
from pathlib import Path

from verislop import canonical


@contextmanager
def provider_context(out: Path, configuration: Path):
    from synthetic_dataset.tools import run_local_hybrid as hybrid

    if configuration.absolute() != (out / "config.json").absolute():
        raise ValueError("hybrid review configuration is outside the frozen trial")
    hybrid.verify_inputs(out)
    previous = os.environ.get("VERISLOP_CONFIG_HOME")
    os.environ["VERISLOP_CONFIG_HOME"] = str(out / "provider-home")
    try:
        yield
        hybrid.verify_inputs(out)
    finally:
        if previous is None:
            os.environ.pop("VERISLOP_CONFIG_HOME", None)
        else:
            os.environ["VERISLOP_CONFIG_HOME"] = previous


def request_binding(out: Path, task: str, pkg) -> None:
    """Tie closure to this frozen natural-language request and its native lineage."""
    from synthetic_dataset.tools import run_local_hybrid as hybrid
    from verislop import cli, recovery, run as native_run
    from verislop.package import Package

    protocol = hybrid.verify_inputs(out)
    if protocol.get("trial_mode") != "tier2-project" or task not in protocol["tasks"]:
        raise ValueError("package task is outside the frozen Tier 2 project selection")
    directory = out / "tasks" / task
    invoked = hybrid.cli_argv(out, task, protocol)
    if canonical.load_file(directory / "invocation.json") != {"argv": invoked, "positive_candidate_arguments": []}:
        raise ValueError("native invocation differs from the frozen project invocation")
    expected = native_run._params_from_args(cli.build_parser().parse_args(invoked))
    root = Package(directory / "runs" / task.lower(), resolve_root=False)
    active, rounds, _ = recovery.resolve_active(root)
    if active.root != pkg.root or root.meta().get("run_parameters") != expected:
        raise ValueError("active package or original run parameters differ from frozen native invocation")
    parameters = dict(expected)
    if rounds:
        parameters.update(prompt_file=str(pkg.path("prompt")), attachments=[],
                          draft_candidate=str(pkg.path("draft")), ledger_candidate=str(pkg.path("interpretation")),
                          resolve=[], non_interactive=True)
        # resolve_active authenticates this context against the immutable lineage.
        parameters["recovery_context"] = canonical.load_file(pkg.root / "recovery-context.json")
    if pkg.meta().get("run_parameters") != parameters:
        raise ValueError("active run parameters differ from the authenticated recovery invocation")
    prompt = (out / "prompts" / f"{task}.txt").read_bytes()
    for package in (root, pkg):
        request = canonical.load_file(package.path("request"))
        if (package.path("prompt").read_bytes() != prompt
                or request.get("document_hash") != canonical.digest(prompt)
                or request.get("byte_length") != len(prompt)
                or request.get("request_ref") != f"project-bootstrap/{task}.txt"
                or request.get("mode") != "software" or request.get("attachments") != []
                or request.get("repository_revision") is not None):
            raise ValueError("package request differs from the exact frozen project prompt")


def native_gate(out: Path, task: str, pkg, report: dict, pipeline: dict, exit_code: int) -> dict:
    """Revalidate the actual selected package; return a compact observation."""
    from synthetic_dataset.tools import bootstrap_tier2
    from verislop import run as native_run

    issues = []
    try:
        request_binding(out, task, pkg)
        if exit_code != 0 or pipeline.get("command") != "run" or pipeline.get("status") != "PASS":
            issues.append("the strict native CLI did not complete successfully")
        summary = pipeline.get("summary", {})
        if (summary.get("package") != str(pkg.root) or summary.get("active_package") != str(pkg.root)
                or summary.get("stopped_at") is not None):
            issues.append("the native result does not identify the completed active package")
        history = pkg.meta().get("stage_history", [])
        expected = native_run._stages_for({"tier": 2, "target": "vscore", "config": str(out / "config.json")})
        if (not history or summary.get("stages") != history
                or [row.get("stage") for row in history] != expected):
            issues.append("native stage history is missing, reordered or differs from the package")
        for row in history:
            # Native verification precedes release review. Its provisional release
            # block is not a mechanical failure; the final retained gates below
            # must independently establish both mechanical and review acceptance.
            provisional = (row.get("stage") == "verify" and row.get("status") == "BLOCKED"
                           and row.get("codes") == ["REVIEW_NOT_RUN"])
            if row.get("status") != "PASS" and not provisional:
                issues.append("native stage did not pass: " + str(row.get("stage")))
        if report.get("terminal_status") != "VERIFIED":
            issues.append("native terminal report is not VERIFIED")
        audit = bootstrap_tier2.native_audit(pkg, report, out / "config.json",
            provider_context=lambda configuration: provider_context(out, configuration))
        issues.extend(audit["issues"])
        observation = {key: audit[key] for key in (
            "mechanical_status", "release_status", "required_obligations", "required_guarantees",
            "required_e2e_passed", "required_non_vacuity_witnesses", "all_required_e2e", "closure_root",
            "mechanical_result")}
        observation["clean_builds"] = len(audit["builds"])
        observation["determinism_mismatches"] = audit["determinism"].get("mismatches")
        observation["required_claims"] = sum(row.get("required") is True for row in audit["mechanical_claims"])
    except Exception as exc:
        observation = {}
        issues.append("native retained-evidence validation failed: " + type(exc).__name__ + ": " + str(exc))
    return {"status": "PASS" if not issues else "BLOCK", "issues": sorted(set(issues)), **observation}


def constructor_coverage(pkg) -> dict:
    """Describe exact accepted source syntax; this is not an additional proof."""
    path = pkg.path("implementation") / "program.vscore.json"
    data = path.read_bytes()
    program = canonical.loads(data)
    constructors, compositions = Counter(), Counter()

    def walk(value, parent=None):
        if isinstance(value, dict):
            tag = value.get("tag")
            if isinstance(tag, str):
                constructors[tag] += 1
                if parent is not None:
                    compositions[parent + " -> " + tag] += 1
                parent = tag
            for child in value.values():
                walk(child, parent)
        elif isinstance(value, list):
            for child in value:
                walk(child, parent)

    walk(program)
    return {"source_path": str(path), "source_sha256": canonical.digest(data),
            "language": program.get("language"), "constructors": dict(sorted(constructors.items())),
            "constructor_compositions": dict(sorted(compositions.items())),
            "authority": "Observed accepted source syntax; native closure supplies assurance"}
