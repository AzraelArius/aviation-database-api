from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import threading

import psycopg
import pytest
from conftest import ROOT

spec = importlib.util.spec_from_file_location('database_setup', ROOT / 'scripts/database.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
CLOCK = datetime(2026, 10, 9, 10, tzinfo=timezone.utc)


def bootstrap(url):
    with psycopg.connect(url, autocommit=True) as conn:
        setup.migrate(conn)
        setup.seed_demo(conn, CLOCK)


def test_bootstrap_repeat_preserves_clock_and_user_records(empty_db_url):
    bootstrap(empty_db_url)
    with psycopg.connect(empty_db_url, autocommit=True) as conn:
        assert conn.execute('SELECT count(*) FROM schema_migrations').fetchone()[0] == 3
        assert conn.execute('SELECT (SELECT count(*) FROM voo),(SELECT count(*) FROM venda),(SELECT count(*) FROM bilhete)').fetchone() == (5, 2, 4)
        conn.execute("UPDATE bilhete SET lugar='1A',no_serie='DEMO-A' WHERE id=1002")
        setup.migrate(conn)
        setup.seed_demo(conn, CLOCK.replace(day=10))
        assert conn.execute('SELECT as_of FROM demo_seed_runs').fetchone()[0] == CLOCK
        assert conn.execute('SELECT lugar FROM bilhete WHERE id=1002').fetchone()[0] == '1A'
        assert conn.execute('SELECT count(*) FROM bilhete').fetchone()[0] == 4
        assert conn.execute('SELECT SUM(passageiros_1c+passageiros_2c) FROM estatisticas_voos').fetchone()[0] == 4


def test_competing_bootstrap_is_once_only(empty_db_url):
    barrier = threading.Barrier(2)
    def run():
        barrier.wait(timeout=5)
        bootstrap(empty_db_url)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)
    with psycopg.connect(empty_db_url) as conn:
        assert conn.execute('SELECT (SELECT count(*) FROM schema_migrations),(SELECT count(*) FROM demo_seed_runs),(SELECT count(*) FROM bilhete)').fetchone() == (3, 1, 4)


@pytest.mark.parametrize('corruption', ['checksum', 'unknown_version'])
def test_migrations_reject_changed_history(empty_db_url, corruption):
    bootstrap(empty_db_url)
    with psycopg.connect(empty_db_url, autocommit=True) as conn:
        if corruption == 'checksum':
            conn.execute("UPDATE schema_migrations SET checksum='changed' WHERE version='001_initial.sql'")
        else:
            conn.execute("INSERT INTO schema_migrations(version,checksum) VALUES('unknown.sql','changed')")
        with pytest.raises(ValueError):
            setup.migrate(conn)
        assert conn.execute('SELECT count(*) FROM bilhete').fetchone()[0] == 4


def test_migration_failure_rolls_back_ddl_and_history(empty_db_url, monkeypatch):
    def migrations():
        yield '001_initial.sql', 'first', 'CREATE TABLE rollback_probe(id integer);'
        yield '002_integrity.sql', 'second', 'SELECT 1/0;'
    monkeypatch.setattr(setup, 'migration_files', migrations)
    with psycopg.connect(empty_db_url, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.DivisionByZero):
            setup.migrate(conn)
        assert conn.execute("SELECT to_regclass('rollback_probe'),to_regclass('schema_migrations')").fetchone() == (None, None)


def test_seed_rejects_nonempty_database_without_deleting_records(empty_db_url):
    with psycopg.connect(empty_db_url, autocommit=True) as conn:
        setup.migrate(conn)
        conn.execute("INSERT INTO aeroporto VALUES('LIS','Existing airport','Lisbon','Portugal')")
        with pytest.raises(ValueError, match='requires empty'):
            setup.seed_demo(conn, CLOCK)
        assert conn.execute('SELECT nome FROM aeroporto').fetchone()[0] == 'Existing airport'
        assert conn.execute("SELECT to_regclass('demo_seed_runs')").fetchone()[0] is None


def test_seed_failure_rolls_back_every_application_row(empty_db_url):
    with psycopg.connect(empty_db_url, autocommit=True) as conn:
        setup.migrate(conn)
        conn.execute('''CREATE FUNCTION reject_demo() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='intentional seed failure'; END $$;
            CREATE TRIGGER reject_demo BEFORE INSERT ON bilhete FOR EACH ROW EXECUTE FUNCTION reject_demo();''')
        with pytest.raises(psycopg.errors.CheckViolation):
            setup.seed_demo(conn, CLOCK)
        assert conn.execute('SELECT (SELECT count(*) FROM aeroporto),(SELECT count(*) FROM voo),(SELECT count(*) FROM venda),(SELECT count(*) FROM bilhete)').fetchone() == (0, 0, 0, 0)
        assert conn.execute("SELECT to_regclass('demo_seed_runs')").fetchone()[0] is None


def test_seed_requires_current_migration_checksums(empty_db_url):
    with psycopg.connect(empty_db_url, autocommit=True) as conn:
        setup.migrate(conn)
        conn.execute("UPDATE schema_migrations SET checksum='changed' WHERE version='002_integrity.sql'")
        with pytest.raises(ValueError, match='Run migrate'):
            setup.seed_demo(conn, CLOCK)
        assert conn.execute('SELECT count(*) FROM aeroporto').fetchone()[0] == 0


@pytest.mark.parametrize('value', ['2026-10-09T10:00:00', 'invalid'])
def test_cli_rejects_ambiguous_or_invalid_clock(value, monkeypatch):
    monkeypatch.setattr('sys.argv', ['database.py','bootstrap','--as-of',value])
    with pytest.raises(SystemExit) as error:
        setup.main()
    assert error.value.code == 2


def test_cli_requires_connection_and_valid_command_options(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr('sys.argv', ['database.py','migrate'])
    with pytest.raises(SystemExit) as error:
        setup.main()
    assert error.value.code == 2
    monkeypatch.setenv('DATABASE_URL','unused')
    monkeypatch.setattr('sys.argv', ['database.py','migrate','--as-of','2026-10-09T10:00:00Z'])
    with pytest.raises(SystemExit) as error:
        setup.main()
    assert error.value.code == 2


def test_cli_connection_failure_returns_failure_status(monkeypatch, capsys):
    monkeypatch.setenv('DATABASE_URL','unused')
    monkeypatch.setattr('sys.argv', ['database.py','bootstrap'])
    def fail(*args, **kwargs):
        raise psycopg.OperationalError('simulated connection failure')
    monkeypatch.setattr(setup.psycopg,'connect',fail)
    assert setup.main() == 1
    assert 'Database setup failed' in capsys.readouterr().err


def test_cli_bootstrap_and_refresh_dispatch(empty_db_url, monkeypatch, capsys):
    from psycopg.conninfo import conninfo_to_dict
    connect = psycopg.connect
    def scoped_connect(url, **kwargs):
        # Keep CLI timeout options while targeting this test's isolated schema.
        kwargs['options'] += ' ' + conninfo_to_dict(url)['options']
        return connect(url, **kwargs)
    monkeypatch.setattr(setup.psycopg,'connect',scoped_connect)
    monkeypatch.setenv('DATABASE_URL',empty_db_url)
    monkeypatch.setattr('sys.argv',['database.py','bootstrap'])
    assert setup.main() == 0
    monkeypatch.setattr('sys.argv',['database.py','refresh-stats'])
    assert setup.main() == 0
    assert 'Statistics refreshed' in capsys.readouterr().out
