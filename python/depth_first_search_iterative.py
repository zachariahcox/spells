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

def first_guess(base, digits):
    # return the first number that has 1s in every digit in base N
    sum = 0
    for d in range(digits):
        sum += base**d
    return sum

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

    # the min length is 1?
    # the maximum length of any mode is the length of the input string - (unique_mode_count - 1)
    # but because we're using this as a guess generator, we need to guess the 11111 case too, so we need to search the whole space.
    max_length = len(input)

    # search space is the number of possibilities raised to number of dimensions (digits)
    # O(N^m) where N is len(input) and M is the number of modes that have to be guessed ()
    max_guesses = max_length**unique_mode_count

    # generate guesses by searching every possible combination of lengths for each mode.
    #  the min possible good guess has 1s in every position, so it's N^m + N^(m-1)...+ N^0?
    good_guesses = []
    start_guess = first_guess(max_length, unique_mode_count)
    for guess_number in range(start_guess, max_guesses):
        # guess number is the where we are in our search space.
        # convert "guess number" to a node address in the search space
        guess, zeros = to_base(guess_number, max_length)

        # check constraints
        # no zeros, each dimensional guess must be between 1 and max_length
        if zeros:
            continue

        # must have a guess for every mode (each dimension must have length >= 1
        if len(guess) != unique_mode_count:
            continue

        # guess MUST produce a the same length as the input string
        check_sum = 0
        for j in range(unique_mode_count):
            instances_of_mode_in_pattern = count_by_mode[unique_modes[j]]
            mode_length_guess = guess[j]
            check_sum += instances_of_mode_in_pattern * mode_length_guess

        if check_sum != len(input):
            continue

        # guess substrings MUST actually match the input string
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
    ("abcdef", "AAAAAAAAAAAAAAAbcdef"),
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