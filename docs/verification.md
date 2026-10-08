# Phases 4 and 5: verification and review record

## Actual results

Verified locally with Python 3.12.3 and PostgreSQL 16.15. No application business
logic, database migration, or setup-runner behavior changed in these phases.

| Check | Result |
| --- | --- |
| Existing baseline | 54 tests passed before additions. |
| Focused additions | 28 tests passed. |
| Complete suite | **82 passed, zero skipped, in 8.64 seconds**. |
| Statement coverage | **254/257 statements: 98.83%**. |
| Branch coverage | **88/92 branches: 95.65%**. |
| Combined pytest-cov result | **97.99%, displayed as 98%**. |
| Ruff | Passed. |
| Python compilation, shell syntax, dependency consistency | Passed. |
| CI workflow YAML/basic configuration | Parsed and checked locally. |
| Local CI command reproduction | Installation, migrations, deterministic fixture load, refresh and full suite passed. |
| GitHub-hosted workflow | **Not executed**; repository remains unpublished. |

The original 54 regressions are preserved. New tests target real gaps: transactional
migration rollback including metadata/DDL; checksum and unknown-history rejection;
seed rollback and populated-target rejection; repeat/concurrent initialization;
API size, method, rate-limit and sanitized-error behavior; configuration rejection;
additional direct SQL integrity paths; and stale higher-isolation snapshots.
No percentage gate or redundant count target was introduced.

Reports from this run are generated at `reports/junit.xml`, `reports/coverage.xml`,
`reports/coverage.json` and `reports/htmlcov/index.html`. They remain ignored by Git.
Reproduction commands are in [testing.md](testing.md).

## Coverage limits

Python coverage excludes PostgreSQL function bodies. Those rules are exercised
through real isolated database writes and concurrency tests, not represented as
SQL line coverage. Remaining Python gaps are the check-in guards for a ticket
being deleted or moved between reads, the factory's no-config branch, and the
CLI module entry wrapper. The factory/entry wrapper run during real container
startup, but are not recorded by the pytest process's coverage tracing. Rare
interleavings and production load are not proven exhaustive by this suite.

## Docker verification

An isolated Compose project on separate ports/volumes was built and started.
The PostgreSQL health check passed; the initializer exited successfully before
Gunicorn started. The API ran as UID 10001. README examples were checked over real
HTTP: a fresh-demo purchase returned reservation 1002 / ticket 1004, and repeated
check-in returned seat `1A` on `DEMO-A`.

Repeated bootstrap preserved that purchase and assignment. Stopping PostgreSQL
caused a sanitized HTTP 503; restarting it restored HTTP 200 through the existing
pool. A separate fresh project intentionally ran seeding before migrations:
initialization failed, and the API remained unstarted. This verifies startup
completion gating, not a continuous API Docker health check.

Buildx is absent in this workspace. The application image built with the documented
legacy-builder fallback and Compose used `--no-build`. Standard Buildx builds are
not verified here; the fallback is deprecated. The isolated verification services
and volumes were removed afterwards and the temporary native PostgreSQL server
was stopped. No user data or original academic records were deleted.

## Files changed

Created:

- `.github/workflows/ci.yml`.
- `tests/test_migrations.py`, `tests/test_api_edges.py`.
- `docs/testing.md`, `docs/demo.md`, `docs/publication.md`, this verification record.

Updated:

- `README.md`: complete portfolio overview, Mermaid architecture/schema diagrams,
  API contracts, real request/response examples, setup/testing/analytics and attribution.
- `tests/conftest.py`: reusable empty-schema fixture; existing fixture behavior retained.
- `pyproject.toml`, `tests/requirements.txt`, `requirements.lock`: constrained coverage/lint tools and configuration.
- `.gitignore`, `.dockerignore`: exclude generated reports, coverage and lint artifacts.
- `docs/setup.md`, `docs/architecture.md`, `docs/phase3.md`: environment/reference details and consistent current/historical verification links.

## Publication review

A fresh repository with no commits or remote is retained. Staged public source
was checked for excluded environment/backup/coursework/build files, student IDs,
university connection settings, personal machine paths and recognizable secret
formats. No unsuitable staged files were found. Development/CI password strings
are clearly marked synthetic placeholders; no real credentials were introduced.
Applicable BSD terms and group attribution remain intact.

Ready for a **portfolio publication review**, with local tests and Docker behavior
verified. Publication still requires the user's approval, owner/repository choice,
and the first real GitHub workflow run. There is no claimed CI success badge,
performance benchmark, production deployment or fake screenshot. Remaining design
limitations are in [architecture.md](architecture.md); suggested description/topics
and publication steps are in [publication.md](publication.md).

No commit, push, publication or Phase 6 work was performed.
