import os
import time
from typing import Optional

import requests

RAW_DIR = "data/raw"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

RETRIES = 3
BACKOFF = [1, 2, 4]


def _download_file(
    url: str,
    dest_path: str,
    session: Optional[requests.Session] = None,
) -> int:
    http = session or requests
    last_exc = None

    for attempt in range(RETRIES):
        try:
            resp = http.get(url, headers=HEADERS, timeout=120)
            resp.raise_for_status()
            content = resp.content
            with open(dest_path, "wb") as f:
                f.write(content)
            return len(content)
        except requests.RequestException as e:
            last_exc = e
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF[attempt])

    raise last_exc  # type: ignore[misc]


def download_files(
    conn,
    links: list[dict],
    raw_dir: str = RAW_DIR,
) -> set[str]:
    os.makedirs(raw_dir, exist_ok=True)
    downloaded: set[str] = set()

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        for link in links:
            if _is_downloaded(conn, link["url"]):
                continue

            dest_path = os.path.join(raw_dir, link["filename"])

            try:
                file_size = _download_file(link["url"], dest_path, session)
            except requests.RequestException:
                _mark_downloaded(conn, link["url"], link["filename"], status="failed")
                continue

            _mark_downloaded(conn, link["url"], link["filename"], file_size=file_size)
            downloaded.add(dest_path)
    finally:
        session.close()

    return downloaded


def _is_downloaded(conn, url: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM downloads_log WHERE url = ?",
        (url,),
    ).fetchone()
    return row is not None


def _mark_downloaded(conn, url: str, filename: str, file_size: int = 0, status: str = "downloaded") -> None:
    conn.execute(
        """INSERT OR REPLACE INTO downloads_log
           (url, filename, downloaded_at, file_size, status)
           VALUES (?, ?, datetime('now'), ?, ?)""",
        (url, filename, file_size, status),
    )
    conn.commit()
