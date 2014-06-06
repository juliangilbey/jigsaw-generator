#! /usr/bin/python3

import random
import sys
import os
import re
import argparse
import subprocess

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

#####################################################################

# Utility functions and global definitions.  These might get moved out
# to separate modules for clarity at some point in the near future.

knowntypes = {
    'smallhexagon'
}

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

def getopt(layout, data, options, opt):
    """Determine the value of opt from various possible sources

    Check the command-line options first for this option, then the
    data, then finally the layout; return the first value found, or
    None if the option is not found anywhere.
    """
    if opt in options:
        return options[opt]
    if opt in data:
        return data[opt]
    if opt in layout:
        return layout[opt]
    return None

def losub(text, subs):
    """Substitute <: var :> strings in text using the dict subs"""
    def subtext(matchobj):
        if matchobj.group(1) in subs:
            return subs[matchobj.group(1)]
        else:
            print('Unrecognised substitution: %s' % matchobj.group(0),
                  file=sys.stderr)
    return re.sub(r'<:\s*(\S*)\s*:>', subtext, text)

def make_entry(entry, defaultsize, hide, usesize=True):
    """Convert a YAML entry into a LaTeX-formatted entry

    The YAML entry will either be a simple text entry, or it will be a
    dictionary with required key "text" and optional entries "size"
    and "hidden".

    In the latter case, the result will be an empty string if "hidden"
    (from the YAML file) is true and the make_entry parameter hide is
    True, otherwise the text will be output.

    If there is a "size" key, this will be added to the defaultsize.
    The output will have the text with the appropriate LaTeX size
    command prepended, unless usesize is False.
    """

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

        if usesize:
            return '%s %s' % (sizes[size], entry['text'])
        else:
            # Force it to be a string
            return '%s' % entry['text']
    else:
        if usesize:
            return '%s %s' % (sizes[defaultsize], entry)
        else:
            # Force it to be a string
            return '%s' % entry

def cardnum(n):
    """Underline 6 and 9; return everything else as a string"""
    if n in [6, 9]:
        return r'\underline{%s}' % n
    else:
        return str(n)

def make_table(pairs, edges, cards, dsubs, dsubsmd):
    """Create table substitutions for the pairs, edges and cards"""
    dsubs['tablepairs'] = ''
    dsubs['tableedges'] = ''
    dsubs['tablecards'] = ''
    dsubsmd['pairs'] = ''
    dsubsmd['edges'] = ''
    dsubsmd['cards'] = ''

    for p in pairs:
        dsubs['tablepairs'] += ((r'%s&%s\\ \hline' '\n') %
                                (make_entry(p[0], normalsize, False),
                                 make_entry(p[1], normalsize, False)))
        row = '|'
        for entry in p:
            mdentry = make_entry(entry, normalsize, False, usesize=False)
            if mdentry:
                row += ' ' + mdentry + ' |'
            else:
                row += ' (BLANK) |'
        dsubsmd['pairs'] += row + '\n'
        
    for e in edges:
        dsubs['tableedges'] += ((r'\strut %s\\ \hline' '\n') %
                                make_entry(e, normalsize, False))
        mdentry = make_entry(e, normalsize, False, usesize=False)
        if mdentry:
            dsubsmd['edges'] += '| ' + mdentry + ' |\n'
        else:
            dsubsmd['edges'] += '| (BLANK) |\n'

    for c in cards:
        dsubs['tablecards'] += ((r'\strut %s\\ \hline' '\n') %
                                make_entry(c, normalsize, False))
        mdentry = make_entry(c, normalsize, False, usesize=False)
        if mdentry:
            dsubsmd['cards'] += '| ' + mdentry + ' |\n'
        else:
            dsubsmd['cards'] += '| (BLANK) |\n'


def make_triangles(data, layout, pairs, edges, dsubs, dsubsmd):
    num_triangle_cards = len(layout['triangleSolutionCards'])

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
                printf('Unrecognised entry in layout file '
                       '(triangleSolutionCards):\n%s' % card)
        trianglesolcard.append(newcard)

    # List: direction of base side
    trianglesolorient = layout['triangleSolutionOrientation']

    # List: direction of base side, direction of card number (from vertical)
    trianglepuzorient = layout['trianglePuzzleOrientation']

    triangleorder = list(range(num_triangle_cards))
    random.shuffle(triangleorder)

    trianglepuzcard = [[]] * num_triangle_cards

    # We will put solution card i in puzzle position triangleorder[i],
    # rotated by a random amount
    for i in range(num_triangle_cards):
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

        dsubs['trisolcard' + str(i + 1)] = (('{%s}' * 5) %
                                            tuple(trianglesolcard[i]))
        dsubs['tripuzcard' + str(j + 1)] = (('{%s}' * 5) %
                                            tuple(trianglepuzcard[j]))

    # For the Markdown version, we only need to record the puzzle cards at
    # this point.

    if 'puzcards3' not in dsubsmd:
        dsubsmd['puzcards3'] = ''
        dsubsmd['puzcards4'] = ''

    for t in trianglepuzcard:
        row = '|'
        for entry in t[0:3]:
            mdentry = make_entry(entry, normalsize, False, usesize=False)
            if mdentry:
                row += ' ' + mdentry + ' |'
            else:
                row += ' (BLANK) |'
        dsubsmd['puzcards3'] += row + '\n'
        dsubsmd['puzcards4'] += row + ' &nbsp; |\n'

    # Testing:
    # for (i, card) in enumerate(trianglesolcard):
    #     print('Sol card %s: (%s, %s, %s), num angle %s' %
    #            (i, card[0], card[1], card[2], card[4]))
    # 
    # for (i, card) in enumerate(trianglepuzcard):
    #     print('Puz card %s: (%s, %s, %s), num angle %s' %
    #            (i, card[0], card[1], card[2], card[3]))



