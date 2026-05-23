from unittest.mock import patch

from ky_voter_tracker.scraper import (
    _categorize,
    _parse_date_from_filename,
    _parse_month,
    get_download_links,
)

SAMPLE_HTML = """\
<div class="ms-rtestate-field">
<h5 class="agencyElement-H5"><span style="font-weight:700;">2017</span></h5>
<p><span style="font-weight:700;">June<br></span></p>
<p><a href="/Resources/Documents/voterstats-20170620-110441.xls"><strong>voterstats-20170620-110441.xls</strong></a><br></p>
<p><a href="/Resources/Documents/voterstatscounty-20170620-110441.pdf">By County</a><br></p>
<p><a href="/Resources/Documents/voterstatsprecinct-20170620-110441.pdf">By Precinct</a><br></p>
<p><a href="/Resources/Documents/voterstatsdistrict-20170620-110441.pdf">By District</a><br></p>

<h5 class="agencyElement-H5"><span style="font-weight:700;">2024</span></h5>
<p><span style="font-weight:700;">January</span></p>
<p><a href="/Resources/Documents/voterstats-January%202024.xls"><strong>voterstats-January 2024.xls</strong></a><br></p>
<p><a href="/Resources/Documents/voterstatscounty-January%202024.pdf">By County</a><br></p>
<p><a href="/Resources/Documents/voterstatsprecinct-January%202024.pdf">By Precinct</a><br></p>
<p><a href="/Resources/Documents/voterstatsdistrict-January%202024.pdf">By District</a><br></p>

<p><span style="font-weight:700;">May Primary 2024 Registration</span></p>
<p><a href="/Resources/Documents/voterstats-May%20Primary%202024.xls">voterstats-May Primary 2024.xls</a></p>
<p><a href="/Resources/Documents/voterstatscounty-May%20Primary%202024.pdf">By County</a></p>
<p><a href="/Resources/Documents/voterstatsprecinct-May%20Primary%202024.pdf">By Precinct</a></p>
<p><a href="/Resources/Documents/voterstatsdistrict-May%20Primary%202024.pdf">By District</a></p>

<p><span style="font-weight:700;">November</span></p>
<p><a href="/Resources/Documents/voterstats-November%202024.xls"><strong>voterstats-November 2024.xls</strong></a><br></p>
<p><a href="/Resources/Documents/voterstatscounty-November%202024.pdf">By County</a><br></p>
<p><a href="/Resources/Documents/voterstatsprecinct-November%202024.pdf">By Precinct</a><br></p>
<p><a href="/Resources/Documents/voterstatsdistrict-November%202024.pdf">By District</a><br></p>

<h5 class="agencyElement-H5"><span style="font-weight:700;">2026</span></h5>
<p><span style="font-weight:700;">April<br></span></p>
<p><a href="/Resources/Documents/voterstats-%20April%202026.xls"><strong>voterstats- April 2026.xls</strong></a><br></p>
<p><a href="/Resources/Documents/voterstatscounty-%20April%202026.pdf">By County</a><br></p>
<p><a href="/Resources/Documents/voterstatsprecinct-%20April%202026.pdf">By Precinct</a><br></p>
<p><a href="/Resources/Documents/voterstatsdistrict-%20April%202026.pdf">By District</a><br></p>
</div>"""

MOCK_RESPONSE = type("MockResponse", (), {
    "raise_for_status": lambda self: None,
    "content": SAMPLE_HTML.encode("utf-8"),
    "status_code": 200,
})()


class TestCategorize:
    def test_overall(self):
        assert _categorize("voterstats-January 2024.xls") == "overall"
        assert _categorize("voterstats-20170620-110441.xls") == "overall"

    def test_county(self):
        assert _categorize("voterstatscounty-January 2024.pdf") == "county"

    def test_precinct(self):
        assert _categorize("voterstatsprecinct-January 2024.pdf") == "precinct"

    def test_district(self):
        assert _categorize("voterstatsdistrict-January 2024.pdf") == "district"

    def test_unknown(self):
        assert _categorize("something_else.xls") is None


class TestParseMonth:
    def test_standard(self):
        assert _parse_month("January 2024") == "2024-01"
        assert _parse_month("December 2023") == "2023-12"

    def test_with_extra_word(self):
        assert _parse_month("May Primary 2024") == "2024-05"
        assert _parse_month("November General 2024") == "2024-11"
        assert _parse_month("Nov General 2023") == "2023-11"

    def test_abbreviated(self):
        assert _parse_month("Jan 2024") == "2024-01"
        assert _parse_month("Nov 2023") == "2023-11"

    def test_leading_hyphen(self):
        assert _parse_month("-April 2026") == "2026-04"

    def test_invalid(self):
        assert _parse_month("") is None
        assert _parse_month("NotAMonth 2024") is None


class TestParseDateFromFilename:
    def test_timestamp_format(self):
        assert _parse_date_from_filename("voterstats-20170620-110441.xls") == "2017-06"
        assert _parse_date_from_filename("voterstats-20221215-092208.xls") == "2022-12"

    def test_timestamp_short_format(self):
        assert _parse_date_from_filename("voterstatscounty-20180416.pdf") == "2018-04"

    def test_month_name_format(self):
        assert _parse_date_from_filename("voterstats-January 2024.xls") == "2024-01"
        assert _parse_date_from_filename("voterstats-December 2023.xls") == "2023-12"

    def test_primary_format(self):
        assert _parse_date_from_filename("voterstats-May Primary 2024.xls") == "2024-05"
        assert _parse_date_from_filename("voterstats-November General 2024.xls") == "2024-11"

    def test_leading_space(self):
        assert _parse_date_from_filename("voterstats- April 2026.xls") == "2026-04"
        assert _parse_date_from_filename("voterstatscounty- April 2026.pdf") == "2026-04"
        assert _parse_date_from_filename("voterstats- January 2026.xls") == "2026-01"


class TestGetDownloadLinks:
    @patch("ky_voter_tracker.scraper.requests.get", return_value=MOCK_RESPONSE)
    def test_parses_correct_count(self, mock_get):
        links = get_download_links()
        assert len(links) == 20

    @patch("ky_voter_tracker.scraper.requests.get", return_value=MOCK_RESPONSE)
    def test_all_categories_present(self, mock_get):
        links = get_download_links()
        cats = {link["category"] for link in links}
        assert cats == {"overall", "county", "precinct", "district"}

    @patch("ky_voter_tracker.scraper.requests.get", return_value=MOCK_RESPONSE)
    def test_months_parsed(self, mock_get):
        links = get_download_links()
        months = {link["month"] for link in links if link["month"] is not None}
        assert "2017-06" in months
        assert "2024-01" in months
        assert "2024-05" in months
        assert "2024-11" in months
        assert "2026-04" in months

    @patch("ky_voter_tracker.scraper.requests.get", return_value=MOCK_RESPONSE)
    def test_no_none_months(self, mock_get):
        links = get_download_links()
        assert all(link["month"] is not None for link in links)

    @patch("ky_voter_tracker.scraper.requests.get", return_value=MOCK_RESPONSE)
    def test_urls_are_absolute(self, mock_get):
        links = get_download_links()
        for link in links:
            assert link["url"].startswith("https://elect.ky.gov")

    @patch("ky_voter_tracker.scraper.requests.get", return_value=MOCK_RESPONSE)
    def test_sort_order(self, mock_get):
        links = get_download_links()
        months = [link["month"] for link in links]
        assert months == sorted(months)
