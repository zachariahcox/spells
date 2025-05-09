class TreeNode:
    """
    A class representing a node in a binary tree.
    
    Attributes:
        val: The value stored in the node
        left: Reference to the left child node
        right: Reference to the right child node
    """
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def inorder_traversal(root, nodes):
    """
    Performs an inorder traversal of the binary tree and collects all nodes in a list.
    
    Args:
        root (TreeNode): The root node of the tree or subtree
        nodes (list): List to collect the nodes in sorted order
    
    Note: For a BST, inorder traversal visits nodes in ascending order of values.
    """
    if root:
        inorder_traversal(root.left, nodes)  # Traverse left subtree first
        nodes.append(root)                   # Visit the current node
        inorder_traversal(root.right, nodes) # Traverse right subtree last

def build_balanced_tree(nodes, start, end):
    """
    Recursively builds a balanced binary search tree from a sorted array of nodes.
    
    Args:
        nodes (list): Sorted list of TreeNode objects (by their values)
        start (int): Starting index in the nodes list
        end (int): Ending index in the nodes list
    
    Returns:
        TreeNode: Root node of the balanced subtree
    """
    if start > end:
        return None
    
    # Use the middle element as the root to ensure balance
    mid = (start + end) // 2
    root = nodes[mid]
    
    # Recursively build left and right subtrees
    root.left = build_balanced_tree(nodes, start, mid - 1)
    root.right = build_balanced_tree(nodes, mid + 1, end)
    
    return root

def balance_bst(root):
    """
    Balances an unbalanced binary search tree.
    
    Args:
        root (TreeNode): Root node of the unbalanced BST
        
    Returns:
        TreeNode: Root node of the balanced BST
    
    Algorithm:
        1. Perform inorder traversal to get nodes in sorted order
        2. Rebuild a balanced tree from the sorted nodes
    """
    nodes = []
    inorder_traversal(root, nodes)
    return build_balanced_tree(nodes, 0, len(nodes) - 1)