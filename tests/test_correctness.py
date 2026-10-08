from concurrent.futures import ThreadPoolExecutor
import threading
import time

import psycopg
from psycopg import sql
import pytest
from conftest import ROOT, module


def payload(*classes):
    return {'nif_cliente': '123456789', 'bilhetes': [[f'Passenger {i}', cls] for i, cls in enumerate(classes)]}


def purchase(client, *classes, flight=1):
    return client.post(f'/compra/{flight}/', json=payload(*classes))


def counts(url):
    with psycopg.connect(url) as conn:
        return conn.execute('SELECT (SELECT COUNT(*) FROM venda), (SELECT COUNT(*) FROM bilhete)').fetchone()


def race(functions):
    barrier = threading.Barrier(len(functions))
    def run(fn):
        barrier.wait(timeout=5)
        return fn()
    with ThreadPoolExecutor(max_workers=len(functions)) as executor:
        return list(executor.map(run, functions))


@pytest.mark.parametrize('classes', [(True, True), (False, False, False), (True, True, False, False, False)])
def test_exact_capacity(client, db_url, classes):
    response = purchase(client, *classes)
    assert response.status_code == 201
    assert len(response.json['bilhetes']) == len(classes)
    assert counts(db_url) == (1, len(classes))


def test_economy_only_aircraft(client):
    assert purchase(client, False, flight=2).status_code == 201
    assert purchase(client, True, flight=2).status_code == 409


def test_purchase_with_other_class_exhausted(client):
    assert purchase(client, True, True).status_code == 201
    assert purchase(client, False, False, False).status_code == 201


@pytest.mark.parametrize('classes', [(True, True, True), (False, False, False, False)])
def test_insufficient_capacity_rolls_back(client, db_url, classes):
    response = purchase(client, *classes)
    assert response.status_code == 409
    assert counts(db_url) == (0, 0)


def test_competing_purchases_across_app_pools(app, db_url):
    other = module.create_app({**app.config, 'DB_POOL_MIN_SIZE': 0})
    def buy(application):
        with application.test_client() as client:
            return purchase(client, True, True).status_code
    try:
        assert sorted(race([lambda: buy(app), lambda: buy(other)])) == [201, 409]
        assert counts(db_url) == (1, 2)
    finally:
        other.extensions['postgres_pool'].close()


def test_checkin_idempotent(client):
    ticket = purchase(client, True).json['bilhetes'][0]
    first = client.post(f'/checkin/{ticket}/')
    second = client.put(f'/checkin/{ticket}/')
    assert first.status_code == second.status_code == 200
    assert first.json == second.json


@pytest.mark.parametrize('same_ticket', [False, True])
def test_concurrent_checkin(app, db_url, same_ticket):
    with app.test_client() as client:
        tickets = purchase(client, False, False).json['bilhetes']
    if same_ticket:
        tickets[1] = tickets[0]
    def check(ticket):
        with app.test_client() as client:
            r = client.post(f'/checkin/{ticket}/')
            assert r.status_code == 200
            return r.json['lugar']
    places = race([lambda: check(tickets[0]), lambda: check(tickets[1])])
    assert (places[0] == places[1]) == same_ticket
    with psycopg.connect(db_url) as conn:
        assert conn.execute('SELECT COUNT(*) = COUNT(DISTINCT lugar) FROM bilhete WHERE lugar IS NOT NULL').fetchone()[0]


def test_duplicate_seat_rejected_by_database(client, db_url):
    ids = purchase(client, False, False).json['bilhetes']
    assert client.post(f'/checkin/{ids[0]}/').status_code == 200
    with pytest.raises(psycopg.errors.UniqueViolation):
        with psycopg.connect(db_url) as conn:
            conn.execute("UPDATE bilhete SET lugar='2A', no_serie='TEST-1' WHERE id=%s", (ids[1],))
    with psycopg.connect(db_url) as conn:
        assert conn.execute('SELECT lugar FROM bilhete WHERE id=%s', (ids[1],)).fetchone()[0] is None


