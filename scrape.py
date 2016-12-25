#!/usr/bin/env python
# encoding: utf-8

'''
Scrape garbage collection dates for Karlsruhe.
'''

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import datetime
import itertools
import os.path
from pprint import pprint
import re

import bs4
import requests
from unidecode import unidecode


_BASE_URL = 'http://web3.karlsruhe.de/service/abfall/akal/akal.php'

_DATE_RE = re.compile(r'\b(\d\d?)\.(\d\d?).(\d\d\d\d)\b')

_RE_FLAGS = re.UNICODE

_RETRIES_PER_STREET = 3


def _remove_bracketed_substrings(s):
    '''
    Remove substrings in brackets.

    Removes any substrings in brackets (``()``), including the brackets.
    Nested brackets are not supported.
    '''
    return re.sub(r'\(.*?\)', '', s)


def _extract_dates(s):
    '''
    Extract everything that looks like a German date from a string.

    Returns a list of ``datetime.date`` instances.
    '''
    dates = []
    for candidate in _DATE_RE.finditer(s):
        groups = map(int, candidate.groups())
        try:
            dates.append(datetime.date(groups[2], groups[1], groups[0]))
        except ValueError:
            pass
    return dates


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
    dates = {}
    soup = soup_from_url(_BASE_URL, params={'strasse': street})
    for title in ['Restmüll, 14-täglich', 'Bioabfall, wöchentlich',
                  'Wertstoff, 14-täglich', 'Papier, 4-wöchentlich',
                  'Sperrmüllabholung']:
        td = soup.find('td', string=title)
        if td:
            text = _remove_bracketed_substrings(td.next_sibling.text)
            dates[title] = _extract_dates(text)
    return dates


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


def _save_data(data):
    with open('data.json', 'w') as f:
        json.dump(data, f)


def scrape():
    streets = {}
    for street in _get_street_list():
        name, numbers = _parse_street(street)
        print(street, name, numbers)
        data = None
        for _ in range(_RETRIES_PER_STREET):
            try:
                data = {k: [d.strftime('%Y-%m-%d') for d in v] for k, v in
                            _scrape_street(street).iteritems()}
                pprint(data)
            except ValueError:
                print('  NO DATE')
            except requests.ConnectionError:
                print('  CONNECTION ERROR')
                continue
            break
        streets.setdefault(name, []).append([numbers, data])
        _save_data(streets)  # Save continuously to allow early interruption
    for value in streets.itervalues():
        value.sort()
    return streets


def normalize_street_name(name):
    name = unicode(unidecode(name.strip().lower()))
    name = re.sub(r'str\b', 'strasse', name, flags=_RE_FLAGS)
    name = re.sub(r'[^\w]', '', name, flags=_RE_FLAGS)
    return name


def _house_number_in_range(number, range):
    '''
    ``number`` is a parsed house number as returned by
    ``_parse_house_number``. ``range`` can be ``None``, a 1-tuple, or a
    2-tuple. A range of ``None`` matches all house numbers. A 1-tuple
    ``(x,)`` matches only ``x``. A 2-tuple ``(x, y)`` matches a number
    if it is between ``x`` and ``y`` (inclusively) and of the same
    parity as ``x`` (if ``x[0]`` and ``number[0]`` are either both even
    or both odd).
    '''
    if range is None:
        return True
    if len(range) == 1:
        return range[0] == number
    if (number[0] % 2) != (range[0][0] % 2):
        return False
    return (range[0] <= number) and (number <= range[1])


class CustomException(Exception): pass
class UnknownStreetException(CustomException): pass
class UnknownHouseNumberException(CustomException): pass


def find_address(data, name, number):
    '''
    ``data`` maps normalized street names to range lists. ``name`` is a
    street name and doesn't need to be normalized. ``number`` is a house
    number as a string.

    Returns the available data for the address.
    '''
    name = normalize_street_name(name)
    parsed_number = _parse_house_number(number)
    try:
        street_data = data[name]
    except KeyError:
        raise UnknownStreetException()
    for range, range_data  in street_data:
        if _house_number_in_range(parsed_number, range):
            print('{} is in {}'.format(parsed_number, range))
            return range_data
        else:
            print('{} is NOT in {}'.format(parsed_number, range))
    raise UnknownHouseNumberException()


if __name__ == '__main__':
    import errno
    import io
    import json

    try:
        with io.open('data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        print('Loaded {} items'.format(len(data)))
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
        print('No stored data, scraping...')
        data = scrape()

    data = {normalize_street_name(key): value
            for key, value in data.iteritems()}

    name = 'Akademiestr'
    number = '26 a'

    print('{} {}'.format(name, number))
    try:
        print(find_address(data, name, number))
    except UnknownStreetException:
        print('ERROR: Unknown street')
    except UnknownHouseNumberException:
        print('ERROR: Unknown house number')

