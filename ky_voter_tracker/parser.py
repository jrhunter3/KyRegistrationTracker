import re
from typing import Optional

import xlrd

HEADER_MAP = {
    "precinct count": "precinct_count",
    "dem": "democratic",
    "rep": "republican",
    "other": "other",
    "ind": "independent",
    "libert": "libertarian",
    "green": "green",
    "const": "constitution",
    "reform": "reform",
    "soc wk": "socialist_workers",
    "ky prty": "kentucky_party",
    "male": "male",
    "female": "female",
    "registered": "total",
}

PARTY_COLS = [
    "democratic", "republican", "other", "independent", "libertarian",
    "green", "constitution", "reform", "socialist_workers", "kentucky_party",
]

COUNTY_PATTERN = re.compile(r"^(\d{3})\s+(.+)$")


def _normalise_header(raw: str) -> Optional[str]:
    cleaned = raw.strip().lower()
    return HEADER_MAP.get(cleaned)


def _parse_cell(value) -> int:
    if value == "" or value is None:
        return 0
    return int(value)


def _build_row_dict(
    row: list,
    col_map: dict[int, str],
    month: str,
    source_file: str,
) -> dict:
    d: dict = {"month": month, "source_file": source_file}
    for idx, key in col_map.items():
        d[key] = _parse_cell(row[idx])
    for col in PARTY_COLS:
        d.setdefault(col, 0)
    d.setdefault("male", 0)
    d.setdefault("female", 0)
    return d


def parse_xls(
    filepath: str,
    month: str,
) -> tuple[Optional[dict], list[dict]]:
    wb = xlrd.open_workbook(filepath)
    sheet = wb.sheet_by_index(0)

    header_row = None
    for r in range(min(5, sheet.nrows)):
        raw = str(sheet.cell_value(r, 0)).strip()
        if raw.lower() == "county":
            header_row = r
            break

    if header_row is None:
        raise ValueError(f"Could not find header row in {filepath}")

    raw_headers = [str(sheet.cell_value(header_row, c)) for c in range(sheet.ncols)]
    col_map: dict[int, str] = {}
    for c, raw in enumerate(raw_headers):
        key = _normalise_header(raw)
        if key:
            col_map[c] = key

    county_rows: list[dict] = []
    statewide: Optional[dict] = None

    for r in range(header_row + 1, sheet.nrows):
        raw_county = str(sheet.cell_value(r, 0)).strip()

        if not raw_county:
            continue

        if raw_county.lower() == "statewide totals":
            row_data = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
            statewide = _build_row_dict(row_data, col_map, month, filepath)
            continue

        m = COUNTY_PATTERN.match(raw_county)
        if not m:
            continue

        row_data = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
        row_dict = _build_row_dict(row_data, col_map, month, filepath)
        row_dict["county_code"] = m.group(1)
        row_dict["county_name"] = m.group(2).strip()
        county_rows.append(row_dict)

    return statewide, county_rows
