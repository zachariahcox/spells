"""
collect stats about regex matches on lists of strings
"""
import sys
import re

dataFile = sys.argv[1]
illegalCount = 0
totalCount = 0
maxLegalNodes = 6 # this is actually very forgiving, but accounts for the max like: stage.2.phase.2.job.2
legalPattern = re.compile("^[a-zA-Z0-9_]+$") # node names are allowed to contain upper and lowercase letters, numbers and _ according to the docs.

with open(dataFile, 'r') as f:
    for l in f.read().splitlines():
        totalCount += 1
        nodeCount = 0
        for n in l.split('.'):
            nodeCount += 1
            if nodeCount > maxLegalNodes or not legalPattern.match(n):
                illegalCount += 1
                break

percentIllegal = round(100 * illegalCount / totalCount)
print(str(percentIllegal) + "% of all strings have illegal node names")
