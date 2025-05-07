
def lastStoneWeight(stones):
    """
    :type stones: List[int]
    :rtype: int
    """
    # termination events
    if not stones or len(stones) == 0:
        return 0
    if len(stones) == 1:
        return stones[0]

    # move top two to front
    def partial_sort(subset):
        def swap(i,j):
            subset[i], subset[j] = subset[j], subset[i]
        
        # initial condition?
        if subset[1] > subset[0]:
            swap(1, 0)

        for k in range(2, len(subset)):
            if subset[k] > subset[0]:
                swap(0, 1)
                swap(k, 0)
            elif subset[k] > subset[1]:
                swap(k, 1)
    
    partial_sort(stones)
    smash = abs(stones[0] - stones[1])
    if smash > 0:
        return lastStoneWeight(stones[2:]+[smash])
    return lastStoneWeight(stones[2:])

def withoutsorts(stones):
    if not stones or len(stones) == 0:
        return 0
    if len(stones) == 1:
        return stones[0]

    largest_index = second_index = None
    for index, w in enumerate(stones):
        if largest_index is None or w > stones[largest_index]:
            # swap
            second_index, largest_index = largest_index, index
        elif second_index is None or w > stones[second_index]:
            second_index = index

    min_index = min(largest_index, second_index)
    max_index = max(largest_index, second_index)
    smash = abs(stones[largest_index] - stones[second_index])
    new_slice = stones[:min_index]+stones[min_index+1:max_index] + stones[max_index+1:]
    if smash > 0:
        return withoutsorts(new_slice + [smash])
    return withoutsorts(new_slice)



        

assert withoutsorts([2,7,4,1,8,1]) == 1
assert withoutsorts([1]) == 1
assert withoutsorts([1,1]) == 0