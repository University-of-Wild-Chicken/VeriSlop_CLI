import json

def solve(data):
    coins = data["coins"]
    target = data["target"]
    n = len(coins)
    if target == 0:
        return {"count": 0, "counts": [0] * n}
    if n == 0:
        return None
    # DP over coin types
    # dp[i][s] = (min_coins, counts_tuple) for first i types to make sum s
    # We'll use a list of dicts or arrays. Since target can be large? counts<=4, at most 6 types, max sum = 6*4*max_denom
    # But target is given, we only need up to target.
    # Use dp as list of length target+1, each entry is (coins_used, counts_tuple) or None
    # Process coins one by one
    # dp[s] = best (min coins, then lexicographically min counts) using processed types to make sum s
    # Initialize: dp[0] = (0, (0,)*n), others None
    # For each coin type i with denom d, count c:
    #   new_dp = copy of dp
    #   for s from 0 to target:
    #       if dp[s] is not None:
    #           for k in 1..c:
    #               ns = s + k*d
    #               if ns > target: break
    #               new_coins = dp[s][0] + k
    #               new_counts = list(dp[s][1]); new_counts[i] = k
    #               new_counts = tuple(new_counts)
    #               if new_dp[ns] is None or (new_coins, new_counts) < (new_dp[ns][0], new_dp[ns][1]):
    #                   new_dp[ns] = (new_coins, new_counts)
    #   dp = new_dp
    # But this is not quite right because we need to combine with previous types properly.
    # Actually, standard bounded knapsack: for each type, we update dp.
    # Let's use dp[s] = (min_coins, counts_tuple) after processing some types.
    # For type i, we can use 0..c_i coins.
    # We'll do:
    #   new_dp = [None]*(target+1)
    #   for s in range(target+1):
    #       if dp[s] is not None:
    #           for k in range(0, c_i+1):
    #               ns = s + k*d_i
    #               if ns > target: break
    #               coins_used = dp[s][0] + k
    #               counts = list(dp[s][1]); counts[i] = k; counts = tuple(counts)
    #               if new_dp[ns] is None or (coins_used, counts) < (new_dp[ns][0], new_dp[ns][1]):
    #                   new_dp[ns] = (coins_used, counts)
    #   dp = new_dp
    # This works because we're combining the best way to make s with previous types and k coins of type i.
    # But wait, dp[s] already includes counts for types 0..i-1, and we set counts[i]=k, and types i+1..n-1 are 0.
    # That's correct.
    
    dp = [None] * (target + 1)
    dp[0] = (0, tuple([0] * n))
    
    for i in range(n):
        d, c = coins[i]
        new_dp = [None] * (target + 1)
        for s in range(target + 1):
            if dp[s] is None:
                continue
            base_coins = dp[s][0]
            base_counts = dp[s][1]
            for k in range(0, c + 1):
                ns = s + k * d
                if ns > target:
                    break
                coins_used = base_coins + k
                counts_list = list(base_counts)
                counts_list[i] = k
                counts_tuple = tuple(counts_list)
                if new_dp[ns] is None or (coins_used, counts_tuple) < (new_dp[ns][0], new_dp[ns][1]):
                    new_dp[ns] = (coins_used, counts_tuple)
        dp = new_dp
    
    if dp[target] is None:
        return None
    else:
        coins_used, counts_tuple = dp[target]
        return {"count": coins_used, "counts": list(counts_tuple)}
