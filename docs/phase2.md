# Phase 2 verification record

Phase 2 corrected exact-capacity and class-only purchases, added strict payload
validation and JSON errors, made check-in idempotent, and introduced PostgreSQL
locking and integrity triggers. All original routes and HTTP methods were retained.
Purchase success uses HTTP 201 and reservation/ticket IDs. Prices use configurable
fixed Decimal fares rather than random values. NIF checks validate nine ASCII digits.

The original dataset audit confirmed 131 oversold first-class groups / 550 excess
tickets and 27,207 historical tickets without seats. Installing constraints against
that dataset was tested to fail atomically without changing records.

Verified on Python 3.12.3 / PostgreSQL 16.15: 54 regressions passed. Coverage includes
exact capacity, one-class purchases, independent competing application pools,
direct competing SQL under READ COMMITTED/REPEATABLE READ/SERIALIZABLE, observed
PostgreSQL lock waits, duplicate seat assignment, rollback, invalid payloads,
missing resources, check-in concurrency, and materialized-view analytics.

The pre-Phase-2 archive is retained outside this repository at
`../backups/entrega-bd-02-09-before-phase2.tar.gz` (SHA-256
`cd460ea604b04733ad7d03830323642fbb7efc4a3940e6c4296d2c8eae79f388`).
The complete Phase 2 file layout/report is also preserved in the pre-Phase-3 backup.

Phase 3 relocated source, SQL and deployment files while preserving these
protections. Current executable commands are in [setup.md](setup.md).
