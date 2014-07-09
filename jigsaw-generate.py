#! /usr/bin/env python3

"""
jigsaw-generate.py
Copyright (C) 2014 Julian Gilbey <J.Gilbey@maths.cam.ac.uk>, <jdg@debian.org>
This program comes with ABSOLUTELY NO WARRANTY.
This is free software, and you are welcome to redistribute it
under certain conditions; see the LICENSE file for details.
"""

import random
import sys
import os
import os.path
import re
import argparse
import subprocess

import yaml
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

#####################################################################

# Utility functions and global definitions.  These might get moved out
# to separate modules for clarity at some point in the near future.

# Template directory
# This may change once we figure out how to do so ;-)
templatedir = '/usr/share/jigsaw'

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

# Is any entry marked as hidden?
exists_hidden = False

def getopt(layout, data, options, opt, default=None):
    """Determine the value of opt from various possible sources

    Check the command-line options first for this option, then the
    data, then finally the layout; return the first value found, or
    default if the option is not found anywhere.
    """
    if opt in options:
        return options[opt]
    if opt in data:
        return data[opt]
    if opt in layout:
        return layout[opt]
    return default

def dosub(text, subs):
    """Substitute <: var :> strings in text using the dict subs"""
    def subtext(matchobj):
        if matchobj.group(1) in subs:
            return str(subs[matchobj.group(1)])
        else:
            print('Unrecognised substitution: %s' % matchobj.group(0),
                  file=sys.stderr)
    return re.sub(r'<:\s*(\S*?)\s*:>', subtext, text)

def opentemplate(name):
    """Searches for and then opens a template file.

    Search first in the current directory, then look in the templates
    directory.  This is currently OS-dependent; this will need making
    OS-independent in the near future.
    """
    
    ### ***FIXME*** this is OS-specific and relies on filesystem
    ### layout; perhaps change to wheel system and use its
    ### facilities for file finding; see
    ### http://pythonwheels.com/ as a starting point
    try:
        f = open(name)
    except:
        try:
            f = open('templates/' + name)
        except:
            f = open(os.path.join(templatedir, name))

        ### ***FIXME*** Once I know how to write new exceptions, use
        ### that here so that I can throw a catchable exception should
        ### I wish to.  For the time being, each calling function will
        ### have to catch the exception individually to produce a
        ### sensible error message

        # except:
        #    sys.exit('Template file %s could not be found or opened' %
        #             name)
    return f

def check_special(c):
    """Check whether a card or domino is special

    Special entries currently recognised are:

    "- newpage: true"
       this produces a new page in the PDF cards output, but nothing
       in the table or Markdown outputs
    "- newlabel: text"
    "- newlabelsize: num"
       these will change the default label

    The function returns either None if the entry is not special, or a
    dict with entries (t, cont) where t is the type of special entry
    ('newpage', 'label' or 'labelsize') and cont is the related
    content.

    Multiple entries in one card/domino are therefore permitted, but
    'text' is not permitted in such a card, and neither is domino data.

    This function also performs some basic checks to ensure that the
    card or domino entries are well-formed.
    """

    if isinstance(c, dict):
        special = False
        if 'newpage' in c:
            special = True
            if c['newpage'] != True:
                print('Invalid value for newpage, only newpage: True '
                      'permitted\nCard/Domino value: %s' % c['newpage'],
                      file=sys.stderr)
                c['newpage'] = True
        if 'newlabel' in c:
            special = True
            if not isinstance(c['newlabel'], str):
                print('Invalid value for newlabel entry: it must be a string.\n'
                      'Entry value: %s' % c['newlabel'],
                      file=sys.stderr)
                del c['newlabel']
        if 'newlabelsize' in c:
            special = True
            if not isinstance(c['newlabelsize'], int):
                c['newlabelsize'] = int(c['newlabelsize'])
        if special:
            if 'text' in c:
                print('Cannot have a special entry (newpage, newlabel, '
                      'newlabelsize) and text\n'
                      'on same card!  Ignoring special requests.',
                      file=sys.stderr)
                return None
            else:
                return c
    else:
        return None

def make_entry(entry, defaultsize, hide, style,
               defaultlabel='', defaultlabelsize=0, blank='(BLANK)'):
    """Convert a YAML entry into a LaTeX or Markdown formatted entry

    Returns the pair (text, label).

    The text is the content to be used for the LaTeX or Markdown.  The
    label is only of interest for card sorts and similar activities;
    it is ignored for jigsaws.

    The YAML entry will either be a simple text entry, or it will be a
    dictionary with required key "text" and optional entries "size",
    "hidden" and "label".

    If there is a "size" key, this will be added to the defaultsize.

    If there is a "label" key, this will override the current default
    label; similarly for the "labelsize" key.

    The "hide" parameter can be:
      "hide": the text will be hidden if "hidden" is true
      "mark": the text will be highlighted if "hidden" is true
      "ignore": the "hidden" key will be ignored

    The "style" parameter can be:
      "table": outputs text with no size marker; highlighted hidden
               text will be prepended with "(*)"
      "tikz":  outputs {regular}{size text} or {hidden}{size text},
               where {hidden} highlights the text
      "md":    outputs text for Markdown: highlighted hidden text will
               be prepended with "(*)"; blank text will be replaced by
               "(BLANK)" or the setting of the blank parameter, and
               all entries will be surrounded on either side by a
               blank space.  There is no size marker.

    """

    label = make_entry_label(entry, style, defaultlabel, defaultlabelsize)

    if isinstance(entry, dict):
        if 'text' not in entry:
            print('No "text" field in entry in data file.  Rest of data is:\n',
                  file=sys.stderr)
            for f in entry:
                print('  %s: %s\n' % (f, entry[f]), file=sys.stderr)
            return (make_entry_util('', '', False, style, blank), label)

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

        if 'hidden' in entry and entry['hidden']:
            global exists_hidden
            exists_hidden = True
            if hide == 'hide':
                return (make_entry_util('', '', False, style, blank), '')
            elif hide == 'mark':
                return (make_entry_util(entry['text'], sizes[size],
                                        True, style, blank), label)
            elif hide == 'ignore':
                return (make_entry_util(entry['text'], sizes[size],
                                        False, style, blank), label)
            else:
                # this shouldn't happen
                sys.exit('This should not happen: bad hide parameter')
        else:
            return (make_entry_util(entry['text'], sizes[size],
                                    False, style, blank), label)

    else:
        return (make_entry_util(entry, sizes[defaultsize], False,
                                style, blank), label)

