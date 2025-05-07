class Node(object):
    def __init__(self, aValue, aNode):
        self.value=aValue
        self.next=aNode

    
class MyLinkedList(object): 
    def __init__(self):
        self.head = None

    def get(self, index):
        """
        :type index: int
        :rtype: int
        """
        node = self.head
        for i in range(index):
            node = node.next
        return node.value
        

    def addAtHead(self, val):
        """
        :type val: int
        :rtype: None
        """
        n = Node(val, self.head)
        self.head = n

    def addAtTail(self, val):
        """
        :type val: int
        :rtype: None
        """
        n = self.head
        while n.next is not None:
            n = n.next
        n.next = Node(val, None)

    def addAtIndex(self, index, val):
        """
        :type index: int
        :type val: int
        :rtype: None
        """

        if index == 0:
            return self.addAtHead(val)
        
        node = self.head
        for i in range(index-1):
            node = node.next
        
        n = Node(val, node.next)
        node.next = n

    def deleteAtIndex(self, index):
        """
        :type index: int
        :rtype: None
        """

        if index == 0:
            if self.head:
                self.head = self.head.next
        else:
            node = self.head
            for _ in range(index-1):
                node = node.next
                if node is None:
                    return 
                
            node.next = node.next.next


myLinkedList = MyLinkedList()
myLinkedList.addAtHead(1)
myLinkedList.addAtTail(3)
myLinkedList.addAtIndex(1, 2)    # linked list becomes 1->2->3
assert 2 == myLinkedList.get(1)  # return 2
myLinkedList.deleteAtIndex(1)    # now the linked list is 1->3
assert 3 == myLinkedList.get(1)  # return 3