"""Closed restricted-source authoring and accepted-AST reconstruction.

The Lean algebra proves transfer/inhabitation of an abstract source-fact model.
The VSCore3 exact semantic source discharge is a separate kernel-checked bridge.
Neither author JSON nor this descriptor parser produces a source-check PASS.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any

from . import canonical, dsl, reify
from .exprjson import app, canon, const, constants, head_const, name_str

ENCODING = "verislop.source-contract-facets/0.1"
MODEL_VERSION = "verislop.source-boundary/0.1"
NS = "VeriSlop.Source"
MODEL_PATH = Path(__file__).parent / "lean" / "SourceBoundary.lean"
TAGS = {"entry": "entry", "typed_total": "typedTotal", "pure_data": "pureData", "restricted_runtime_only": "restrictedRuntimeOnly",
        "no_external_io": "noExternalIO", "input_preserved": "inputPreserved", "deterministic": "deterministic",
        "no_floating_point": "noFloatingPoint"}
REVERSE_TAGS = {v: k for k, v in TAGS.items()}
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ENTRY_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,127}$")
MAX_REQUIREMENTS = 32
MAX_SOURCE_FACETS = 32


class SourceError(ValueError):
    pass


def library_source() -> bytes:
    return MODEL_PATH.read_bytes()


def model_source_hash() -> str:
    return canonical.digest(library_source())


def validate_requirements(rows: Any, *, arity: int | None = None) -> list[dict]:
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_REQUIREMENTS:
        raise SourceError(f"source requirements must contain 1..{MAX_REQUIREMENTS} closed constructors")
    tags = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("tag"), str) or row["tag"] not in TAGS:
            raise SourceError("unknown source requirement constructor")
        tag = row["tag"]
        if tag in tags:
            raise SourceError(f"duplicate source requirement {tag}")
        tags.add(tag)
        if set(row) != ({"tag", "file", "entry", "arity"} if tag == "entry" else {"tag"}):
            raise SourceError(f"{tag}: only closed requirement parameters are permitted")
        if tag == "entry":
            f, q, a = row["file"], row["entry"], row["arity"]
            if f != "program.vscore.json":
                raise SourceError("source entry file must be exactly program.vscore.json")
            if not isinstance(q, str) or not ENTRY_IDENT.fullmatch(q):
                raise SourceError("source entry must be a valid VSCore identifier")
            if type(a) is not int or a < 0 or arity is not None and a != arity:
                raise SourceError("entry arity must equal the nonnegative accepted endpoint signature")
    return rows


def validate_definitions(definitions: Any, symbols: dict) -> dict:
    if not isinstance(definitions, dict) or len(definitions) > MAX_SOURCE_FACETS:
        raise SourceError("source_requirements must be a bounded declaration map")
    for name, row in definitions.items():
        if not isinstance(name, str) or not IDENT.fullmatch(name) or name.startswith("_vs_"):
            raise SourceError("source requirement definition must have an ordinary local identifier")
        if not isinstance(row, dict) or set(row) != {"symbol", "requirements"}:
            raise SourceError("source definition requires exactly symbol and requirements")
        if not isinstance(row["symbol"], str) or row["symbol"] not in symbols:
            raise SourceError("source endpoint must identify an actual supplied typed symbol")
        validate_requirements(row["requirements"], arity=len(symbols[row["symbol"]]["args"]))
    return definitions


def render_requirements(rows: list[dict], string_literal) -> str:
    def one(row):
        base = f"_root_.{NS}.SourceRequirement.{TAGS[row['tag']]}"
        if row["tag"] == "entry":
            return f"({base} {string_literal(row['file'])} {string_literal(row['entry'])} {row['arity']})"
        return base
    return "[" + ", ".join(one(r) for r in rows) + "]"


def source_prop(definition: str, endpoint_type: dict) -> dict:
    return app(const(NS + ".Contract"), endpoint_type, const(definition))


def value_package(package: dict) -> dict | None:
    return package.get("value") if package.get("encoding") == ENCODING else package


def source_facets(package: dict) -> list[dict]:
    return package.get("source", []) if package.get("encoding") == ENCODING else []


def statement_value_package(statement: dict) -> dict | None:
    """Executable value surface only; source-only and opaque statements have none."""
    if statement.get("representation") not in ("contract_dsl", "source_facets"):
        return None
    return value_package(statement.get("formula_package", {}))


def symbols(package: dict) -> set[str]:
    return {row["symbol"] for row in source_facets(package)}


@lru_cache(maxsize=4)
def _expected_model_hashes(pin: str, source_hash: str) -> dict[str, str]:
    """Independently compile/replay the pinned library; candidate definitions are never the pin."""
    from . import fsutil, leanbridge
    from .exprjson import decl_hash
    if model_source_hash() != source_hash:
        raise SourceError("source model changed during pinning")
    tc = leanbridge.resolve_toolchain(pin)
    with fsutil.temporary_directory(prefix="verislop-source-model-") as tmp:
        result = leanbridge.compile_module(tc, library_source(), Path(tmp))
        if not result.ok or result.sorry_positions or result.olean is None:
            raise SourceError("normative source model failed compilation: " + "; ".join(result.errors))
        response = leanbridge.run_kernel_tool(tc, result.olean, {"export": True, "axioms": True})
        if not response.get("replay", {}).get("ok") or not response.get("import", {}).get("ok"):
            raise SourceError("normative source model failed independent kernel replay")
        out = {name_str(c["name"]): decl_hash(c) for c in response.get("constants", [])
               if name_str(c["name"]).startswith(NS + ".") and "export_error" not in c
               and c.get("kind") != "missing_after_replay"}
        if NS + ".Contract" not in out or NS + ".contract_sound" not in out:
            raise SourceError("normative source model export is incomplete")
        return out


def verify_model(decls: dict, hashes: dict, pin: str) -> None:
    expected = _expected_model_hashes(pin, model_source_hash())
    if any(hashes.get(name) != digest for name, digest in expected.items()):
        raise SourceError("source model declarations differ from the independently replayed normative library")
    if {n for n in decls if n.startswith(NS + ".")} != set(expected):
        raise SourceError("source model namespace contains undeclared or missing definitions")


def _literal(expr: dict, key: str):
    if set(expr) == {"lit"} and set(expr["lit"]) == {key}:
        if key == "nat" and isinstance(expr["lit"][key], str) and expr["lit"][key].isdigit():
            return int(expr["lit"][key])
        if key == "str" and isinstance(expr["lit"][key], str):
            return expr["lit"][key]
    n, args = head_const(expr)
    if key == "nat" and n == "OfNat.ofNat" and len(args) == 3 and args[0] == const("Nat"):
        numeral = _literal(args[1], "nat")
        if head_const(args[2]) == ("instOfNatNat", [args[1]]):
            return numeral
    raise SourceError("source requirement parameter is not a closed literal")


def _decode_list(expr: dict) -> list[dict]:
    rows = []
    for _ in range(MAX_REQUIREMENTS + 1):
        n, args = head_const(expr)
        if n == "List.nil" and len(args) == 1 and args[0] == const(NS + ".SourceRequirement"):
            return validate_requirements(rows)
        if n != "List.cons" or len(args) != 3 or args[0] != const(NS + ".SourceRequirement"):
            raise SourceError("source requirements must be a closed constructor list")
        ctor, fields = head_const(args[1])
        tag = REVERSE_TAGS.get(ctor.removeprefix(NS + ".SourceRequirement.")) if ctor else None
        if tag is None or ctor != NS + ".SourceRequirement." + TAGS[tag]:
            raise SourceError("source requirement uses an unknown constructor")
        if tag == "entry" and len(fields) == 3:
            rows.append({"tag": tag, "file": _literal(fields[0], "str"), "entry": _literal(fields[1], "str"),
                         "arity": _literal(fields[2], "nat")})
        elif tag != "entry" and not fields:
            rows.append({"tag": tag})
        else:
            raise SourceError("source requirement constructor has incorrect parameter arity")
        expr = args[2]
    raise SourceError("source requirement list exceeds its bound")


def _decode_contract(expr: dict, profile: dsl.Profile, decls: dict, hashes: dict) -> dict:
    n, args = head_const(expr)
    if n != NS + ".Contract" or len(args) != 2:
        raise SourceError("expected an exact source Contract application")
    endpoint_type, def_ref = args
    definition, no_args = head_const(def_ref)
    row = decls.get(definition, {})
    if (not definition or no_args or row.get("kind") != "definition" or row.get("safety") != "safe"
            or row.get("level_params") or canon(row.get("type", {}), []) != canon(app(const(NS + ".SourceDefinition"), endpoint_type), [])):
        raise SourceError("source contract requires one safe closed SourceDefinition constant")
    ctor, fields = head_const(row.get("value", {}))
    if ctor != NS + ".SourceDefinition.mk" or len(fields) != 3 or canon(fields[0], []) != canon(endpoint_type, []):
        raise SourceError("source definition must contain the exact closed constructor")
    lean_decl, endpoint_args = head_const(fields[1])
    matches = [(sid, s) for sid, s in profile.symbols.items() if s["lean_decl"] == lean_decl]
    if endpoint_args or len(matches) != 1 or fields[1] != const(lean_decl):
        raise SourceError("source endpoint must be the actual accepted monomorphic data-function constant")
    sid, symbol = matches[0]
    if canon(decls[lean_decl]["type"], []) != canon(endpoint_type, []):
        raise SourceError("source endpoint type differs from its accepted declaration")
    requirements = validate_requirements(_decode_list(fields[2]), arity=len(symbol["args"]))
    return {"requirement_id": definition.rsplit(".", 1)[-1], "definition": definition,
            "definition_hash": hashes[definition], "symbol": sid, "lean_decl": lean_decl,
            "decl_hash": hashes[lean_decl], "requirements": requirements,
            "model_version": MODEL_VERSION, "model_source_hash": model_source_hash()}


def _source_tree(expr: dict, profile: dsl.Profile, decls: dict, hashes: dict) -> list[dict]:
    # A bounded, canonical right-associated conjunction; no optional source facets.
    rows = []
    for _ in range(MAX_SOURCE_FACETS):
        n, args = head_const(expr)
        if n == "And" and len(args) == 2:
            rows.append(_decode_contract(args[0], profile, decls, hashes))
            expr = args[1]
        else:
            rows.append(_decode_contract(expr, profile, decls, hashes))
            return rows
    raise SourceError("source facet conjunction exceeds its bound")


def reify_contract(type_expr: dict, profile: dsl.Profile, decls: dict, hashes: dict, *, pin: str,
                   theorem: str, binding: dict) -> tuple[dict | None, set[str], list[dict], set[str]]:
    """Decode only accepted constructor AST. Return package, unfoldings, kernel checks, added roots."""
    if NS + ".Contract" not in constants(type_expr):
        if binding.get("source_requirements") or binding.get("value_projection"):
            raise SourceError("source facet bindings do not occur in the accepted theorem type")
        return None, set(), [], set()
    verify_model(decls, hashes, pin)
    formula, unfolded, value_expr = None, set(), None
    try:
        source = _source_tree(type_expr, profile, decls, hashes)
    except SourceError:
        n, args = head_const(type_expr)
        if n != "And" or len(args) != 2:
            raise SourceError("source facets must be an unconditional exact top-level conjunction") from None
        source = _source_tree(args[1], profile, decls, hashes)
        value_expr = args[0]
        formula, why, unfolded = reify.reify_formula(value_expr, profile, decls)
        if formula is None:
            raise SourceError("mixed contract value facet is not executable: " + why)
    defs = [r["definition"] for r in source]
    if len(defs) != len(set(defs)):
        raise SourceError("source requirement definition is repeated in one guarantee")
    if binding.get("source_requirements") != defs:
        raise SourceError("explicit source facet bindings differ from the exact accepted conjunction")
    package = {"encoding": ENCODING, "semantic_profile": profile.profile_id,
               "value": dsl.make_package(formula, profile.profile_id, encoding=profile.encoding) if formula else None,
               "source": source, "value_projection": None}
    checks, roots = [], set(defs)
    projection = binding.get("value_projection")
    if formula is not None:
        info = decls.get(projection, {}) if isinstance(projection, str) else {}
        if (info.get("kind") != "theorem" or info.get("safety") != "safe" or info.get("level_params")
                or theorem not in {name_str(x) for x in info.get("value_constants", [])}):
            raise SourceError("mixed guarantee needs a kernel-replayed value projection depending on its original theorem")
        package["value_projection"] = {"lean_symbol": projection, "decl_hash": hashes[projection],
                                       "source_theorem": theorem, "projection": "left"}
        checks.append({"id": "value:" + theorem, "theorem": info["name"], "expr": reify.denote_formula(formula, profile)})
        roots.add(projection)
    elif projection is not None:
        raise SourceError("source-only guarantee cannot invent a value projection")
    return package, unfolded, checks, roots


def denote_package(package: dict, profile: dsl.Profile, decls: dict) -> dict:
    """Rebuild the COMPLETE theorem type; the kernel checks exact definitional equality."""
    props = [source_prop(r["definition"], decls[r["lean_decl"]]["type"]) for r in source_facets(package)]
    if not props:
        raise SourceError("source package requires at least one source facet")
    result = props[-1]
    for prop in reversed(props[:-1]):
        result = app(const("And"), prop, result)
    value = value_package(package)
    return app(const("And"), reify.denote_formula(value["formula"], profile), result) if value else result
