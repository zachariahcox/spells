class Node(object):
    def __init__(self, k, v, p, n):
        self.key = k
        self.value = v
        self.prev = p
        self.next = n

class LRUCache(object):

    def __init__(self, capacity):
        """
        :type capacity: int
        """
        self.cache = {}
        self.head = None
        self.tail = None
        self.cap = capacity
        self.size = 0

    def get(self, key):
        """
        :type key: int
        :rtype: int
        """
        node = self.cache.get(key)
        if node is None:
            return -1

        # update LRU parts
        # remove node from list
        self.remove_node(node)
        self.add_to_head(node)
        return node.value

    def add_to_head(self, node):
        node.next = self.head
        node.prev = None
        if self.head:
            self.head.prev = node
        self.head = node
        if self.tail is None:
            self.tail = node
    
    def remove_node(self, node):
        if self.tail == node:
            self.tail = node.prev
        if self.head == node:
            self.head = None
            
        if node.prev:
            node.prev.next = node.next 
        if node.next:
            node.next.prev = node.prev

    def put(self, key, value):
        """
        :type key: int
        :type value: int
        :rtype: None
        """
        node = self.cache.get(key)
        if node is None:
            # adding new element to cache
            node = Node(key, value, None, None)
            self.add_to_head(node)
            # add to cache
            self.cache[key] = node

            if len(self.cache) > self.cap:
                t = self.tail
                if t:
                    self.remove_node(t)
                    del self.cache[t.key]
        else:
            # replacing value in cache
            node.value = value
            self.remove_node(node)
            self.add_to_head(node)


# Your LRUCache object will be instantiated and called as such:
lRUCache = LRUCache(2)
lRUCache.put(1, 1) # cache is {1=1}
lRUCache.put(2, 2) # cache is {1=1, 2=2}
assert 1 == lRUCache.get(1)    # return 1
lRUCache.put(3, 3)             # LRU key was 2, evicts key 2, cache is {1=1, 3=3}
assert -1 == lRUCache.get(2)   # returns -1 (not found)
lRUCache.put(4, 4)             # LRU key was 1, evicts key 1, cache is {4=4, 3=3}
assert -1 == lRUCache.get(1)   # return -1 (not found)
assert 3 == lRUCache.get(3)    # return 3
assert 4 == lRUCache.get(4)    # return 4