#!/usr/bin/env python3
"""Transactional SQL migrations and a separate, once-only demonstration seed."""
import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / 'database/schema/001_initial.sql',
    ROOT / 'database/migrations/002_integrity.sql',
    ROOT / 'database/migrations/003_statistics.sql',
)


def lock(conn):
    # Scoped to the current database and schema; serializes setup commands.
    conn.execute('SELECT pg_advisory_xact_lock(hashtext(current_schema()), 714032)')


def migration_files():
    for path in MIGRATIONS:
        content = path.read_bytes()
        yield path.name, hashlib.sha256(content).hexdigest(), content.decode()


def migrate(conn):
    with conn.transaction():
        lock(conn)
        conn.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
            version text PRIMARY KEY, checksum text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        installed = dict(conn.execute('SELECT version, checksum FROM schema_migrations').fetchall())
        known = {path.name for path in MIGRATIONS}
        if installed.keys() - known:
            raise ValueError('Database contains migrations unknown to this checkout.')
        for version, checksum, content in migration_files():
            if version in installed:
                if checksum != installed[version]:
                    raise ValueError(f'Applied migration changed: {version}. Add a new migration instead.')
                continue
            conn.execute(content, prepare=False)
            conn.execute('INSERT INTO schema_migrations(version,checksum) VALUES (%s,%s)', (version, checksum))
            print(f'Applied {version}')
    print('Database migrations are up to date.')


def seed_demo(conn, as_of=None):
    with conn.transaction():
        lock(conn)
        installed = dict(conn.execute('SELECT version,checksum FROM schema_migrations').fetchall())
        expected = {version: checksum for version, checksum, _ in migration_files()}
        if installed != expected:
            raise ValueError('Run migrate with this checkout before loading the demo seed.')
        conn.execute('''CREATE TABLE IF NOT EXISTS demo_seed_runs (
            name text PRIMARY KEY, as_of timestamptz NOT NULL,
            loaded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
        existing = conn.execute("SELECT as_of FROM demo_seed_runs WHERE name='demo_v1'").fetchone()
        if existing:
            print(f'Demo already loaded with clock {existing[0].isoformat()}; no records changed.')
            return
        for table in ('aeroporto','aviao','assento','voo','venda','bilhete'):
            # Fixed internal identifiers, never user-controlled SQL.
            if conn.execute(f'SELECT EXISTS(SELECT 1 FROM {table})').fetchone()[0]:
                raise ValueError('Demo seed requires empty application tables; existing records are preserved.')
        as_of = as_of or datetime.now(timezone.utc).replace(microsecond=0)
        conn.execute("SELECT set_config('aviation.demo_as_of', %s, true)", (as_of.astimezone(timezone.utc).isoformat(),))
        conn.execute((ROOT / 'database/seeds/demo.sql').read_text(), prepare=False)
        conn.execute("INSERT INTO demo_seed_runs(name,as_of) VALUES('demo_v1',%s)", (as_of,))
        conn.execute('REFRESH MATERIALIZED VIEW estatisticas_voos')
    print(f'Demo loaded with clock {as_of.isoformat()}.')


def parse_clock(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError('--as-of requires an ISO timestamp with a timezone.')
    return parsed.astimezone(timezone.utc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['migrate','seed-demo','bootstrap','refresh-stats'])
    parser.add_argument('--as-of', type=parse_clock, help='Fixed UTC clock for deterministic demo schedules.')
    args = parser.parse_args()
    url = os.environ.get('DATABASE_URL')
    if not url:
        parser.error('Set DATABASE_URL to the target PostgreSQL database.')
    if args.as_of and args.command not in ('seed-demo','bootstrap'):
        parser.error('--as-of applies only to seed-demo and bootstrap.')
    try:
        with psycopg.connect(url, autocommit=True, options='-c timezone=UTC -c lock_timeout=10000 -c statement_timeout=60000') as conn:
            if args.command in ('migrate','bootstrap'):
                migrate(conn)
            if args.command in ('seed-demo','bootstrap'):
                seed_demo(conn, args.as_of)
            if args.command == 'refresh-stats':
                conn.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY estatisticas_voos')
                print('Statistics refreshed.')
    except (psycopg.Error, ValueError) as error:
        detail = error.diag.message_primary if isinstance(error, psycopg.Error) else str(error)
        print(f'Database setup failed: {detail or type(error).__name__}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
