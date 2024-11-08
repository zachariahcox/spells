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

def to_base(number, base):
    result = []
    zeros = 0
    while number > 0:
        digit = number % base
        result.append(digit)
        number //= base

        # keep track of zeros for this particular case
        if digit == 0:
            zeros += 1

    result.reverse()
    return result, zeros

def solve(pattern, input):
    # analytics on the pattern
    # how many modes are there
    # how many times do they appear?
    count_by_mode = {}
    for m in pattern:
        c = count_by_mode.get(m, 0)
        count_by_mode[m] = c + 1
    unique_mode_count = len(count_by_mode)
    unique_modes = list(sorted(count_by_mode.keys()))

    # the maximum length of any guess is the length of the input string
    max_length = len(input)

    #  search space is the number of possibilities raised to number of dimensions (digits)
    max_guesses = max_length**unique_mode_count

    # generate guesses by searching every possible combination of lengths for each mode.
    good_guesses = []
    for guess_number in range(max_guesses):
        # convert "guess number" in base 10 to a node in the search space
        guess, zeros = to_base(guess_number, max_length)

        # check constraints
        # no zeros, each dimensional guess must be between 1 and max_length
        if zeros:
            continue

        # guess must have the same number of dimensions as the pattern
        if len(guess) != unique_mode_count:
            continue

        # guess must produce a the same length as the input string
        check_sum = 0
        for j in range(len(guess)):
            instances_of_mode_in_pattern = count_by_mode[unique_modes[j]]
            mode_length_guess = guess[j]
            check_sum += instances_of_mode_in_pattern * mode_length_guess

        if check_sum != len(input):
            continue

        # guess substrings must actually match the input string
        guess_strings = {} # each guess produces a specific substring for a given input
        input_index = 0 # where are we in the input string
        valid = True
        for m in pattern:
            # load stored guess
            guess_string = guess_strings.get(m)

            if not guess_string:
                # cache one if first instance
                mode_index = unique_modes.index(m)
                mode_length = guess[mode_index]
                guess_string = input[input_index:input_index + mode_length]
                guess_strings[m] = guess_string # critical -- the pattern only "matches" if this string is repeated
            else:
                # subsequent instances much match exactly
                actual = input[input_index : input_index + len(guess_string)]
                valid = actual == guess_string
                if not valid:
                    break # this guess does not match the input / pattern combo

            # "consume" this many characters from the input and loop
            input_index += len(guess_string)

        # result
        if valid:
            good_guesses.append(guess_strings)

        # log progress in case we need to resume elsewhere
        # log log log
    return good_guesses


for p, i in [
    ("abba", "aabbbbaa"),
    ("abba", "AAAAAAAA"),
    ("abba", "ABC"),
    ("abba", "aabb"),
    ("abba", "dogdogdogdog"),
    ("abba", "dogcatcatdog"),
    ("abba", "aabbbbaa"),
    ("abc", "abccba"),
    ("ababa", "AB BA AB BA AB"),
    ("edcba", "AABCDE")
    ]:
    solutions = solve(p, i)
    if solutions:
        print("pattern:", p, "\ninput:  ", i, "\n  found", len(solutions), "solutions")
        # for s in solutions:
        #     print("pattern:", p, "\ninput:  ", i, "\n  ", s, "is a valid solution")
    else:
        print("pattern:", p, "\ninput:  ", i, "\n  No solution found")