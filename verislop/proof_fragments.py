"""Conservative proof-body insertion; frozen Lean scaffold is never model-authored.

This is a deliberately restricted lexical protocol, not a general Lean parser.
Unsupported declaration layouts are rejected. Ordinary Lean acceptance remains
the authority for the assembled candidate's meaning and proof validity.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

from . import canonical, fsutil, leanbridge, sandbox
from .errors import Diagnostic, InfrastructureError


class FragmentError(ValueError):
    def __init__(self, message: str, response: str = ""):
        super().__init__(message)
        self.response = response


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    line: int
    column: int
    first: bool


COMMANDS = frozenset({
    "import", "namespace", "end", "section", "theorem", "lemma", "example",
    "def", "abbrev", "opaque", "axiom", "constant", "instance", "structure",
    "inductive", "class", "variable", "variables", "universe", "universes",
    "open", "export", "attribute", "set_option", "syntax", "macro", "elab",
    "notation", "infix", "infixl", "infixr", "prefix", "postfix", "mutual",
    "private", "protected", "noncomputable", "unsafe", "local", "scoped",
    "initialize", "builtin_initialize", "deriving", "declare_syntax_cat", "#",
    "@", "include", "omit", "macro_rules", "elab_rules", "run_cmd",
    "register_option", "simproc", "builtin_simproc", "def_simproc",
})
PAIRS = {"(": ")", "[": "]", "{": "}", "⦃": "⦄"}
SYNTAX_HELPER = Path(__file__).resolve().parent / "lean" / "VeriSlopProofSyntax.lean"


def _syntax_failure(message: str) -> InfrastructureError:
    return InfrastructureError(message, [Diagnostic("VERIFIER_FAILURE", message, severity="infrastructure")])


@lru_cache(maxsize=64)
def _parse_terms(terms: tuple[str, ...], helper_sha256: str, toolchain_pin: str, lean_sha256: str) -> None:
    """Independent syntax boundary; never elaborate or execute candidate text."""
    tc = leanbridge.resolve_toolchain(toolchain_pin)
    if tc.identity()["lean_binary_sha256"] != lean_sha256:
        raise _syntax_failure("proof syntax toolchain changed during validation")
    helper = SYNTAX_HELPER.read_bytes()
    if canonical.digest(helper) != helper_sha256:
        raise _syntax_failure("proof syntax helper changed during validation")
    with fsutil.temporary_directory(prefix="verislop-proof-syntax-") as tmp:
        root = Path(tmp)
        (root / "VeriSlopProofSyntax.lean").write_bytes(helper)
        fsutil.write_json(root / "request.json", {"terms": list(terms)})
        try:
            result = sandbox.run([str(tc.lean), "-j1", "-M2048", "--run", "VeriSlopProofSyntax.lean",
                                  "request.json", "response.json"], root, timeout=30,
                                 memory_mb=2048 + leanbridge.LEAN_AS_HEADROOM_MB, cpu_seconds=35,
                                 require_network_isolation=True, read_only_paths=[tc.prefix],
                                 env_extra={"PATH": f"{tc.prefix / 'bin'}:/usr/bin:/bin"})
        except RuntimeError as exc:
            raise _syntax_failure(f"proof syntax helper infrastructure failed: {exc}") from None
        if result.timed_out or result.returncode != 0 or not (root / "response.json").is_file():
            raise _syntax_failure("proof syntax helper failed: " + result.stdout.decode("utf-8", "replace")[:1000]
                                  + result.stderr.decode("utf-8", "replace")[:1000])
        try:
            output = canonical.load_file(root / "response.json")
            rows = output["results"]
            if output["format"] != "verislop.proof-term-syntax/0.1" or len(rows) != len(terms):
                raise ValueError("mismatched syntax result binding")
            for row in rows:
                if row.get("ok") is False:
                    raise FragmentError("proof body is not exactly one Lean term: " + row["error"])
                if row != {"ok": True}:
                    raise ValueError("invalid syntax result")
        except (KeyError, TypeError, ValueError, canonical.CanonicalJSONError) as exc:
            if isinstance(exc, FragmentError):
                raise
            raise _syntax_failure(f"proof syntax helper returned an invalid result: {type(exc).__name__}") from None


def validate_terms(terms: list[str], toolchain_pin: str = leanbridge.DEFAULT_TOOLCHAIN) -> None:
    tc = leanbridge.resolve_toolchain(toolchain_pin)
    _parse_terms(tuple(terms), canonical.digest(SYNTAX_HELPER.read_bytes()), toolchain_pin,
                 tc.identity()["lean_binary_sha256"])


def lex(source: str) -> list[Token]:
    tokens: list[Token] = []
    i, line, line_start = 0, 1, 0
    last_line = 0

    def advance(end: int) -> None:
        nonlocal i, line, line_start
        chunk = source[i:end]
        line += chunk.count("\n")
        if "\n" in chunk:
            line_start = i + chunk.rfind("\n") + 1
        i = end

    while i < len(source):
        if source[i].isspace():
            advance(i + 1)
            continue
        if source.startswith("--", i):
            end = source.find("\n", i)
            advance(len(source) if end < 0 else end)
            continue
        if source.startswith("/-", i):
            depth, end = 1, i + 2
            while end < len(source) and depth:
                if source.startswith("/-", end):
                    depth, end = depth + 1, end + 2
                elif source.startswith("-/", end):
                    depth, end = depth - 1, end + 2
                else:
                    end += 1
            if depth:
                raise FragmentError("unterminated Lean block comment")
            advance(end)
            continue
        start, start_line, column = i, line, i - line_start
        char = source[i]
        if char == 'r' and i + 1 < len(source) and source[i + 1] in {'#', '"'}:
            raise FragmentError("raw Lean strings are outside the fragment protocol")
        if char in {'"', '«', "'"}:
            close = '»' if char == '«' else char
            end = i + 1
            while end < len(source) and source[end] != close:
                if source[end] == "\\" and char != '«':
                    end += 2
                else:
                    end += 1
            if end >= len(source):
                raise FragmentError("unterminated Lean literal or quoted identifier")
            end += 1
        elif char.isalpha() or char == "_":
            end = i + 1
            while end < len(source) and (source[end].isalnum() or source[end] in "_'!?"):
                end += 1
        elif char.isdigit():
            end = i + 1
            while end < len(source) and source[end].isdigit():
                end += 1
        elif source.startswith(":=", i) or source.startswith("=>", i) or source.startswith("->", i):
            end = i + 2
        else:
            end = i + 1
        tokens.append(Token(source[start:end], start, end, start_line, column, last_line != start_line))
        last_line = start_line
        advance(end)
    return tokens


@dataclass(frozen=True)
class Theorem:
    name: str
    header: tuple[str, ...]
    header_text: str
    start: int
    body_start: int
    body_end: int
    hole: bool


def _identifier(token: str) -> bool:
    return ((token.startswith('«') and token.endswith('»')) or
            (bool(token) and (token[0].isalpha() or token[0] == "_") and
             all(c.isalnum() or c in "_'!?" for c in token)))


def declarations(source: str) -> list[Theorem]:
    tokens = lex(source)
    result: list[Theorem] = []
    for index, token in enumerate(tokens):
        if token.text not in {"theorem", "lemma"}:
            continue
        if not token.first:
            raise FragmentError("theorem command must start its own line without modifiers")
        if index + 1 >= len(tokens) or not _identifier(tokens[index + 1].text):
            raise FragmentError("fragment requires an explicitly named theorem")
        cursor = index + 2
        name_parts = [tokens[index + 1].text]
        while cursor + 1 < len(tokens) and tokens[cursor].text == "." and _identifier(tokens[cursor + 1].text):
            name_parts.extend([".", tokens[cursor + 1].text])
            cursor += 2
        stack: list[str] = []
        assignment = None
        while cursor < len(tokens):
            part = tokens[cursor]
            if part.text in {"let", "where", "with"}:
                raise FragmentError("unsupported theorem header syntax")
            if part.text == ":=" and not stack:
                assignment = cursor
                break
            if part.text in PAIRS:
                stack.append(PAIRS[part.text])
            elif part.text in PAIRS.values():
                if not stack or stack.pop() != part.text:
                    raise FragmentError("unbalanced theorem header")
            if part.first and part.column <= token.column and part.text in COMMANDS:
                raise FragmentError("theorem header lacks a supported := proof assignment")
            cursor += 1
        if assignment is None or ":" not in [t.text for t in tokens[index:assignment]]:
            raise FragmentError("theorem header lacks an explicit proposition")
        body_start = tokens[assignment].end
        body_end = None
        body_tokens = []
        for following in tokens[assignment + 1:]:
            if following.first and following.column <= token.column and following.text in COMMANDS:
                break
            if following.first and following.line > tokens[assignment].line and following.column <= token.column:
                raise FragmentError("unsupported unindented command or proof syntax after theorem assignment")
            body_end = following.end
            body_tokens.append(following.text)
        if not body_tokens:
            raise FragmentError("empty theorem proof body")
        result.append(Theorem("".join(name_parts), tuple(t.text for t in tokens[index:assignment]),
                              source[token.start:tokens[assignment].start], token.start,
                              body_start, body_end, "sorry" in body_tokens))
    names = [t.name for t in result]
    if len(names) != len(set(names)):
        raise FragmentError("ambiguous or duplicate theorem names in the frozen source")
    return result


def _selected(frozen_decls: list[Theorem], selected_names: list[str] | None) -> set[str]:
    eligible = {t.name for t in frozen_decls if t.hole}
    if selected_names is None:
        return eligible
    if (not isinstance(selected_names, list) or not selected_names
            or any(not isinstance(name, str) for name in selected_names)
            or len(set(selected_names)) != len(selected_names) or not set(selected_names) <= eligible):
        raise FragmentError("proof focus names must be a nonempty subset of frozen theorem holes")
    return set(selected_names)


def expected_headers(frozen: str, selected_names: list[str] | None = None) -> list[str]:
    decls = _frozen_declarations(frozen)
    selected = _selected(decls, selected_names)
    return [t.header_text + ":=" for t in decls if t.name in selected]


def _frozen_declarations(frozen: str) -> list[Theorem]:
    forbidden = {"macro", "macro_rules", "elab", "elab_rules", "syntax", "notation", "run_cmd", "#"}
    if any(token.text in forbidden for token in lex(frozen)):
        raise FragmentError("custom syntax, metaprogramming and command evaluation are outside the fragment protocol")
    theorems = declarations(frozen)
    for theorem in theorems:
        if theorem.hole:
            body = tuple(t.text for t in lex(frozen[theorem.body_start:theorem.body_end]))
            if body not in {("by", "sorry"), ("sorry",)}:
                raise FragmentError("fragment-eligible frozen theorems require a sole sorry proof hole")
    return theorems


def validate_previous(previous: str, frozen: str, toolchain_pin: str = leanbridge.DEFAULT_TOOLCHAIN) -> None:
    frozen_decls = _frozen_declarations(frozen)
    expected = {t.name for t in frozen_decls if t.hole}
    prior_decls = declarations(previous)
    if ([(t.name, t.header) for t in prior_decls] != [(t.name, t.header) for t in frozen_decls]
            or _masked(previous, prior_decls, expected) != _masked(frozen, frozen_decls, expected)):
        raise FragmentError("previous candidate does not preserve the exact frozen scaffold and headers")
    validate_terms([previous[t.body_start:t.body_end] for t in prior_decls if t.name in expected], toolchain_pin)


def _masked(source: str, theorems: list[Theorem], expected: set[str]) -> str:
    for theorem in reversed(theorems):
        if theorem.name in expected:
            source = source[:theorem.body_start] + "<VERISLOP_PROOF_BODY>" + source[theorem.body_end:]
    return source


def validate_focused_candidate(candidate: str, frozen: str, baseline: str,
                               selected_names: list[str],
                               toolchain_pin: str = leanbridge.DEFAULT_TOOLCHAIN) -> None:
    """Full-file proposals cannot rewrite proofs outside the exact dispatch."""
    selected = _selected(_frozen_declarations(frozen), selected_names)
    validate_previous(baseline, frozen, toolchain_pin)
    validate_previous(candidate, frozen, toolchain_pin)
    if (_masked(candidate, declarations(candidate), selected)
            != _masked(baseline, declarations(baseline), selected)):
        raise FragmentError("focused full-file proposal changed bytes outside selected proof bodies", candidate)


def assemble(response: str, frozen: str, previous: str | None = None,
             *, toolchain_pin: str = leanbridge.DEFAULT_TOOLCHAIN,
             selected_names: list[str] | None = None) -> str:
    """Insert exact submitted proof bytes only; fail closed on unsupported syntax."""
    try:
        submitted = response.strip()
        fenced = re.fullmatch(r"```lean\s*\n(.*?)\n?```", submitted, re.S)
        if fenced:
            submitted = fenced.group(1)
        frozen_decls = _frozen_declarations(frozen)
        selected = _selected(frozen_decls, selected_names)
        expected = {t.name: t for t in frozen_decls if t.name in selected}
        if not expected:
            raise FragmentError("frozen source has no supported theorem holes")
        base = frozen
        if previous is not None:
            validate_previous(previous, frozen, toolchain_pin)
            base = previous
        proposed = declarations(submitted)
        if not proposed:
            raise FragmentError("response contains no supported theorem command")
        # A token's spelling does not determine whether it is a command: `@`
        # is also explicit application, and `open ... in` can occur in a term.
        # Headers are matched exactly below and proof bodies are parsed through
        # EOF by Lean. Only tokens outside those declaration spans are extra.
        for token in lex(submitted):
            if not any(theorem.start <= token.start < theorem.body_end for theorem in proposed):
                raise FragmentError(f"extra or unsupported command in theorem fragment: {token.text}")
        if lex(submitted)[0].start != proposed[0].start:
            raise FragmentError("response contains text before its first theorem command")
        bodies = {}
        for theorem in proposed:
            if theorem.name not in expected or theorem.header != expected[theorem.name].header:
                raise FragmentError(f"fragment header does not match a frozen theorem: {theorem.name}")
            bodies[theorem.name] = submitted[theorem.body_start:theorem.body_end]
        validate_terms(list(bodies.values()), toolchain_pin)
        base_decls = declarations(base)
        for theorem in reversed(base_decls):
            if theorem.name in bodies:
                body = bodies[theorem.name]
                base = base[:theorem.body_start] + body + base[theorem.body_end:]
        return base
    except FragmentError as exc:
        exc.response = response
        raise
