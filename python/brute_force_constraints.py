"""
solve a 2d constraint problem, brute force, recursive backtracking.
It will visit all possible solutions using the stack to keep track of state.
This one is based on the Nqueens problem.
"""

def meets_constraint(board, proposedX, proposedY):
    """
    return true iff this move would meet the constraints given the previous state of the board
    """
    # constraint 1: cannot have another move in the same x dimension
    #   (because the algorithm moves low to high x, we only need to check the left values)
    for x in range(proposedX):
        if board[proposedY][x]:
            # found a move that attacks this square
            return False

    # constraint 2: no other moves in low direction diagonals
    #  start from the highest value (proposed x) and move to the left
    x = proposedX
    low_y = proposedY
    high_y = proposedY
    max_rows = len(board)
    while x >= 0:
        # find potential moves in new column
        x -= 1 # move to the left
        low_y -= 1 # move down a row
        high_y += 1 # move up a row
        if x < 0:
            # we searched the whole range and didn't find any previous moves apparently!
            break

        if low_y >= 0 and board[low_y][x]:
            return False # found a previous move in the low diagonal

        if high_y < max_rows and board[high_y][x]:
            return False # found a previous move in the high diagonal

    # seems ok!
    return True

def solve_low_to_high_column_wise(solutions, board, x):
    """
    return true when the board has a valid solution
    solutions is a list that will be populated with all valid solutions
    board is a 2d matrix of boolean values, where True means a move is made at that position
    x is a proposed column index to consider for the next move.
    """
    # given column x, find a valid y position
    for y in range(rows):
        if meets_constraint(board, x, y):
            # found one, store the proposed move in the matrix
            #   (we will backtrack at the close of this scope)
            board[y][x] = True

            # check for complete solution
            if x == len(board[y]) - 1: # last column
                # this is a valid solution
                # return True # return True if we only want to find one solution

                # MODIFIED: otherwise, add to list and keep looking for more.
                solutions.append(deepcopy(board))

            # recurse using this matrix as the new state
            elif solve_low_to_high_column_wise(solutions, board, x + 1):
                return True # (y, x) is part of a solution, so we can return True

            # backtrack
            # this set of values (y, x) meets the local constraint, but is not part of a full solution
            # reset the bit and try the next y value
            board[y][x] = False

    return False # no solution

def deepcopy(matrix):
    # could also just import copy and use copy.deepcopy
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
        print(" ".join(["+" if c else "_" for c in board[r]]))

if __name__ == '__main__':
    columns = 4
    rows = 4
    board = [[False for _ in range(columns)] for _ in range(rows)]

    solutions = []
    solve_low_to_high_column_wise(solutions, board, 0)

    if not solutions:
        print("no solutions")
    else :
        print("found", len(solutions), "solutions", "\n\n")
        for s in solutions:
            print("solution:")
            prettyprint(s)
            print("\n\n")
