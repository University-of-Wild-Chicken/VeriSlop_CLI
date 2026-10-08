def solve(data):
    grid = [row[:] for row in data["grid"]]

    def search(pos):
        if pos == 16:
            return [row[:] for row in grid]
        r, c = divmod(pos, 4)
        if grid[r][c] != 0:
            return search(pos + 1)

        for value in range(1, 5):
            if any(grid[r][j] == value for j in range(4)):
                continue
            if any(grid[i][c] == value for i in range(4)):
                continue
            br, bc = (r // 2) * 2, (c // 2) * 2
            if any(grid[i][j] == value
                   for i in range(br, br + 2)
                   for j in range(bc, bc + 2)):
                continue
            grid[r][c] = value
            result = search(pos + 1)
            if result is not None:
                return result
            grid[r][c] = 0
        return None

    return search(0)
