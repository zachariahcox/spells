'''
This is a basic cli to open and read a file. 
Example of loading each row into an object. 
'''
import sys
import os

class Row(object):
    def __init__(self, time, name):
        self.time = time
        self.name = name
    def __str__(self):
        return self.time + '\t' + self.name

def parse_meta(line):
    # tokens = line.split(' ')
    return line

def parse_rows(lines):
    tokens = []
    for l in lines:
        first_char = 0
        if l.startswith('(Start'):
            first_char = l.index(')') + 2 # skip stuff like (Start Index 8000)
        data = l[first_char:]
        tokens += data.split(' ')

    rows = []
    method = []
    for t in tokens:
        # time segments are separated by ':'
        i = t.rfind(':')
        if i == -1:
            method.append(t)
        else:
            try:
                # see if the time segment is an int
                ti = i + 1
                time = int(t[ti:])

                # we did not throw, so it was, print the whole method
                method.append(t[:i])
                print(time, '\t', ' '.join(method))

                # reset token list
                method = []
            except ValueError:
                # it is not
                method.append(t)
    return rows

if __name__ == "__main__":
    assert len(sys.argv) == 2, 'please provide the path to a data file.'
    f = sys.argv[1]
    assert os.path.isfile(f), f + " is not a file."

    # clean and tokenize data
    with open(f, 'r') as src:
        lines = [l.rstrip() for l in src.readlines()]

    # for csv-like formats, the first line might contain metadata
    meta = parse_meta(lines[0])
    print (meta)

    # parse the rest of the lines
    rows = parse_rows(lines[1:])
    for r in rows:
        print(r)
