"""
recursively chck if a binary tree is balanced.
"""

class Node(object):
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right= None

def height(node):
    if not node:
        return 0

    lh = height(node.left)
    rh = height(node.right)
    return 1 + max(lh, rh)

def is_balanced(node):
    if not node:
        return True

    lh = height(node.left)
    rh = height(node.right)
    if abs(lh-rh) > 1:
        return False

    return is_balanced(node.left) and is_balanced(node.right)

    
def get_balanced_height(node):
    if not node:
        return 0
    
    lh = get_balanced_height(node.left)
    rh = get_balanced_height(node.right)

    if not lh or not rh:
        return -1 # not balanced

    if abs(lh - rh) > 1:
        return -1 # not balanced
    
    return 1 + max(lh, rh)


# unbalanced tree test
root = Node(1)
root.left = Node(2)
root.right = Node(3)
root.left.left = Node(4)
root.left.right = Node(5)
root.left.left.left = Node(8)

print(get_balanced_height(root) > 0)
print(is_balanced(root))