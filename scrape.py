#!/usr/bin/env python
# encoding: utf-8

'''
Scrape garbage collection dates for Karlsruhe.
'''

# FIXME:
#
# - If a house number range is given then it is either for odd or
#   for even house numbers (depending on its first number), so we
#   cannot simply use [[0], ['~']] as a replacement when no range
#   is given.

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime
import itertools
import os.path
import re

import bs4
import requests


_BASE_URL = 'http://web3.karlsruhe.de/service/abfall/akal/akal.php'

_DATE_RE = re.compile(r'\b(\d\d?)\.(\d\d?).(\d\d\d\d)\b')


def extract_date(s):
    '''
    Extract the first thing that looks like a (German) date.

    Raises ``ValueError`` if no valid date is found.
    '''
    for candidate in _DATE_RE.finditer(s):
        groups = map(int, candidate.groups())
        try:
            return datetime.date(groups[2], groups[1], groups[0])
        except ValueError:
            pass
    raise ValueError('Did not find a valid date in {!r}.'.format(s))


def soup_from_url(url, **kwargs):
    '''
    Get an URL and parse it into a ``BeautifulSoup``.
    '''
    r = requests.get(url, **kwargs)
    r.raise_for_status()
    return bs4.BeautifulSoup(r.text, 'html.parser')


def _get_street_list():
    soup = soup_from_url(_BASE_URL, params={'von': 'A', 'bis': '['})
    select = soup.find('select', attrs={'name': 'strasse'})
    return [opt.text for opt in select.find_all('option')]


def _scrape_street(street):
    soup = soup_from_url(_BASE_URL, params={'strasse': street})
    td = soup.find('td', string='Sperrmüllabholung').next_sibling
    if not td:
        raise ValueError('Unknown page format')
    return extract_date(td.text)


def _parse_house_number(number):
    '''
    Parse a house number string.

    Splits the string ``number`` into a list of consecutive letter and
    number substrings. The numbers are converted to integers, the
    letters are converted to upper case. The string ``Ende`` (in any
    case) is treated specially and returns ``['~']`` (which compares
    as greater with any digit and letter from A-Z).
    '''
    if number.lower() == 'ende':
        return ['~']
    number = re.sub(r'\s', '', number)
    maps = [lambda x: x.upper(), int]
    return [maps[x[0]](''.join(x[1])) for x in
            itertools.groupby(number, key=unicode.isdigit)]


def _parse_street(street):
    first_digit = re.search(r'\d', street)
    if first_digit is None:
        return street.title(), None
    index = first_digit.start()
    name = street[:index].strip().title()
    numbers = [_parse_house_number(num) for num in street[index:].split('-')]
    return name, numbers


def scrape():
    streets = {}
    for street in _get_street_list():
        name, numbers = _parse_street(street)
        if numbers is None:
            numbers = [[0], ['~']]
        print(street, name, numbers)
        # Make sure the street is listed even if there's an error later on
        streets.setdefault(name, [])
        try:
            date = _scrape_street(street)
            streets[name].append([numbers, date])
            print('  {}'.format(date))
        except ValueError:
            print('  NO DATE')
        except requests.ConnectionError:
            print('  CONNECTION ERROR')
    for value in streets.itervalues():
        value.sort()
    return streets

