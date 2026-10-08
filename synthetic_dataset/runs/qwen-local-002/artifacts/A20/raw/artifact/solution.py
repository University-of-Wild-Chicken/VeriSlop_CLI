import json
from math import comb

def solve(data):
    word = data.get("word", "")
    n = len(word)
    if n == 0:
        return 0
    
    # Count frequencies of each character
    freq = {}
    for c in word:
        freq[c] = freq.get(c, 0) + 1
    
    rank = 0
    # Process each position
    for i in range(n):
        current_char = word[i]
        # For each character smaller than current_char that is still available
        for c in sorted(freq.keys()):
            if c >= current_char:
                break
            if freq[c] > 0:
                # If we place c at position i, how many permutations are possible?
                # Total remaining positions: n - i - 1
                # Frequencies: freq with c reduced by 1
                remaining = n - i - 1
                # Number of distinct permutations = remaining! / (product of factorials of each char's count)
                # We can compute this as a multinomial coefficient
                # But we need to be careful with large numbers. Use exact arithmetic.
                # Compute: remaining! / (freq[c]-1)! / product_{d != c} freq[d]!
                # This is equivalent to: C(remaining, freq[c]-1) * C(remaining - (freq[c]-1), freq[d1]) * ...
                # But it's easier to compute the full multinomial.
                
                # Let's compute the number of permutations of the remaining multiset
                # where we've used one c.
                # new_freq = freq with c reduced by 1
                # count = remaining! / (new_freq[c]! * product_{d != c} new_freq[d]!)
                # But new_freq[d] = freq[d] for d != c, and new_freq[c] = freq[c] - 1
                
                # We can compute this incrementally. Let's precompute factorials up to n.
                # But n <= 60, so we can compute factorials easily.
                
                # Actually, let's just compute the multinomial coefficient directly.
                # We'll compute it as: remaining! / ( (freq[c]-1)! * product_{d != c} freq[d]! )
                # But we need to be careful: the product includes all characters.
                
                # Let's compute the denominator as the product of factorials of the new frequencies.
                # And numerator as factorial(remaining).
                
                # Since n is small (<=60), we can compute factorials.
                # But we need to do this for each position and each smaller character, so it might be a bit slow but acceptable.
                
                # Let's precompute factorials up to n.
                # Actually, we can compute the multinomial coefficient using a helper function.
                
                # Let's define a helper to compute the number of distinct permutations of a multiset given its frequency dict.
                # But we'll just compute it inline.
                
                # Compute the number of permutations:
                # perm_count = factorial(remaining) // (factorial(freq[c]-1) * product(factorial(freq[d]) for d != c))
                # But we need to be careful: the product should be over all characters in the new frequency dict.
                
                # Let's compute it step by step.
                # First, compute the product of factorials of all frequencies except c, and then multiply by factorial(freq[c]-1).
                # Actually, it's easier to compute the full denominator.
                
                # Let's precompute factorials up to n.
                # We'll do this outside the loop for efficiency.
                
                # But since we're inside the loop, let's just compute it.
                # Actually, let's restructure: precompute factorials once.
                
                # For now, let's just compute it directly.
                # We'll compute the multinomial coefficient.
                
                # Let's compute the denominator as the product of factorials of the new frequencies.
                # new_freq = {c: freq[c]-1, d: freq[d] for d != c}
                # But we don't want to create a new dict each time.
                
                # Let's compute the denominator as:
                # denom = factorial(freq[c]-1)
                # for d in freq:
                #     if d != c:
                #         denom *= factorial(freq[d])
                # perm_count = factorial(remaining) // denom
                
                # But this is O(n) per character, and we have O(n) positions and O(26) characters, so it's O(n^2 * 26) which is fine for n<=60.
                
                # Let's do it.
                
                # Precompute factorials up to n.
                # Actually, let's precompute them once at the beginning.
                
                # But we're inside the loop. Let's just compute it.
                
                # Let's compute the denominator.
                denom = 1
                for d in freq:
                    if d == c:
                        denom *= _factorial(freq[d] - 1)
                    else:
                        denom *= _factorial(freq[d])
                perm_count = _factorial(remaining) // denom
                rank += perm_count
        # After processing, reduce the frequency of current_char
        freq[current_char] -= 1
        if freq[current_char] == 0:
            del freq[current_char]
    
    return rank

def _factorial(n):
    if n < 0:
        return 0
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