def test_mid_purchase_database_failure_rolls_back(client, db_url):
    with psycopg.connect(db_url) as conn:
        conn.execute('''CREATE FUNCTION reject_second_ticket() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.nome_passegeiro = 'Passenger 1' THEN
              RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='injected private test failure';
            END IF; RETURN NEW; END $$;
            CREATE TRIGGER zz_reject_second BEFORE INSERT ON bilhete FOR EACH ROW EXECUTE FUNCTION reject_second_ticket();''')
    response = purchase(client, False, False)
    assert response.status_code == 409
    assert 'private' not in response.get_data(as_text=True)
    assert counts(db_url) == (0, 0)


def insert_ticket(conn, name, first=True, flight=1):
    sale = conn.execute("INSERT INTO venda(nif_cliente,hora) VALUES ('123456789',clock_timestamp()::timestamp) RETURNING codigo_reserva").fetchone()[0]
    return conn.execute('''INSERT INTO bilhete(voo_id,codigo_reserva,nome_passegeiro,preco,prim_classe)
        VALUES (%s,%s,%s,100,%s) RETURNING id''', (flight, sale, name, first)).fetchone()[0]


@pytest.mark.parametrize('isolation', ['READ COMMITTED', 'REPEATABLE READ', 'SERIALIZABLE'])
def test_direct_sql_competing_capacity(db_url, isolation):
    with psycopg.connect(db_url) as conn:
        insert_ticket(conn, 'Existing')
    def buy(name):
        try:
            with psycopg.connect(db_url) as conn:
                conn.execute(sql.SQL('SET TRANSACTION ISOLATION LEVEL ' + isolation))
                insert_ticket(conn, name)
            return 'committed'
        except (psycopg.errors.CheckViolation, psycopg.errors.SerializationFailure):
            return 'rejected'
    assert sorted(race([lambda: buy('A'), lambda: buy('B')])) == ['committed', 'rejected']
    assert counts(db_url) == (2, 2)


def test_direct_sql_waits_for_competing_writer(db_url):
    # Force overlap: second insert must wait while the first holds the flight lock.
    first = psycopg.connect(db_url)
    second_started = threading.Event()
    try:
        insert_ticket(first, 'First', first=False, flight=2)
        def second():
            second_started.set()
            try:
                with psycopg.connect(db_url) as conn:
                    insert_ticket(conn, 'Second', first=False, flight=2)
            except psycopg.errors.CheckViolation:
                return 'rejected'
            return 'committed'
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(second)
            assert second_started.wait(5)
            # Observe actual PostgreSQL blocking, rather than assuming thread timing.
            with psycopg.connect(db_url) as observer:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if observer.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock')").fetchone()[0]:
                        break
                    time.sleep(.02)
                    observer.execute('SELECT pg_stat_clear_snapshot()')
                else:
                    pytest.fail('Second writer never blocked on PostgreSQL lock')
            assert not future.done()
            first.commit()
            assert future.result(timeout=5) == 'rejected'
    finally:
        first.close()
    assert counts(db_url) == (1, 1)


@pytest.mark.parametrize('body', [None, [], {}, {'nif_cliente': 123456789, 'bilhetes': [['A', True]]},
    {'nif_cliente': '123', 'bilhetes': [['A', True]]}, {'nif_cliente': '123456789', 'bilhetes': []},
    {'nif_cliente': '123456789', 'bilhetes': [['', True]]}, {'nif_cliente': '123456789', 'bilhetes': [['A', 'false']]},
    {'nif_cliente': '123456789', 'bilhetes': [['A', True], [' A ', False]]},
    {'nif_cliente': '123456789', 'bilhetes': [['A']]}, {'nif_cliente': '123456789', 'bilhetes': [['x'*81, True]]}])
def test_invalid_payloads(client, db_url, body):
    response = client.post('/compra/1/', json=body) if body is not None else client.post('/compra/1/', data='null', content_type='application/json')
    assert response.status_code == 400
    assert 'error' in response.json
    assert counts(db_url) == (0, 0)


def test_bad_json_and_content_type(client):
    assert client.post('/compra/1/', data='{', content_type='application/json').status_code == 400
    assert client.post('/compra/1/', data='{}').status_code == 415


@pytest.mark.parametrize('path', ['/compra/0/', '/compra/nope/', '/compra/2147483648/', '/checkin/-1/'])
def test_invalid_ids(client, path):
    assert client.post(path, json=payload(True)).status_code == 400


