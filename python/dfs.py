"""
DFS with backtracking -- returns a valid path through the graph
"""
def check_condition(graph, index):
    if index < 0 or index >= len(graph):
        return False
    return graph[index] == 0

def neighbors(graph, index):
    rc = []
    if index < 0 or index >= len(graph):
        return rc
    value = graph[index]
    l = index - value
    if l >= 0:
        rc.append(l)
    r = index + value
    if r < len(graph):
        rc.append(r)
    return rc

def find_path(graph, visited, path, index) -> bool:
    if check_condition(graph, index):
        return True

    # only visit each node once
    visited.add(index)

    for n in neighbors(graph, index):
        if n in visited:
            continue # we've already tried that one
        path.append(n)
        if find_path(graph, visited, path, n):
            return True
        else:
            path.pop() # didn't work!
    return False

# is there a path to a node with value 0?
# each node reaches two children. The value is the index offset left and right
# eg: [3,1,2], the "1" node can reach indices 0 and 2. The 3 node has no children, the 2 has index 0 as a child.
for graph, start, expected in [
    ([4,2,3,0,3,1,2], 5, [5, 4, 1, 3]),
    ([4,2,3,0,3,1,2], 0, [0, 4, 1, 3]),
    ([0], 0, [0]),
    ([3,0,2,1,2], 2, [])
]:
    path = [start]
    actual = find_path(graph, set(), path, start)
    if not actual:
        path.clear()
    print("expected: ", expected)
    print("  actual: ", path, actual)