# Phase 3 verification and change record

## Preservation and file changes

The original folder was renamed to `aviation-database-api`. Before restructuring,
a complete backup was created at `../backups/entrega-bd-02-09-before-phase3.tar.gz`.
SHA-256: `13378d0c4e6c1616f17bce772a7e58b8cdae206e6ba384e9f2069582c7f3bd7a`.

| Previous location | Current location / action |
| --- | --- |
| `app/app.py` | Split into the factory, routes, validation, database access and error modules under `src/aviation_api/`. |
| `app/wsgi.py` | Replaced by root `wsgi.py` importing the factory. |
| `app/requirements.txt` | Moved to root; added tested transitive constraints in `requirements.lock`. |
| `app/LICENSE.md` | Moved to root with unchanged license text and normalized LF line endings; included in the Docker image. |
| `app/entrypoint`, `app/start` | Moved to `scripts/`; bounded wait and Gunicorn behavior retained. |
| `data/aviacao.sql` | Table design moved to `database/schema/001_initial.sql`; destructive DROP statements removed. Exact original archived separately. |
| `data/constraints.sql` | Moved to `database/migrations/002_integrity.sql`; only transaction ownership/comments changed. The migration runner owns BEGIN/COMMIT. |
| `data/views.sql` | Moved to `database/migrations/003_statistics.sql`. |
| `data/analytics.sql` | Moved to `database/analytics/reports.sql`. |
| `data/seed_audit.sql` | Moved to `database/legacy/seed_audit.sql`. |
| Original seed and notebook | Preserved outside the public tree in `../backups/aviation-coursework-original/`. Dataset verified byte-for-byte unchanged. |
| Existing tests | All 54 cases retained; only module imports and relocated SQL paths adjusted. |
| Legacy scaffold artifacts | Removed from public tree: Fly/Heroku/CGI files, development Dockerfile, deployment README, stale Django/lint configuration and all 23 Zone.Identifier files. Preserved in backups. |

New files include the transactional setup CLI, separate demo SQL, packaging
configuration, Dockerfile/Compose setup, `.env.example`, ignore/editor settings,
attribution and setup/architecture documentation. Compiled Python and editable
installation metadata generated during verification were removed from the tree.

A fresh local Git repository on `main` was initialized and the public source was
staged. No old coursework history was imported, no commit was created, no remote
was configured, and nothing was published. Ignore checks verified that `.env`,
compiled files, notebooks, PDFs and Windows metadata cannot be added accidentally
through ordinary Git staging.

## Verified results

- Editable installation `pip install -e '.[test]'` succeeded in an isolated Python 3.12.3 environment.
- Focused regression selection: **11 passed**, 43 deselected.
- Complete existing regression suite: **54 passed in 2.79 seconds** against PostgreSQL 16.15.
- Compose configuration and Python/shell syntax validated.
- Clean native PostgreSQL installation applied three migrations, loaded four airports,
  two aircraft, ten seats, five flights, two sales and four tickets under all integrity rules.
- Fixed-clock initialization repeated with a different requested clock preserved the
  original `2026-10-09T10:00:00Z` schedule and row counts.
- Changed applied migration checksums and unmarked populated seed targets were
  rejected; test transactions were rolled back and existing records remained intact.
- Docker image built and Compose started PostgreSQL, initializer and two-worker Gunicorn successfully.
- Real HTTP checks passed for airports, upcoming flights, exact remaining capacity,
  repeated check-in, capacity rejection, missing ticket and invalid payload.
- Repeating Compose initialization after the HTTP purchase preserved its new sale
  and four tickets. API container UID was 10001.
- Original dataset hash matched the backup. Publication scan found no student
  numbers, university connection settings, assignment notebook/PDF or copied specification text.

## Environment limits and remaining work

The Docker daemon was accessible after authorized sandbox escalation. Buildx was
absent, so the tested image build used `DOCKER_BUILDKIT=0 docker build`; Compose
then ran the image with `--no-build`. Normal Compose/Buildx image building was not
verified here. The setup document includes both the standard command and the
verified fallback. The legacy-builder fallback is deprecated upstream.

Redis-backed shared limiting, production privileges/authentication, production
load/performance, cloud deployment, CI and a full portfolio README are not verified
or provided in this phase. Existing architectural limitations are documented in
[architecture.md](architecture.md). Exact startup, migration, seed and testing
commands are in [setup.md](setup.md).

The isolated Compose verification containers/volume and temporary native PostgreSQL
server were stopped/removed after testing. The built application image remains
available. Preserved backups and original data remain outside the public project.

This is the historical Phase 3 record. Later testing, CI and README changes are
covered by [the current verification record](verification.md).
