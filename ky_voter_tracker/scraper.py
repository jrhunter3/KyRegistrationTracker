import re
from typing import Optional
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

URL = "https://elect.ky.gov/Resources/Pages/Registration-Statistics.aspx"
BASE = "https://elect.ky.gov"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

PREFIX_ORDER = [
    ("voterstatscounty", "county"),
    ("voterstatsprecinct", "precinct"),
    ("voterstatsdistrict", "district"),
    ("voterstats-", "overall"),
]


def _categorize(filename: str) -> Optional[str]:
    name_lower = filename.lower()
    for prefix, category in PREFIX_ORDER:
        if name_lower.startswith(prefix):
            return category
    return None


def _parse_month(date_part: str) -> Optional[str]:
    cleaned = date_part.strip().lstrip("- ")
    m = re.match(r"([A-Za-z]+)\s+(?:\w+\s+)?(\d{4})$", cleaned)
    if not m:
        return None
    month_name = m.group(1).lower()
    year = m.group(2)
    month_num = MONTH_MAP.get(month_name)
    if month_num is None:
        return None
    return f"{year}-{month_num:02d}"


def _parse_date_from_filename(filename: str) -> Optional[str]:
    name = filename.rsplit(".", 1)[0]

    ts_match = re.search(r"(\d{8})-(\d{6})$", name)
    if ts_match:
        ymd = ts_match.group(1)
        return f"{ymd[:4]}-{ymd[4:6]}"

    ts_short = re.search(r"(\d{8})$", name)
    if ts_short:
        ymd = ts_short.group(1)
        return f"{ymd[:4]}-{ymd[4:6]}"

    for prefix, _ in PREFIX_ORDER:
        if name.lower().startswith(prefix):
            date_part = name[len(prefix):].lstrip("- ")
            return _parse_month(date_part)

    if name.lower().startswith("voterstats-"):
        date_part = name[len("voterstats-"):].lstrip("- ")
        return _parse_month(date_part)

    return None


def get_download_links() -> list[dict]:
    resp = requests.get(URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "lxml")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "/Resources/Documents/voterstats" not in href:
            continue

        raw_filename = href.rsplit("/", 1)[-1]
        filename = unquote(raw_filename)
        category = _categorize(filename)
        if category is None:
            continue

        full_url = href if href.startswith("http") else BASE + href

        month = _parse_date_from_filename(filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        links.append({
            "url": full_url,
            "filename": filename,
            "category": category,
            "month": month,
            "file_type": ext,
        })

    links.sort(key=lambda x: (x["month"] or "0000-00", x["category"], x["filename"]))
    return links
