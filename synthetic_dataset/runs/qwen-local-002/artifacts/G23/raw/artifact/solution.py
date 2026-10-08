import math

def solve(data):
    capacity = data["capacity"]
    period = data["period"]
    rate = data["rate"]
    requests = data["requests"]

    # Balance is represented as an integer number of tokens * period.
    # Initial bucket is full at time 0.
    balance = capacity * period
    last_time = 0
    accepted = []
    balances = []

    for at, amount in requests:
        # Refill from last_time to at
        # Refill amount in tokens*period units = rate * (at - last_time)
        # because rate tokens per period => rate * (delta_time / period) tokens
        # tokens*period = rate * delta_time
        delta = at - last_time
        if delta > 0:
            balance += rate * delta
            # Cap at capacity * period
            if balance > capacity * period:
                balance = capacity * period
        last_time = at

        # Check if enough tokens: balance >= amount * period
        if balance >= amount * period:
            balance -= amount * period
            accepted.append(True)
        else:
            accepted.append(False)
        balances.append(balance)

    return {
        "accepted": accepted,
        "balances": balances,
        "denominator": period
    }