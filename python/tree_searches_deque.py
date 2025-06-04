"""
using a deque (double-ended queue) for iterative traversal.
"""

from collections import deque

class Node:
    def __init__(self, value):
        self.value = value
        self.children = []

    def add_child(self, child_node):
        self.children.append(child_node)

def count_nodes_at_each_level(root):
    """
    Count the number of nodes at each level of a tree using DFS with a deque.
    """
    if root is None:
        return []

    stack = deque([root])
    level_counts = []

    while stack:
        # each iteration represents a new level in the tree
        # count the number of nodes at the current depth
        nodes_at_depth = len(stack)
        level_counts.append(nodes_at_depth)

        # process all nodes at the current depth
        for _ in range(nodes_at_depth):
            node = stack.popleft()
            for child in node.children:
                stack.append(child)

    return level_counts


def dfs(root, find_value=None):
    """
    Perform depth-first search (DFS) on a tree using a deque.
    """
    if root is None:
        return

    q = deque([root])
    while q:
        node = q.pop() # pop from the right end for DFS
        
        # Check if we found the value we're looking for
        if find_value is not None and node.value == find_value:
            return node
        
        # Add children to the stack
        for child in node.children:
            q.append(child)
        
    return None  # Return None if the value is not found


def bfs(root, find_value=None):
    """
    Perform breadth-first search (BFS) on a tree using a deque.
    """
    if root is None:
        return None

    q = deque([root])
    while q:
        node = q.popleft()  # pop from the left end for BFS

        # Check if we found the value we're looking for
        if find_value is not None and node.value == find_value:
            return node

        # Add children to the queue
        for child in node.children:
            q.append(child)

    return None  # Return None if the value is not found
