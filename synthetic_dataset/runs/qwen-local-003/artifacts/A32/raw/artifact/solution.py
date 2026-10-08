import json

def solve(data):
    grid = data["grid"]
    n = 4
    # Check givens for conflicts
    for i in range(n):
        row = grid[i]
        col = [grid[r][i] for r in range(n)]
        for v in row:
            if v != 0:
                if row.count(v) > 1 or col.count(v) > 1:
                    return None
        # Check box
    for br in range(0, n, 2):
        for bc in range(0, n, 2):
            box = []
            for r in range(br, br+2):
                for c in range(bc, bc+2):
                    box.append(grid[r][c])
            for v in box:
                if v != 0 and box.count(v) > 1:
                    return None
    
    # Backtracking to find lexicographically smallest solution
    def box_of(r, c):
        return (r // 2) * 2 + (c // 2)
    
    def is_valid(r, c, val):
        # Check row
        for cc in range(n):
            if cc != c and grid[r][cc] == val:
                return False
        # Check column
        for rr in range(n):
            if rr != r and grid[rr][c] == val:
                return False
        # Check box
        br = (r // 2) * 2
        bc = (c // 2) * 2
        for rr in range(br, br+2):
            for cc in range(bc, bc+2):
                if (rr != r or cc != c) and grid[rr][cc] == val:
                    return False
        return True
    
    def backtrack(idx):
        if idx == n * n:
            return True
        r = idx // n
        c = idx % n
        if grid[r][c] != 0:
            return backtrack(idx + 1)
        for val in range(1, n+1):
            if is_valid(r, c, val):
                grid[r][c] = val
                if backtrack(idx + 1):
                    return True
                grid[r][c] = 0
        return False
    
    # Make a copy to avoid modifying original
    work = [row[:] for row in grid]
    # Replace grid reference with work
    # We need to use work in is_valid and backtrack
    # Let's refactor to use work
    def is_valid_work(r, c, val):
        for cc in range(n):
            if cc != c and work[r][cc] == val:
                return False
        for rr in range(n):
            if rr != r and work[rr][c] == val:
                return False
        br = (r // 2) * 2
        bc = (c // 2) * 2
        for rr in range(br, br+2):
            for cc in range(bc, bc+2):
                if (rr != r or cc != c) and work[rr][cc] == val:
                    return False
        return True
    
    def backtrack_work(idx):
        if idx == n * n:
            return True
        r = idx // n
        c = idx % n
        if work[r][c] != 0:
            return backtrack_work(idx + 1)
        for val in range(1, n+1):
            if is_valid_work(r, c, val):
                work[r][c] = val
                if backtrack_work(idx + 1):
                    return True
                work[r][c] = 0
        return False
    
    if backtrack_work(0):
        return work
    else:
        return None
