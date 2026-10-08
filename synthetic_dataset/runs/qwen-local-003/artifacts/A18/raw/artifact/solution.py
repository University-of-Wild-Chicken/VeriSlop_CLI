from fractions import Fraction

def solve(data):
    ops = data.get("operations", [])
    values = {}
    results = []
    for op in ops:
        if op[0] == "add":
            _, ident, val = op
            values[ident] = val
        elif op[0] == "remove":
            ident = op[1]
            if ident in values:
                del values[ident]
        elif op[0] == "median":
            if not values:
                results.append(None)
            else:
                vals = sorted(values.values())
                n = len(vals)
                if n % 2 == 1:
                    med = Fraction(vals[n // 2], 1)
                else:
                    med = Fraction(vals[n // 2 - 1] + vals[n // 2], 2)
                results.append([med.numerator, med.denominator])
    return results
