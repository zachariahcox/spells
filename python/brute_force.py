columns = 4
rows = 4

def legal_move(board, proposedX, proposedY):
    """return true iff this move would be valid"""
    # check the row with proposed y
    for x in range(proposedX):
        if board[proposedY][x]:
            # found a move that attacks this square
            return False

    # diagonals
    x = proposedX
    lowy = proposedY
    highy = proposedY
    while x >= 0:
        x -= 1
        if x < 0:
            break

        lowy -= 1
        highy += 1

        if lowy >= 0 and board[lowy][x]:
            return False

        if highy < rows and board[highy][x]:
            return False

    # seems ok!
    return True

def find_solutions(board):
    solutions = []
    solve(solutions, board, 0)
    return solutions

def solve(solutions, board, x):
    """
    return true iff we find a valid column position
    """
    # find a valid y position for column x
    for y in range(rows):
        if legal_move(board, x, y):
            # found one
            board[y][x] = True

            # this may be a complete solution
            if x == columns - 1:
                solutions.append(deepcopy(board))
                board[y][x] = False
                return False # keep looking

            # try to recurse from here
            elif solve(solutions, board, x + 1):
                return True # apparently this works!

            # reset the bit and try the next row
            board[y][x] = False

    return False # no solution

def deepcopy(matrix):
    if matrix is None:
        return None
    if not isinstance(matrix, list):
        return None

    if len(matrix) < 1:
        return None

    row = matrix[0]
    if row is None or len(row) < 1:
        return None

    dup = [[False for _ in range(len(row))] for _ in range(len(matrix))]
    for r in range(len(matrix)):
        for c in range(len(row)):
            dup[r][c] = matrix[r][c]
    return dup

def prettyprint(board):
    for r in range(rows):
        print("\t".join(map(str, board[r])))

if __name__ == '__main__':
    board = [[False for _ in range(columns)] for _ in range(rows)]
    solutions = find_solutions(board)
    if not solutions:
        print("no solutions")
    else :
        print(f"found {len(solutions)} solutions")
        # for s in solutions:
        #     print("solution:")
        #     prettyprint(s)
