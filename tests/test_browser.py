"""Real Chromium, fully intercepted local fixtures; no SubHD download requests."""

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from scrapling.fetchers import StealthySession

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import subhd

SRT = b"1\n00:00:01,000 --> 00:00:02,000\nHello\n"


class BrowserFlowTests(unittest.TestCase):
    def fixture_session(self, calls, imdb="tt4154796", returned_url="/down/fixture-nonce"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("Movie.chs.srt", SRT)
        payload = buffer.getvalue()

        def route_request(route):
            request = route.request
            parsed = urlsplit(request.url)
            calls.append({"path": parsed.path, "method": request.method, "body": request.post_data})
            if parsed.hostname != "subhd.tv":
                route.abort()
                return
            if parsed.path == "/a/Ab12Cd":
                route.fulfill(status=200, content_type="text/html; charset=utf-8", headers={"Set-Cookie": "fixture-session=one; Path=/; Secure; HttpOnly"}, body='''
                    <h1>Movie</h1><div class="subtitle-edition">Movie.2019</div>
                    <a href="https://www.imdb.com/title/''' + imdb + '''">IMDb</a>
                    <a class="subtitle-file-name" data-filename="Movie.chs.srt"></a>
                    <button class="subtitle-prepare-download" data-sid="Ab12Cd">下载字幕文件</button>''')
            elif parsed.path == "/api/sub/prepare-download":
                self.assertEqual(request.method, "POST")
                self.assertEqual(json.loads(request.post_data), {"sid": "Ab12Cd"})
                self.assertEqual(request.headers.get("x-requested-with"), "XMLHttpRequest")
                self.assertIn("fixture-session=one", request.headers.get("cookie", ""))
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps({"success": True, "url": returned_url}))
            elif parsed.path == "/down/fixture-nonce":
                self.assertIn("fixture-session=one", request.headers.get("cookie", ""))
                route.fulfill(status=200, content_type="text/html; charset=utf-8", body='''
                    <button id="download" disabled>下载字幕文件</button>
                    <script>
                    setTimeout(() => document.getElementById('download').disabled = false, 100);
                    document.getElementById('download').onclick = () => location.href = '/fixture-file';
                    </script>''')
            elif parsed.path == "/fixture-file":
                route.fulfill(status=200, content_type="application/zip",
                              headers={"Content-Disposition": 'attachment; filename="subtitle.zip"'}, body=payload)
            else:
                route.abort()

        class FixtureSession(StealthySession):
            def fetch(self, url, **kwargs):
                def setup(page):
                    page.route("**/*", route_request)
                kwargs["page_setup"] = setup
                return super().fetch(url, **kwargs)

        return FixtureSession

    def test_prepare_same_session_and_file_download(self):
        calls = []
        with patch.object(subhd, "StealthySession", self.fixture_session(calls)):
            body = subhd.download_archive("Ab12Cd", "tt4154796")
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            self.assertEqual(archive.read("Movie.chs.srt"), SRT)
        self.assertEqual([call["path"] for call in calls], [
            "/a/Ab12Cd", "/api/sub/prepare-download", "/down/fixture-nonce", "/fixture-file",
        ])

    def test_wrong_movie_never_prepares_download(self):
        calls = []
        with patch.object(subhd, "StealthySession", self.fixture_session(calls, imdb="tt0944947")):
            with self.assertRaises(subhd.SourceError) as error:
                subhd.download_archive("Ab12Cd", "tt4154796")
        self.assertEqual(error.exception.status, 422)
        self.assertEqual([call["path"] for call in calls], ["/a/Ab12Cd"])

    def test_foreign_download_url_is_not_visited(self):
        calls = []
        with patch.object(subhd, "StealthySession", self.fixture_session(calls, returned_url="https://evil.test/down/file")):
            with self.assertRaises(subhd.SourceError):
                subhd.download_archive("Ab12Cd", "tt4154796")
        self.assertEqual([call["path"] for call in calls], ["/a/Ab12Cd", "/api/sub/prepare-download"])


if __name__ == "__main__":
    unittest.main()
