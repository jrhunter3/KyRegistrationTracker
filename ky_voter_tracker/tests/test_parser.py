from unittest.mock import MagicMock, patch

from ky_voter_tracker.parser import (
    _normalise_header,
    _parse_cell,
    _to_ints,
    _build_pdf_row,
    parse_xls,
    parse_county_pdf,
    parse_precinct_pdf,
    parse_district_pdf,
)


class TestNormaliseHeader:
    def test_known_headers(self):
        assert _normalise_header("Dem") == "democratic"
        assert _normalise_header("dem") == "democratic"
        assert _normalise_header("Rep") == "republican"
        assert _normalise_header("Ind") == "independent"
        assert _normalise_header("Libert") == "libertarian"
        assert _normalise_header("Soc Wk") == "socialist_workers"
        assert _normalise_header("Registered") == "total"
        assert _normalise_header("Precinct count") == "precinct_count"

    def test_unknown_header(self):
        assert _normalise_header("Something Else") is None
        assert _normalise_header("") is None


class TestParseCell:
    def test_float(self):
        assert _parse_cell(123.0) == 123

    def test_int(self):
        assert _parse_cell(456) == 456

    def test_string_digit(self):
        assert _parse_cell("789") == 789

    def test_empty(self):
        assert _parse_cell("") == 0
        assert _parse_cell(None) == 0


class MockSheet:
    def __init__(self, rows: list[list]):
        self._rows = rows

    @property
    def nrows(self):
        return len(self._rows)

    @property
    def ncols(self):
        return max(len(r) for r in self._rows) if self._rows else 0

    def cell_value(self, r: int, c: int):
        return self._rows[r][c] if c < len(self._rows[r]) else ""


SAMPLE_DATA = [
    ["County", "Precinct count", "Dem", "Rep", "Other", "Ind", "Libert", "Green", "Const", "Reform", "Soc Wk", "Male", "Female", "Registered"],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["001  ADAIR", 16.0, 3740.0, 8978.0, 435.0, 322.0, 20.0, 3.0, 1.0, 0.0, 0.0, 6483.0, 7016.0, 13499.0],
    ["002  ALLEN", 13.0, 4770.0, 8779.0, 759.0, 252.0, 26.0, 8.0, 2.0, 0.0, 1.0, 6949.0, 7648.0, 14597.0],
    ["", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["Statewide totals", "", 1681381.0, 1359775.0, 133729.0, 117628.0, 6507.0, 1334.0, 397.0, 104.0, 62.0, 1635133.0, 1685937.0, 3321070.0],
]


def _make_mock_book(sheet_data=None):
    sheet = MockSheet(sheet_data or SAMPLE_DATA)
    wb = MagicMock()
    wb.sheet_by_index.return_value = sheet
    return wb


class TestParseXls:
    def test_parses_county_rows(self):
        wb = _make_mock_book()
        with patch("ky_voter_tracker.parser.xlrd.open_workbook", return_value=wb):
            statewide, counties = parse_xls("/fake/path.xls", "2017-06")

        assert len(counties) == 2
        assert counties[0]["county_code"] == "001"
        assert counties[0]["county_name"] == "ADAIR"
        assert counties[0]["democratic"] == 3740
        assert counties[0]["total"] == 13499

    def test_parses_statewide(self):
        wb = _make_mock_book()
        with patch("ky_voter_tracker.parser.xlrd.open_workbook", return_value=wb):
            statewide, counties = parse_xls("/fake/path.xls", "2017-06")

        assert statewide is not None
        assert statewide["total"] == 3321070
        assert statewide["democratic"] == 1681381
        assert statewide["republican"] == 1359775

    def test_month_and_file_passthrough(self):
        wb = _make_mock_book()
        with patch("ky_voter_tracker.parser.xlrd.open_workbook", return_value=wb):
            statewide, counties = parse_xls("/fake/path.xls", "2017-06")

        for c in counties:
            assert c["month"] == "2017-06"
            assert c["source_file"] == "/fake/path.xls"
        assert statewide["month"] == "2017-06"
        assert statewide["source_file"] == "/fake/path.xls"

    def test_handles_extra_column(self):
        extra_data = [
            ["County", "Precinct count", "Dem", "Rep", "Other", "Ind", "Libert", "Green", "Const", "Reform", "Soc Wk", "KY Prty", "Male", "Female", "Registered"],
            ["001  ADAIR", 16.0, 3740.0, 8978.0, 435.0, 322.0, 20.0, 3.0, 1.0, 0.0, 0.0, 0.0, 6483.0, 7016.0, 13499.0],
            ["Statewide totals", "", 100.0, 200.0, 10.0, 5.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 300.0, 400.0, 700.0],
        ]
        wb = _make_mock_book(extra_data)
        with patch("ky_voter_tracker.parser.xlrd.open_workbook", return_value=wb):
            statewide, counties = parse_xls("/fake/path.xls", "2024-01")

        assert len(counties) == 1
        assert "kentucky_party" in counties[0]
        assert "kentucky_party" in statewide

    def test_raises_on_missing_header(self):
        bad_data = [["Not", "A", "Header"], ["001  ADAIR", 16.0, 10.0]]
        wb = _make_mock_book(bad_data)
        with patch("ky_voter_tracker.parser.xlrd.open_workbook", return_value=wb):
            try:
                parse_xls("/fake/path.xls", "2024-01")
                assert False, "Expected ValueError"
            except ValueError as e:
                assert "header" in str(e).lower()


class MockPage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self, x_tolerance=1):
        return self._text


