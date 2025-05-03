

def matrix_multiply(A, B):
    """
    multiply two matrices, where A and B are list[list[int]]
    """    
    # will it work?
    # length of a row of A must be the same as number of rows of B
    rowsA, colsA = len(A), len(A[0])
    rowsB, colsB = len(B), len(B[0])
    if colsA != rowsB:
        return None # probably should throw exception here instead.
    
    # size of result
    # if A is NxM and B is IxJ, then M == I and the output will have N rows, J columns
    # each element will be the vector dot produt of the A row and the B column
    output = [[0 for _ in range(colsB)] for _ in range(rowsA)] # init to zeros

    for r in range(rowsA):
        for c in range(colsB):
            for n in range(colsA):
                output[r][c] += A[r][n] * B[n][c] # assumes it was initialized to zeros.
    
    return output


if __name__ == "__main__":
    # a 2x2 matrix
    a = [[1,2],
         [3,4]]
    # a 2x3 matrix
    b = [[1,2,3],
         [4,5,6]]
    
    assert matrix_multiply(a,b) == [[9, 12, 15], [19, 26, 33]]
    assert matrix_multiply(b,a) == None
