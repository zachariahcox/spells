import math

def to_base(number, base):
    digits = []
    while number > 0:
        digits.append(number % base)
        number //= base
    return list(reversed(digits))

def digits_in_base(number, base):
    # this doesn't 100% work all the time!
    # floating point math is hard, use the log10 function to hit some lookup tables I think!
    if base == 10:
        return int(math.log10(number) + 1)
    return math.floor(math.log(number, base) + 1)

def test(digits, base):
    sum = 0
    l = len(digits) - 1
    for i, d in enumerate(digits):
        sum += d * base**(l-i)
    return sum

if __name__ == "__main__":
    for n in [3**3, 127, 56, 246, 1000]:
        for b in [2, 3, 4, 5, 7, 10]:
            digits = to_base(n,b)
            digits_count = digits_in_base(n, b)
            assert n == test(digits, b), "all integers should be representable"
            assert digits_count == len(digits), "the number of digits should match the length of the list"
            print(n, "is", digits, "in base", b, "and has", digits_count, "digits")

