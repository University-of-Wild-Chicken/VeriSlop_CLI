def solve(x):
    if x["m"] == 0:
        return 0
    total = 0
    for i in range(x["n"]):
        total += (x["a"] * i + x["b"]) // x["m"]
    return total
