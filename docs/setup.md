# Development setup

Requirements: Docker Engine with the Compose and Buildx plugins, or Python 3.12
and a running PostgreSQL 16 server. Standard PostgreSQL is sufficient; this project
uses no geospatial types or queries and does not require PostGIS.

## Minimal Docker startup

From the repository root:

```bash
cp .env.example .env
docker compose up -d --build --wait
curl http://localhost:8080/
curl http://localhost:8080/voos/LIS/
```

Compose starts PostgreSQL, waits for its readiness check, runs a one-shot `init`
service, and then starts Gunicorn with two workers. The initializer applies the
three migrations and loads the separate demo dataset. `.env` is ignored by Git;
its example password is only a local development placeholder. Both published
ports bind to localhost. No university server or account is required.

Startup gating uses Compose's documented
[health and completion conditions](https://docs.docker.com/compose/how-tos/startup-order/).
The [official PostgreSQL image](https://hub.docker.com/_/postgres) uses a persistent
volume here; initialization is handled by the project's migration command rather
than relying on first-boot SQL files.

This verification workspace lacks the Buildx plugin. Its tested fallback is:

```bash
DOCKER_BUILDKIT=0 docker build -t aviation-database-api:local .
docker compose up -d --no-build --wait
```

The fallback uses Docker's deprecated legacy builder. A regular developer setup
should install Buildx and use the normal startup command above.

Inspect services or stop them without deleting the database:

```bash
docker compose ps -a
docker compose logs init api
docker compose down
```

Changing the example environment after the first database initialization does not
change existing database credentials. Existing volumes keep data and demo times.
To start over, use a new Compose project name and unused ports, or explicitly
remove an expendable development volume after confirming that its data is unwanted.

## Database initialization and migrations

Normal first startup performs these automatically. Explicit commands are:

```bash
docker compose run --rm init python scripts/database.py migrate
docker compose run --rm init python scripts/database.py seed-demo
docker compose run --rm init python scripts/database.py refresh-stats
```

Execution order:

1. `database/schema/001_initial.sql`: original table design, without destructive DROP statements.
2. `database/migrations/002_integrity.sql`: Phase 2 locks, triggers, checks, unique constraints and query indexes.
3. `database/migrations/003_statistics.sql`: flight statistics materialized view and refresh indexes.
4. `database/seeds/demo.sql`: optional, separate demo data with every integrity rule enabled.

Migrations execute atomically under a PostgreSQL advisory transaction lock and
record their checksums in `schema_migrations`. Repeated calls skip applied versions.
Changed applied migrations and unknown migration versions are rejected. Add future
SQL files to the ordered migration list; do not edit an already deployed migration.
Existing populated legacy databases are not automatically adopted or repaired.

The demo seed records its chosen clock in `demo_seed_runs` and loads only once.
It refuses nonempty application tables unless its own seed marker already exists.
It never drops records or silently repairs an incomplete or incompatible import.
All schedules, names, IDs, classes and prices are deterministic relative to this
clock; the default is the current UTC time so flight queries work immediately.
For an exactly repeatable first load:

```bash
docker compose up -d db
docker compose run --rm init python scripts/database.py migrate
docker compose run --rm init python scripts/database.py seed-demo --as-of 2026-10-09T10:00:00Z
docker compose up -d api
```

A repeated seed command preserves its original clock even if `--as-of` changes.
Flights will eventually become historical; use a new disposable database for a
fresh demonstration. Updating existing flight times would weaken the intended
immutability rules and is not part of seeding.

For existing deployments, stop API workers, build the updated image, run `migrate`,
and then start the API. Integrity migrations take exclusive table locks and may
reject incompatible existing data. Do not run a seed over real application data.

## Local Python with Compose PostgreSQL

```bash
cp .env.example .env
docker compose up -d db
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]' -c requirements.lock
export DATABASE_URL='postgresql://aviation_dev:local_only_aviation@127.0.0.1:5432/aviation'
python scripts/database.py migrate
python scripts/database.py seed-demo
flask --app aviation_api:create_app run --port 8080
```

Host commands do not automatically read `.env`; export `DATABASE_URL` explicitly.
Use your own connection string if PostgreSQL is installed directly. An equivalent
non-Docker first step is `createdb aviation`, with a local connection string such
as `export DATABASE_URL='dbname=aviation'`.

The editable package installs the code under `src/aviation_api`. The direct
application dependencies are pinned in `requirements.txt`; tested transitive
versions are constrained in `requirements.lock`. The Docker Python base tag may
receive patch updates; image builds are reproducible at the dependency-version
level, not guaranteed byte-for-byte identical across future base-image changes.

## Demo requests

The demo contains four airports, two aircraft, ten seats, five flights, two
reservations and four tickets. Flight 1001 has one first-class and three economy
seats available; flight 1003 has economy seats only. Ticket 1002 is ready for
check-in. The past flight's tickets already have valid seat assignments.

```bash
curl -X POST http://localhost:8080/compra/1001/ \
  -H 'Content-Type: application/json' \
  -d '{"nif_cliente":"123456789","bilhetes":[["Demo Passenger",true]]}'
curl -X PUT http://localhost:8080/checkin/1002/
```

These commands change demo data. NIFs are synthetic format examples; no checksum
or real taxpayer validation is performed. Use the returned ticket IDs for new
check-in requests. Repeating a purchase can create another sale; repeating
check-in returns the existing seat.

## Automated tests and quality checks

Use an isolated test database. Names must end in `_test`. Tests create and remove
only their own random schemas; the test role needs schema creation privileges.
Do not point tests at the demonstration or a production database.

With Compose PostgreSQL and the activated virtual environment:

```bash
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" aviation_test'
export TEST_DATABASE_URL='postgresql://aviation_dev:local_only_aviation@127.0.0.1:5432/aviation_test'
pytest -q tests/test_correctness.py \
  -k 'exact_capacity or competing or duplicate_seat or mid_purchase'
pytest -q
```

Create the test database once; omit `createdb` if it already exists. Tests skip
integration cases when `TEST_DATABASE_URL` is unset, so verify the pass/skip counts.
All 54 original regressions remain; new setup and edge-case tests are included in the complete suite.
See [testing.md](testing.md) for lint, coverage, CI and current verification results.

## Materialized statistics and analytics

Statistics are refreshed after the initial demo load. Later purchases do not
automatically refresh the materialized view:

```bash
docker compose run --rm init python scripts/database.py refresh-stats
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < database/analytics/reports.sql
```

## Original dataset

The complete original seed is preserved outside the public repository and has
not been modified. It cannot load under the strengthened capacity constraints.
See [the legacy-data record](../database/legacy/README.md) for hashes, findings
and instructions for running the read-only audit in a separate baseline database.

## Environment variables

| Variable | Default / use |
| --- | --- |
| `DATABASE_URL` | Required application/setup connection string. Host `.env.example` targets localhost; Compose overrides it with the container host. |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Compose database initialization: `aviation`, `aviation_dev`, `local_only_aviation`. Development placeholders only. |
| `POSTGRES_PORT` / `HTTP_PORT` | Localhost published ports: 5432 / 8080. |
| `WEB_CONCURRENCY` | Gunicorn worker count: 2. Each process owns its pool. |
| `FLASK_ENV` | Startup script mode; Compose uses `production` for Gunicorn. |
| `FLASK_DEBUG` | Compose sets 0. Do not enable debug mode publicly. |
| `FLASK_TICKET_PRICE_FIRST` / `FLASK_TICKET_PRICE_ECONOMY` | Decimal demo fares: 300.00 / 150.00. |
| `FLASK_DB_POOL_MIN_SIZE` / `FLASK_DB_POOL_MAX_SIZE` / `FLASK_DB_POOL_TIMEOUT` | Pool configuration: 1 / 10 / 5 seconds. |
| `FLASK_DB_OPTIONS` | Trusted libpq options; default UTC, 5-second lock timeout and 10-second statement timeout. |
| `FLASK_MAX_CONTENT_LENGTH` | Maximum request body: 65536 bytes. |
| `FLASK_LOG_LEVEL` | Application logging: INFO. |
| `RATELIMIT_STORAGE_URI` | `memory://`; process-local. Redis is not provisioned here. |
| `FLASK_RATELIMIT_ENABLED` | Enabled by default; isolated tests disable it except rate-limit tests. |
| `TEST_DATABASE_URL` | Dedicated test database ending in `_test`; required for integration verification. |

Compose passes `PGDATABASE`, `PGUSER` and `PGPASSWORD` to its application/initializer
containers from the development PostgreSQL variables. Libpq combines these with
the container `DATABASE_URL`; passwords need not be interpolated into a URI.
`FLASK_*` values use Flask's environment configuration parsing; use JSON `true`/
`false` for boolean overrides. Configuration files containing real credentials
remain local and ignored.
