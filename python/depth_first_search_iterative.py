"""
The basic idea is you're given a pattern defined by single characters.
The pattern represent a specific sequence of characters in an input string.

The puzzle is to determine if a a given input string matches the pattern.

The basic solution is to count the number of different characters in the pattern.
Each character represents a different dimension that needs to be searched.
IE, for a two character pattern, there's a 2d solution space.

You can make a "guess" as to the lengths of each character in the pattern, then see if that provides a solution.
A guess is "wrong" if the length of the guess would produce a contradiction.

It's possible to place additional constraint on the guess before proceeding with the validation phase.
You can make an assertion that the min length of any pattern is 1.
You can then assert that sum of the lengths of the pattern must be the same as the length of the input string.
"""
import math

def solve(pattern, input):
    modes = list(set(pattern)) # unique modes in the pattern
    number_modes = len(modes)
    count_by_mode = {}
    for m in modes:
        count = 0
        for p in pattern:
            if p == m:
                count += 1
        count_by_mode[m] = count

    max_length = len(input) # max possible length of any mode
    max_guesses = max_length**number_modes #  # total number of possibilities the number of possibilities raised to number of unique modes

    # generate guesses
    guesses = []
    for i in range(1, max_guesses + 1):
        factor = 1
        guess = [0] * number_modes # allocate guess with the correct number of digits
        produced_a_zero = False # ignore guesses where the mode is the entire length of the input
        for digit in range(number_modes-1, -1, -1):
            g = int(math.ceil(i / factor) % max_length)
            if g == 0:
                # too long
                produced_a_zero = True
                break
            guess[digit] = g
            factor *= max_length

        # check constraints
        # no zeros
        if produced_a_zero:
            continue
        # lengths must sum up to the length of the string
        check_sum = 0
        for i in range(number_modes):
            check_sum += count_by_mode[modes[i]] * guess[i]
        if check_sum != len(input):
            continue

        # seems like a reasonable guess
        guesses.append(guess)
        # print(guess)

    # test guesses
    for guess in guesses:
        guess_strings = {}
        input_index = 0
        valid = True
        for m in pattern:
            guess_string = guess_strings.get(m)
            if not guess_string:
                mode_index = modes.index(m)
                mode_length = guess[mode_index]
                guess_string = input[input_index:input_index + mode_length]
                guess_strings[m] = guess_string # critical -- the pattern only "matches" if this string is repeated
            else:
                actual = input[input_index:input_index + len(guess_string)]
                valid = actual == guess_string
                if not valid:
                    break # this guess does not match the input / pattern combo

            # prep for next iteration
            input_index += len(guess_string)

        #result
        print(guess_strings, "is a OK" if valid else "is BAD")


# solve("abba", "aabbbbaa")
# solve("abc", "abccba")
# solve("ababa", "AB BA AB BA AB ")
solve("abcde", "aabcde")