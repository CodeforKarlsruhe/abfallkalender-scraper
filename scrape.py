#!/usr/bin/env python
# encoding: utf-8

'''
Scrape garbage collection dates for Karlsruhe.
'''

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import csv
import datetime
import itertools
import os.path
import re

import bs4
import requests
from unidecode import unidecode


_BASE_URL = 'http://web3.karlsruhe.de/service/abfall/akal/akal.php'

_DATE_RE = re.compile(r'\b(\d\d?)\.(\d\d?).(\d\d\d\d)\b')

_RE_FLAGS = re.UNICODE

_RETRIES_PER_STREET = 3


_SERVICES = {
    'ka-rest-14': 'Restmüll (14-täglich)',
    'ka-bio-7': 'Biomüll (wöchentlich)',
    'ka-wert-14': 'Wertstoff (14-täglich)',
    'ka-papier-28': 'Altpapier (4-wöchentlich)',
    'ka-sperr-365': 'Sperrmüll',
}


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
    for key, title in [
        ('ka-rest-14', 'Restmüll, 14-täglich'),
        ('ka-bio-7', 'Bioabfall, wöchentlich'),
        ('ka-wert-14', 'Wertstoff, 14-täglich'),
        ('ka-papier-28', 'Papier, 4-wöchentlich'),
        ('ka-sperr-356', 'Sperrmüllabholung'),
    ]:
        td = soup.find('td', string=title)
        if td:
            text = _remove_bracketed_substrings(td.next_sibling.text)
            dates[key] = _extract_dates(text)
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


def _unparse_house_number(number):
    '''
    Convert a house number to a string.
    '''
    return ''.join(unicode(x) for x in number)


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
        print(street)
        data = None
        for _ in range(_RETRIES_PER_STREET):
            try:
                data = {k: [d.strftime('%Y-%m-%d') for d in v] for k, v in
                            _scrape_street(street).iteritems()}
            except ValueError:
                # No date
                pass
            except requests.ConnectionError:
                continue
            break
        streets.setdefault(name, []).append([numbers, data])
    for value in streets.itervalues():
        value.sort()
    return streets


def normalize_street_name(name):
    name = unicode(unidecode(name.strip().lower()))
    name = re.sub(r'str\b', 'strasse', name, flags=_RE_FLAGS)
    name = re.sub(r'[^\w]', '', name, flags=_RE_FLAGS)
    return name


def csv_export(data):
    '''
    Export data to CSV files.
    '''
    csv_opts = {'delimiter': b',', 'quoting': csv.QUOTE_NONNUMERIC}
    with open('services.csv', 'wb') as f:
        writer = csv.writer(f, **csv_opts)
        for id, title in _SERVICES.iteritems():
            writer.writerow([id.encode('utf-8'), title.encode('utf-8')])
    with open('dates.csv', 'wb') as f:
        writer = csv.writer(f, **csv_opts)
        for street, servicedates in data.iteritems():
            street = street.encode('utf-8')
            for numbers, services in servicedates:
                if numbers is None:
                    numbers = [['0'], ['0']]
                if len(numbers) == 1:
                    numbers = [numbers[0], numbers[0]]
                numbers = [['0'] if x == ['~'] else x for x in numbers]
                numbers = [_unparse_house_number(x) for x in numbers]
                for service, dates in services.iteritems():
                    service = service.encode('utf-8')
                    for date in dates:
                        writer.writerow(['Karlsruhe', street, numbers[0],
                                         numbers[1], service, date])


if __name__ == '__main__':
    import errno
    import json

    data = scrape()
    data = {normalize_street_name(key): value
            for key, value in data.iteritems()}

    csv_export(data)

