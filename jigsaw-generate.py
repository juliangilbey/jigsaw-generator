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

#####################################################################

# Functions.  These might get moved out to separate modules for
# clarity at some point in the near future.

# LaTeX font sizes
sizes = [r'\tiny',
         r'\scriptsize',
         r'\footnotesize',
         r'\small',
         r'\normalsize',
         r'\large',
         r'\Large',
         r'\LARGE',
         r'\huge',
         r'\Huge'
         ]
normalsize = 4

def losub(text, subs):
    """Substitute <: var :> strings in text using the dict subs"""
    def subtext(matchobj):
        if matchobj.group(1) in subs:
            return subs[matchobj.group(1)]
        else:
            print('Unrecognised substitution: %s' % matchobj.group(0),
                  file=sys.stderr)
    return re.sub(r'<:\s*(\S*)\s*:>', subtext, text)

def make_entry(entry, defaultsize, hide):
    """Convert a YAML entry into a LaTeX-formatted entry

    The YAML entry will either be a simple text entry, or it will be a
    dictionary with required key "text" and optional entries "size"
    and "hidden".

    In the latter case, the result will be an empty string if "hidden"
    (from the YAML file) is true and the make_entry parameter hide is
    True, otherwise the text will be output.

    If there is a "size" key, this will be added to the defaultsize.
    The output will have the text with the appropriate LaTeX size
    command prepended."""

    if isinstance(entry, dict):
        if 'text' not in entry:
            print('No "text" field in entry in data file.  Rest of data is:\n',
                  file=sys.stderr)
            for f in entry:
                print('  %s: %s\n' % (f, entry[f]), file=sys.stderr)
            return ''
            
        if hide and 'hidden' in entry and entry['hidden']:
            return ''
        if 'size' in entry:
            try:
                size = defaultsize + int(entry['size'])
                if size < 0:
                    size = 0
                if size >= len(sizes):
                    size = len(sizes) - 1
            except:
                print('Unrecognised size entry for text %(text)s:\n'
                      'size = %(size)s\n'
                      'Defaulting to default size\n' %
                      entry, file=sys.stderr)
                size = defaultsize
        else:
            size = defaultsize

        return "%s %s" % (sizes[size], entry['text'])
    else:
        return "%s %s" % (sizes[defaultsize], entry)

#####################################################################

# The actions

# Command line:
#   jigsaw-generate [options] puzzlefile[.yaml]
# There are no options at present, but this may change later

# Step 1: Open the file

parser = argparse.ArgumentParser()
parser.add_argument('puzfile', metavar='puzzlefile[.yaml]',
                    help='yaml file containing puzzle data')
args = parser.parse_args()
if args.puzfile[-5:] == '.yaml':
    puzfile = args.puzfile
else:
    puzfile = args.puzfile + '.yaml'
puzbase = puzfile[:-5]

try:
    infile = open(puzfile)
except:
    sys.exit('Cannot open %s for reading' % puzfile)

try:
    data = load(infile, Loader=Loader)
except yaml.YAMLError, exc:
    if hasattr(exc, 'problem_mark'):
        mark = exc.problem_mark
        sys.exit('Error parsing puzzle data file\nError position: line %s, column %s' % (mark.line+1, mark.column+1))
else:
    sys.exit('Error parsing data file: %s' % exc)

knowntypes = {
    'smallhexagon': jigsaw.jigsaw
}

if 'type' in data and data['type'] in knowntypes:
    puztype = data['type']
elif 'type' in data:
    sys.exit('Unrecognised jigsaw type %s' % data['type'])
else:
    sys.exit('No jigsaw type found in puzzle file')

# Step 2: Open template files and layout file.  ***FIXME*** At some
# point, this should be modified to allow for local versions, and also
# to search in the system directory for these files.  At present, they
# are expected to be in the local directory.

layoutf = open(puztype + '.yaml')
layout = load(layoutf, Loader=Loader)

try:
    headerf = open('template-' + puztype + '-header.tex')
except:
    headerf = open('template-header.tex')
header = headerf.read()

try:
    bodytablef = open('template-' + puztype + '-table.tex')
except:
    bodytablef = open('template-table.tex')
bodytable = bodytablef.read()

# ***FIXME*** Hmm, card sorts or dominoes may not have a solution.
# We'll come back to this point.
bodypuzf = open('template-' + puztype + '-puzzle.tex')
bodypuz = bodypuzf.read()

bodysolf = open('template-' + puztype + '-solution.tex')
bodysol = bodysolf.read()

# ***FIXME*** The output filenames should be specifiable on the
# command line.  Also, not every puzzle type may do all three of
# these, so they should be conditional.
outpuz = open(puzbase + '-puzzle.tex', 'w')
outsol = open(puzbase + '-solution.tex', 'w')
outtable = open(puzbase + '-table.tex', 'w')

