import os
import tempfile
from unittest.mock import patch

from ky_voter_tracker.database import init_db, mark_downloaded
from ky_voter_tracker.downloader import download_files


class MockResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests.exceptions import HTTPError
            raise HTTPError(f"{self.status_code} Error")


SAMPLE_LINKS = [
    {"url": "https://elect.ky.gov/a.xls", "filename": "a.xls", "category": "overall", "month": "2024-01", "file_type": "xls"},
    {"url": "https://elect.ky.gov/b.xls", "filename": "b.xls", "category": "overall", "month": "2024-02", "file_type": "xls"},
    {"url": "https://elect.ky.gov/c.xls", "filename": "c.xls", "category": "overall", "month": "2024-03", "file_type": "xls"},
]


class TestDownloadFiles:
    def test_downloads_new_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = init_db(":memory:")
            responses = {
                "https://elect.ky.gov/a.xls": MockResponse(b"aaa"),
                "https://elect.ky.gov/b.xls": MockResponse(b"bbb"),
            }

            def mock_get(url, **kwargs):
                return responses[url]

            with patch("ky_voter_tracker.downloader.requests.Session.get", side_effect=mock_get):
                result = download_files(conn, SAMPLE_LINKS[:2], raw_dir=tmpdir)

            assert len(result) == 2
            assert os.path.join(tmpdir, "a.xls") in result
            assert os.path.join(tmpdir, "b.xls") in result
            with open(os.path.join(tmpdir, "a.xls"), "rb") as f:
                assert f.read() == b"aaa"
            with open(os.path.join(tmpdir, "b.xls"), "rb") as f:
                assert f.read() == b"bbb"

    def test_skips_already_downloaded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = init_db(":memory:")
            mark_downloaded(conn, "https://elect.ky.gov/a.xls", "a.xls", file_size=3)

            def mock_get(url, **kwargs):
                return MockResponse(b"bbb")

            with patch("ky_voter_tracker.downloader.requests.Session.get", side_effect=mock_get):
                result = download_files(conn, SAMPLE_LINKS[:2], raw_dir=tmpdir)

            assert len(result) == 1
            assert os.path.join(tmpdir, "b.xls") in result
            assert not os.path.exists(os.path.join(tmpdir, "a.xls"))

    def test_handles_failed_download(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = init_db(":memory:")

            def mock_get(url, **kwargs):
                if "a.xls" in url:
                    from requests.exceptions import HTTPError
                    raise HTTPError("404 Not Found")
                return MockResponse(b"bbb")

            with patch("ky_voter_tracker.downloader.requests.Session.get", side_effect=mock_get):
                result = download_files(conn, SAMPLE_LINKS[:2], raw_dir=tmpdir)

            assert len(result) == 1
            assert os.path.join(tmpdir, "b.xls") in result
            assert not os.path.exists(os.path.join(tmpdir, "a.xls"))

            failed = conn.execute(
                "SELECT status FROM downloads_log WHERE url = ?",
                ("https://elect.ky.gov/a.xls",),
            ).fetchone()
            assert failed["status"] == "failed"

    def test_creates_raw_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = os.path.join(tmpdir, "nonexistent", "deep")
            conn = init_db(":memory:")

            def mock_get(url, **kwargs):
                return MockResponse(b"data")

            with patch("ky_voter_tracker.downloader.requests.Session.get", side_effect=mock_get):
                result = download_files(conn, SAMPLE_LINKS[:1], raw_dir=raw_dir)

            assert len(result) == 1
            assert os.path.isdir(raw_dir)

    def test_returns_empty_set_when_nothing_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = init_db(":memory:")
            mark_downloaded(conn, "https://elect.ky.gov/a.xls", "a.xls", file_size=3)
            mark_downloaded(conn, "https://elect.ky.gov/b.xls", "b.xls", file_size=3)

            with patch("ky_voter_tracker.downloader.requests.Session.get") as mock_get:
                result = download_files(conn, SAMPLE_LINKS[:2], raw_dir=tmpdir)

            assert len(result) == 0
            mock_get.assert_not_called()

    def test_logs_file_size(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = init_db(":memory:")

            def mock_get(url, **kwargs):
                return MockResponse(b"1234567890")

            with patch("ky_voter_tracker.downloader.requests.Session.get", side_effect=mock_get):
                download_files(conn, SAMPLE_LINKS[:1], raw_dir=tmpdir)

            row = conn.execute(
                "SELECT file_size FROM downloads_log WHERE url = ?",
                ("https://elect.ky.gov/a.xls",),
            ).fetchone()
            assert row["file_size"] == 10