def make_entry_util(text, size, mark_hidden, style, blank):
    """Create the output once the text, size, hide and style are determined

    This should be called with mark_hidden being True or False; hidden
    text should be replaced by '' before this function is called.
    """

    text = text.rstrip()
    if mark_hidden:
        if style == 'table':
            return '(*) %s' % img2tex(text)
        elif style == 'tikz':
            return '{hidden}{%s %s}' % (size, img2tex(text))
        elif style == 'md':
            return '(*) %s' % text
    else:
        if style == 'table':
            return img2tex(text)
        elif style == 'tikz':
            return '{regular}{%s %s}' % (size, img2tex(text))
        elif style == 'md':
            return '%s' % (text if text else blank)

def make_entry_label(entry, style, defaultlabel, defaultlabelsize):
    if isinstance(entry, dict):
        if 'label' in entry:
            labeltext = entry['label'].rstrip()
        else:
            labeltext = defaultlabel.rstrip()

        if 'labelsize' in entry:
            labelsize = entry['labelsize']
        else:
            labelsize = defaultlabelsize
    else:
        labeltext = defaultlabel.rstrip()
        labelsize = defaultlabelsize

    if style == 'table':
        return img2tex(labeltext)
    elif style == 'tikz':
        if labeltext:
            return '%s %s' % (sizes[labelsize], img2tex(labeltext))
        else:
            return ''
    elif style == 'md':
        return labeltext

img_re = re.compile(r'!\[([^\]]*)\]\(([^\)]*)\)')

def img2tex(text):
    text = str(text)  # just in case the text is purely numeric
    images = img_re.search(text)
    while images:
        caption, img = images.groups()
        if caption:
            text = img_re.sub(r'\imagecap{%s}{%s}' % (img, caption),
                              text, count=1)
        else:
            text = img_re.sub(r'\image{%s}' % img, text, count=1)

        images = img_re.search(text)

    return text

def cardnum(n):
    """Underline 6 and 9; return everything else as a string"""
    if n in [6, 9]:
        return r'\underline{%s}' % n
    else:
        return str(n)

def make_table(pairs, edges, cards, dsubs, dsubsmd):
    """Create table substitutions for the pairs and edges"""
    dsubs['tablepairs'] = ''
    dsubs['tableedges'] = ''
    dsubs['tablecards'] = ''
    dsubsmd['pairs'] = ''
    dsubsmd['edges'] = ''
    dsubsmd['cards'] = ''

    for p in pairs:
        dsubs['tablepairs'] += ((r'%s&%s\\ \hline' '\n') %
            (make_entry(p[0], normalsize, 'mark', 'table')[0],
             make_entry(p[1], normalsize, 'mark', 'table')[0]))
        row = '|'
        for entry in p:
            row += ' ' + make_entry(entry, 0, 'mark', 'md')[0] + ' |'
        dsubsmd['pairs'] += row + '\n'
        
    for e in edges:
        dsubs['tableedges'] += ((r'\strut %s\\ \hline' '\n') %
                                make_entry(e, normalsize, 'mark', 'table')[0])
        dsubsmd['edges'] += '| ' + make_entry(e, 0, 'mark', 'md')[0] + ' |\n'

    # The next bit is only used for the PDF version of the table output,
    # so we don't make too much effort over label handling
    defaultlabel = dsubs['label'] if 'label' in dsubs else ''
    for c in cards:
        s = check_special(c)
        if s:
            if 'newlabel' in c:
                defaultlabel = c['newlabel']
            continue
        cont, label = make_entry(c, normalsize, 'mark', 'table',
                                 defaultlabel, normalsize)
        dsubs['tablecards'] += ((r'%s%s\\ \hline' '\n') %
                                (('[' + label + '] ' if label else ''), cont))
        cont, label = make_entry(c, 0, 'mark', 'md', defaultlabel)
        dsubsmd['cards'] += ('| %s%s |\n' %
                             (('[' + label + '] ' if label else ''), cont))

def make_triangles(data, layout, pairs, edges, dsubs, dsubsmd):
    """Handle triangular-shaped jigsaw pieces, putting in the Qs and As

    Read the puzzle layout and the puzzle data, and fill in questions
    and answers for any triangular-shaped pieces, preparing the output
    substitution variables in the process.
    """

    puzzle_size = getopt(layout, data, {}, 'puzzleTextSize', 5)
    solution_size = getopt(layout, data, {}, 'solutionTextSize', 5)

    num_triangle_cards = len(layout['triangleSolutionCards'])

    # We read the solution layout from the YAML file, and place the
    # data into our lists.  We don't format them yet, as the
    # formatting may be different for the puzzle and solution

    trianglesolcard = []
    for card in layout['triangleSolutionCards']:
        newcard = []
        for entry in card:
            entrynum = int(entry[1:]) - 1  # -1 to convert to 0-based arrays
            if entry[0] == 'Q':
                newcard.append(pairs[entrynum][0])
            elif entry[0] == 'A':
                newcard.append(pairs[entrynum][1])
            elif entry[0] == 'E':
                newcard.append(edges[entrynum])
            else:
                printf('Unrecognised entry in layout file '
                       '(triangleSolutionCards):\n%s' % card,
                       file=sys.stderr)
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
    for (i, solcard) in enumerate(trianglesolcard):
        j = triangleorder[i]
        rot = random.randint(0, 2) # anticlockwise rotation
        trianglepuzcard[j] = [solcard[(3 - rot) % 3],
                              solcard[(4 - rot) % 3],
                              solcard[(5 - rot) % 3],
                              cardnum(j + 1), trianglepuzorient[j][1]]
        puzcard = trianglepuzcard[j]
        # What angle does the card number go in the solution?
        # angle of puzzle card + (orientation of sol card - orientation of
        # puz card) - rotation angle [undoing rotation]
        angle = (trianglepuzorient[j][1] +
                 (trianglesolorient[i] - trianglepuzorient[j][0]) -
                 120 * rot)
        solcard.extend([cardnum(j + 1), (angle + 180) % 360 - 180])

        dsubs['trisolcard' + str(i + 1)] = (('{%s}' * 5) %
            (make_entry(solcard[0], solution_size, 'mark', 'tikz')[0],
             make_entry(solcard[1], solution_size, 'mark', 'tikz')[0],
             make_entry(solcard[2], solution_size, 'mark', 'tikz')[0],
             '%s %s' % (sizes[max(solution_size-3, 0)], solcard[3]),
             solcard[4]))
        dsubs['tripuzcard' + str(j + 1)] = (('{%s}' * 5) %
            (make_entry(puzcard[0], puzzle_size, 'hide', 'tikz')[0],
             make_entry(puzcard[1], puzzle_size, 'hide', 'tikz')[0],
             make_entry(puzcard[2], puzzle_size, 'hide', 'tikz')[0],
             '%s %s' % (sizes[max(puzzle_size-3, 0)], puzcard[3]),
             puzcard[4]))

    # For the Markdown version, we only need to record the puzzle cards at
    # this point.

    if 'puzcards3' not in dsubsmd:
        dsubsmd['puzcards3'] = ''
    if 'puzcards4' not in dsubsmd:
        dsubsmd['puzcards4'] = ''

    for t in trianglepuzcard:
        row = '|'
        for entry in t[0:3]:
            row += ' ' + make_entry(entry, 0, 'hide', 'md')[0] + ' |'
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

