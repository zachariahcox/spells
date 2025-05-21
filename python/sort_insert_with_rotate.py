def insertion_sort(elements):

    # split the array into the sorted (to the left) and unsorted (to the right) elements
    # the first ordered subsequence is just the first element
    for i in range(1, len(elements)): # the 0th element is already sorted
        value = elements[i]
        j = i -1 # first element to left of i
        while j >= 0 and value < elements[j]:
            j -= 1 # keep going!
        
        if j + 1 == i:
            continue # sequence is len 2 and already sorted

        # the value should be inserted between j and j+1
        # we will insert it _at_ j+1 and "slide" all elements from j+1 to i-1 to the right by 1
        # this shift operation is pretty boring and _could_ be implemented with a raw std::memcopy for potential gains.
        elements[j+2 : i+1] = elements[j+1 : i]
        
        # elements[i] now equals the previous elements[i-1]
        elements[j+1] = value
    return elements

print(insertion_sort([5,4,7,8,1,9,4,2,6,8,9,5,4]))