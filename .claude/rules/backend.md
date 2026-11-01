---
paths: ["backend/**"]
---

# Backend conventions (SPEC §22)

- Python 3.12 and `uv`; `ruff` for lint and format (line length 100); `mypy` strict.
- Type hints everywhere; Pydantic models for all I/O; no `print`, use structlog.
- Pure functions in `pipeline/`; I/O stays at the edges (connectors, API).
- DDL only through Alembic.
- Constants and thresholds only from `config/*.yaml`, loaded through `core/config.py`.
- `datetime` always timezone-aware, in UTC.
- Every GeoDataFrame has an explicit CRS; every load asserts the CRS.
- All network traffic goes through `core/http.py`.
- Every new source gets a `sources.yaml` entry, a fixture and a parser test.
- Codes (JLS, settlements, stations) are strings.
- Never load large rasters whole.
