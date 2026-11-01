"""Refresh the materialized views that Martin serves as vector tiles."""

from sqlalchemy import Connection, text

VIEWS = (
    "tiles.jls",
    "tiles.grid_pop",
    "tiles.grid_risk",
    "tiles.jls_risk",
    "tiles.zupanije",
    "tiles.naselja",
    "tiles.nature",
)


def refresh_tiles(conn: Connection) -> None:
    for view in VIEWS:
        conn.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