def make_squares(data, layout, pairs, edges, dsubs, dsubsmd):
    """Handle square-shaped jigsaw pieces, putting in the Qs and As

    Read the puzzle layout and the puzzle data, and fill in questions
    and answers for any square-shaped pieces, preparing the output
    substitution variables in the process.

    This is very similar to the make_triangles function.
    """

    puzzle_size = getopt(layout, data, {}, 'puzzleTextSize', 5)
    solution_size = getopt(layout, data, {}, 'solutionTextSize', 5)

    num_triangle_cards = len(layout['triangleSolutionCards'])
    num_square_cards = len(layout['squareSolutionCards'])

    # We read the solution layout from the YAML file, and place the
    # data into our lists.  We don't format them yet, as the
    # formatting may be different for the puzzle and solution

    squaresolcard = []
    for card in layout['squareSolutionCards']:
        newcard = []
        for entry in card:
            entrynum = int(entry[1:]) - 1  # -1 to convert to 0-based arrays
            if entry[0] == 'Q':
                newcard.append(pairs[entrynum][0])
            elif entry[0] == 'A':
                newcard.append(pairs[entrynum][1])
            elif entry[0] == 'E':
                newcard.append(edges[entrynum])
            else:
                printf('Unrecognised entry in layout file '
                       '(squareSolutionCards):\n%s' % card,
                       file=sys.stderr)
        squaresolcard.append(newcard)

    # List: direction of base side
    squaresolorient = layout['squareSolutionOrientation']

    # List: direction of base side, direction of card number (from vertical)
    squarepuzorient = layout['squarePuzzleOrientation']

    squareorder = list(range(num_square_cards))
    random.shuffle(squareorder)

    squarepuzcard = [[]] * num_square_cards

    # We will put solution card i in puzzle position squareorder[i],
    # rotated by a random amount
    for (i, solcard) in enumerate(squaresolcard):
        j = squareorder[i]
        rot = random.randint(0, 3) # anticlockwise rotation
        squarepuzcard[j] = [solcard[(4 - rot) % 4],
                            solcard[(5 - rot) % 4],
                            solcard[(6 - rot) % 4],
                            solcard[(7 - rot) % 4],
                            cardnum(j + num_triangle_cards + 1),
                            squarepuzorient[j][1]]
        puzcard = squarepuzcard[j]
        # What angle does the card number go in the solution?
        # angle of puzzle card + (orientation of sol card - orientation of
        # puz card) - rotation angle [undoing rotation]
        angle = (squarepuzorient[j][1] +
                 (squaresolorient[i] - squarepuzorient[j][0]) -
                 90 * rot)
        solcard.extend([cardnum(j + num_triangle_cards + 1),
                        (angle + 180) % 360 - 180])

        dsubs['sqsolcard' + str(i + 1)] = (('{%s}' * 6) %
            (make_entry(solcard[0], solution_size, 'mark', 'tikz')[0],
             make_entry(solcard[1], solution_size, 'mark', 'tikz')[0],
             make_entry(solcard[2], solution_size, 'mark', 'tikz')[0],
             make_entry(solcard[3], solution_size, 'mark', 'tikz')[0],
             '%s %s' % (sizes[max(solution_size-3, 0)], solcard[4]),
             solcard[5]))
        dsubs['sqpuzcard' + str(j + 1)] = (('{%s}' * 6) %
            (make_entry(puzcard[0], puzzle_size, 'hide', 'tikz')[0],
             make_entry(puzcard[1], puzzle_size, 'hide', 'tikz')[0],
             make_entry(puzcard[2], puzzle_size, 'hide', 'tikz')[0],
             make_entry(puzcard[3], puzzle_size, 'hide', 'tikz')[0],
             '%s %s' % (sizes[max(puzzle_size-3, 0)], puzcard[4]),
             puzcard[5]))

    # For the Markdown version, we only need to record the puzzle cards at
    # this point.

    if 'puzcards4' not in dsubsmd:
        dsubsmd['puzcards4'] = ''

    for t in squarepuzcard:
        row = '|'
        for entry in t[0:4]:
            row += ' ' + make_entry(entry, 0, 'hide', 'md')[0] + ' |'
        dsubsmd['puzcards4'] += row + '\n'

    # Testing:
    # for (i, card) in enumerate(squaresolcard):
    #     print('Sol card %s: (%s, %s, %s, %s), num angle %s' %
    #            (i, card[0], card[1], card[2], card[3], card[5]))
    # 
    # for (i, card) in enumerate(squarepuzcard):
    #     print('Puz card %s: (%s, %s, %s), num angle %s' %
    #            (i, card[0], card[1], card[2], card[3], card[4]))


