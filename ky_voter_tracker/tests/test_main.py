from ky_voter_tracker.main import _filter_links_by_month, _parse_args


class TestFilterLinksByMonth:
    def test_no_filters_returns_all(self):
        links = [
            {"month": "2020-01"},
            {"month": "2020-02"},
            {"month": "2020-03"},
        ]
        result = _filter_links_by_month(links, None, None)
        assert result == links

    def test_from_month_filters_earlier(self):
        links = [
            {"month": "2020-01"},
            {"month": "2020-02"},
            {"month": "2020-03"},
        ]
        result = _filter_links_by_month(links, "2020-02", None)
        assert len(result) == 2
        assert result[0]["month"] == "2020-02"
        assert result[1]["month"] == "2020-03"

    def test_until_month_filters_later(self):
        links = [
            {"month": "2020-01"},
            {"month": "2020-02"},
            {"month": "2020-03"},
        ]
        result = _filter_links_by_month(links, None, "2020-02")
        assert len(result) == 2
        assert result[0]["month"] == "2020-01"
        assert result[1]["month"] == "2020-02"

    def test_both_bounds(self):
        links = [
            {"month": "2020-01"},
            {"month": "2020-02"},
            {"month": "2020-03"},
            {"month": "2020-04"},
        ]
        result = _filter_links_by_month(links, "2020-02", "2020-03")
        assert len(result) == 2
        assert result[0]["month"] == "2020-02"
        assert result[1]["month"] == "2020-03"

    def test_skips_none_month_links(self):
        links = [
            {"month": "2020-01"},
            {"month": None},
            {"month": "2020-02"},
        ]
        result = _filter_links_by_month(links, "2020-02", None)
        assert len(result) == 1
        assert result[0]["month"] == "2020-02"

    def test_no_links_in_range(self):
        links = [
            {"month": "2020-01"},
            {"month": "2020-02"},
        ]
        result = _filter_links_by_month(links, "2021-01", None)
        assert result == []

    def test_all_links_included_within_range(self):
        links = [
            {"month": "2020-01"},
            {"month": "2020-02"},
            {"month": "2020-03"},
        ]
        result = _filter_links_by_month(links, "2019-01", "2021-01")
        assert result == links


class TestParseArgs:
    def test_defaults(self):
        args = _parse_args([])
        assert args.from_month is None
        assert args.until_month is None

    def test_from_flag(self):
        args = _parse_args(["--from", "2020-01"])
        assert args.from_month == "2020-01"

    def test_until_flag(self):
        args = _parse_args(["--until", "2020-12"])
        assert args.until_month == "2020-12"

    def test_both_flags(self):
        args = _parse_args(["--from", "2020-01", "--until", "2020-12"])
        assert args.from_month == "2020-01"
        assert args.until_month == "2020-12"
