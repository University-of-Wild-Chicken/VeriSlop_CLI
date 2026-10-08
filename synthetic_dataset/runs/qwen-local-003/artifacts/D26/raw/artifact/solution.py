import json
import re

def solve(data):
    values = data.get("values", [])
    
    def tokenize(s):
        tokens = []
        i = 0
        n = len(s)
        while i < n:
            if s[i].isdigit() and s[i].isascii():
                j = i
                while j < n and s[j].isdigit() and s[j].isascii():
                    j += 1
                tokens.append(('num', int(s[i:j])))
                i = j
            else:
                j = i
                while j < n and not (s[j].isdigit() and s[j].isascii()):
                    j += 1
                tokens.append(('text', s[i:j].casefold()))
                i = j
        return tokens
    
    def compare(a, b):
        ta = tokenize(a)
        tb = tokenize(b)
        min_len = min(len(ta), len(tb))
        for i in range(min_len):
            type_a, val_a = ta[i]
            type_b, val_b = tb[i]
            if type_a == type_b:
                if type_a == 'num':
                    if val_a != val_b:
                        return -1 if val_a < val_b else 1
                else:
                    if val_a != val_b:
                        return -1 if val_a < val_b else 1
            else:
                # numeric token sorts before text token
                return -1 if type_a == 'num' else 1
        if len(ta) != len(tb):
            return -1 if len(ta) < len(tb) else 1
        return 0
    
    # Use stable sort with key that preserves original order for equal keys
    # Since Python's sort is stable, we can use a key function that returns the token list
    # But we need custom comparison, so we use functools.cmp_to_key
    from functools import cmp_to_key
    
    indexed = list(enumerate(values))
    indexed.sort(key=cmp_to_key(lambda x, y: compare(x[1], y[1])))
    
    return [v for _, v in indexed]
