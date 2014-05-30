#! /usr/bin/python3

import random
import sys
import os
import re
import argparse

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

parser = argparse.ArgumentParser()
parser.add_argument("puzfile", metavar="puzzlefile[.yaml]",
                    help="yaml file containing puzzle data")
args = parser.parse_args()
if args.puzfile[-5:] == '.yaml':
    puzfile = args.puzfile
else:
    puzfile = args.puzfile + '.yaml'
puzbase = puzfile[:-5]

knowntypes = {
    'smallhexagon': True
}

def losub(text, subs):
    """Substitute <:= var :> strings in text using the dict subs"""
    def subtext(matchobj):
        if matchobj.group(1) in subs:
            return subs[matchobj.group(1)]
        else:
            print("Unrecognised substitution: %s" % matchobj.group(0),
                  file=sys.stderr)
    return re.sub(r"<:=\s*(\S*)\s*:>", subtext, text)

# This will be taken from command line parameter soon!
try:
    infile = open(puzfile)
except:
    sys.exit("Cannot open %s for reading" % puzfile)

headerf = open("template-header.tex")
bodytablef = open("template-table.tex")

data = load(infile, Loader=Loader)

if 'type' in data and data['type'] in knowntypes:
    puztype = data['type']
elif 'type' in data:
    sys.exit("Unrecognised jigsaw type %s" % data['type'])
else:
    sys.exit("No jigsaw type found in puzzle file")

layoutf = open(puztype + ".yaml")
bodypuzf = open("template-" + puztype + "-puzzle.tex")
bodysolf = open("template-" + puztype + "-solution.tex")
layout = load(layoutf, Loader=Loader)

bodypuz = bodypuzf.read()
bodysol = bodysolf.read()
bodytable = bodytablef.read()

outpuz = open(puzbase + "-puzzle.tex", "w")
outsol = open(puzbase + "-solution.tex", "w")
outtable = open(puzbase + "-table.tex", "w")

header = headerf.read()
print(header, file=outpuz)
print(header, file=outsol)
print(header, file=outtable)

# This dict will contain the substitutions needed for the template
# files
dsubs = dict()

if 'title' in data:
    dsubs['title'] = data['title']
else:
    dsubs['title'] = ''
random.seed(dsubs['title'])

# Read the card content
# Three types of cards: pairs, edges, cards (which are single cards
# for sorting activities)
if 'pairs' in layout:
    if 'pairs' in data:
        pairs = data['pairs']
        if layout['pairs'] == 0:
            if len(pairs) == 0:
                sys.exit("Puzzle type %s needs at least one pair" %
                         layout['typename'])
        else:
            if len(pairs) != layout['pairs']:
                sys.exit("Puzzle type %s needs exactly %s pairs" %
                         (layout['typename'], layout['pairs']))
    else:
        sys.exit("Puzzle type %s requires pairs in data file" %
                 layout['typename'])
elif 'pairs' in data:
    sys.exit("Puzzle type %s does not accept pairs in data file" %
             layout['typename'])

if 'edges' in layout:
    if 'edges' in data:
        edges = data['edges']
        if len(edges) > layout['edges']:
            print("Warning: more than %s edges given; extra will be ignored" %
                  layout['edges'], file=sys.stderr)
            edges = edges[:layout['edges']]
        elif len(edges) < layout['edges']:
            print("Warning: fewer than %s edges given; remainder will be blank"
                  % layout['edges'], file=sys.stderr)
            edges += [""] * (layout['edges'] - len(edges))
    else:
        edges = [""] * layout['edges']
elif 'edges' in data:
    sys.exit("Puzzle type %s does not accept edges in data file" %
             layout['typename'])

if 'cards' in layout:
    if 'cards' in data:
        cards = data['cards']
        if layout['cards'] == 0:
            if len(cards) == 0:
                sys.exit("Puzzle type %s needs at least one cards" %
                         layout['typename'])
        else:
            if len(cards) != layout['cards']:
                sys.exit("Puzzle type %s needs exactly %s cards" %
                         (layout['typename'], layout['cards']))
    else:
        sys.exit("Puzzle type %s requires cards in data file" %
                 layout['typename'])
elif 'cards' in data:
    sys.exit("Puzzle type %s does not accept cards in data file" %
             layout['typename'])


dsubs['tablepairs'] = ''
dsubs['tableedges'] = ''
dsubs['tablecards'] = ''

for p in pairs:
    dsubs['tablepairs'] += (r'%s&%s\\ \hline%s' %
                            (make_entry(p[0]), make_entry(p[1]), "\n"))
for e in edges:
    dsubs['tableedges'] += r'\strut %s\\ \hline%s' % (make_entry(e), "\n")

for c in cards:
    dsubs['tablecards'] += r'\strut %s\\ \hline%s' % (make_entry(c), "\n")

for i in range(6):
    if random.choice([True, False]):
        pairs[i][0], pairs[i][1] = pairs[i][1], pairs[i][0]

trianglesolcard = [[]] * 6
trianglepuzorient = [[]] * 6
trianglepuzcard = [[]] * 6

# This needs to go in a smallhexagon template module
# List: base, side 2, side 3 (anticlockwise)
trianglesolcard[0] = [pairs[0][0], edges[0], pairs[5][1]]
trianglesolcard[1] = [edges[1], pairs[4][1], pairs[5][0]]
trianglesolcard[2] = [pairs[3][1], pairs[4][0], edges[2]]
trianglesolcard[3] = [pairs[3][0], edges[3], pairs[2][1]]
trianglesolcard[4] = [edges[4], pairs[1][1], pairs[2][0]]
trianglesolcard[5] = [pairs[0][1], pairs[1][0], edges[5]]

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
        return r'\underline{%d}' % n
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
    angle = (trianglepuzorient[j][1] +
             (trianglesolorient[i] - trianglepuzorient[j][0]) -
             120 * rot)
    trianglesolcard[i].extend([cardnum(j + 1), (angle + 180) % 360 - 180])

    dsubs['solutioncard' + str(i + 1)] = (('{%s}' * 5) %
                                          tuple(trianglesolcard[i]))
    dsubs['problemcard' + str(j + 1)] = (('{%s}' * 5) %
                                         tuple(trianglepuzcard[j]))

# Testing:
# for i in range(6):
#     print("Sol card %d: (%s, %s, %s), num angle %d" %
#            (i, trianglesolcard[i][0], trianglesolcard[i][1], trianglesolcard[i][2], trianglesolcard[i][4]))
# 
# for i in range(6):
#     print("Puz card %d: (%s, %s, %s), num angle %d" %
#            (i, trianglepuzcard[i][0], trianglepuzcard[i][1], trianglepuzcard[i][2], trianglepuzcard[i][3]))

btext = losub(bodytable, dsubs)
print(btext, file=outtable)
outtable.close()

ptext = losub(bodypuz, dsubs)
print(ptext, file=outpuz)
outpuz.close()

stext = losub(bodysol, dsubs)
print(stext, file=outsol)
outsol.close()
