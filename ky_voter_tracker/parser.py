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


PRECINCT_CSLDSC_RE = re.compile(r"^\d+-\d+-\d+-\d*$")
PRECINCT_CODE_RE = re.compile(r"^[A-Z]\d{3}$")

PRECINCT_DATA_KEYS = [
    "democratic", "republican", "other", "independent",
    "libertarian", "green", "constitution", "reform",
    "socialist_workers",
]

PRECINCT_DATA_KEYS_EXTRA = [
    "kentucky_party",
]

PDF_DATA_KEYS_13 = [
    "precinct_count", "democratic", "republican", "other",
    "independent", "libertarian", "green", "constitution",
    "reform", "socialist_workers",
    "male", "female", "total",
]

PDF_DATA_KEYS_14 = [
    "precinct_count", "democratic", "republican", "other",
    "independent", "libertarian", "green", "constitution",
    "reform", "socialist_workers", "kentucky_party",
    "male", "female", "total",
]


def _build_pdf_row(
    values: list[int],
    county_code: Optional[str],
    county_name: Optional[str],
    month: str,
    source_file: str,
) -> dict:
    if len(values) == 13:
        keys = PDF_DATA_KEYS_13
    else:
        keys = PDF_DATA_KEYS_14

    d: dict = {"month": month, "source_file": source_file}
    for idx, key in enumerate(keys):
        if idx < len(values):
            d[key] = values[idx]
    if county_code is not None:
        d["county_code"] = county_code
    if county_name is not None:
        d["county_name"] = county_name
    for col in PARTY_COLS:
        d.setdefault(col, 0)
    d.setdefault("male", 0)
    d.setdefault("female", 0)
    return d


def _to_ints(raw: list[str]) -> list[int]:
    result = []
    for v in raw:
        try:
            result.append(int(v))
        except ValueError:
            result.append(0)
    return result


def parse_county_pdf(
    filepath: str,
    month: str,
) -> tuple[Optional[dict], list[dict]]:
    statewide = None
    counties = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1)
            for line in text.split("\n"):
                stripped = line.strip()
                if not stripped:
                    continue

                if stripped.lower().startswith("statewide totals"):
                    parts = stripped.split()
                    if len(parts) >= 15:
                        vals = _to_ints(parts[2:])
                        statewide = _build_pdf_row(
                            vals, None, None, month, filepath,
                        )
                    continue

                parts = stripped.split()
                if len(parts) < 15 or len(parts) > 16:
                    continue
                if not parts[0].isdigit() or len(parts[0]) != 3:
                    continue
                if int(parts[0]) < 1 or int(parts[0]) > 120:
                    continue

                vals = _to_ints(parts[2:])
                row_dict = _build_pdf_row(
                    vals, parts[0], parts[1], month, filepath,
                )
                counties.append(row_dict)

    return statewide, counties


def parse_precinct_pdf(
    filepath: str,
    month: str,
) -> list[dict]:
    rows: list[dict] = []
    county_code = None
    county_name = None

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1)
            lines = text.split("\n")
            i = 0
            while i < len(lines):
                stripped = lines[i].strip()
                i += 1
                if not stripped:
                    continue

                parts = stripped.split()

                # County header line: "001 ADAIR"
                if len(parts) == 2 and parts[0].isdigit() and len(parts[0]) == 3:
                    code = int(parts[0])
                    if 1 <= code <= 120:
                        county_code = parts[0]
                        county_name = parts[1]
                        continue

                # Skip: page headers, column headers, subtotals
                first = parts[0]
                if first == "Precinct" or first == "Voter" or first.startswith(("April", "June", "6/", "7/", "8/", "9/", "10/", "11/", "12/")):
                    continue
                if len(first) == 1 and first.isalpha() and len(parts) > 1 and parts[1] == "Totals":
                    continue
                if first == "Totals":
                    continue

                # Check for precinct row: starts with letter+3digits
                if not PRECINCT_CODE_RE.match(first):
                    continue
                if county_code is None:
                    continue

                # Find C-S-LD-SC token
                csldsc_idx = None
                for j, p in enumerate(parts):
                    if PRECINCT_CSLDSC_RE.match(p):
                        csldsc_idx = j
                        break

                if csldsc_idx is None or csldsc_idx < 1:
                    continue

                precinct_code = parts[0]
                precinct_name = " ".join(parts[1:csldsc_idx])
                csldsc = parts[csldsc_idx]

                # Handle C-S-LD-SC with trailing hyphen (digit on next line)
                if csldsc.endswith("-") and i < len(lines):
                    next_line = lines[i].strip()
                    if next_line.isdigit():
                        csldsc += next_line
                        i += 1

                raw_values = parts[csldsc_idx + 1:]

                if len(raw_values) < 11:
                    continue

                vals = _to_ints(raw_values)

                d: dict = {
                    "month": month,
                    "county_code": county_code,
                    "county_name": county_name,
                    "precinct": f"{precinct_code} {precinct_name}",
                    "c_s_ld_sc": csldsc,
                    "source_file": filepath,
                }

                for idx, key in enumerate(PRECINCT_DATA_KEYS):
                    if idx < len(vals):
                        d[key] = vals[idx]

                offset = len(PRECINCT_DATA_KEYS)
                if len(vals) >= offset + 3:
                    d["male"] = vals[offset]
                    d["female"] = vals[offset + 1]
                    d["total"] = vals[offset + 2]
                    if len(vals) >= offset + 4:
                        d["kentucky_party"] = vals[offset]
                        d["male"] = vals[offset + 1]
                        d["female"] = vals[offset + 2]
                        d["total"] = vals[offset + 3]

                for col in PARTY_COLS:
                    d.setdefault(col, 0)
                d.setdefault("male", 0)
                d.setdefault("female", 0)

                rows.append(d)

    return rows
