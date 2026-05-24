import re
from typing import Optional

import pdfplumber
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


def _parse_pdf_header(words: list[dict], header_y: float) -> dict[float, str]:
    header_entries = []
    for w in words:
        if w["top"] >= header_y - 2 and w["top"] <= header_y + 15:
            header_entries.append(w)

    header_entries.sort(key=lambda x: (x["x0"], x["top"]))

    merged = []
    for w in header_entries:
        if merged and w["x0"] - merged[-1]["x1"] < 3:
            merged[-1]["text"] += " " + w["text"]
            merged[-1]["x1"] = max(merged[-1]["x1"], w["x1"])
        else:
            merged.append({"text": w["text"], "x0": w["x0"], "x1": w["x1"]})

    col_map: dict[float, str] = {}
    for entry in merged:
        key = entry["text"].strip().lower()
        canonical = HEADER_MAP.get(key)
        if canonical:
            x_center = (entry["x0"] + entry["x1"]) / 2
            col_map[x_center] = canonical

    return col_map


def _parse_pdf_row_dict(
    values: list[int],
    col_centers: list[float],
    col_map: dict[float, str],
    month: str,
    source_file: str,
) -> dict:
    d: dict = {"month": month, "source_file": source_file}
    for idx, val in enumerate(values):
        if idx < len(col_centers):
            key = col_map.get(col_centers[idx])
            if key:
                d[key] = val
    for col in PARTY_COLS:
        d.setdefault(col, 0)
    d.setdefault("male", 0)
    d.setdefault("female", 0)
    return d


def parse_county_pdf(
    filepath: str,
    month: str,
) -> tuple[Optional[dict], list[dict]]:
    statewide = None
    counties = []

    with pdfplumber.open(filepath) as pdf:
        col_map: Optional[dict[float, str]] = None
        col_centers: Optional[list[float]] = None
        header_y = None

        for page in pdf.pages:
            words = page.extract_words(x_tolerance=3, y_tolerance=3)

            if header_y is None:
                for w in words:
                    if w["text"] == "County":
                        header_y = w["top"]
                        break

            if col_map is None and header_y is not None:
                col_map = _parse_pdf_header(words, header_y)
                col_centers = sorted(col_map.keys())

            rows: dict[float, list[dict]] = {}
            for w in words:
                if header_y is not None and w["top"] <= header_y + 12:
                    continue
                y_key = round(w["top"], 0)
                rows.setdefault(y_key, []).append(w)

            for y_key in sorted(rows.keys()):
                row_words = sorted(rows[y_key], key=lambda x: x["x0"])
                texts = [w["text"] for w in row_words]
                if not texts:
                    continue

                combined = " ".join(texts)
                if combined.strip().lower().startswith("statewide totals"):
                    raw_values = texts[2:] if len(texts) > 2 else []
                    values = _to_ints(raw_values)
                    if col_centers is not None and col_map is not None:
                        statewide = _parse_pdf_row_dict(
                            values, col_centers, col_map, month, filepath,
                        )
                    continue

                if not texts[0].isdigit() or len(texts[0]) != 3:
                    continue
                if int(texts[0]) < 1 or int(texts[0]) > 120:
                    continue

                county_code = texts[0]
                county_name = texts[1]
                raw_values = texts[2:]
                values = _to_ints(raw_values)
                if col_centers is not None and col_map is not None:
                    row_dict = _parse_pdf_row_dict(
                        values, col_centers, col_map, month, filepath,
                    )
                    row_dict["county_code"] = county_code
                    row_dict["county_name"] = county_name
                    counties.append(row_dict)

    return statewide, counties


def _to_ints(raw: list[str]) -> list[int]:
    result = []
    for v in raw:
        try:
            result.append(int(v))
        except ValueError:
            result.append(0)
    return result