def make_cardsort_cards(data, layout, options,
                        cards, puztemplate, soltemplate,
                        puztemplatemd, soltemplatemd, dsubs, dsubsmd):
    """Handle card sorting cards, making the content for puzzle and solution

    The body content is returned via the dictionaries as dsubs['puzbody'],
    dsubs['solbody'] and similarly for dsubsmd.

    Special card content does special things:

    "- newpage: true"
       this produces a new page in the PDF cards output, but nothing
       in the table or Markdown outputs
    "- newlabel: text"
    "- newlabelsize: num"
       these will change the default label
    """

    dosoln = getopt(layout, data, {}, 'produceSolution', True)
    numbering_cards = getopt(layout, data, {}, 'numberCards', True)
    size = getopt(layout, data, {}, 'textSize', 5)
    defaultlabelsize = getopt(layout, data, {}, 'labelSize', max(size - 2,0))
    defaultlabel = data['label'] if 'label' in data else ''
    cardtitle = data['cardTitle'] if 'cardTitle' in data else ''
    if 'cardTitle' in data:
        if 'cardTitleSize' in data:
            titlesize = data['cardTitleSize']
        else:
            titlesize = max(defaultlabelsize - 1, 0)
        dsubs['cardtitle'] = '%s %s' % (sizes[titlesize], data['cardTitle'])
    else:
        dsubs['cardtitle'] = ''
    dsubsmd['cardtitle'] = data['cardTitle'] if 'cardTitle' in data else ''

    rows = getopt(layout, data, {}, 'rows')
    columns = getopt(layout, data, {}, 'columns')
    dsubs['rows'] = rows
    dsubsmd['rows'] = rows
    dsubs['columns'] = columns
    dsubsmd['columns'] = columns

    # We do a presift of the cards to identify the real cards as
    # opposed to the special cards.  It would be more efficient to
    # only read through the cards once, but that would make the code
    # more complex than needed, and this part of the code is fairly
    # fast anyway.

    # When we are done, realcards will contain the indices of all real
    # cards in the cards list.
    realcards = []
    for (i, c) in enumerate(cards):
        if check_special(c):
            continue
        else:
            realcards.append(i)

    num_cards = len(realcards)
    cardorder = list(range(num_cards))
    if getopt(layout, data, {}, 'shuffleCards', False):
        random.shuffle(cardorder)
    invcardorder = {j: i for (i, j) in enumerate(cardorder)}

    puzbody = puztemplate['begin_document']
    puzbodymd = puztemplatemd['begin_document']
    if dosoln:
        solbody = soltemplate['begin_document']
        solbodymd = soltemplatemd['begin_document']

    # We will put solution card i in puzzle position cardorder[i].
    i = 0 
    pagecards = 0
    for c in cards:
        s = check_special(c)
        if s:
            if 'newlabel' in c:
                defaultlabel = c['newlabel']
            if 'newlabelsize' in c:
                defaultlabelsize = c['newlabelsize']
            if 'newpage' in c:
                # this would presumably only occur for non-shuffled cards;
                # it would make no sense otherwise
                if layout['shuffleCards']:
                    print('newpage makes no sense for shuffled cards!'
                          ' Ignoring', file=sys.stderr)
                else:
                    pagecards = 0
                    # the next loop through will do the new page stuff
            continue

        row = (pagecards % (rows * columns)) // columns + 1
        col = pagecards % columns + 1
        puzsubs = { 'rownum': row, 'colnum': col }
        solsubs = { 'rownum': row, 'colnum': col }
        if numbering_cards:
            puzsubs['cardnum'] = '%s %s' % (sizes[max(size-3, 0)], i + 1)
            solsubs['cardnum'] = '%s %s' % (sizes[max(size-3, 0)],
                                            invcardorder[i] + 1)
        else:
            puzsubs['cardnum'] = ''
            solsubs['cardnum'] = ''
        puzsubsmd = dict(puzsubs)
        solsubsmd = dict(solsubs)

        if pagecards == 0:
            if i > 0:
                puzbody += puztemplate['end_page']
            puzbody += puztemplate['begin_page']
        if dosoln and i % (rows * columns) == 0:
            if i > 0:
                solbody += soltemplate['end_page']
            solbody += soltemplate['begin_page']
        
        puzsubs['text'], puzsubs['label'] = make_entry(
            cards[realcards[cardorder[i]]], size, 'hide', 'tikz',
            defaultlabel, defaultlabelsize)
        puzbody += dosub(puztemplate['item'], puzsubs)
        puzsubsmd['text'], puzsubsmd['label'] = make_entry(
            cards[realcards[cardorder[i]]], 0, 'hide', 'md', defaultlabel,
            blank='&nbsp;')
        puzbodymd += dosub(puztemplatemd['item'], puzsubsmd)
        if dosoln:
            solsubs['text'], solsubs['label'] = make_entry(
                cards[realcards[i]], size, 'mark', 'tikz',
                defaultlabel, defaultlabelsize)
            solbody += dosub(soltemplate['item'], solsubs)
            solsubsmd['text'], solsubsmd['label'] = make_entry(
                cards[realcards[i]], 0, 'mark', 'md', defaultlabel,
                blank='&nbsp;')
            solbodymd += dosub(soltemplatemd['item'], solsubsmd)

        i += 1
        pagecards += 1
        if pagecards == rows * columns:
            pagecards = 0

    puzbody += puztemplate['end_page']
    if dosoln: solbody += soltemplate['end_page']

    puzbody += puztemplate['end_document']
    puzbodymd += puztemplatemd['end_document']
    if dosoln:
        solbody += soltemplate['end_document']
        solbodymd += soltemplatemd['end_document']

    dsubs['puzbody'] = puzbody
    dsubsmd['puzbody'] = puzbodymd
    if dosoln:
        dsubs['solbody'] = solbody
        dsubsmd['solbody'] = solbodymd

