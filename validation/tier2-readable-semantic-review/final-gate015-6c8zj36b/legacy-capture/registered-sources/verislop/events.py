"""Schema-versioned JSON Lines event stream (specification §11).

Candidate proposals and verifier decisions are distinct event types. Events are progress
reports; they never carry authority over lifecycle outcomes.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, TextIO

from . import SCHEMA_VERSION, canonical, fsutil

EVENT_TYPES = (
    "run_started", "stage_started", "stage_finished", "progress",
    "candidate_proposal", "verifier_decision", "review_decision", "diagnostic", "run_finished",
)


class EventSink:
    def __init__(self, run_id: str, pkg: Path | None = None, target: str | None = None, quiet: bool = False) -> None:
        self.run_id = run_id
        self.pkg = Path(pkg) if pkg else None
        self.quiet = quiet
        self._stream: TextIO | None = None
        self._package_stream: TextIO | None = None
        self._own_stream = False
        self.seq = 0
        if self.pkg:
            fd = fsutil.open_regular_file(self.pkg / "events.jsonl", os.O_RDWR | os.O_CREAT | os.O_APPEND,
                                          create_parents=True)
            with os.fdopen(os.dup(fd), "rb") as existing:
                self.seq = sum(1 for _ in existing)
            self._package_stream = os.fdopen(fd, "a", encoding="utf-8")
        if target == "-":
            self._stream = sys.stderr
        elif target:
            fd = fsutil.open_regular_file(Path(target), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
            self._stream = os.fdopen(fd, "a", encoding="utf-8")
            self._own_stream = True

    def emit(self, type_: str, phase: str, message: str = "", **fields: Any) -> None:
        if type_ not in EVENT_TYPES:
            raise ValueError(f"unknown event type {type_}")
        self.seq += 1
        event: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "seq": self.seq,
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": type_,
            "phase": phase,
        }
        if message:
            event["message"] = message
        for key in ("obligation_id", "milestone", "outcome", "evidence_ref", "code", "details"):
            if fields.get(key) is not None:
                event[key] = fields[key]
        line = canonical.dumps(event).decode("utf-8")
        if self._package_stream:
            self._package_stream.write(line + "\n")
            self._package_stream.flush()
        if self._stream:
            self._stream.write(line + "\n")
            self._stream.flush()
        if not self.quiet and message and type_ in ("stage_started", "progress", "diagnostic", "verifier_decision"):
            prefix = {"stage_started": "==>", "diagnostic": "  !", "verifier_decision": "  ✓" if fields.get("outcome") == "PASS" else "  •"}.get(type_, "   ")
            sys.stderr.write(f"{prefix} [{phase}] {message}\n")
            sys.stderr.flush()

    def close(self) -> None:
        if self._package_stream:
            self._package_stream.close()
        if self._own_stream and self._stream:
            self._stream.close()
