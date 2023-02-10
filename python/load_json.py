import json
import os
import sys

def parse(d):
    print(d)

if __name__ == "__main__":
    assert len(sys.argv) == 2, 'please provide the path to a data file.'
    f = sys.argv[1]
    assert os.path.isfile(f), f + " is not a file."

    with open(f, 'r', encoding="utf8") as src:
        data = json.load(src)
    
    parse(data)
