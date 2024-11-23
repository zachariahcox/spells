'''
Python framework to parse piped output
$> cat /path/to/some/file | python pipes.py
'''
import sys

def parse(line):
    """
    do work to each line
    """
    assert(isinstance(line, str))
    print(len(line))

if __name__ == "__main__":
    # it's hard to debug python when it's in the middle of a long pipe command.
    if len(sys.argv) > 1:
        # read from file to enable easier debugging
        with open(sys.argv[1], 'r') as f:
            for line in f.readlines():
                parse(line.rstrip())
    else:
        # read from stdin, allowing for usage like:
        # $> cat /path/to/some/file | python pipes.py
        for line in sys.stdin:
            parse(line.rstrip())

