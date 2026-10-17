"""Authenticate hybrid fallback correspondence before accepting mailbox text.

Model identity and compliance with carrier tool restrictions remain unattested.
The local response, request, frozen protocol and retained carrier must agree.
"""
from __future__ import annotations

from pathlib import Path
import re

from verislop import canonical
from .luna_data_pipeline_poc import _relay_binding
from .sol_data_pipeline_worker import MODEL, validate_response as basic_response


def validate_response(out: Path, task: str, request_path: Path, envelope: dict) -> None:
    # Runtime import avoids the harness/transport module cycle.
    from . import run_local_hybrid as hybrid

    try:
        protocol = hybrid.verify_inputs(out)
        if task not in protocol["tasks"] or protocol.get("relay_mode") != "file":
            raise ValueError("response task or relay is outside the frozen trial")
        if not re.fullmatch(r"request-[0-9]{4}\.json", request_path.name):
            raise ValueError("invalid request filename")
        expected_path = out.absolute() / "tasks" / task / "mailbox" / request_path.name
        if request_path.absolute() != expected_path or request_path.is_symlink():
            raise ValueError("response request is outside the current task mailbox")
        request = canonical.load_file(request_path)
        request_id = request_path.stem.removeprefix("request-")
        if (request.get("request_id") != request_id or request.get("transport") != "collaboration"
                or request.get("requested_model") != MODEL
                or request.get("purpose") not in protocol.get("sol_routes", {}).get(request.get("agent"), [])):
            raise ValueError("request differs from the declared Sol fallback route")
        request_hash = canonical.digest_file(request_path)
        _, agent = basic_response(envelope, request_id, request_hash)
        binding = _relay_binding(out, task, request_path, request, protocol, create_carrier=False)
        expected = {"task": task, "protocol_sha256": canonical.digest_file(out / "protocol.json"),
                    "model_override": MODEL, "fork_turns": "none",
                    **{key: binding[key] for key in ("carrier_path", "carrier_sha256", "spawn_message_sha256")}}
        if (any(envelope.get(key) != value for key, value in expected.items())
                or envelope.get("model_identity_attested") is not False):
            raise ValueError("response does not match the frozen protocol and exact carrier binding")
        current_response = request_path.with_name(f"response-{request_id}.json").absolute()
        for path in (out / "tasks").glob("*/mailbox/response-*.json"):
            if path.name.startswith("response-receipt-") or path.absolute() == current_response:
                continue
            if canonical.load_file(path).get("agent_task_id") == agent:
                raise ValueError("every Sol request requires a fresh agent across the trial")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise hybrid.failure("Sol response binding rejected: " + str(exc), "response_binding",
                             binding_failure=True) from None