def make_domino_cards(data, layout, options,
                      pairs, puztemplate, soltemplate,
                      puztemplatemd, soltemplatemd, dsubs, dsubsmd):
    """Handle domino cards, making the content for puzzle and solution

    This is very similar to the make_cardsort_cards function.

    The body content is returned via the dictionaries as dsubs['puzbody'],
    dsubs['solbody'] and similarly for dsubsmd.
    """

    numbering_cards = getopt(layout, data, {}, 'numberCards', True)
    size = getopt(layout, data, {}, 'textSize', 5)
    # We don't use labels for dominoes, but the next two lines do no
    # harm, and a labelsize is used to calculate the titlesize a few
    # lines further on
    defaultlabelsize = getopt(layout, data, {}, 'labelSize', max(size - 2,0))
    defaultlabel = data['label'] if 'label' in data else ''
    cardtitle = data['cardTitle'] if 'cardTitle' in data else ''
    if 'cardTitle' in data:
        if 'cardTitleSize' in data:
            titlesize = data['cardTitleSize']
        else:
            titlesize = max(defaultlabelsize - 1, 0)
        dsubs['cardtitle'] = '%s %s' % (sizes[titlesize], data['cardTitle'])
    else:
        dsubs['cardtitle'] = ''
    dsubsmd['cardtitle'] = data['cardTitle'] if 'cardTitle' in data else ''

    rows = getopt(layout, data, {}, 'rows')
    columns = getopt(layout, data, {}, 'columns')
    dsubs['rows'] = rows
    dsubsmd['rows'] = rows
    dsubs['columns'] = columns
    dsubsmd['columns'] = columns

    loop = getopt(layout, data, options, 'loop', True)
    start = getopt(layout, data, options, 'start', 'Start')
    finish = getopt(layout, data, options, 'finish', 'Finish')

    # We temporarily append a terminal pair if we're not looping
    if not loop:
        pairs.append([finish, start])

    # We do a presift of the domino pairs to identify the real pairs
    # as opposed to the special ones.  It would be more efficient to
    # only read through the dominoes once, but that would make the code
    # more complex than needed, and this part of the code is fairly
    # fast anyway.

    # At present, there should not be any special domino pairs, but we
    # leave this code (based on make_cardsort_cards) in case we later
    # decide to allow this.

    # When we are done, realpairs will contain the indices of all real
    # pairs in the pairs list.
    realpairs = []
    for (i, p) in enumerate(pairs):
        if check_special(p):
            continue
        else:
            realpairs.append(i)

    num_pairs = len(realpairs)
    cardorder = list(range(num_pairs))
    # In dominoes, we must shuffle the printing order!
    random.shuffle(cardorder)
    invcardorder = {j: i for (i, j) in enumerate(cardorder)}

    # This is how the cards will be laid out (where n=num_pairs-1,
    # where num_pairs is the number of pairs if loop == True and one
    # more than this if loop == False (to take account of Start/Finish
    # pair, where Start=An, Finish=Qn); note that our Q and A counting
    # starts at 0:
    # 
    # Solution cards:
    # solution card 0: An - Q0
    # solution card 1: A0 - Q1
    # ...
    # solution card n-1: A(n-2) - Q(n-1)
    # solution card n: A(n-1) - Qn

    puzbody = puztemplate['begin_document']
    puzbodymd = puztemplatemd['begin_document']
    solbody = soltemplate['begin_document']
    solbodymd = soltemplatemd['begin_document']

    # We will put solution card i in puzzle position cardorder[i].
    i = 0 
    for p in pairs:
        s = check_special(p)
        if s:
            print('Special cards are not accepted for dominoes',
                  file=sys.stderr)
            continue
            # the following will never be executed, but it remains in
            # case we decide to resurrect this behaviour
            if 'newlabel' in p:
                defaultlabel = p['newlabel']
            if 'newlabelsize' in p:
                defaultlabelsize = p['newlabelsize']
            if 'newpage' in p:
                # this does not make sense for dominoes
                print('newpage makes no sense for dominoes! Ignoring.',
                      file=sys.stderr)
            continue

        row = (i % (rows * columns)) // columns + 1
        col = i % columns + 1
        puzsubs = { 'rownum': row, 'colnum': col }
        solsubs = { 'rownum': row, 'colnum': col }
        if numbering_cards:
            puzsubs['cardnum'] = '%s %s' % (sizes[max(size-3, 0)], i + 1)
            solsubs['cardnum'] = '%s %s' % (sizes[max(size-3, 0)],
                                            invcardorder[i] + 1)
        else:
            puzsubs['cardnum'] = ''
            solsubs['cardnum'] = ''
        puzsubsmd = dict(puzsubs)
        solsubsmd = dict(solsubs)

        if i % (rows * columns) == 0:
            if i > 0:
                puzbody += puztemplate['end_page']
                solbody += soltemplate['end_page']
            puzbody += puztemplate['begin_page']
            solbody += soltemplate['begin_page']
        
        # on ith solution card, textL = A(l-1), textR = Q(l)
        puzi = cardorder[i]
        puzi1 = (cardorder[i] - 1 + num_pairs) % num_pairs
        soli = i
        soli1 = (i - 1 + num_pairs) % num_pairs

        puzsubs['textL'], puzsubs['labelL'] = make_entry(
            pairs[realpairs[puzi1]][1], size, 'hide', 'tikz',
            defaultlabel, defaultlabelsize)
        puzsubs['textR'], puzsubs['labelR'] = make_entry(
            pairs[realpairs[puzi]][0], size, 'hide', 'tikz',
            defaultlabel, defaultlabelsize)
        puzbody += dosub(puztemplate['item'], puzsubs)
        puzsubsmd['textL'], puzsubsmd['labelL'] = make_entry(
            pairs[realpairs[puzi1]][1], 0, 'hide', 'md', defaultlabel)
        puzsubsmd['textR'], puzsubsmd['labelR'] = make_entry(
            pairs[realpairs[puzi]][0], 0, 'hide', 'md', defaultlabel)
        puzbodymd += dosub(puztemplatemd['item'], puzsubsmd)
        solsubs['textL'], solsubs['labelL'] = make_entry(
            pairs[realpairs[soli1]][1], size, 'mark', 'tikz',
            defaultlabel, defaultlabelsize)
        solsubs['textR'], solsubs['labelR'] = make_entry(
            pairs[realpairs[soli]][0], size, 'mark', 'tikz',
            defaultlabel, defaultlabelsize)
        solbody += dosub(soltemplate['item'], solsubs)
        solsubsmd['textL'], solsubsmd['labelL'] = make_entry(
            pairs[realpairs[soli1]][1], 0, 'mark', 'md', defaultlabel)
        solsubsmd['textR'], solsubsmd['labelR'] = make_entry(
            pairs[realpairs[soli]][0], 0, 'mark', 'md', defaultlabel)
        solbodymd += dosub(soltemplatemd['item'], solsubsmd)

        i += 1

    puzbody += puztemplate['end_page']
    solbody += soltemplate['end_page']

    puzbody += puztemplate['end_document']
    puzbodymd += puztemplatemd['end_document']
    solbody += soltemplate['end_document']
    solbodymd += soltemplatemd['end_document']

    dsubs['puzbody'] = puzbody
    dsubsmd['puzbody'] = puzbodymd
    dsubs['solbody'] = solbody
    dsubsmd['solbody'] = solbodymd

    if not loop:
        # We remove the temporarily appended terminal pair
        pairs.pop()


rerun_regex = re.compile(b'rerun ', re.I)

def runlatex(file, options):
    """Run (lua)latex on file"""

    # We may use the options at a later point to specify the LaTeX
    # engine to use, so including it now to reduce amount of code to
    # modify later.
    for count in range(4):
        try:
            output = subprocess.check_output(['lualatex',
                                              '--interaction=nonstopmode',
                                              file])
        except subprocess.CalledProcessError as cpe:
            print('Warning: lualatex %s failed, return value %s' %
                  (file, cpe.returncode), file=sys.stderr)
            print('See the lualatex log file for more details.',
                  file=sys.stderr)
            break

        if not rerun_regex.search(output):
            break


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

    generate(data, options)


