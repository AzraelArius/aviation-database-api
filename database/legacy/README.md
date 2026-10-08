# Original dataset: preserved outside the public repository

The original `populate.sql`, baseline `aviacao.sql` and notebook are retained in
`../backups/aviation-coursework-original/` relative to the repository root.
A complete pre-Phase-3 archive also exists at
`../backups/entrega-bd-02-09-before-phase3.tar.gz`. These files are local preservation
artifacts, not required for startup and not included in this repository's Git history.

Original file SHA-256 hashes:

| File | SHA-256 |
| --- | --- |
| `populate.sql` | `ddd73661366f0fda73b35d73548643a0c38a74183385ea5d21be481af0381194` |
| `aviacao.sql` | `ea6f482d55fe46693640bdc06bf4fa16e21a7b840656300e4bc8e2e881fb2d8f` |
| Original notebook | `8946e9c2027839bc37225cff4840b1539b2a8833d3bbab181c3391d2a522df15` |

PostgreSQL verified 131 oversold flight/class groups, all first class, totaling
550 excess tickets. The original seed has 14,946 first-class and 15,002 economy
tickets despite much smaller first-class capacity. The original baseline schema
did not install the notebook capacity trigger. The generator source is absent,
so its exact ticket-class selection logic cannot be confirmed.

The original seed is not silently repaired or imported by the demo initializer.
The new capacity protections must not be bypassed to import it. The original
notebook contains copied assignment requirements and student identifiers; it was
removed from the public tree, with useful SQL already rewritten in standalone
scripts and the group credited without student identifiers.

For optional reproduction, create a **separate disposable baseline database**
and use the local archived files. The baseline schema resets tables, so never
run this against a database containing wanted data:

```bash
createdb aviation_original_audit
psql -v ON_ERROR_STOP=1 -1 -d aviation_original_audit \
  -f ../backups/aviation-coursework-original/aviacao.sql \
  -f ../backups/aviation-coursework-original/populate.sql
psql -v ON_ERROR_STOP=1 -d aviation_original_audit -f database/legacy/seed_audit.sql
```

A public clone intentionally contains no coursework notebook or full original
seed. Use `database/seeds/demo.sql` through the documented seed command instead.
