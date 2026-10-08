from fractions import Fraction


def solve(data):
    values = {}
    results = []
    for operation in data["operations"]:
        kind = operation[0]
        if kind == "add":
            values[operation[1]] = operation[2]
        elif kind == "remove":
            values.pop(operation[1], None)
        elif kind == "median":
            ordered = sorted(values.values())
            size = len(ordered)
            if size == 0:
                results.append(None)
            elif size % 2:
                results.append([ordered[size // 2], 1])
            else:
                median = Fraction(ordered[size // 2 - 1] + ordered[size // 2], 2)
                results.append([median.numerator, median.denominator])
    return results
