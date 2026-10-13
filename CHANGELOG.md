# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Changed

- Require Python 3.12+ and align Ruff/Pyright with the minimum supported version.
- Upgrade runtime dependencies to aiohttp 3.14.5, Pydantic 2.14.1 and SQLAlchemy
  2.1.4; align requirements.txt and package metadata.
- Update optional drivers to PyMySQL 1.2.3 and psycopg[binary] 3.3.6, and developer
  tools to pytest 9.1.1, Ruff 0.17.0, Pyright 1.1.414, setuptools 84.0.0, build
  1.6.1 and wheel 0.48.0. Declare the setuptools build backend for isolated builds.

### Fix

- Apply explicit falsy/NULL filters, filter before pagination, count matching rows
  and use mapped ascending/descending ordering with validated page arguments.
- Make soft-delete visibility consistent across get/list/paging/total. Queries now
  exclude deleted rows by default; `range_all=True` includes all rows.
- Close internally owned sessions on every path without closing or reusing caller
  sessions. Require an explicit session for `auto_commit=False` and add a transaction
  context for atomic groups of operations.
- Validate ORM output before managed commits, support missing records and avoid
  overwriting unset fields during partial updates. Accept any one primary key source
  for updates and reject conflicting IDs.
- Respect autoincrement/model/server key defaults and populate bulk-insert results.
- Construct connection URLs safely, support SQLite and compatible custom pools,
  bind raw SQL parameters and buffer owned row results before connection release.
- Declare Python/Pydantic/SQLAlchemy compatibility and optional database drivers.
- Fix implicit optional annotations, ORM base typing, imports and exception
  logging diagnostics; keep lint/type checks compatible with Python 3.12.

### Test

- Add SQLite regression tests for CRUD, transaction ownership, cleanup and error
  paths; make the CRUD example runnable without external database credentials.
- Add loopback HTTP/SSE regression checks for JSON/binary responses, sync/async
  callbacks, the completion sentinel and custom errors on the upgraded aiohttp.


## [v1.2.2] - 2024-08-29

### Performance

- Use `scoped_session` to manage session.

### Refactor

- Rename `Base` to `RDBBase` in `rdb` module.

### Test

- Update `crud` test case.


## [v1.2.1] - 2024-07-06

### Fix

- Make `log`, `http_utils` and `models` modules visible.

### Test

- Add logger test case.

### Docs

- Update `CHANGELOG.md`.
- Add `Contributors Wall` to `README.md`.


## [v1.2.0] - 2024-07-05

### Style

- Restructuring of the project.

## [v1.1.0] - 2024-06-20

### Feature

- CRUD common apis based on `SQLAlchemy`, including `GET`, `LIST`, `CREATE`, `BULK SAVE`, `UPDATE`, `TOTAL`, `GET PAGING`, `DELETE`, `PHYSICAL DELETE`, `EXECUTE SQL`

## [v1.0.0] - 2024-06-19

### Feature

- Log template based on `logging in std`.
- Http utils based on `aiohttp`, including `SSE HANDLER`, `HEAD`, `GET`, `POST`, `OPTIONS`, `PUT`, `PATCH`, `DELETE`.