# ***FIXME*** Should all three have the same header?
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

if 'puzzleTextSize' in data:
    puzzleTextSize = data['puzzleTextSize']
else:
    puzzleTextSize = layout['puzzleTextSize']

if 'solutionTextSize' in data:
    solutionTextSize = data['solutionTextSize']
else:
    solutionTextSize = layout['solutionTextSize']

# Read the card content
# Three types of cards: pairs, edges, cards (which are single cards
# for sorting activities)
if 'pairs' in layout:
    if 'pairs' in data:
        pairs = data['pairs']
        if layout['pairs'] == 0:  # which means any number of pairs
            if len(pairs) == 0:
                sys.exit('Puzzle type %s needs at least one pair' %
                         layout['typename'])
        else:
            if len(pairs) != layout['pairs']:
                sys.exit('Puzzle type %s needs exactly %s pairs' %
                         (layout['typename'], layout['pairs']))
    else:
        sys.exit('Puzzle type %s requires pairs in data file' %
                 layout['typename'])
elif 'pairs' in data:
    sys.exit('Puzzle type %s does not accept pairs in data file' %
             layout['typename'])

if 'edges' in layout:
    if 'edges' in data:
        edges = data['edges']
        if len(edges) > layout['edges']:
            print('Warning: more than %s edges given; extra will be ignored' %
                  layout['edges'], file=sys.stderr)
            edges = edges[:layout['edges']]
        elif len(edges) < layout['edges']:
            print('Warning: fewer than %s edges given; remainder will be blank'
                  % layout['edges'], file=sys.stderr)
            edges += [''] * (layout['edges'] - len(edges))
    else:
        edges = [''] * layout['edges']
elif 'edges' in data:
    sys.exit('Puzzle type %s does not accept edges in data file' %
             layout['typename'])

if 'cards' in layout:
    if 'cards' in data:
        cards = data['cards']
        if layout['cards'] == 0:
            if len(cards) == 0:
                sys.exit('Puzzle type %s needs at least one card' %
                         layout['typename'])
        else:
            if len(cards) != layout['cards']:
                sys.exit('Puzzle type %s needs exactly %s cards' %
                         (layout['typename'], layout['cards']))
    else:
        sys.exit('Puzzle type %s requires cards in data file' %
                 layout['typename'])
elif 'cards' in data:
    sys.exit('Puzzle type %s does not accept cards in data file' %
             layout['typename'])


dsubs['tablepairs'] = ''
dsubs['tableedges'] = ''
dsubs['tablecards'] = ''

for p in pairs:
    dsubs['tablepairs'] += (r'%s&%s\\ \hline%s' %
                            (make_entry(p[0], normalsize, False),
                             make_entry(p[1], normalsize, False), '\n'))
for e in edges:
    dsubs['tableedges'] += (r'\strut %s\\ \hline%s' %
                            (make_entry(e, normalsize, False), '\n'))

for c in cards:
    dsubs['tablecards'] += (r'\strut %s\\ \hline%s' %
                            (make_entry(c, normalsize, False), '\n'))

if 'triangleSolutionCards' in layout:
    numSolutionCards = len(layout['triangleSolutionCards'])

    if layout['flip']:
        for p in pairs:
            if random.choice([True, False]):
                p[0], p[1] = p[1], p[0]

    # We read the solution layout from the YAML file, and place the
    # data into our lists.  We don't format them yet, as the
    # formatting may be different for the puzzle and solution

    trianglesolcard = []
    for card in layout['triangleSolutionCards']:
        newcard = []
        for entry in card:
            entrynum = int(entry[1:])
            if entry[0] == 'Q':
                newcard.append(pairs[entrynum][0])
            elif entry[0] == 'A':
                newcard.append(pairs[entrynum][1])
            elif entry[0] == 'E':
                newcard.append(edges[entrynum])
            else:
                printf("Unrecognised entry in layout file (triangleSolutionCards): %s"
                       % card)
        trianglesolcard.append(newcard)

********
# List: direction of base side
trianglesolorient = [180, 0, 180, 0, 180, 0]

# List: direction of base side, direction of card number (from vertical)
trianglepuzorient = []
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
        return r'\underline{%s}' % n
    else:
        return str(n)

trianglepuzcard = []

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
#     print('Sol card %s: (%s, %s, %s), num angle %s' %
#            (i, trianglesolcard[i][0], trianglesolcard[i][1], trianglesolcard[i][2], trianglesolcard[i][4]))
# 
# for i in range(6):
#     print('Puz card %s: (%s, %s, %s), num angle %s' %
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
