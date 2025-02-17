#!/usr/lib/python
# -*- coding: utf-8 -*-
#
#       This is a re-implementation of Python's timsort in Python
#       itself. This is purely for learning purposes. :)
#       References: [
#           https://en.wikipedia.org/wiki/Timsort,
#           http://wiki.c2.com/?TimSort
#       ]
#
# Copyright 2017 Nandaja Varma <nandajavarma@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301,
# USA.


def binary_search(the_array, item, start, end):
    if start == end:
        if the_array[start] > item:
            return start
        else:
            return start + 1
    if start > end:
        return start

    mid = (start + end)/ 2
    if the_array[mid] < item:
        return binary_search(the_array, item, mid + 1, end)
    elif the_array[mid] > item:
        return binary_search(the_array, item, start, mid - 1)
    else:
        return mid


"""
Insertion sort that the heap sort uses if the array size is small or if
the size of the "run" is small
"""
def insertion_sort(the_array):
    len_the_array = len(the_array)
    for index in range(1, len_the_array):
        value = the_array[index]
        pos = binary_search(the_array, value, 0, index - 1)
        the_array = the_array[:pos] + [value] + the_array[pos:index] + the_array[index+1:]
    return the_array

def merge(left, right):
    """
    Takes two sorted lists and returns a single sorted list by comparing the
    elements one at a time.
    """
    if not left:
        return right
    if not right:
        return left
    if left[0] < right[0]:
        return [left[0]] + merge(left[1:], right)
    else:
        return [right[0]] + merge(left, right[1:])


def timsort(the_array):
    runs, sorted_runs = [], []

    #
    # split array into "runs"
    # a run is a subset of monotonically increasing values
    #
    len_the_array = len(the_array)
    new_run = [the_array[0]] # a new array with just the first element of the input
    for i in range(1, len_the_array):

        # exit
        if i == len_the_array - 1:
            # found the end!
            new_run.append(the_array[i])
            runs.append(new_run)
            break

        if the_array[i] < the_array[i-1]:
            # i is not monotonically increasing
            #   break the run
            if not new_run:
                runs.append([the_array[i-1]]) # i-1 was a run of one, don't bother adding it to the new_run
                new_run.append(the_array[i])  # start new run
            else:
                # new run has at least one element, so add it to the runs
                runs.append(new_run)
                new_run = [] # todo: should this be the the_array[i]?
        else:
            # i is monotonically increasing, so add to the run
            new_run.append(the_array[i])

    #
    # insertion sort each run
    #
    for each in runs:
        sorted_runs.append(insertion_sort(each))

    #
    # merge sort the runs together
    #
    sorted_array = []
    for run in sorted_runs:
        sorted_array = merge(sorted_array, run)
    print(sorted_array)
