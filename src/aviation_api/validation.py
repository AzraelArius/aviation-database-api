# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
from flask import request
from .errors import APIError


def positive_id(value):
    if not 1 <= len(value) <= 10 or not value.isascii() or not value.isdecimal() or not 0 < int(value) <= 2147483647:
        raise APIError(400, 'invalid_id', 'ID must be a positive 32-bit integer.')
    return int(value)


def require_airport(cur, code):
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        raise APIError(400, 'invalid_airport', 'Airport code must contain three letters.')
    code = code.upper()
    if not cur.execute('SELECT 1 FROM aeroporto WHERE codigo = %s', (code,)).fetchone():
        raise APIError(404, 'airport_not_found', 'Airport does not exist.')
    return code


def purchase_payload():
    data = request.get_json()
    if not isinstance(data, dict):
        raise APIError(400, 'invalid_payload', 'JSON body must be an object.')
    nif = data.get('nif_cliente')
    if not isinstance(nif, str) or len(nif) != 9 or not nif.isascii() or not nif.isdecimal():
        raise APIError(400, 'invalid_nif', 'nif_cliente must be a string of nine digits.')
    tickets = data.get('bilhetes')
    if not isinstance(tickets, list) or not tickets:
        raise APIError(400, 'invalid_tickets', 'bilhetes must be a nonempty list of [name, boolean class] pairs.')
    cleaned = []
    names = set()
    for ticket in tickets:
        if not isinstance(ticket, list) or len(ticket) != 2:
            raise APIError(400, 'invalid_ticket', 'Each ticket must be a [name, boolean class] pair.')
        name, first_class = ticket
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80 or not name.isprintable():
            raise APIError(400, 'invalid_name', 'Passenger name must contain 1–80 printable characters.')
        if type(first_class) is not bool:
            raise APIError(400, 'invalid_class', 'Ticket class must be a JSON boolean.')
        name = name.strip()
        if name in names:
            raise APIError(400, 'duplicate_passenger', 'Passenger names must be unique within a purchase.')
        names.add(name)
        cleaned.append((name, first_class))
    return nif, cleaned
