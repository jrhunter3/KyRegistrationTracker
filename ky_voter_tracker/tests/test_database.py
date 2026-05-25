from ky_voter_tracker.database import (
    init_db,
    insert_registration,
    get_registrations,
    insert_county_stats,
    get_county_stats,
    insert_precinct_stats,
    get_precinct_stats,
    delete_precinct_stats_by_month,
    insert_district_stats,
    get_district_stats,
    delete_district_stats_by_month,
    mark_downloaded,
    mark_parsed,
    is_downloaded,
    get_downloaded_urls,
    get_unparsed_files,
    reset_parsed_flags,
    reset_parsed_flags_for_urls,
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


_PRECINCT_ARGS = (
    "2024-01", "001", "ADAIR", "A001 MAIN", "201-2-012-3",
    100, 200, 30, 20, 10, 5, 3, 1, 0, 0,
    200, 300, 500, "test.xls",
)

_DISTRICT_ARGS_CONGRESS = (
    "2024-01", "congressional", "1",
    1000, 2000, 300, 200, 100, 50, 30, 10, 0, 0,
    2000, 3000, 5000, "test.xls",
)


class TestDeletePrecinctStatsByMonth:
    def test_deletes_only_matching_month(self):
        conn = _memory_db()
        insert_precinct_stats(conn, *_PRECINCT_ARGS)
        args2 = (
            "2024-02", "001", "ADAIR", "A001 MAIN", "201-2-012-3",
            100, 200, 30, 20, 10, 5, 3, 1, 0, 0,
            200, 300, 500, "test.xls",
        )
        insert_precinct_stats(conn, *args2)
        delete_precinct_stats_by_month(conn, "2024-01")
        remaining = conn.execute("SELECT COUNT(*) FROM precinct_stats").fetchone()[0]
        assert remaining == 1
        rows = conn.execute("SELECT month FROM precinct_stats").fetchall()
        assert rows[0]["month"] == "2024-02"

    def test_no_effect_when_month_empty(self):
        conn = _memory_db()
        insert_precinct_stats(conn, *_PRECINCT_ARGS)
        delete_precinct_stats_by_month(conn, "2099-12")
        remaining = conn.execute("SELECT COUNT(*) FROM precinct_stats").fetchone()[0]
        assert remaining == 1


class TestDistrictStats:
    def test_insert_and_retrieve(self):
        conn = _memory_db()
        insert_district_stats(conn, *_DISTRICT_ARGS_CONGRESS)
        rows = get_district_stats(conn)
        assert len(rows) == 1
        r = rows[0]
        assert r["district_type"] == "congressional"
        assert r["district_number"] == "1"
        assert r["total"] == 5000

    def test_filter_by_type(self):
        conn = _memory_db()
        insert_district_stats(conn, *_DISTRICT_ARGS_CONGRESS)
        args2 = (
            "2024-01", "house", "001",
            100, 200, 30, 20, 10, 5, 3, 1, 0, 0,
            200, 300, 500, "test.xls",
        )
        insert_district_stats(conn, *args2)
        rows = get_district_stats(conn, district_type="house")
        assert len(rows) == 1
        assert rows[0]["district_number"] == "001"

    def test_filter_by_month(self):
        conn = _memory_db()
        insert_district_stats(conn, *_DISTRICT_ARGS_CONGRESS)
        args2 = (
            "2024-02", "congressional", "1",
            2000, 3000, 400, 300, 200, 100, 50, 20, 10, 0,
            3000, 4000, 7000, "test.xls",
        )
        insert_district_stats(conn, *args2)
        rows = get_district_stats(conn, from_month="2024-02", until_month="2024-02")
        assert len(rows) == 1
        assert rows[0]["total"] == 7000

    def test_upsert_replaces(self):
        conn = _memory_db()
        insert_district_stats(conn, *_DISTRICT_ARGS_CONGRESS)
        args2 = (
            "2024-01", "congressional", "1",
            999, 888, 77, 66, 55, 44, 33, 22, 11, 0,
            500, 600, 1100, "second.xls",
        )
        insert_district_stats(conn, *args2)
        rows = get_district_stats(conn, district_type="congressional")
        assert len(rows) == 1
        assert rows[0]["total"] == 1100


class TestDeleteDistrictStatsByMonth:
    def test_deletes_only_matching_month(self):
        conn = _memory_db()
        insert_district_stats(conn, *_DISTRICT_ARGS_CONGRESS)
        args2 = (
            "2024-02", "congressional", "1",
            2000, 3000, 400, 300, 200, 100, 50, 20, 10, 0,
            3000, 4000, 7000, "test.xls",
        )
        insert_district_stats(conn, *args2)
        delete_district_stats_by_month(conn, "2024-01")
        remaining = conn.execute("SELECT COUNT(*) FROM district_stats").fetchone()[0]
        assert remaining == 1
        rows = conn.execute("SELECT month FROM district_stats").fetchall()
        assert rows[0]["month"] == "2024-02"

    def test_then_insert_after_delete(self):
        conn = _memory_db()
        insert_district_stats(conn, *_DISTRICT_ARGS_CONGRESS)
        delete_district_stats_by_month(conn, "2024-01")
        remaining = conn.execute("SELECT COUNT(*) FROM district_stats").fetchone()[0]
        assert remaining == 0
        insert_district_stats(conn, *_DISTRICT_ARGS_CONGRESS)
        rows = get_district_stats(conn)
        assert len(rows) == 1


class TestGetCountyStatsFilters:
    def test_from_month(self):
        conn = _memory_db()
        insert_county_stats(conn, *_COUNTY_ARGS_ADAIR)
        args2 = (
            "2024-02", "001", "ADAIR", 16, 3740, 8978, 435, 322, 20, 3, 1, 0, 0, 0, 6483, 7016, 13499, "test.xls"
        )
        insert_county_stats(conn, *args2)
        rows = get_county_stats(conn, from_month="2024-02")
        assert len(rows) == 1
        assert rows[0]["month"] == "2024-02"

    def test_until_month(self):
        conn = _memory_db()
        insert_county_stats(conn, *_COUNTY_ARGS_ADAIR)
        args2 = (
            "2024-02", "001", "ADAIR", 16, 3740, 8978, 435, 322, 20, 3, 1, 0, 0, 0, 6483, 7016, 13499, "test.xls"
        )
        insert_county_stats(conn, *args2)
        rows = get_county_stats(conn, until_month="2024-01")
        assert len(rows) == 1
        assert rows[0]["month"] == "2024-01"

    def test_filter_by_county_name(self):
        conn = _memory_db()
        insert_county_stats(conn, *_COUNTY_ARGS_ADAIR)
        insert_county_stats(conn, *_COUNTY_ARGS_ALLEN)
        rows = get_county_stats(conn, county_name="ALLEN")
        assert len(rows) == 1
        assert rows[0]["county_code"] == "002"


class TestGetPrecinctStats:
    def test_insert_and_retrieve(self):
        conn = _memory_db()
        insert_precinct_stats(conn, *_PRECINCT_ARGS)
        rows = get_precinct_stats(conn)
        assert len(rows) == 1
        r = rows[0]
        assert r["month"] == "2024-01"
        assert r["county_code"] == "001"
        assert r["precinct"] == "A001 MAIN"
        assert r["total"] == 500

    def test_filter_by_month(self):
        conn = _memory_db()
        insert_precinct_stats(conn, *_PRECINCT_ARGS)
        args2 = (
            "2024-02", "001", "ADAIR", "A001 MAIN", "201-2-012-3",
            100, 200, 30, 20, 10, 5, 3, 1, 0, 0,
            200, 300, 500, "test.xls",
        )
        insert_precinct_stats(conn, *args2)
        rows = get_precinct_stats(conn, from_month="2024-02", until_month="2024-02")
        assert len(rows) == 1
        assert rows[0]["month"] == "2024-02"

    def test_filter_by_county_code(self):
        conn = _memory_db()
        insert_precinct_stats(conn, *_PRECINCT_ARGS)
        args2 = (
            "2024-01", "002", "ALLEN", "B001 OTHER", "202-3-015-4",
            200, 300, 40, 30, 20, 10, 5, 2, 1, 0,
            400, 500, 900, "test.xls",
        )
        insert_precinct_stats(conn, *args2)
        rows = get_precinct_stats(conn, county_code="002")
        assert len(rows) == 1
        assert rows[0]["county_name"] == "ALLEN"


class TestResetParsedFlags:
    def test_resets_parsed_to_downloaded(self):
        conn = _memory_db()
        mark_downloaded(conn, "https://example.com/a.xls", "a.xls")
        mark_parsed(conn, "https://example.com/a.xls")
        reset_parsed_flags(conn)
        row = conn.execute(
            "SELECT status, parsed FROM downloads_log WHERE url = ?",
            ("https://example.com/a.xls",),
        ).fetchone()
        assert row["status"] == "downloaded"
        assert row["parsed"] == 0

    def test_does_not_affect_failed(self):
        conn = _memory_db()
        mark_downloaded(conn, "https://example.com/a.xls", "a.xls", status="failed")
        reset_parsed_flags(conn)
        row = conn.execute(
            "SELECT status FROM downloads_log WHERE url = ?",
            ("https://example.com/a.xls",),
        ).fetchone()
        assert row["status"] == "failed"


class TestResetParsedFlagsForUrls:
    def test_resets_selected_urls_only(self):
        conn = _memory_db()
        urls = [f"https://example.com/{i}.xls" for i in range(3)]
        for i, url in enumerate(urls):
            mark_downloaded(conn, url, f"{i}.xls")
            mark_parsed(conn, url)
        mark_downloaded(conn, "https://example.com/other.xls", "other.xls")
        mark_parsed(conn, "https://example.com/other.xls")

        reset_parsed_flags_for_urls(conn, urls[:2])

        for url in urls[:2]:
            row = conn.execute(
                "SELECT status, parsed FROM downloads_log WHERE url = ?", (url,)
            ).fetchone()
            assert row["status"] == "downloaded"
            assert row["parsed"] == 0
        row = conn.execute(
            "SELECT status FROM downloads_log WHERE url = ?", (urls[2],)
        ).fetchone()
        assert row["status"] == "parsed"
        row = conn.execute(
            "SELECT status FROM downloads_log WHERE url = ?",
            ("https://example.com/other.xls",),
        ).fetchone()
        assert row["status"] == "parsed"

    def test_empty_urls_does_nothing(self):
        conn = _memory_db()
        mark_downloaded(conn, "https://example.com/a.xls", "a.xls")
        mark_parsed(conn, "https://example.com/a.xls")
        reset_parsed_flags_for_urls(conn, [])
        row = conn.execute(
            "SELECT status FROM downloads_log WHERE url = ?",
            ("https://example.com/a.xls",),
        ).fetchone()
        assert row["status"] == "parsed"

    def test_only_resets_parsed_files(self):
        conn = _memory_db()
        mark_downloaded(conn, "https://example.com/a.xls", "a.xls", status="failed")
        reset_parsed_flags_for_urls(conn, ["https://example.com/a.xls"])
        row = conn.execute(
            "SELECT status FROM downloads_log WHERE url = ?",
            ("https://example.com/a.xls",),
        ).fetchone()
        assert row["status"] == "failed"
