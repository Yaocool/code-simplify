# Changelog

All notable changes to this project will be documented here.

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
