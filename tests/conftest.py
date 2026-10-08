import os
from pathlib import Path
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

import aviation_api as module

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def empty_db_url():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to an isolated PostgreSQL database ending in _test')
    if not conninfo_to_dict(url).get('dbname', '').endswith('_test'):
        pytest.fail('TEST_DATABASE_URL database name must end in _test')
    schema = 'aviation_test_' + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    scoped = make_conninfo(url, options=f'-c search_path={schema} -c timezone=UTC')
    try:
        yield scoped
    finally:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


@pytest.fixture
def db_url(empty_db_url):
    with psycopg.connect(empty_db_url, autocommit=True) as conn:
        for name in ('database/schema/001_initial.sql', 'database/migrations/002_integrity.sql', 'tests/seed.sql'):
            conn.execute((ROOT / name).read_text(), prepare=False)
    return empty_db_url


@pytest.fixture
def app(db_url):
    app = module.create_app({'TESTING': True, 'DATABASE_URL': db_url,
        'DB_OPTIONS': conninfo_to_dict(db_url)['options'] + ' -c lock_timeout=5000 -c statement_timeout=10000',
        'RATELIMIT_ENABLED': False, 'DB_POOL_MIN_SIZE': 0})
    yield app
    app.extensions['postgres_pool'].close()


@pytest.fixture
def client(app):
    return app.test_client()
