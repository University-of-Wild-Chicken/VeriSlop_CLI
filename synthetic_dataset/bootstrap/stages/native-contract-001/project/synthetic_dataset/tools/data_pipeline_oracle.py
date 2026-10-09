"""Independent, finite request oracles; never imported by the CLI or model agents."""
from __future__ import annotations

import random
import json
from typing import Any

TASKS = ("P01-numeric-batch", "P02-row-projection", "P03-unicode-labels")
SEED = 20261008
CASE_COUNT = 160
TEXTS = ("", " ", "\t", "café", "cafe\u0301", "東京", "🐈", "a\x00b", "x", "x\ny", "ß", "\U0010ffff")
NUMBERS = (0, 1, -1, 2, -2, 17, -17, 2**63, -(2**63), 2**128 + 1, -(2**128 + 1))


def expected(task: str, data: dict[str, Any]) -> dict[str, Any]:
    # Deliberately imperative request definitions, independent of Lean evaluation.
    if task == TASKS[0]:
        output, total, count = [], 0, 0
        for value in data["values"]:
            if value >= data["minimum"]:
                transformed = value * data["factor"]
                output.append(transformed)
                total += transformed
                count += 1
        return {"values": output, "total": total, "count": count}
    if task == TASKS[1]:
        output, total, count = [], 0, 0
        for row in data["rows"]:
            if row["enabled"] is True and row["amount"] >= data["minimum"]:
                output.append({"tag": row["tag"], "amount": row["amount"]})
                total += row["amount"]
                count += 1
        return {"rows": output, "total": total, "count": count}
    if task == TASKS[2]:
        output, count = [], 0
        for label in data["labels"]:
            if label != "":
                output.append(data["prefix"] + label)
                count += 1
        return {"labels": output, "count": count}
    raise ValueError("Unknown preregistered task")


def wire(value: Any) -> dict[str, Any]:
    if type(value) is bool:
        return {"bool": value}
    if type(value) is int:
        return {"int": str(value)}
    if type(value) is str:
        return {"str": value}
    if type(value) is list:
        return {"list": [wire(item) for item in value]}
    if type(value) is dict:
        return {"dict": {key: wire(item) for key, item in value.items()}}
    raise TypeError("Oracle value is outside the fixed JSON data domain")


def cases(task: str) -> list[dict[str, Any]]:
    rng = random.Random(SEED + TASKS.index(task))
    data = []
    if task == TASKS[0]:
        for minimum in (-1, 0, 1):
            for factor in (-2, 0, 3):
                for values in ([], [minimum], [minimum-1, minimum, minimum, minimum+1], list(NUMBERS)):
                    data.append({"values": values, "minimum": minimum, "factor": factor})
    elif task == TASKS[1]:
        for minimum in (-1, 0, 1):
            data.append({"rows": [], "minimum": minimum})
            for enabled in (False, True):
                rows = [{"tag": tag, "amount": amount, "enabled": enabled}
                        for tag, amount in zip(TEXTS, (*NUMBERS, 0))]
                data.append({"rows": rows + rows[:2], "minimum": minimum})
    else:
        for prefix in TEXTS:
            for labels in ([], [""], ["", " ", "", "x", "x"], list(TEXTS)):
                data.append({"labels": labels, "prefix": prefix})
    seen = {json.dumps(row, sort_keys=True, ensure_ascii=False) for row in data}
    while len(data) < CASE_COUNT:
        size = rng.randrange(0, 25)
        number = lambda: rng.choice(NUMBERS) if rng.randrange(2) else rng.randrange(-10000, 10001)
        if task == TASKS[0]:
            row = {"values": [number() for _ in range(size)], "minimum": number(), "factor": number()}
        elif task == TASKS[1]:
            row = {"rows": [{"tag": rng.choice(TEXTS), "amount": number(), "enabled": bool(rng.randrange(2))}
                           for _ in range(size)], "minimum": number()}
        else:
            row = {"labels": [rng.choice(TEXTS) for _ in range(size)], "prefix": rng.choice(TEXTS)}
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            data.append(row)
    return [{"case_id": f"C{i:03}", "input_wire": wire(row), "expected_wire": wire(expected(task, row))}
            for i, row in enumerate(data)]