class MockPdf:
    def __init__(self, pages: list[MockPage]):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


COUNTY_PDF_TEXT = """6/1/2017 Commonwealth of Kentucky - State Board of Elections Page 1 of 2
Voter Registration Statistics Report
County Precinct Dem Rep Other Ind Libert Green Const Reform Soc Wk Male Female Registered
001 ADAIR 16 3740 8978 435 322 20 3 1 0 0 6483 7016 13499
002 ALLEN 13 4770 8779 759 252 26 8 2 0 1 6949 7648 14597
Statewide totals 29 8510 17757 1194 574 46 11 3 0 1 13432 14664 28096"""


class TestToInts:
    def test_all_digits(self):
        assert _to_ints(["123", "456", "789"]) == [123, 456, 789]

    def test_mixed(self):
        assert _to_ints(["123", "abc", "456"]) == [123, 0, 456]

    def test_empty_string(self):
        assert _to_ints(["", "123"]) == [0, 123]

    def test_empty_list(self):
        assert _to_ints([]) == []


class TestBuildPdfRow:
    def test_13_values(self):
        vals = [2, 100, 200, 30, 20, 10, 5, 3, 1, 0, 250, 300, 550]
        d = _build_pdf_row(vals, "001", "ADAIR", "2017-06", "test.pdf")
        assert d["precinct_count"] == 2
        assert d["democratic"] == 100
        assert d["republican"] == 200
        assert d["male"] == 250
        assert d["female"] == 300
        assert d["total"] == 550
        assert d["kentucky_party"] == 0

    def test_14_values(self):
        vals = [2, 100, 200, 30, 20, 10, 5, 3, 1, 0, 15, 250, 300, 550]
        d = _build_pdf_row(vals, "001", "ADAIR", "2017-06", "test.pdf")
        assert d["kentucky_party"] == 15
        assert d["male"] == 250
        assert d["female"] == 300
        assert d["total"] == 550

    def test_defaults_missing_party(self):
        vals = [2, 100, 200, 30, 20, 10, 5, 3, 1, 0, 250, 300, 550]
        d = _build_pdf_row(vals, "001", "ADAIR", "2017-06", "test.pdf")
        for col in ["democratic", "republican", "independent"]:
            assert col in d
        assert d["kentucky_party"] == 0

    def test_no_county_info(self):
        vals = [6, 1000, 2000, 300, 200, 100, 50, 30, 10, 0, 2000, 3000, 5000]
        d = _build_pdf_row(vals, None, None, "2017-06", "test.pdf")
        assert "county_code" not in d
        assert "county_name" not in d
        assert d["month"] == "2017-06"


