

def check_condition(graph, index):
    """
    in this example, just check for 0
    """
    return graph[index] == 0

def neighbors(graph, index):
    """
    Return all the nodes reachable from the given index in the graph.
    In this case, assume a "node" can "reach" nodes + and - the value of the node. 
    It could easily be modeled with other "child" pointers.
    """
    value = graph[index]
    return [index + value, index - value]

def bfs(graph, start_index, condition):
    """
    Perform a breadth-first search on the graph starting from the given node.
    The basic idea is to list all the reachable nodes from the current node, then come back to them later.
    O(N) where N is the number of nodes in the graph (we only visit each node at max once)
    """
    need_to_visit = [start_index]
    found = {start_index} # set of all nodes we've found, ensuring O(N)

    while need_to_visit:
        # grab the next node to visit
        node_index = need_to_visit.pop(0)

        # check exit condition
        if condition(graph, node_index):
            return True

        # add all reachable nodes to the queue
        for ni in neighbors(graph, node_index):
            if ni >= 0 and ni < len(graph) and ni not in found:
                need_to_visit.append(ni)
                found.add(ni)

    # if we get here, we didn't find the exit condition and ran out of nodes to visit.
    return False

assert(True == bfs([4,2,3,0,3,1,2], 5, check_condition))
assert(True == bfs([4,2,3,0,3,1,2], 0, check_condition))
assert(False == bfs([3,0,2,1,2], 2, check_condition))