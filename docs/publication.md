# GitHub presentation and publication review

## Suggested description

Flask and PostgreSQL aviation API with atomic ticket purchases, concurrency-safe check-in, SQL analytics and integration tests.

## Suggested topics

`python`, `flask`, `postgresql`, `psycopg`, `sql`, `rest-api`, `docker-compose`,
`pytest`, `github-actions`, `transactions`, `database-design`, `backend`.

The README's technology badges describe the stack. Its CI badge says configured;
it does not imply a successful hosted run. After the repository owner/path is
chosen and the first actual workflow completes, replace it with a real workflow
badge URL such as:

```text
https://github.com/YOUR_OWNER/aviation-database-api/actions/workflows/ci.yml/badge.svg
```

## Before publication

- Review `git diff --cached` and `git status --short`; commit only the intended public tree after approval.
- Keep `.env`, real credentials, coverage/build artifacts and local backups excluded.
- Keep the preserved notebook and original dataset outside this repository; do not add coursework archives or student identifiers.
- Confirm contributor attribution and retained BSD notices are intact.
- Choose the GitHub owner/repository path and enable Actions; verify an actual hosted CI run before claiming CI passes.
- Treat localhost development credentials and database privileges as a demo setup, not production hardening.

The repository currently has no commits and no configured remote; there is no old
coursework Git history to publish accidentally. Existing staged files and new
working-tree changes are reviewable locally. Nothing is committed, pushed or
published by these phases. The current readiness assessment and verification
limits are in [verification.md](verification.md).