class TestParseCountyPdf:
    def test_parses_counties(self):
        pages = [MockPage(COUNTY_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            statewide, counties = parse_county_pdf("/fake/county.pdf", "2017-06")

        assert len(counties) == 2
        assert counties[0]["county_code"] == "001"
        assert counties[0]["county_name"] == "ADAIR"
        assert counties[0]["precinct_count"] == 16
        assert counties[0]["democratic"] == 3740
        assert counties[0]["total"] == 13499
        assert counties[1]["county_code"] == "002"
        assert counties[1]["county_name"] == "ALLEN"

    def test_parses_statewide(self):
        pages = [MockPage(COUNTY_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            statewide, counties = parse_county_pdf("/fake/county.pdf", "2017-06")

        assert statewide is not None
        assert statewide["precinct_count"] == 29
        assert statewide["total"] == 28096
        assert statewide["democratic"] == 8510
        assert statewide["republican"] == 17757

    def test_month_and_file_passthrough(self):
        pages = [MockPage(COUNTY_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            statewide, counties = parse_county_pdf("/fake/county.pdf", "2017-06")

        assert counties[0]["month"] == "2017-06"
        assert counties[0]["source_file"] == "/fake/county.pdf"
        assert statewide["month"] == "2017-06"

    def test_skips_non_county_lines(self):
        text = """County Header
Column Header
Statewide totals 99 100 200 30 20 10 5 3 1 0 200 300 500
Something else"""
        pages = [MockPage(text)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            statewide, counties = parse_county_pdf("/fake/county.pdf", "2017-06")

        assert len(counties) == 0
        assert statewide is not None


PRECINCT_PDF_TEXT = """Precinct Voter Registration Statistics
County Dem Rep Other Ind Libert Green Const Reform Soc Wk Male Female Registered
001 ADAIR
A001 PRECINCT1 201-2-012-3 100 200 30 20 10 5 3 1 0 200 300 500
A002 PRECINCT2 202-3-015- 100 200 30 20 10 5 3 1 0 200 300 500
3
A003 PRECINCT3 203-4-018-4 100 200 30 20 10 5 3 1 0 15 200 300 500
Totals"""


class TestParsePrecinctPdf:
    def test_parses_precincts(self):
        pages = [MockPage(PRECINCT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_precinct_pdf("/fake/precinct.pdf", "2024-01")

        assert len(rows) == 3
        assert rows[0]["county_code"] == "001"
        assert rows[0]["county_name"] == "ADAIR"
        assert rows[0]["precinct"] == "A001 PRECINCT1"
        assert rows[0]["c_s_ld_sc"] == "201-2-012-3"
        assert rows[0]["democratic"] == 100
        assert rows[0]["total"] == 500

    def test_handles_span_line_csldsc(self):
        pages = [MockPage(PRECINCT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_precinct_pdf("/fake/precinct.pdf", "2024-01")

        # Second precinct has C-S-LD-SC split across lines: "202-3-015-" + "3"
        assert rows[1]["c_s_ld_sc"] == "202-3-015-3"

    def test_handles_14_columns(self):
        pages = [MockPage(PRECINCT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_precinct_pdf("/fake/precinct.pdf", "2024-01")

        # Third precinct has 14 values (includes kentucky_party)
        assert rows[2]["kentucky_party"] == 15

    def test_defaults_missing_columns(self):
        pages = [MockPage(PRECINCT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_precinct_pdf("/fake/precinct.pdf", "2024-01")

        assert "kentucky_party" in rows[0]
        assert rows[0]["male"] == 200
        assert rows[0]["female"] == 300

    def test_month_and_file_passthrough(self):
        pages = [MockPage(PRECINCT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_precinct_pdf("/fake/precinct.pdf", "2024-01")

        assert rows[0]["month"] == "2024-01"
        assert rows[0]["source_file"] == "/fake/precinct.pdf"


DISTRICT_PDF_TEXT = """4/1/2024 Commonwealth of Kentucky - Page 1 of 6
Voter Registration Statistics Report
Congressional Districts
District Dem Rep Other Ind Libert Green Const Reform Soc Wk Male Female Registered
1 Congressional District 1000 2000 300 200 100 50 30 10 0 2000 3000 5000
2 Congressional District 2000 3000 400 300 200 100 50 20 10 3000 4000 7000
Statewide totals 3000 5000 700 500 300 150 80 30 10 5000 7000 12000
House Districts
District Dem Rep Other Ind Libert Green Const Reform Soc Wk Male Female Registered
001 House District 100 200 30 20 10 5 3 1 0 200 300 500
035 House District 200 300 40 30 20 10 5 2 1 300 400 700
35 House District 10 20 5 3 2 1 0 0 0 20 30 50
100 House District 300 400 50 40 30 15 8 3 2 400 500 900
Statewide totals 610 920 125 93 62 31 16 6 3 920 1230 2150
Senate Districts
District Dem Rep Other Ind Libert Green Const Reform Soc Wk Male Female Registered
01 Senate District 500 800 100 80 50 20 10 5 2 800 1000 1800
38 Senate District 600 900 120 90 60 25 12 6 3 900 1100 2000
Statewide totals 1100 1700 220 170 110 45 22 11 5 1700 2100 3800
Supreme Court Districts
District Dem Rep Other Ind Libert Green Const Reform Soc Wk Male Female Registered
1 Supreme Court District 1000 2000 300 200 100 50 30 10 0 2000 3000 5000
7 Supreme Court District 2000 3000 400 300 200 100 50 20 10 3000 4000 7000
Statewide totals 3000 5000 700 500 300 150 80 30 10 5000 7000 12000"""


class TestParseDistrictPdf:
    def test_parses_all_types(self):
        pages = [MockPage(DISTRICT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_district_pdf("/fake/district.pdf", "2024-04")

        types = {r["district_type"] for r in rows}
        assert types == {"congressional", "house", "senate", "supreme_court"}

    def test_counts_per_type(self):
        pages = [MockPage(DISTRICT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_district_pdf("/fake/district.pdf", "2024-04")

        from collections import Counter
        counts = Counter(r["district_type"] for r in rows)
        assert counts["congressional"] == 2
        assert counts["house"] == 4
        assert counts["senate"] == 2
        assert counts["supreme_court"] == 2

    def test_preserves_raw_district_number(self):
        pages = [MockPage(DISTRICT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_district_pdf("/fake/district.pdf", "2024-04")

        house_rows = [r for r in rows if r["district_type"] == "house"]
        nums = {r["district_number"] for r in house_rows}
        assert "001" in nums
        assert "035" in nums
        assert "35" in nums
        assert "100" in nums

    def test_parses_data_correctly(self):
        pages = [MockPage(DISTRICT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_district_pdf("/fake/district.pdf", "2024-04")

        c1 = [r for r in rows if r["district_type"] == "congressional" and r["district_number"] == "1"][0]
        assert c1["democratic"] == 1000
        assert c1["republican"] == 2000
        assert c1["total"] == 5000

    def test_skips_statewide_and_column_header(self):
        pages = [MockPage(DISTRICT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_district_pdf("/fake/district.pdf", "2024-04")

        types = [r["district_type"] for r in rows]
        assert len(types) == len(rows)
        assert all(t in ("congressional", "house", "senate", "supreme_court") for t in types)

    def test_month_and_file_passthrough(self):
        pages = [MockPage(DISTRICT_PDF_TEXT)]
        with patch("ky_voter_tracker.parser.pdfplumber.open", return_value=MockPdf(pages)):
            rows = parse_district_pdf("/fake/district.pdf", "2024-04")

        assert rows[0]["month"] == "2024-04"
        assert rows[0]["source_file"] == "/fake/district.pdf"
