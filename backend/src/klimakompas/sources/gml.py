"""Streaming helpers for the DGU INSPIRE GML files."""

from collections.abc import Iterator
from typing import IO, Any

import numpy as np
import shapely
from lxml import etree
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry

GML = "{http://www.opengis.net/gml/3.2}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
XLINK_TITLE = "{http://www.w3.org/1999/xlink}title"
GN_TEXT = "{http://inspire.ec.europa.eu/schemas/gn/4.0}text"
GML_ID = f"{GML}id"
BASE_LOCAL_ID = "{http://inspire.ec.europa.eu/schemas/base/3.3}localId"
EPSG_3035 = "http://www.opengis.net/def/crs/EPSG/0/3035"
SRID = 3035


def iter_elements(stream: IO[bytes], tag: str) -> Iterator[Any]:
    """Yield matching elements and free each one afterwards, so 2.6 GB files fit in memory."""
    for _, element in etree.iterparse(stream, events=("end",), tag=tag, huge_tree=True):
        yield element
        element.clear()
        parent = element.getparent()
        if parent is not None:
            while element.getprevious() is not None:
                del parent[0]


def href_id(element: Any) -> str:
    href: str = element.get(XLINK_HREF, "")
    return href.removeprefix("#")


def _check_crs(element: Any) -> None:
    name = element.get("srsName")
    if name != EPSG_3035:
        raise ValueError(f"expected EPSG:3035 geometry, found {name}")


def _coordinates(text: str) -> Any:
    """GML gives EPSG:3035 as northing, easting; we store x (easting), y (northing)."""
    values = np.array(text.split(), dtype=float).reshape(-1, 2)
    coordinates = values[:, ::-1]
    # Everywhere in Croatia easting exceeds northing, so this catches a swapped axis order.
    if not (coordinates[:, 0] > coordinates[:, 1]).all():
        raise ValueError("unexpected axis order in EPSG:3035 coordinates")
    return coordinates


def _polygon(element: Any) -> Polygon:
    exterior = element.find(f"{GML}exterior/{GML}LinearRing/{GML}posList")
    interiors = element.findall(f"{GML}interior/{GML}LinearRing/{GML}posList")
    return Polygon(_coordinates(exterior.text), [_coordinates(item.text) for item in interiors])


def parse_multisurface(element: Any) -> MultiPolygon:
    """Parse gml:MultiSurface and repair invalid rings, keeping only polygonal parts."""
    _check_crs(element)
    polygons = [_polygon(item) for item in element.iter(f"{GML}Polygon")]
    return polygonal(shapely.make_valid(MultiPolygon(polygons)))


def polygonal(geometry: BaseGeometry) -> MultiPolygon:
    parts = shapely.get_parts(geometry)
    polygons: list[Polygon] = []
    for part in parts:
        if isinstance(part, Polygon):
            polygons.append(part)
        elif isinstance(part, MultiPolygon) or part.geom_type == "GeometryCollection":
            polygons.extend(polygonal(part).geoms)
    return MultiPolygon(polygons)


def parse_point(element: Any) -> Point:
    _check_crs(element)
    return Point(_coordinates(element.find(f"{GML}pos").text)[0])


def to_ewkb(geometry: BaseGeometry) -> str:
    """Hex EWKB, which PostGIS reads directly from COPY."""
    return str(shapely.to_wkb(shapely.set_srid(geometry, SRID), hex=True, include_srid=True))
