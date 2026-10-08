# Architecture decisions

## Small Flask package

- `src/aviation_api/__init__.py`: factory, configuration, lazy connection pool and rate limiter.
- `routes.py`: original five aviation routes and SQL operations.
- `validation.py`: IDs, airport codes and purchase payload validation.
- `db.py`: pooled transaction access.
- `errors.py`: JSON HTTP/API/database errors and sanitized request logging.
- `wsgi.py`: Gunicorn application entry point.

This follows Flask's [package organization pattern](https://flask.palletsprojects.com/en/stable/patterns/packages/).
There is no ORM, service framework, frontend or new product functionality. SQL
operations remain close to the original implementation. Route paths, methods,
response shapes and validation behavior from Phase 2 remain unchanged.

## PostgreSQL owns integrity

Phase 2's per-flight database locks and per-class capacity trigger are preserved.
The trigger still writes the flight row before counting capacity, protecting
READ COMMITTED writers and rejecting stale higher-isolation writers. Unique
flight/seat assignments remain enforced independently of the application.
Purchases retain complete transactional rollback; check-in retains flight-first
locking and idempotent responses. Database-parent edits remain restricted.

Migrations use a separate advisory lock only to serialize setup commands. It is
not a substitute for ticket-operation locks. SQL files no longer contain their
own BEGIN/COMMIT wrappers because the migration runner owns the entire transaction.

## Separate schemas, migrations and seeds

The original relational schema is recognizable, including Portuguese names and
the historical `nome_passegeiro` spelling. Its destructive reset statements were
removed. Additional constraints and materialized statistics are ordered SQL
migrations; analytics are read-only scripts outside the migration sequence.
No extension or PostGIS dependency is necessary.

The seed is synthetic and stable relative to a recorded UTC clock. It is separate
from migrations and from the original invalid dataset. Seeding never disables
triggers and is deliberately refused on an unmarked, populated database. Test
fixtures remain independent from demo data so existing capacity/concurrency
regressions retain their original meaning.

## Development containers

Compose runs only PostgreSQL, a one-shot initializer, and the Flask/Gunicorn image.
The image runs as an unprivileged OS user. The PostgreSQL development role owns
the database; it is not a least-privilege production role. Credentials in the
example are public development placeholders and ports are localhost-only.

The original bounded PostgreSQL wait script is retained; Compose adds database
readiness and migration completion gating. Startup is independent of the
university environment. PostgreSQL data persists across container restarts.
BSD notices and the full license are included in the application image.

## Remaining limitations

- Development database privileges and placeholder credentials need a separate production design.
- In-memory rate limiting remains per worker; shared Redis limiting is optional but not provisioned or verified here.
- PUT purchases remain non-idempotent for compatibility; no automatic retry is safe after an uncertain response.
- PostgreSQL timestamps remain timezone-free, with UTC application sessions.
- GET results remain positional arrays; a versioned object-based API is deferred.
- Materialized statistics require explicit refresh; no scheduler is provided.
- Migration DDL can block writers; apply it while API workers are stopped.
- GitHub CI is configured; its first hosted execution and cloud deployment remain outside local verification.

## Verification and readiness

PostgreSQL has a Docker health check, and successful initializer completion gates
API startup. The API has no separate Docker health probe. Startup gating does not
automatically stop the API during a later database outage; clients receive a
sanitized 503 and the connection pool can recover after PostgreSQL restarts.
These behaviors are exercised in the local Docker verification record.

The configured [CI workflow](../.github/workflows/ci.yml) runs isolated PostgreSQL
integration tests and Python lint/coverage checks. Its first GitHub-hosted execution
remains pending; [verification.md](verification.md) records actual local results.
