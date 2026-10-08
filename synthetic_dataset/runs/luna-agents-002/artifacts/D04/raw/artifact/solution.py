import re
from functools import cmp_to_key

_SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)


def _parse(version):
    if not isinstance(version, str):
        return None
    match = _SEMVER.fullmatch(version)
    if match is None:
        return None

    major, minor, patch = (int(match.group(i)) for i in range(1, 4))
    prerelease_text = match.group(4)
    prerelease = None
    if prerelease_text is not None:
        prerelease = []
        for identifier in prerelease_text.split("."):
            if re.fullmatch(r"[0-9]+", identifier):
                if len(identifier) > 1 and identifier[0] == "0":
                    return None
                prerelease.append((0, int(identifier)))
            else:
                prerelease.append((1, identifier))
    return (major, minor, patch, prerelease)


def _compare_identifiers(left, right):
    for a, b in zip(left, right):
        if a[0] != b[0]:
            return -1 if a[0] == 0 else 1
        if a[1] != b[1]:
            return -1 if a[1] < b[1] else 1
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def _compare(left, right):
    for a, b in zip(left[:3], right[:3]):
        if a != b:
            return -1 if a < b else 1

    left_pre, right_pre = left[3], right[3]
    if left_pre is None:
        return 0 if right_pre is None else 1
    if right_pre is None:
        return -1
    return _compare_identifiers(left_pre, right_pre)


def solve(data):
    parsed_clauses = []
    for clause in data["clauses"]:
        parsed = []
        prerelease_cores = set()
        for comparator in clause:
            version = _parse(comparator["version"])
            # Comparator versions are guaranteed valid by the input contract.
            parsed.append((comparator["op"], version))
            if version[3] is not None:
                prerelease_cores.add(version[:3])
        parsed_clauses.append((parsed, prerelease_cores))

    accepted = []
    invalid = []
    for index, original in enumerate(data["versions"]):
        candidate = _parse(original)
        if candidate is None:
            invalid.append(index)
            continue

        matched = False
        for clause, prerelease_cores in parsed_clauses:
            if candidate[3] is not None and candidate[:3] not in prerelease_cores:
                continue

            clause_matches = True
            for op, comparator_version in clause:
                comparison = _compare(candidate, comparator_version)
                if op == "=" and comparison != 0:
                    clause_matches = False
                elif op == "<" and comparison >= 0:
                    clause_matches = False
                elif op == "<=" and comparison > 0:
                    clause_matches = False
                elif op == ">" and comparison <= 0:
                    clause_matches = False
                elif op == ">=" and comparison < 0:
                    clause_matches = False
                if not clause_matches:
                    break

            if clause_matches:
                matched = True
                break

        if matched:
            accepted.append((original, candidate))

    accepted.sort(key=cmp_to_key(lambda a, b: _compare(a[1], b[1])))
    return {"accepted": [original for original, _ in accepted], "invalid": invalid}
