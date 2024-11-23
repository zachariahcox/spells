import sys

# do some work
def parse(line):
    """
    do work to each line
    """
    print(len(line))

if __name__ == "__main__":
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