def generate(data, options):
    """Generate output from data, using options passed to this function.

    Thus function is presently called from main(), but might well be
    called from a GUI at some point in the future, which is why it has
    been separated out.

    When this function is called, data must contain a recognised
    jigsaw type, and the options dictionary must contain an entry
    'puzbase' with the file basename for this particular puzzle.
    """

    # Open template files and layout file.

    if 'type' in data:
        puztype = data['type']
        try:
            layoutf = opentemplate(puztype + '.yaml')
        except:
            sys.exit('Unrecognised jigsaw type %s' % data['type'])
    else:
        sys.exit('No jigsaw type found in puzzle file')

    try:
        layout = load(layoutf, Loader=Loader)
    except yaml.YAMLError as exc:
        if hasattr(exc, 'problem_mark'):
            mark = exc.problem_mark
            sys.exit('Error parsing puzzle layout file %s.yaml\n'
                     'Error position: line %s, column %s' %
                     (puztype, mark.line+1, mark.column+1))

    category = layout['category']
    try:
        generator = {
            'jigsaw': generate_jigsaw,
            'cardsort': generate_cardsort,
            'dominoes': generate_cardsort
            }[category]
    except KeyError:
        sys.exit('Unrecognised category in %s layout file: %s' %
                 (puztype, category))

    generator(data, options, layout)


def generate_jigsaw(data, options, layout):
    """Generate output from data for jigsaw-type puzzles."""

    # ***FIXME*** The output filenames should be specifiable on the
    # command line.  Also, there should be options for which outputs
    # to produce.

    puzbase = options['puzbase']

    bodypuzfile = getopt(layout, data, options, 'puzzleTemplateTeX')
    if bodypuzfile:
        headerfile = getopt(layout, data, options, 'puzzleHeaderTeX')
        if headerfile:
            bodypuz = opentemplate(bodypuzfile).read()
            outpuzfile = puzbase + '-puzzle.tex'
            outpuz = open(outpuzfile, 'w')
            header = opentemplate(headerfile).read()
            print(header, file=outpuz)
            puzzletex = True
        else:
            print('puzzleTemplateTeX file specified but not puzzleHeaderTeX',
                  file=sys.stderr)
            puzzletex = False
    else:
        puzzletex = False

    bodysolfile = getopt(layout, data, options, 'solutionTemplateTeX')
    if bodysolfile:
        headerfile = getopt(layout, data, options, 'solutionHeaderTeX')
        if headerfile:
            bodysol = opentemplate(bodysolfile).read()
            outsolfile = puzbase + '-solution.tex'
            outsol = open(outsolfile, 'w')
            header = opentemplate(headerfile).read()
            print(header, file=outsol)
            solutiontex = True
        else:
            print('solutionTemplateTeX file specified '
                  'but not solutionHeaderTeX',
                  file=sys.stderr)
            solutiontex = False
    else:
        solutiontex = False

    bodytablefile = getopt(layout, data, options, 'tableTemplateTeX')
    if bodytablefile:
        headerfile = getopt(layout, data, options, 'tableHeaderTeX')
        if headerfile:
            bodytable = opentemplate(bodytablefile).read()
            outtablefile = puzbase + '-table.tex'
            outtable = open(outtablefile, 'w')
            header = opentemplate(headerfile).read()
            print(header, file=outtable)
            tabletex = True
        else:
            print('tableTemplateTeX file specified but not tableHeaderTeX',
                  file=sys.stderr)
            tabletex = False
    else:
        tabletex = False

    bodypuzmdfile = getopt(layout, data, options, 'puzzleTemplateMarkdown')
    if bodypuzmdfile:
        headerfile = getopt(layout, data, options, 'puzzleHeaderMarkdown')
        if headerfile:
            bodypuzmd = opentemplate(bodypuzmdfile).read()
            outpuzmdfile = puzbase + '-puzzle.md'
            outpuzmd = open(outpuzmdfile, 'w')
            header = opentemplate(headerfile).read()
            print(header, file=outpuzmd)
            puzzlemd = True
        else:
            print('puzzleTemplateMarkdown file specified '
                  'but not puzzleHeaderMarkdown',
                  file=sys.stderr)
            puzzlemd = False
    else:
        puzzlemd = False

    bodysolmdfile = getopt(layout, data, options, 'solutionTemplateMarkdown')
    if bodysolmdfile:
        headerfile = getopt(layout, data, options, 'solutionHeaderMarkdown')
        if headerfile:
            bodysolmd = opentemplate(bodysolmdfile).read()
            outsolmdfile = puzbase + '-solution.md'
            outsolmd = open(outsolmdfile, 'w')
            header = opentemplate(headerfile).read()
            print(header, file=outsolmd)
            solutionmd = True
        else:
            print('solutionTemplateMarkdown file specified '
                  'but not solutionHeaderMarkdown',
                  file=sys.stderr)
            solutionmd = False
    else:
        solutionmd = False

    # These dicts will contain the substitutions needed for the
    # template files; the first is for the LaTeX output files, the
    # second is for the Markdown output files.

    # The Markdown output files are much simpler, as they are intended
    # to be embedded in larger documents, for those who cannot access
    # the PDF files.
    dsubs = {}
    dsubsmd = {}

    if 'title' in data:
        dsubs['title'] = data['title']
    else:
        dsubs['title'] = ''
    random.seed(dsubs['title'])

    # Read the card content
    # Three types of cards: pairs, edges, cards (which are single cards
    # for sorting activities, and do not appear in jigsaw types)
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

    if 'cards' in data:
        sys.exit('Puzzle type %s does not accept cards in data file' %
                 layout['typename'])
    cards = []  # so later call to make_table doesn't break

    if getopt(layout, data, options, 'shufflePairs'):
        random.shuffle(pairs)
    if getopt(layout, data, options, 'shuffleEdges'):
        random.shuffle(edges)

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
    global exists_hidden
    exists_hidden = False

    if tabletex or solutionmd:
        make_table(pairs, edges, cards, dsubs, dsubsmd)

    if 'triangleSolutionCards' in layout:
        make_triangles(data, layout, flippedpairs, edges, dsubs, dsubsmd)

    if 'squareSolutionCards' in layout:
        make_squares(data, layout, flippedpairs, edges, dsubs, dsubsmd)

    if exists_hidden:
        hiddennote = getopt(layout, data, options, 'hiddennote',
          'Entries that are hidden in the puzzle are highlighted in yellow.')
        hiddennotemd = getopt(layout, data, options, 'hiddennotemd',
          'Entries that are hidden in the puzzle are indicated with (*).')
        hiddennotetable = getopt(layout, data, options, 'hiddennotetable',
                                 hiddennotemd)
        dsubs['hiddennotesolution'] = hiddennote
        dsubs['hiddennotetable'] = hiddennotetable
        dsubsmd['hiddennotemd'] = hiddennotemd
    else:
        dsubs['hiddennotesolution'] = ''
        dsubs['hiddennotetable'] = ''
        dsubsmd['hiddennotemd'] = ''

    dsubs['puzzlenote'] = getopt(layout, data, options, 'note', '')
    dsubsmd['puzzlenote'] = getopt(layout, data, options, 'note', '')

    if tabletex:
        btext = dosub(bodytable, dsubs)
        print(btext, file=outtable)
        outtable.close()
        runlatex(outtablefile, options)

    if puzzletex:
        ptext = dosub(bodypuz, dsubs)
        print(ptext, file=outpuz)
        outpuz.close()
        runlatex(outpuzfile, options)

    if solutiontex:
        stext = dosub(bodysol, dsubs)
        print(stext, file=outsol)
        outsol.close()
        runlatex(outsolfile, options)

    if puzzlemd:
        ptextmd = dosub(bodypuzmd, dsubsmd)
        print(ptextmd, file=outpuzmd)
        outpuzmd.close()

    if solutionmd:
        stextmd = dosub(bodysolmd, dsubsmd)
        print(stextmd, file=outsolmd)
        outsolmd.close()