#####################################################################

def main():
    """Process the command line and generate the appropriate output files.

    Command line:
       jigsaw-generate [options] puzzlefile[.yaml]
    There are no options at present, but this will change later.

    We will generate both LaTeX output files and (eventually) a
    markdown file which can be included where needed.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('puzfile', metavar='puzzlefile[.yaml]',
                        help='yaml file containing puzzle data')
    args = parser.parse_args()

    if args.puzfile[-5:] == '.yaml':
        puzfile = args.puzfile
    else:
        puzfile = args.puzfile + '.yaml'
    puzbase = puzfile[:-5]

    # We may well have more options in the future
    options = { 'puzbase': puzbase }

    try:
        infile = open(puzfile)
    except:
        sys.exit('Cannot open %s for reading' % puzfile)

    try:
        data = load(infile, Loader=Loader)
    except yaml.YAMLError as exc:
        if hasattr(exc, 'problem_mark'):
            mark = exc.problem_mark
            sys.exit('Error parsing puzzle data file\n'
                     'Error position: line %s, column %s' %
                     (mark.line+1, mark.column+1))

    if 'type' in data:
        if data['type'] not in knowntypes:
            sys.exit('Unrecognised jigsaw type %s' % data['type'])
    else:
        sys.exit('No jigsaw type found in puzzle file')

    generate_jigsaw(data, options)


def generate_jigsaw(data, options):
    """Generate jigsaw output from data, using options passed to this function.

    Thus function is presently called from main(), but might well be
    called from a GUI at some point in the future, which is why it has
    been separated out.

    When this function is called, data must contain a recognised
    jigsaw type, and the options dictionary must contain an entry
    'puzbase' with the file basename for this particular puzzle.
    """

    # Open template files and layout file.

    # ***FIXME*** At some point, this should be modified to allow for
    # local versions of template files, and also to search in the
    # system directory (wherever that may be) for these files.  At
    # present, they are expected to be in the local directory.

    puztype = data['type']
    puzbase = options['puzbase']

    layoutf = open(puztype + '.yaml')
    try:
        layout = load(layoutf, Loader=Loader)
    except yaml.YAMLError as exc:
        if hasattr(exc, 'problem_mark'):
            mark = exc.problem_mark
            sys.exit('Error parsing puzzle layout file %s.yaml\n'
                     'Error position: line %s, column %s' %
                     (puztype, mark.line+1, mark.column+1))

    # ***FIXME*** The output filenames should be specifiable on the
    # command line.  Also, there should be options for which outputs
    # to produce.

    if 'puzzleTemplateTeX' in layout:
        bodypuz = open(layout['puzzleTemplateTeX']).read()
        outpuzfile = puzbase + '-puzzle.tex'
        outpuz = open(outpuzfile, 'w')
        header = open(layout['puzzleHeaderTeX']).read()
        print(header, file=outpuz)
        puzzletex = True
    else:
        puzzletex = False

    if 'solutionTemplateTeX' in layout:
        bodysol = open(layout['solutionTemplateTeX']).read()
        outsolfile = puzbase + '-solution.tex'
        outsol = open(outsolfile, 'w')
        header = open(layout['solutionHeaderTeX']).read()
        print(header, file=outsol)
        solutiontex = True
    else:
        solutiontex = False

    if 'tableTemplateTeX' in layout:
        bodytable = open(layout['tableTemplateTeX']).read()
        outtablefile = puzbase + '-table.tex'
        outtable = open(outtablefile, 'w')
        header = open(layout['tableHeaderTeX']).read()
        print(header, file=outtable)
        tabletex = True
    else:
        tabletex = False

    if 'puzzleTemplateMarkdown' in layout:
        bodypuzmd = open(layout['puzzleTemplateMarkdown']).read()
        outpuzmdfile = puzbase + '-puzzle.md'
        outpuzmd = open(outpuzmdfile, 'w')
        header = open(layout['puzzleHeaderMarkdown']).read()
        print(header, file=outpuzmd)
        puzzlemd = True
    else:
        puzzlemd = False

    if 'solutionTemplateMarkdown' in layout:
        bodysolmd = open(layout['solutionTemplateMarkdown']).read()
        outsolmdfile = puzbase + '-solution.md'
        outsolmd = open(outsolmdfile, 'w')
        header = open(layout['solutionHeaderMarkdown']).read()
        print(header, file=outsolmd)
        solutionmd = True
    else:
        solutionmd = False

    # These dicts will contain the substitutions needed for the
    # template files; the first is for the LaTeX output files, the
    # second is for the Markdown output files.

    # The Markdown output files are much simpler, as they are intended
    # to be embedded in larger documents, for those who cannot access
    # the PDF files.
    dsubs = dict()
    dsubsmd = dict()

    if 'title' in data:
        dsubs['title'] = data['title']
    else:
        dsubs['title'] = ''
    random.seed(dsubs['title'])

    if 'puzzleTextSize' in data:
        puzzle_text_size = data['puzzleTextSize']
    else:
        puzzle_text_size = layout['puzzleTextSize']

    if 'solutionTextSize' in data:
        solution_text_size = data['solutionTextSize']
    else:
        solution_text_size = layout['solutionTextSize']

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
    else:
        pairs = []  # so that later bits of code don't barf

    if 'edges' in layout:
        if 'edges' in data:
            edges = data['edges']
            if len(edges) > layout['edges']:
                print('Warning: more than %s edges given; '
                      'extra will be ignored' % layout['edges'],
                      file=sys.stderr)
                edges = edges[:layout['edges']]
            elif len(edges) < layout['edges']:
                print('Warning: fewer than %s edges given; '
                      'remainder will be blank' % layout['edges'],
                      file=sys.stderr)
                edges += [''] * (layout['edges'] - len(edges))
        else:
            edges = [''] * layout['edges']
    elif 'edges' in data:
        sys.exit('Puzzle type %s does not accept edges in data file' %
                 layout['typename'])
    else:
        edges = []  # so that later bits of code don't barf

    if 'cards' in layout:
        if 'cards' in data:
            cards = data['cards']
            if layout['cards'] == 0:  # which means any number of cards
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
    else:
        cards = []

    if getopt(layout, data, options, 'shufflePairs'):
        random.shuffle(pairs)
    if getopt(layout, data, options, 'shuffleEdges'):
        random.shuffle(edges)
    if getopt(layout, data, options, 'shuffleCards'):
        random.shuffle(cards)

    # We preserve the original pairs data for the table; we only flip
    # the questions and answers (if requested) for the puzzle cards
    if getopt(layout, data, options, 'flip'):
        flippedpairs = []
        for p in pairs:
            if random.choice([True, False]):
                flippedpairs.append([p[1], p[0]])
            else:
                flippedpairs.append([p[0], p[1]])
    else:
        flippedpairs = pairs

    # The following calls will add the appropriate substitution
    # variables to dsubs and dsubsmd
    if tabletex or solutionmd:
        make_table(pairs, edges, cards, dsubs, dsubsmd)

    if 'triangleSolutionCards' in layout:
        make_triangles(data, layout, flippedpairs, edges, dsubs, dsubsmd)

    if tabletex:
        btext = losub(bodytable, dsubs)
        print(btext, file=outtable)
        outtable.close()
        ret = subprocess.call(['lualatex', '--interaction=batchmode',
                               outtablefile], stdout=subprocess.DEVNULL)
        if ret:
            print("Warning: lualatex %s failed, return value %s" %
                  (outtablefile, ret), file=sys.stderr)

    if puzzletex:
        ptext = losub(bodypuz, dsubs)
        print(ptext, file=outpuz)
        outpuz.close()
        ret = subprocess.call(['lualatex', '--interaction=batchmode',
                               outpuzfile], stdout=subprocess.DEVNULL)
        if ret:
            print("Warning: lualatex %s failed, return value %s" %
                  (outpuzfile, ret), file=sys.stderr)

    if solutiontex:
        stext = losub(bodysol, dsubs)
        print(stext, file=outsol)
        outsol.close()
        ret = subprocess.call(['lualatex', '--interaction=batchmode',
                               outsolfile], stdout=subprocess.DEVNULL)
        if ret:
            print("Warning: lualatex %s failed, return value %s" %
                  (outsolfile, ret), file=sys.stderr)

    if puzzlemd:
        ptextmd = losub(bodypuzmd, dsubsmd)
        print(ptextmd, file=outpuzmd)
        outpuzmd.close()

    if solutionmd:
        stextmd = losub(bodysolmd, dsubsmd)
        print(stextmd, file=outsolmd)
        outsolmd.close()


# This allows this script to be invoked directly and also (hopefully
# at some later stage) for the functions to be called via a GUI
if __name__ == '__main__':
    main()
