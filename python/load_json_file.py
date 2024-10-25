import json
import os
import sys

def parse(d):
    # print(d)

    contributors = set()
    comments = d.get('comments')
    for c in comments:
        a = c['author']
        contributors.add(a.get('displayName'))
        for r in c.get('replies', []):
            a = r.get('author')
            contributors.add(a.get('displayName'))
    
    sc = sorted(contributors)
    for c in sc:
        print(c)

if __name__ == "__main__":
    assert len(sys.argv) == 2, 'please provide the path to a data file.'
    f = sys.argv[1]
    assert os.path.isfile(f), f + " is not a file."

    with open(f, 'r', encoding="utf8") as src:
        data = json.load(src)
    
    parse(data)
