"""Prompt routing (specification §3.1).

The classifier returns SOFTWARE, NON_SOFTWARE or UNCERTAIN with a short reason and the byte
spans that support the decision. It is a deterministic lexical router. Its confidence assists
routing only and never counts as evidence for any obligation. UNCERTAIN never silently
bypasses verification: it becomes an interpretation ambiguity.
"""

from __future__ import annotations

import re
from typing import Any

from . import SCHEMA_VERSION, canonical
from .segment import segments

CLASSIFIER_ID = "verislop.lexical-classifier/0.1"

_SOFTWARE_STRONG = [
    r"implement\w*", r"function\w*", r"method\w*", r"class(es)?", r"api\w*", r"endpoint\w*",
    r"refactor\w*", r"debug\w*", r"bugs?", r"compil\w+", r"build\w*", r"deploy\w*", r"unit tests?",
    r"test suites?", r"repositor\w+", r"codebase", r"librar(y|ies)", r"modules?", r"scripts?",
    r"programs?", r"algorithm\w*", r"pars(e|er|es|ing)", r"returns?", r"exceptions?", r"interfaces?",
    r"schemas?", r"databases?", r"sql", r"json", r"http\w*", r"cli", r"command[- ]line", r"runtime",
    r"integers?", r"booleans?", r"overflow\w*", r"regressions?", r"pull requests?", r"commits?",
    r"source code", r"type signatures?", r"natural numbers?", r"preconditions?", r"postconditions?",
    r"invariants?",
]
_SOFTWARE_WEAK = [
    r"inputs?", r"outputs?", r"errors?", r"caller", r"comput\w+", r"calculat\w+", r"defin\w+",
    r"validat\w+", r"config\w*", r"tests?", r"code", r"strings?", r"lists?", r"arrays?", r"files?",
    r"requests?", r"responses?", r"servers?", r"clients?", r"increment\w*", r"limits?",
]
_NON_SOFTWARE = [
    r"poems?", r"essays?", r"recipes?", r"stor(y|ies)", r"novels?", r"songs?", r"lyrics", r"travel\w*",
    r"itinerar(y|ies)", r"vacations?", r"paintings?", r"biograph\w+", r"diet\w*", r"workouts?",
    r"horoscopes?", r"weddings?", r"cover letters?", r"birthday", r"jokes?",
]


def _compile(words: list[str]) -> re.Pattern[str]:
    return re.compile(r"\b(" + "|".join(words) + r")\b", re.IGNORECASE)


_RE_STRONG = _compile(_SOFTWARE_STRONG)
_RE_WEAK = _compile(_SOFTWARE_WEAK)
_RE_NON = _compile(_NON_SOFTWARE)


def _matches(pattern: re.Pattern[str], text: str, base: int, raw: bytes) -> list[tuple[int, int, str]]:
    out = []
    for m in pattern.finditer(text):
        start = base + len(text[: m.start()].encode("utf-8"))
        end = base + len(text[: m.end()].encode("utf-8"))
        out.append((start, end, raw[start:end].decode("utf-8")))
    return out


def classify(prompt: bytes, document_ref: str) -> dict[str, Any]:
    text = prompt.decode("utf-8")
    strong = _matches(_RE_STRONG, text, 0, prompt)
    weak = _matches(_RE_WEAK, text, 0, prompt)
    non = _matches(_RE_NON, text, 0, prompt)
    sw = 2 * len(strong) + len(weak)
    ns = 2 * len(non)
    if sw >= 3 and sw >= 2 * ns:
        decision = "SOFTWARE"
    elif ns >= 2 and sw <= 1:
        decision = "NON_SOFTWARE"
    else:
        decision = "UNCERTAIN"
    reason = (
        f"lexical score software={sw} (strong={len(strong)}, weak={len(weak)}), "
        f"non_software={ns}; decision rule: SOFTWARE if software>=3 and software>=2*non_software, "
        f"NON_SOFTWARE if non_software>=2 and software<=1, otherwise UNCERTAIN"
    )
    seg_out = []
    for a, b in segments(prompt):
        chunk = prompt[a:b].decode("utf-8")
        s_sw = 2 * len(_RE_STRONG.findall(chunk)) + len(_RE_WEAK.findall(chunk))
        s_ns = 2 * len(_RE_NON.findall(chunk))
        label = "software" if s_sw > s_ns and s_sw > 0 else ("non_software" if s_ns > s_sw else "neutral")
        seg_out.append({"start_byte": a, "end_byte": b, "label": label})
    support = (non if decision == "NON_SOFTWARE" else strong + weak)
    support.sort()
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "routing",
        "classifier": CLASSIFIER_ID,
        "document_ref": document_ref,
        "document_hash": canonical.digest(prompt),
        "mode": "auto",
        "decision": decision,
        "routing_result": "NOT_APPLICABLE" if decision == "NON_SOFTWARE" else ("AMBIGUOUS" if decision == "UNCERTAIN" else "OBLIGATION_PIPELINE"),
        "reason": reason,
        "supporting_spans": [{"start_byte": a, "end_byte": b, "text": t} for a, b, t in support[:32]],
        "segments": seg_out,
        "confidence_is_evidence": False,
    }


def forced_software(prompt: bytes, document_ref: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": "routing",
        "classifier": "none (mode=software bypasses classification)",
        "document_ref": document_ref,
        "document_hash": canonical.digest(prompt),
        "mode": "software",
        "decision": "SOFTWARE",
        "routing_result": "OBLIGATION_PIPELINE",
        "reason": "--mode software bypasses classification by explicit user choice",
        "supporting_spans": [],
        "segments": [{"start_byte": a, "end_byte": b, "label": "software"} for a, b in segments(prompt)],
        "confidence_is_evidence": False,
    }
