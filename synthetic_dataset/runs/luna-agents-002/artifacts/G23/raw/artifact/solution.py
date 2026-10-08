def solve(data):
    capacity = data["capacity"]
    period = data["period"]
    rate = data["rate"]
    requests = data["requests"]

    limit = capacity * period
    balance = limit
    previous_time = 0
    accepted = []
    balances = []

    for at, amount in requests:
        balance = min(limit, balance + (at - previous_time) * rate)
        previous_time = at

        cost = amount * period
        if balance >= cost:
            balance -= cost
            accepted.append(True)
        else:
            accepted.append(False)
        balances.append(balance)

    return {"accepted": accepted, "balances": balances, "denominator": period}
