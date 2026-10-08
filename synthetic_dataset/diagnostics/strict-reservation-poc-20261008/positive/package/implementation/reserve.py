def reserve(balance, amount):
    if amount <= balance:
        return ("ok", balance - amount)
    return ("error", "insufficient")
