"""Raw response storage: data/raw/<source_id>/<YYYY-MM-DD>/ with meta.json (SPEC §4.1)."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from klimakompas.core.http import HttpClient


def save_raw(
    data_dir: Path, source_id: str, filename: str, response: httpx.Response, license_name: str
) -> Path:
    now = datetime.now(UTC)
    folder = data_dir / "raw" / source_id / now.date().isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    body = response.content
    (folder / filename).write_bytes(body)

    _record(
        folder,
        {
            "file": filename,
            "url": str(response.url),
            "fetched_at": now.isoformat(),
            "status": response.status_code,
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "sha256": hashlib.sha256(body).hexdigest(),
            "size": len(body),
            "license": license_name,
        },
    )
    return folder / filename


def _record(folder: Path, entry: dict[str, Any]) -> None:
    meta_path = folder / "meta.json"
    entries: list[dict[str, Any]] = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else []
    )
    entries.append(entry)
    meta_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _has_record(path: Path) -> bool:
    meta_path = path.parent / "meta.json"
    if not meta_path.exists():
        return False
    entries = json.loads(meta_path.read_text(encoding="utf-8"))
    return any(entry["file"] == path.name for entry in entries)


def ensure_raw(
    client: HttpClient,
    data_dir: Path,
    source_id: str,
    filename: str,
    url: str,
    license_name: str,
) -> Path:
    """Return the newest stored copy of a large file, downloading it only when needed."""
    now = datetime.now(UTC)
    stored = sorted((data_dir / "raw" / source_id).glob(f"*/{filename}"))
    if stored and _has_record(stored[-1]):
        return stored[-1]

    entry: dict[str, Any] = {"file": filename, "url": url, "fetched_at": now.isoformat()}
    head = client.request("HEAD", url)
    expected = head.headers.get("Content-Length")
    if stored and head.is_success and str(stored[-1].stat().st_size) == expected:
        # Same size as the published file, so an unrecorded copy is adopted without a new download.
        path = stored[-1]
        response = head
    else:
        folder = data_dir / "raw" / source_id / now.date().isoformat()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / filename
        response = client.download(url, path)
    entry |= {
        "status": response.status_code,
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "sha256": _sha256(path),
        "size": path.stat().st_size,
        "license": license_name,
    }
    _record(path.parent, entry)
    return path
