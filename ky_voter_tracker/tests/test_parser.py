from unittest.mock import MagicMock, patch

from ky_voter_tracker.parser import (
    _normalise_header,
    _parse_cell,
    parse_xls,
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
