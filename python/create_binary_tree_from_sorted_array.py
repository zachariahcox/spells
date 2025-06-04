
class Node(object):
    def __init__(self, data, left, right):
        self.data = data
        self.left = left
        self.right = right
    def __str__(self):
        return f"{self.data}: {self.left}, {self.right}"

def to_bst(data):
    if not data:
        return None
    
    length = len(data);
    if length == 0:
        return None
    
    mid = int(length / 2)
    return Node(data[mid], to_bst(data[:mid]), to_bst(data[mid+1:]))

def tree_print(root):
    from collections import deque
    q = deque([root])
    while q:
        n = q.pop()

        print(n)

        if n.left:
            q.append(n.left)
        if n.right:
            q.append(n.right)

d = [1,2,3,4,5,6,7]
root = to_bst(d)
tree_print(root)