def test_missing_resources(client):
    assert purchase(client, True, flight=999).status_code == 404
    assert client.post('/checkin/999/').status_code == 404
    assert client.get('/voos/XXX/').status_code == 404
    assert client.get('/voos/LIS/XXX/').status_code == 404
    assert client.get('/voos/toolong/').status_code == 400


def test_queries(client):
    assert len(client.get('/').json) == 2
    assert len(client.get('/voos/lis/').json) == 2
    assert len(client.get('/voos/LIS/OPO/').json) == 2
    assert purchase(client, True, True, False, False, False).status_code == 201
    assert len(client.get('/voos/LIS/OPO/').json) == 1


def test_departed_purchase(client, db_url):
    with psycopg.connect(db_url) as conn:
        conn.execute("UPDATE voo SET hora_partida=clock_timestamp()-interval '1 hour' WHERE id=1")
    assert purchase(client, True).status_code == 409
    assert counts(db_url) == (0, 0)


@pytest.mark.parametrize('statement', [
    "UPDATE bilhete SET lugar='2A',no_serie='TEST-1' WHERE id=1",
    "UPDATE bilhete SET lugar='1A',no_serie='TEST-2' WHERE id=1",
    "UPDATE bilhete SET lugar='1A' WHERE id=1",
    "UPDATE bilhete SET preco=-1 WHERE id=1",
    "UPDATE bilhete SET nome_passegeiro=' ' WHERE id=1",
    "UPDATE venda SET hora=hora+interval '1 day' WHERE codigo_reserva=1",
    "UPDATE voo SET hora_partida=hora_partida+interval '1 minute' WHERE id=1",
    "DELETE FROM assento WHERE lugar='1A' AND no_serie='TEST-1'",
])
def test_direct_constraints(client, db_url, statement):
    assert purchase(client, True).status_code == 201
    with pytest.raises(psycopg.IntegrityError):
        with psycopg.connect(db_url) as conn:
            conn.execute(statement)


def test_ticket_class_update_capacity(client, db_url):
    ids = purchase(client, True, True, False).json['bilhetes']
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(db_url) as conn:
            conn.execute('UPDATE bilhete SET prim_classe=true WHERE id=%s', (ids[-1],))


def test_database_unconfigured():
    app = module.create_app({'DATABASE_URL': None, 'RATELIMIT_ENABLED': False})
    with app.test_client() as client:
        r = client.get('/')
        assert r.status_code == 503
        assert r.json['error']['code'] == 'database_unavailable'


def test_connection_failure_is_sanitized():
    app = module.create_app({'DATABASE_URL': 'dbname=unavailable_test host=/tmp/aviation-no-such-socket',
        'RATELIMIT_ENABLED': False, 'DB_POOL_MIN_SIZE': 0, 'DB_POOL_TIMEOUT': .1})
    try:
        with app.test_client() as client:
            response = client.get('/')
            assert response.status_code == 503
            assert 'socket' not in response.get_data(as_text=True)
    finally:
        app.extensions['postgres_pool'].close()


def test_direct_multirow_oversell_rolls_back(db_url):
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(db_url) as conn:
            sale = conn.execute("INSERT INTO venda(nif_cliente,hora) VALUES ('123456789',clock_timestamp()) RETURNING codigo_reserva").fetchone()[0]
            conn.execute('''INSERT INTO bilhete(voo_id,codigo_reserva,nome_passegeiro,preco,prim_classe)
                VALUES (1,%s,'A',100,true),(1,%s,'B',100,true),(1,%s,'C',100,true)''', (sale, sale, sale))
    assert counts(db_url) == (0, 0)


def test_direct_duplicate_seat_concurrency(client, db_url):
    ids = purchase(client, False, False).json['bilhetes']
    def assign(ticket):
        try:
            with psycopg.connect(db_url) as conn:
                conn.execute("UPDATE bilhete SET lugar='2A',no_serie='TEST-1' WHERE id=%s", (ticket,))
            return 'committed'
        except (psycopg.errors.UniqueViolation, psycopg.errors.DeadlockDetected):
            return 'rejected'
    assert sorted(race([lambda: assign(ids[0]), lambda: assign(ids[1])])) == ['committed', 'rejected']


