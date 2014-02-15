#! /usr/bin/python3

import random
import random
import sys
import re

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def losub(text, subs):
    def subtext(matchobj):
        if matchobj.group(1) in subs:
            return subs[matchobj.group(1)]
        else:
            print("Unrecognised substitution: {}".format(matchobj.group(0)),
                  file=sys.stderr)
    return re.sub(r"<:=\s*(\S*)\s*:>", subtext, text)

infile = open("puzzle.yaml")
headerf = open("template-header.tex")
bodypuzf = open("template-smallhexagon-puzzle.tex")
bodysolf = open("template-smallhexagon-solution.tex")
bodytablef = open("template-table.tex")
outpuz = open("puzzle-puzzle.tex", "w")
outsol = open("puzzle-solution.tex", "w")
outtable = open("puzzle-table.tex", "w")

data = load(infile, Loader=Loader)

random.seed(1)  # Will eventually do this using filename hash

header = headerf.read()
print(header, file=outpuz)
print(header, file=outsol)
print(header, file=outtable)

bodypuz = bodypuzf.read()
bodysol = bodysolf.read()
bodytable = bodytablef.read()

dsubs = dict()
if 'type' in data:
    if data['type'] == 'smallhexagon':
        # good
        pass
    else:
        sys.exit("Unrecognised jigsaw type")

if 'title' in data:
    dsubs['title'] = data['title']
else:
    dsubs['title'] = ''

if 'pairs' in data:
    pairs = data['pairs']
    if len(pairs) != 6:
        sys.exit("Small hexagons need exactly 6 pairs")
else:
    sys.exit("Require pairs in puzzle data file")

if 'edges' in data:
    edges = data['edges']
    if len(edges) > 6:
        print("Warning: more than 6 edges given; extra will be ignored",
              file=sys.stderr)
    elif len(edges) < 6:
        print("Warning: fewer than 6 edges given; remainder will be blank",
              file=sys.stderr)
        edges += [""] * 6
else:
    edges = [""] * 6

dsubs['tablepairs'] = ''
dsubs['tableedges'] = ''

for p in pairs:
    dsubs['tablepairs'] += r'{}&{}\\\hline{}'.format(p[0], p[1], "\n")
for e in range(6):
    dsubs['tableedges'] += r'\strut {}\\\hline{}'.format(edges[e], "\n")

for i in range(6):
    if random.choice([True, False]):
        pairs[i][0], pairs[i][1] = pairs[i][1], pairs[i][0]

trianglesolcard = [[]] * 6
trianglepuzorient = [[]] * 6
trianglepuzcard = [[]] * 6

# This needs to go in a smallhexagon template module
# List: base, side 2, side 3 (anticlockwise)
trianglesolcard[0] = [pairs[0][1], pairs[1][0], edges[0]]
trianglesolcard[1] = [edges[1], pairs[1][1], pairs[2][0]]
trianglesolcard[2] = [pairs[3][0], edges[2], pairs[2][1]]
trianglesolcard[3] = [pairs[3][1], pairs[4][0], edges[3]]
trianglesolcard[4] = [edges[4], pairs[4][1], pairs[5][0]]
trianglesolcard[5] = [pairs[0][0], edges[5], pairs[5][1]]

# List: direction of base side
trianglesolorient = [180, 0, 180, 0, 180, 0]

# List: direction of base side, direction of card number (from vertical)
trianglepuzorient[0] = [180,  30]
trianglepuzorient[1] = [0  , -30]
trianglepuzorient[2] = [180,  30]
trianglepuzorient[3] = [0,   -30]
trianglepuzorient[4] = [180,  30]
trianglepuzorient[5] = [0,   -30]

triangleorder = list(range(6))
random.shuffle(triangleorder)

# underline 6 and 9
def cardnum(n):
    if n in [6, 9]:
        return r'\underline{{{}}}'.format(n)
    else:
        return str(n)

# We will put solution card i in puzzle position triangleorder[i],
# rotated by a random amount
for i in range(6):
    j = triangleorder[i]
    rot = random.randint(0, 2) # anticlockwise rotation
    trianglepuzcard[j] = [trianglesolcard[i][(3 - rot) % 3],
                          trianglesolcard[i][(4 - rot) % 3],
                          trianglesolcard[i][(5 - rot) % 3],
                          cardnum(j + 1), trianglepuzorient[j][1]]
    # What angle does the card number go in the solution?
    # angle of puzzle card + (orientation of sol card - orientation of
    # puz card) - rotation angle [undoing rotation]
    angle = trianglepuzorient[j][1] + \
            (trianglesolorient[i] - trianglepuzorient[j][0]) - \
            120 * rot
    trianglesolcard[i].extend([cardnum(j + 1), (angle + 180) % 360 - 180])

    dsubs['solutioncard' + str(i + 1)] = ('{{{}}}' * 5).\
        format(*trianglesolcard[i])
    dsubs['problemcard' + str(j + 1)] = ('{{{}}}' * 5).\
        format(*trianglepuzcard[j])

# Testing:
# for i in range(6):
#     print("Sol card {}: ({}, {}, {}), num angle {}".\
#               format(i, trianglesolcard[i][0], trianglesolcard[i][1], trianglesolcard[i][2], trianglesolcard[i][4]))
# 
# for i in range(6):
#     print("Puz card {}: ({}, {}, {}), num angle {}".\
#               format(i, trianglepuzcard[i][0], trianglepuzcard[i][1], trianglepuzcard[i][2], trianglepuzcard[i][3]))

btext = losub(bodytable, dsubs)
print(btext, file=outtable)
outtable.close()

ptext = losub(bodypuz, dsubs)
print(ptext, file=outpuz)
outpuz.close()

stext = losub(bodysol, dsubs)
print(stext, file=outsol)
outsol.close()
