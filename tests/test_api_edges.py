from concurrent.futures import ThreadPoolExecutor
import threading

import psycopg
import pytest
from conftest import module
from test_correctness import insert_ticket, purchase


def test_body_limit_and_method_errors_are_json(client):
    too_large = client.post('/compra/1/', data='x'*(64*1024+1), content_type='application/json')
    assert too_large.status_code == 413 and too_large.json['error']['code'] == 'request_entity_too_large'
    wrong_method = client.delete('/checkin/1/')
    assert wrong_method.status_code == 405
    assert 'POST' in wrong_method.headers['Allow'] and 'PUT' in wrong_method.headers['Allow']
    assert client.get('/missing/').json['error']['code'] == 'not_found'


def test_unexpected_error_is_sanitized(app, monkeypatch):
    import importlib
    routes_module = importlib.import_module('aviation_api.routes')
    def fail():
        raise RuntimeError('private passenger or database information')
    monkeypatch.setattr(routes_module,'database',fail)
    with app.test_client() as client:
        response = client.get('/')
        assert response.status_code == 500
        assert 'private' not in response.get_data(as_text=True)


def test_rate_limit_errors_remain_json():
    app = module.create_app({'DATABASE_URL':None,'RATELIMIT_ENABLED':True})
    with app.test_client() as client:
        responses = [client.get('/') for _ in range(51)]
    assert responses[-1].status_code == 429
    assert responses[-1].json['error']['code'] == 'too_many_requests'


@pytest.mark.parametrize('price', ['-0.01','100000.00','NaN','1.001'])
def test_invalid_configured_prices_fail_fast(price):
    with pytest.raises(ValueError):
        module.create_app({'DATABASE_URL':None,'TICKET_PRICE_FIRST':price})


def test_flight_query_time_window_and_three_flight_limit(client, db_url):
    with psycopg.connect(db_url) as conn:
        conn.execute('''INSERT INTO voo(no_serie,hora_partida,hora_chegada,partida,chegada)
            SELECT 'TEST-1',CURRENT_TIMESTAMP+offset_time,CURRENT_TIMESTAMP+offset_time+interval '30 minutes','LIS','OPO'
            FROM (VALUES(interval '-1 hour'),(interval '5 hours'),(interval '6 hours'),(interval '13 hours')) offsets(offset_time)''')
    assert len(client.get('/voos/LIS/').json) == 4
    future = client.get('/voos/LIS/OPO/').json
    assert len(future) == 3
    assert [row[0] for row in future] == ['TEST-1','TEST-2','TEST-1']


@pytest.mark.parametrize('statement', [
    "UPDATE venda SET nif_cliente='abcdefghi' WHERE codigo_reserva=1",
    "UPDATE bilhete SET preco='NaN'::numeric WHERE id=1",
    "UPDATE bilhete SET codigo_reserva=NULL WHERE id=1",
    "UPDATE voo SET no_serie='TEST-2' WHERE id=1",
    "UPDATE bilhete SET voo_id=2 WHERE id=1",
])
def test_additional_direct_integrity_rules(client, db_url, statement):
    assert purchase(client,True).status_code == 201
    with pytest.raises(psycopg.IntegrityError):
        with psycopg.connect(db_url) as conn:
            conn.execute(statement)


@pytest.mark.parametrize('isolation', ['REPEATABLE READ','SERIALIZABLE'])
def test_stale_snapshot_cannot_oversell(db_url, isolation):
    first = psycopg.connect(db_url)
    snapshot_ready = threading.Event()
    try:
        insert_ticket(first,'Winner',first=False,flight=2)
        def stale_purchase():
            with psycopg.connect(db_url) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL '+isolation)
                assert conn.execute('SELECT count(*) FROM bilhete').fetchone()[0] == 0
                snapshot_ready.set()
                with pytest.raises(psycopg.errors.SerializationFailure):
                    insert_ticket(conn,'Stale',first=False,flight=2)
                conn.rollback()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(stale_purchase)
            assert snapshot_ready.wait(timeout=5)
            first.commit()
            future.result(timeout=5)
    finally:
        first.close()
    with psycopg.connect(db_url) as conn:
        assert conn.execute('SELECT count(*) FROM bilhete').fetchone()[0] == 1