@pytest.mark.parametrize('mutation', [
    "INSERT INTO bilhete(voo_id,codigo_reserva,nome_passegeiro,preco,prim_classe) VALUES(1,1,'Late',100,true)",
    "UPDATE bilhete SET codigo_reserva=1 WHERE id=1",
])
def test_sale_time_must_precede_departure(db_url, mutation):
    with psycopg.connect(db_url) as conn:
        # Sale 1 is deliberately too late; sale 2 is valid.
        conn.execute("INSERT INTO venda(nif_cliente,hora) SELECT '123456789',hora_partida FROM voo WHERE id=1")
        insert_ticket(conn, 'Valid')
    with pytest.raises(psycopg.errors.CheckViolation):
        with psycopg.connect(db_url) as conn:
            conn.execute(mutation)


def test_checkin_reports_unavailable_seat(client, db_url):
    ticket = purchase(client, False).json['bilhetes'][0]
    with psycopg.connect(db_url) as conn:
        # Deliberately simulate legacy corruption; normal writes cannot do this.
        conn.execute('ALTER TABLE assento DISABLE TRIGGER guard_seat_layout')
        conn.execute("DELETE FROM assento WHERE no_serie='TEST-1' AND NOT prim_classe")
        conn.execute('ALTER TABLE assento ENABLE TRIGGER guard_seat_layout')
    response = client.post(f'/checkin/{ticket}/')
    assert response.status_code == 409
    assert response.json['error']['code'] == 'no_available_seat'


def test_parameterized_passenger_name(client, db_url):
    name = "O'Brien'; DROP TABLE voo; --"
    r = client.post('/compra/1/', json={'nif_cliente': '123456789', 'bilhetes': [[name, True]]})
    assert r.status_code == 201
    with psycopg.connect(db_url) as conn:
        assert conn.execute('SELECT nome_passegeiro FROM bilhete').fetchone()[0] == name
        assert conn.execute('SELECT COUNT(*) FROM voo').fetchone()[0] == 2


def test_materialized_view_and_analytics(db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute((ROOT / 'database/migrations/003_statistics.sql').read_text(), prepare=False)
        assert conn.execute('SELECT SUM(passageiros_1c+passageiros_2c) FROM estatisticas_voos').fetchone()[0] == 0
        conn.execute("""INSERT INTO voo(no_serie,hora_partida,hora_chegada,partida,chegada)
            VALUES('TEST-1',CURRENT_TIMESTAMP-interval '1 day',CURRENT_TIMESTAMP-interval '23 hours','OPO','LIS')""")
        sale = conn.execute("INSERT INTO venda(nif_cliente,hora) VALUES('123456789',CURRENT_TIMESTAMP-interval '2 days') RETURNING codigo_reserva").fetchone()[0]
        conn.execute("""INSERT INTO bilhete(voo_id,codigo_reserva,nome_passegeiro,preco,prim_classe)
            VALUES(3,%s,'First',200,true),(3,%s,'Economy',100,false)""", (sale, sale))
        # View stays stale until explicitly refreshed.
        assert conn.execute('SELECT COUNT(*) FROM estatisticas_voos').fetchone()[0] == 2
        conn.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY estatisticas_voos')
        assert conn.execute('SELECT passageiros_1c,passageiros_2c,vendas_1c,vendas_2c FROM estatisticas_voos WHERE hora_partida<CURRENT_TIMESTAMP').fetchone() == (1, 1, 200, 100)
        cur = conn.execute((ROOT / 'database/analytics/reports.sql').read_text(), prepare=False)
        results = [cur.fetchall()]
        while cur.nextset():
            results.append(cur.fetchall())
        assert len(results) == 4
        assert results[0][0][:2] == ('Lisbon', 'Porto')
        assert float(results[0][0][2]) == .4
        assert results[1] == []  # No completed flight by TEST-2 in the time window.
        global_revenue = [row for row in results[2] if row[7:9] == (15, 7)]
        assert len(global_revenue) == 1 and global_revenue[0][-1] == 300
        assert any(row[5] == 15 and row[-1] == 1 for row in results[3])