def generate_cardsort(data, options, layout):
    """Generate cards for a cardsort or domino activity"""

    # ***FIXME*** The output filenames should be specifiable on the
    # command line.  Also, there should be options for which outputs
    # to produce.

    puzbase = options['puzbase']
    category = layout['category']
    if category == 'cardsort':
        dosoln = getopt(layout, data, {}, 'produceSolution', True)
    else:
        dosoln = True

    bodypuzfile = getopt(layout, data, options, 'puzzleTemplateTeX')
    if bodypuzfile:
        headerfile = getopt(layout, data, options, 'puzzleHeaderTeX')
        if headerfile:
            bodypuz = opentemplate(bodypuzfile).read()
            outpuzfile = puzbase + '-puzzle.tex'
            outpuz = open(outpuzfile, 'w')
            header = opentemplate(headerfile).read()
            print(header, file=outpuz)
            puzzletex = True
        else:
            print('puzzleTemplateTeX file specified but not puzzleHeaderTeX',
                  file=sys.stderr)
            puzzletex = False
    else:
        puzzletex = False

    if dosoln:
        bodysolfile = getopt(layout, data, options, 'solutionTemplateTeX')
        if bodysolfile:
            headerfile = getopt(layout, data, options, 'solutionHeaderTeX')
            if headerfile:
                bodysol = opentemplate(bodysolfile).read()
                outsolfile = puzbase + '-solution.tex'
                outsol = open(outsolfile, 'w')
                header = opentemplate(headerfile).read()
                print(header, file=outsol)
                solutiontex = True
            else:
                print('solutionTemplateTeX file specified '
                      'but not solutionHeaderTeX',
                      file=sys.stderr)
                solutiontex = False
        else:
            solutiontex = False
    else:
        solutiontex = False

    bodytablefile = getopt(layout, data, options, 'tableTemplateTeX')
    if bodytablefile:
        headerfile = getopt(layout, data, options, 'tableHeaderTeX')
        if headerfile:
            bodytable = opentemplate(bodytablefile).read()
            outtablefile = puzbase + '-table.tex'
            outtable = open(outtablefile, 'w')
            header = opentemplate(headerfile).read()
            print(header, file=outtable)
            tabletex = True
        else:
            print('tableTemplateTeX file specified but not tableHeaderTeX',
                  file=sys.stderr)
            tabletex = False
    else:
        tabletex = False

    bodypuzmdfile = getopt(layout, data, options, 'puzzleTemplateMarkdown')
    if bodypuzmdfile:
        headerfile = getopt(layout, data, options, 'puzzleHeaderMarkdown')
        if headerfile:
            bodypuzmd = opentemplate(bodypuzmdfile).read()
            outpuzmdfile = puzbase + '-puzzle.md'
            outpuzmd = open(outpuzmdfile, 'w')
            header = opentemplate(headerfile).read()
            print(header, file=outpuzmd)
            puzzlemd = True
        else:
            print('puzzleTemplateMarkdown file specified '
                  'but not puzzleHeaderMarkdown',
                  file=sys.stderr)
            puzzlemd = False
    else:
        puzzlemd = False

    if dosoln:
        bodysolmdfile = getopt(layout, data, options, 'solutionTemplateMarkdown')
        if bodysolmdfile:
            headerfile = getopt(layout, data, options, 'solutionHeaderMarkdown')
            if headerfile:
                bodysolmd = opentemplate(bodysolmdfile).read()
                outsolmdfile = puzbase + '-solution.md'
                outsolmd = open(outsolmdfile, 'w')
                header = opentemplate(headerfile).read()
                print(header, file=outsolmd)
                solutionmd = True
            else:
                print('solutionTemplateMarkdown file specified '
                      'but not solutionHeaderMarkdown',
                      file=sys.stderr)
                solutionmd = False
        else:
            solutionmd = False
    else:
        solutionmd = False

    # Templates for card sorts are a little more complex than for
    # jigsaws, as the TeX version needs explicit blocks for start of
    # document, start of page, end of page and end of document.  The
    # Markdown version likewise has a template for each item, so that
    # styling needs - for example, that each card should live inside a
    # <div> or <span> element - can be handled.

    # So the TeX template must have the form:
    # %%% BEGIN DOCUMENT
    # ...
    # %%% BEGIN PAGE
    # ...
    # %%% BEGIN ITEM
    # ...
    # %%% END PAGE
    # ...
    # %%% END DOCUMENT
    # ...

    # And the Markdown template has the form:
    # ### BEGIN DOCUMENT
    # ...
    # ### BEGIN ITEM
    # ...
    # ### END DOCUMENT
    # ...

    # Any content before the initial '%%% BEGIN DOCUMENT' will be
    # ignored.  Also, the '%%%' or '###' must appear at the start of a
    # line, and anything trailing content following the 'BEGIN
    # DOCUMENT' etc. will be ignored.

    # The "item" section for card sorts would normally consist of the
    # single line something like:
    # 
    # \card{<: rownum :>}{<: colnum :>}{<: cardnum :>}{<: text :>}{<: label :>}

    # where the rownum and colnum are clear, the card number will be
    # from 1 upwards in order in the puzzle, and the content is the
    # actual text (with size and hidden indicators as with the
    # jigsaw), and \card is an appropriate TeX command which typesets
    # the requested card.  The Markdown "item" section is likewise
    # substituted with these variables.

    # For dominoes, essentially the same is true, except that the
    # macro has 7 arguments, the last four being textL, textR, labelL,
    # labelR, being the text for the left and right halves of the
    # domino and the labels for the same.

    # The cards will be produced from top (row 1) to bottom (row n)
    # and in each row from left (column 1) to right (column m).  After
    # the final card on a page, and also after all the cards are used
    # up, the end page content will be output (but only once if the
    # final card occurs at the end of a page), and before the first
    # card of a page, the begin page content will be output.

    puztemplate = {}
    puztemplatemd = {}
    soltemplate = {}
    soltemplatemd = {}

    if puzzletex:
        templatematch = re.search('^%%% BEGIN DOCUMENT.*?^(.*?)'
                                  '^%%% BEGIN PAGE.*?^(.*?)'
                                  '^%%% BEGIN ITEM.*?^(.*?)'
                                  '^%%% END PAGE.*?^(.*?)'
                                  '^%%% END DOCUMENT.*?^(.*)',
                                  bodypuz, re.M | re.S)
        if templatematch:
            puztemplate['begin_document'] = templatematch.group(1)
            puztemplate['begin_page'] = templatematch.group(2)
            puztemplate['item'] = templatematch.group(3)
            puztemplate['end_page'] = templatematch.group(4)
            puztemplate['end_document'] = templatematch.group(5)
        else:
            sys.exit('TeX puzzle template does not have required structure')

        if dosoln:
            templatematch = re.search('^%%% BEGIN DOCUMENT.*?^(.*?)'
                                      '^%%% BEGIN PAGE.*?^(.*?)'
                                      '^%%% BEGIN ITEM.*?^(.*?)'
                                      '^%%% END PAGE.*?^(.*?)'
                                      '^%%% END DOCUMENT.*?^(.*)',
                                      bodysol, re.M | re.S)
            if templatematch:
                soltemplate['begin_document'] = templatematch.group(1)
                soltemplate['begin_page'] = templatematch.group(2)
                soltemplate['item'] = templatematch.group(3)
                soltemplate['end_page'] = templatematch.group(4)
                soltemplate['end_document'] = templatematch.group(5)
            else:
                sys.exit('TeX solution template does not have '
                         'required structure')

    if puzzlemd:
        templatemdmatch = re.search('^### BEGIN DOCUMENT.*?$(.*?)'
                                    '^### BEGIN ITEM.*?$(.*?)'
                                    '^### END DOCUMENT.*?$(.*?)',
                                    bodypuzmd, re.M | re.S)
        if templatemdmatch:
            puztemplatemd['begin_document'] = templatemdmatch.group(1)
            puztemplatemd['item'] = templatemdmatch.group(2)
            puztemplatemd['end_document'] = templatemdmatch.group(3)
        else:
            sys.exit('Markdown puzzle template does not have '
                     'required structure')

        if dosoln:
            templatemdmatch = re.search('^### BEGIN DOCUMENT.*?$(.*?)'
                                        '^### BEGIN ITEM.*?$(.*?)'
                                        '^### END DOCUMENT.*?$(.*?)',
                                        bodysolmd, re.M | re.S)
            if templatemdmatch:
                soltemplatemd['begin_document'] = templatemdmatch.group(1)
                soltemplatemd['item'] = templatemdmatch.group(2)
                soltemplatemd['end_document'] = templatemdmatch.group(3)
            else:
                sys.exit('Markdown solution template does not have '
                         'required structure')


    # These dicts will contain the substitutions needed for the
    # template files; the first is for the LaTeX output files, the
    # second is for the Markdown output files.  These are only used
    # for the document and page templates; we use separate ones for
    # each item.

    # The Markdown output files are much simpler, as they are intended
    # to be embedded in larger documents, for those who cannot access
    # the PDF files.
    dsubs = {}
    dsubsmd = {}

    if 'title' in data:
        dsubs['title'] = data['title']
    else:
        dsubs['title'] = ''
    random.seed(dsubs['title'])

    # Read the card content

    # Two types of cards for cardsort-like puzzles: pairs (for domino
    # cards) and cards (which are single cards for sorting
    # activities); edges do not appear in this sort of activity
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

    if 'edges' in data:
        sys.exit('Puzzle type %s does not accept edges in data file' %
                 layout['typename'])
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
        cards = []  # so that later bits of code don't barf

    # We don't shuffle the cards yet, as we need the original order
    # for the solution and table.  Shuffling pairs is fine, though, as
    # their original order is immaterial if shufflePairs is requested.

    if getopt(layout, data, options, 'shufflePairs'):
        random.shuffle(pairs)
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
    global exists_hidden
    exists_hidden = False

    if tabletex:
        make_table(pairs, edges, cards, dsubs, dsubsmd)

    if layout['category'] == 'cardsort':
        make_cardsort_cards(data, layout, options,
                            cards, puztemplate, soltemplate,
                            puztemplatemd, soltemplatemd, dsubs, dsubsmd)
    else:
        make_domino_cards(data, layout, options,
                          flippedpairs, puztemplate, soltemplate,
                          puztemplatemd, soltemplatemd, dsubs, dsubsmd)

    if exists_hidden:
        dsubs['hiddennotesolution'] = 'Entries that are hidden in the puzzle are highlighted in yellow.'
        dsubs['hiddennotetable'] = 'Entries that are hidden in the puzzle are indicated with (*).'
        dsubsmd['hiddennotemd'] = 'Entries that are hidden in the puzzle are indicated with (*).'
    else:
        dsubs['hiddennotesolution'] = ''
        dsubs['hiddennotetable'] = ''
        dsubsmd['hiddennotemd'] = ''

    dsubs['puzzlenote'] = getopt(layout, data, options, 'note', '')
    dsubsmd['puzzlenote'] = getopt(layout, data, options, 'note', '')

    dsubs['puzbody'] = dosub(dsubs['puzbody'], dsubs)
    dsubsmd['puzbody'] = dosub(dsubsmd['puzbody'], dsubsmd)
    if dosoln:
        dsubs['solbody'] = dosub(dsubs['solbody'], dsubs)
        dsubsmd['solbody'] = dosub(dsubsmd['solbody'], dsubsmd)

    if tabletex:
        btext = dosub(bodytable, dsubs)
        print(btext, file=outtable)
        outtable.close()
        runlatex(outtablefile, options)

    if puzzletex:
        print(dsubs['puzbody'], file=outpuz)
        outpuz.close()
        runlatex(outpuzfile, options)

    if solutiontex:
        print(dsubs['solbody'], file=outsol)
        outsol.close()
        runlatex(outsolfile, options)

    if puzzlemd:
        print(dsubsmd['puzbody'], file=outpuzmd)
        outpuzmd.close()

    if solutionmd:
        print(dsubsmd['solbody'], file=outsolmd)
        outsolmd.close()


# This allows this script to be invoked directly and also (hopefully
# at some later stage) for the functions to be called via a GUI
if __name__ == '__main__':
    main()

