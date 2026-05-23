from ky_voter_tracker.database import (
    init_db,
    insert_registration,
    get_registrations,
    insert_county_stats,
    get_county_stats,
    mark_downloaded,
    mark_parsed,
    is_downloaded,
    get_downloaded_urls,
    get_unparsed_files,
)


def _memory_db():
    return init_db(":memory:")


_REG_ARGS = (
    "2024-01", 1000, 400, 350, 50, 30, 20, 10, 5, 3, 2, 0, 480, 520, "test.xls"
)

_COUNTY_ARGS_ADAIR = (
    "2024-01", "001", "ADAIR", 16, 3740, 8978, 435, 322, 20, 3, 1, 0, 0, 0, 6483, 7016, 13499, "test.xls"
)

_COUNTY_ARGS_ALLEN = (
    "2024-01", "002", "ALLEN", 13, 4770, 8779, 759, 252, 26, 8, 2, 0, 1, 0, 6949, 7648, 14597, "test.xls"
)


class TestInitDb:
    def test_creates_tables(self):
        conn = _memory_db()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [row["name"] for row in tables]
        assert "registrations" in names
        assert "county_stats" in names
        assert "downloads_log" in names

    def test_schema_columns(self):
        conn = _memory_db()
        cols = conn.execute("PRAGMA table_info(registrations)").fetchall()
        col_names = {row["name"] for row in cols}
        assert "kentucky_party" in col_names
        assert "male" in col_names
        assert "female" in col_names

        cols = conn.execute("PRAGMA table_info(county_stats)").fetchall()
        col_names = {row["name"] for row in cols}
        assert "county_code" in col_names
        assert "county_name" in col_names
        assert "precinct_count" in col_names
        assert "libertarian" in col_names


class TestRegistrations:
    def test_insert_and_retrieve(self):
        conn = _memory_db()
        insert_registration(conn, *_REG_ARGS)
        rows = get_registrations(conn)
        assert len(rows) == 1
        r = rows[0]
        assert r["month"] == "2024-01"
        assert r["total"] == 1000
        assert r["democratic"] == 400
        assert r["republican"] == 350
        assert r["independent"] == 30
        assert r["libertarian"] == 20
        assert r["male"] == 480
        assert r["female"] == 520

    def test_upsert_same_month_replaces(self):
        conn = _memory_db()
        insert_registration(conn, *_REG_ARGS)
        args2 = ("2024-01", 2000, 800, 700, 100, 60, 40, 20, 10, 6, 4, 0, 960, 1040, "second.xls")
        insert_registration(conn, *args2)
        rows = get_registrations(conn)
        assert len(rows) == 1
        assert rows[0]["total"] == 2000

    def test_multiple_months(self):
        conn = _memory_db()
        insert_registration(conn, *_REG_ARGS)
        args2 = ("2024-02", 2000, 800, 700, 100, 60, 40, 20, 10, 6, 4, 0, 960, 1040, "b.xls")
        insert_registration(conn, *args2)
        rows = get_registrations(conn)
        assert len(rows) == 2
        assert rows[0]["month"] == "2024-01"
        assert rows[1]["month"] == "2024-02"


class TestGetRegistrationsFilters:
    def test_from_month(self):
        conn = _memory_db()
        insert_registration(conn, *_REG_ARGS)
        args2 = ("2024-02", 2000, 800, 700, 100, 60, 40, 20, 10, 6, 4, 0, 960, 1040, "b.xls")
        insert_registration(conn, *args2)
        rows = get_registrations(conn, from_month="2024-02")
        assert len(rows) == 1

    def test_range(self):
        conn = _memory_db()
        insert_registration(conn, *_REG_ARGS)
        args2 = ("2024-02", 2000, 800, 700, 100, 60, 40, 20, 10, 6, 4, 0, 960, 1040, "b.xls")
        insert_registration(conn, *args2)
        args3 = ("2024-03", 3000, 1200, 1050, 150, 90, 60, 30, 15, 9, 6, 0, 1440, 1560, "c.xls")
        insert_registration(conn, *args3)
        rows = get_registrations(conn, from_month="2024-02", until_month="2024-02")
        assert len(rows) == 1
        assert rows[0]["month"] == "2024-02"


class TestCountyStats:
    def test_insert_and_retrieve(self):
        conn = _memory_db()
        insert_county_stats(conn, *_COUNTY_ARGS_ADAIR)
        rows = get_county_stats(conn)
        assert len(rows) == 1
        r = rows[0]
        assert r["county_code"] == "001"
        assert r["county_name"] == "ADAIR"
        assert r["total"] == 13499
        assert r["democratic"] == 3740
        assert r["libertarian"] == 20

    def test_filter_by_county_code(self):
        conn = _memory_db()
        insert_county_stats(conn, *_COUNTY_ARGS_ADAIR)
        insert_county_stats(conn, *_COUNTY_ARGS_ALLEN)
        rows = get_county_stats(conn, county_code="002")
        assert len(rows) == 1
        assert rows[0]["county_name"] == "ALLEN"

    def test_upsert_same_county_same_month_replaces(self):
        conn = _memory_db()
        insert_county_stats(conn, *_COUNTY_ARGS_ADAIR)
        args2 = (
            "2024-01", "001", "ADAIR", 16, 999, 888, 77, 66, 55, 44, 33, 22, 11, 0,
            5000, 6000, 11000, "second.xls"
        )
        insert_county_stats(conn, *args2)
        rows = get_county_stats(conn, county_code="001")
        assert len(rows) == 1
        assert rows[0]["democratic"] == 999


class TestDownloadsLog:
    def test_mark_and_check(self):
        conn = _memory_db()
        url = "https://example.com/test.xls"
        assert not is_downloaded(conn, url)
        mark_downloaded(conn, url, "test.xls", file_size=1234)
        assert is_downloaded(conn, url)

    def test_mark_parsed(self):
        conn = _memory_db()
        url = "https://example.com/test.xls"
        mark_downloaded(conn, url, "test.xls")
        mark_parsed(conn, url)
        row = conn.execute(
            "SELECT status FROM downloads_log WHERE url = ?", (url,)
        ).fetchone()
        assert row["status"] == "parsed"

    def test_get_unparsed_files(self):
        conn = _memory_db()
        mark_downloaded(conn, "https://example.com/a.xls", "a.xls")
        mark_downloaded(conn, "https://example.com/b.xls", "b.xls")
        mark_parsed(conn, "https://example.com/a.xls")
        unparsed = get_unparsed_files(conn)
        assert len(unparsed) == 1
        assert unparsed[0]["filename"] == "b.xls"

    def test_get_downloaded_urls(self):
        conn = _memory_db()
        mark_downloaded(conn, "https://example.com/a.xls", "a.xls")
        mark_downloaded(conn, "https://example.com/b.xls", "b.xls")
        urls = get_downloaded_urls(conn)
        assert len(urls) == 2
