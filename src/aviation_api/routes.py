# Copyright (c) BDist Development Team
# Distributed under the terms of the Modified BSD License.
from flask import Blueprint, current_app, jsonify
from .db import database
from .errors import APIError
from .validation import positive_id, purchase_payload, require_airport

routes = Blueprint("aviation", __name__)


@routes.get('/')
def get_all_airports():
    with database() as conn, conn.cursor() as cur:
        airports = cur.execute('SELECT nome, cidade FROM aeroporto ORDER BY codigo').fetchall()
    return jsonify(airports), 200

@routes.get('/voos/<partida>/')
def get_flights(partida):
    with database() as conn, conn.cursor() as cur:
        partida = require_airport(cur, partida)
        flights = cur.execute('''SELECT no_serie, hora_partida, chegada FROM voo
            WHERE partida = %s AND hora_partida BETWEEN CURRENT_TIMESTAMP AND CURRENT_TIMESTAMP + INTERVAL '12 hours'
            ORDER BY hora_partida, id''', (partida,)).fetchall()
    return jsonify(flights), 200

@routes.get('/voos/<partida>/<chegada>/')
def get_next_flights(partida, chegada):
    with database() as conn, conn.cursor() as cur:
        partida, chegada = require_airport(cur, partida), require_airport(cur, chegada)
        flights = cur.execute('''SELECT no_serie, hora_partida FROM voo v
            WHERE v.partida = %s AND v.chegada = %s AND CURRENT_TIMESTAMP <= v.hora_partida
              AND EXISTS (SELECT 1 FROM assento a WHERE a.no_serie = v.no_serie
                GROUP BY a.prim_classe HAVING COUNT(*) > (SELECT COUNT(*) FROM bilhete b
                    WHERE b.voo_id = v.id AND b.prim_classe = a.prim_classe))
            ORDER BY v.hora_partida, v.id LIMIT 3''', (partida, chegada)).fetchall()
    return jsonify(flights), 200

@routes.route('/compra/<voo_id>/', methods=['POST', 'PUT'])
def buy_tickets(voo_id):
    voo_id = positive_id(voo_id)
    nif, tickets = purchase_payload()
    with database() as conn, conn.cursor() as cur:
        # Lock before counting; a separate statement gets a fresh READ COMMITTED snapshot.
        flight = cur.execute('SELECT no_serie, hora_partida FROM voo WHERE id = %s FOR UPDATE', (voo_id,)).fetchone()
        if flight is None:
            raise APIError(404, 'flight_not_found', 'Flight does not exist.')
        if cur.execute('SELECT %s <= clock_timestamp()::timestamp', (flight.hora_partida,)).fetchone()[0]:
            raise APIError(409, 'flight_departed', 'Tickets cannot be purchased after departure.')
        for first_class in (True, False):
            needed = sum(cls == first_class for _, cls in tickets)
            if not needed:
                continue
            available = cur.execute('''SELECT
                (SELECT COUNT(*) FROM assento WHERE no_serie = %s AND prim_classe = %s) -
                (SELECT COUNT(*) FROM bilhete WHERE voo_id = %s AND prim_classe = %s)''',
                (flight.no_serie, first_class, voo_id, first_class)).fetchone()[0]
            if needed > available:
                raise APIError(409, 'insufficient_capacity', 'Insufficient seats in the requested class.')
        reservation = cur.execute('''INSERT INTO venda(nif_cliente, balcao, hora)
            VALUES (%s, NULL, clock_timestamp()::timestamp) RETURNING codigo_reserva''', (nif,)).fetchone()[0]
        ids = []
        for name, first_class in tickets:
            price = current_app.config['TICKET_PRICE_FIRST' if first_class else 'TICKET_PRICE_ECONOMY']
            ids.append(cur.execute('''INSERT INTO bilhete(voo_id, codigo_reserva, nome_passegeiro, preco, prim_classe)
                VALUES (%s, %s, %s, %s, %s) RETURNING id''', (voo_id, reservation, name, price, first_class)).fetchone()[0])
    return jsonify(codigo_reserva=reservation, bilhetes=ids), 201

@routes.route('/checkin/<bilhete_id>/', methods=['POST', 'PUT'])
def do_check_in(bilhete_id):
    bilhete_id = positive_id(bilhete_id)
    with database() as conn, conn.cursor() as cur:
        found = cur.execute('SELECT voo_id FROM bilhete WHERE id = %s', (bilhete_id,)).fetchone()
        if found is None:
            raise APIError(404, 'ticket_not_found', 'Ticket does not exist.')
        # Same lock order as purchase: flight first, then ticket.
        cur.execute('SELECT id FROM voo WHERE id = %s FOR UPDATE', (found.voo_id,)).fetchone()
        ticket = cur.execute('SELECT voo_id, prim_classe, lugar, no_serie FROM bilhete WHERE id = %s FOR UPDATE', (bilhete_id,)).fetchone()
        if ticket is None:
            raise APIError(404, 'ticket_not_found', 'Ticket does not exist.')
        if ticket.voo_id != found.voo_id:
            raise APIError(409, 'ticket_changed', 'Ticket changed concurrently; retry check-in.')
        if ticket.lugar is not None:
            return jsonify(bilhete_id=bilhete_id, lugar=ticket.lugar, no_serie=ticket.no_serie), 200
        seat = cur.execute('''SELECT a.lugar, a.no_serie FROM assento a JOIN voo v ON v.no_serie = a.no_serie
            WHERE v.id = %s AND a.prim_classe = %s AND NOT EXISTS (
                SELECT 1 FROM bilhete b WHERE b.voo_id = v.id AND b.lugar = a.lugar)
            ORDER BY a.lugar LIMIT 1''', (ticket.voo_id, ticket.prim_classe)).fetchone()
        if seat is None:
            raise APIError(409, 'no_available_seat', 'No seat is available in the ticket class.')
        cur.execute('UPDATE bilhete SET lugar = %s, no_serie = %s WHERE id = %s', (seat.lugar, seat.no_serie, bilhete_id))
    return jsonify(bilhete_id=bilhete_id, lugar=seat.lugar, no_serie=seat.no_serie), 200
