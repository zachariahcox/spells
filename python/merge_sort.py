def merge(left, right):
    result = []

    i = 0
    j = 0
    len_left = len(left)
    len_right = len(right)
    while i < len_left and j < len_right:
        # choose the smaller element to copy to the result
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    # one of these will be a no-op, but copy the remaining element without the compares
    result += left[i:]
    result += right[j:]
    return result

def merge_sort(list):
    # check for recursion exit criteria
    if len(list) < 2:
        return list # single elements are sorted!

    # split the input in half, recursively merge each side
    middle = len(list) / 2
    left = merge_sort(list[:middle])
    right = merge_sort(list[middle:])

    # return the sorted result
    return merge(left, right)