"""Raw response storage: data/raw/<source_id>/<YYYY-MM-DD>/ with meta.json (SPEC §4.1)."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


def save_raw(
    data_dir: Path, source_id: str, filename: str, response: httpx.Response, license_name: str
) -> Path:
    now = datetime.now(UTC)
    folder = data_dir / "raw" / source_id / now.date().isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    body = response.content
    (folder / filename).write_bytes(body)

    meta_path = folder / "meta.json"
    entries: list[dict[str, Any]] = (
        json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else []
    )
    entries.append(
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
        }
    )
    meta_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return folder / filename
