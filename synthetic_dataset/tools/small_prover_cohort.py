"""Six fresh, proof-free inputs for the finite small-prover evaluation.

Only typed contract/source syntax is supplied here. There are deliberately no
Lean proof expressions, imported fixture helpers, expected responses, or grader
cases. The formal frontend supplies the theorem holes.
"""
from __future__ import annotations

from verislop import formal_frontend as ff


def var(index):
    return {"tag": "var", "index": index}


def lit(sort, value):
    return {"tag": sort.lower(), "value": str(value)}


def binary(tag, left, right):
    return {"tag": tag, "left": left, "right": right}


def forall(sort, body):
    return {"tag": "forall", "sort": sort, "body": body}


def call(symbol, *args):
    return {"tag": "call", "symbol": symbol, "args": list(args)}


def length(value):
    return {"tag": "list_length", "value": value}


def envelope():
    return {"encoding": ff.VERSION_V2, "enums": {}, "records": {},
            "symbols": {}, "predicates": {}, "theorems": {},
            "obligations": {}, "witness_obligations": {}}


def row(oid, kind, role, statement):
    return {"id": oid, "kind": kind, "role": role, "statement": statement,
            "required": True, "dependencies": [], "scope": ["the complete stated mathematical domain"],
            "acceptance_criteria": ["the exact frozen theorem is accepted by the pinned Lean kernel"],
            "sources": [{"quote": statement, "origin": "explicit", "interpretation": statement}]}


def single(case, request, name, args, result, body, formula):
    ast = envelope()
    ast["symbols"][name] = {"args": args, "result": result, "body": body}
    ast["theorems"]["guarantee"] = {"formula": formula}
    ast["obligations"] = {"D1": {"declarations": [{"kind": "symbol", "name": name}]},
                          "O1": {"theorem": "guarantee"}}
    return {"id": case, "request": request, "ast": ast, "obligations": [
        row("D1", "entity", "declaration", request), row("O1", "postcondition", "guarantee", request)]}


def cases():
    xs = {"list": "Int"}
    nat_body = binary("add", var(0), lit("Nat", 7))
    out = [single("nat", "For every mathematical natural n, bump(n) is n plus seven and is at least n.",
        "bump", ["Nat"], "Nat", nat_body,
        forall("Nat", binary("le", var(0), call("bump", var(0))))) ]
    int_body = binary("int_add", var(0), lit("Int", -5))
    out.append(single("int", "For every mathematical integer x, shift(x) is x minus five; adding five restores x.",
        "shift", ["Int"], "Int", int_body,
        forall("Int", binary("eq", binary("int_add", call("shift", var(0)), lit("Int", 5)), var(0)))))
    mapped = {"tag": "list_map", "value": var(0), "function": {"sort": "Int", "body":
        binary("int_add", var(0), lit("Int", 3))}}
    out.append(single("map", "For every finite list of mathematical integers, shift_all adds three to each element and preserves list length.",
        "shift_all", [xs], xs, mapped,
        forall(xs, binary("eq", length(call("shift_all", var(0))), length(var(0))))))
    filtered = {"tag": "list_filter", "value": var(0), "function": {"sort": "Int", "body":
        {"tag": "decide", "formula": binary("le", lit("Int", 0), var(0))}}}
    out.append(single("filter", "For every finite list of mathematical integers, nonnegative retains exactly the nonnegative elements; its output length is at most its input length.",
        "nonnegative", [xs], xs, filtered,
        forall(xs, binary("le", length(call("nonnegative", var(0))), length(var(0))))))
    folded = {"tag": "list_foldl", "value": var(0), "initial": lit("Nat", 0), "function": {
        "accumulator_sort": "Nat", "element_sort": "Int", "body": binary("add", var(1), lit("Nat", 1))}}
    out.append(single("fold", "For every finite list of mathematical integers, count_by_fold starts at natural zero and increments once per element; its result equals the list length.",
        "count_by_fold", [xs], "Nat", folded,
        forall(xs, binary("eq", call("count_by_fold", var(0)), length(var(0))))))
    packet, direction = {"record": "Parcel"}, {"enum": "Heading"}
    field = lambda name: {"tag": "field", "sort": "Parcel", "field": name, "value": var(0)}
    adjusted = {"tag": "record", "sort": "Parcel", "fields": [field("heading"), {"tag": "ite",
        "condition": binary("bool_eq", field("heading"), {"tag": "enum", "sort": "Heading", "constructor": "up"}),
        "then": binary("int_add", field("amount"), lit("Int", 4)),
        "else": binary("int_sub", field("amount"), lit("Int", 2))}]}
    request = ("Heading has exactly up, down, and level. Parcel has heading:Heading and amount:Int. "
        "For every Parcel, adjust preserves heading and adds four to amount for up, subtracting two otherwise. "
        "Deliver adjust in program.vscore.json with arity one, typed total evaluation, deterministic results, "
        "preserved inputs, no external I/O or floating point, pure data, and only the restricted source runtime.")
    ast = envelope()
    ast["enums"] = {"Heading": {"constructors": ["up", "down", "level"]}}
    ast["records"] = {"Parcel": {"fields": [{"name": "heading", "sort": direction}, {"name": "amount", "sort": "Int"}]}}
    ast["symbols"] = {"adjust": {"args": [packet], "result": packet, "body": adjusted}}
    properties = ["typed_total", "deterministic", "input_preserved", "no_external_io",
                  "no_floating_point", "pure_data", "restricted_runtime_only"]
    ast["source_requirements"] = {"Delivery": {"symbol": "adjust", "requirements": [
        {"tag": "entry", "file": "program.vscore.json", "entry": "adjust", "arity": 1},
        *({"tag": name} for name in properties)]}}
    ast["theorems"] = {"adjustment": {"formula": forall(packet, binary("eq", call("adjust", var(0)), adjusted)), "source": ["Delivery"]},
                       "delivery": {"source": ["Delivery"]}}
    ast["obligations"] = {"D1": {"declarations": [{"kind": "enum", "name": "Heading"},
        {"kind": "record", "name": "Parcel"}, {"kind": "symbol", "name": "adjust"}]},
        "O1": {"theorem": "adjustment"}, "S1": {"theorem": "delivery"}}
    source_field = lambda name: {"tag": "project", "value": var(0), "field": name}
    program = {"language": "vscore/0.3", "profile": "data-pipeline/0.3", "declarations": [
        {"tag": "record", "id": "Parcel", "fields": [{"id": "heading", "type": direction}, {"id": "amount", "type": "int"}]}],
        "helpers": [], "entries": [{"id": "adjust", "params": [packet], "result": packet, "body": {
            "tag": "record", "record": "Parcel", "fields": [
                {"id": "heading", "value": source_field("heading")}, {"id": "amount", "value": {
                    "tag": "if", "cond": binary("eq", source_field("heading"), {"tag": "enum", "enum": "Heading", "ctor": "up"}),
                    "then": binary("add", source_field("amount"), lit("Int", 4)),
                    "else": binary("sub", source_field("amount"), lit("Int", 2))}}]}}]}
    out.append({"id": "record-enum", "request": request, "ast": ast,
        "obligations": [row("D1", "entity", "declaration", request), row("O1", "postcondition", "guarantee", request),
                        row("S1", "safety_property", "guarantee", request)], "bridge_program": program})
    return out
