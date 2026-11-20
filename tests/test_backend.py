import io
import json
import os
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from scrapling.parser import Selector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import subhd

TOKEN = "test6!"
SRT = b"1\n00:00:01,000 --> 00:00:02,000\nHello\n"


def detail_html(sid="Ab12Cd", imdb="tt4154796", edition="Movie.2019.1080p", files=None):
    files = files or ["Movie.2019.chs.srt"]
    return f'''<h1>Movie (2019)</h1><a href="https://www.imdb.com/title/{imdb}">IMDb</a>
        <div class="subtitle-edition">{edition}</div>
        <div class="subtitle-metadata-tags"><span>简体</span><span>英语</span></div>
        <button class="subtitle-prepare-download" data-sid="{sid}">下载字幕文件</button>''' + "".join(
        f'<a class="subtitle-file-name" data-filename="{name}"></a>' for name in files)


def archive_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in files:
            archive.writestr(name, body)
    return output.getvalue()


class ParsingTests(unittest.TestCase):
    def test_listing_and_detail(self):
        page = Selector('''<div class="view-text"><a href="/a/Ab12Cd">Movie.2019</a></div>
            <div class="view-text"><a href="/a/Ab12Cd">duplicate</a></div>
            <div class="view-text"><a href="/a/../../internal">invalid</a></div>''')
        self.assertEqual(subhd.parse_listing(page), [{"sid": "Ab12Cd", "edition": "Movie.2019"}])
        detail = subhd.parse_detail(Selector(detail_html()), "Ab12Cd")
        self.assertEqual(detail["edition"], "Movie.2019.1080p")
        self.assertTrue(subhd.matches_context(detail, "tt4154796"))
        self.assertFalse(subhd.matches_context(detail, "tt0944947"))
        with self.assertRaises(subhd.SourceError):
            subhd.parse_detail(Selector(detail_html()), "Other1")

    def test_episode_matching(self):
        for name in ["Show.S01E02.chs.srt", "Show.1x02.en.srt", "Show.S01E01-E03.chs.srt", "S01/E02.srt"]:
            self.assertIs(subhd.episode_file_matches(name, 1, 2), True, name)
        for name in ["Show.S01E20.srt", "Show.S11E02.srt", "Show.S02E02.srt", "S02/E02.srt"]:
            self.assertIs(subhd.episode_file_matches(name, 1, 2), False, name)
        self.assertEqual(subhd.episode_marks("S01E01E03"), {(1, 1), (1, 3)})
        pack = subhd.parse_detail(Selector(detail_html(edition="Show.S01.Complete", files=["Show.S01E02.srt"])), "Ab12Cd")
        self.assertTrue(subhd.matches_context(pack, "tt4154796", 1, 2))
        self.assertFalse(subhd.matches_context(pack, "tt4154796", 1, 3))
        generic = subhd.parse_detail(Selector(detail_html(edition="Show.S01E02", files=["Chinese.srt"])), "Ab12Cd")
        self.assertTrue(subhd.matches_context(generic, "tt4154796", 1, 2))
        self.assertFalse(subhd.matches_context(generic, "tt4154796", 1, 20))
        wrong_season = subhd.parse_detail(Selector(detail_html(edition="Show.S02.Complete", files=["E02.srt"])), "Ab12Cd")
        self.assertFalse(subhd.matches_context(wrong_season, "tt4154796", 1, 2))
        self.assertTrue(subhd.matches_context(wrong_season, "tt4154796", 2, 2))
        wrong_season["title"] = "剧名 第二季"
        wrong_season["edition"] = "Complete season"
        self.assertFalse(subhd.matches_context(wrong_season, "tt4154796", 1, 2))
        self.assertEqual(subhd.season_marks("剧名 第二十一季"), {21})

    def test_download_url_isolation(self):
        self.assertEqual(subhd.download_page_url("/down/Ab12Cd?nonce=fixture"), "https://subhd.tv/down/Ab12Cd?nonce=fixture")
        for value in ["https://evil.test/down/a", "//evil.test/down/a", "/a/Ab12Cd", "/down/a#fragment", "/down/../api/test", "/down/%2e%2e/api/test", None]:
            with self.assertRaises(subhd.SourceError):
                subhd.download_page_url(value)

    def test_archive_filters_episode_and_unsafe_files(self):
        body = archive_bytes([
            ("Show.S01E02.chs.srt", SRT), ("Show.S01E20.chs.srt", SRT),
            ("../escape.srt", SRT), ("/absolute.srt", SRT),
            ("fake.srt", b"<html>challenge</html>"), ("readme.txt", b"readme"),
        ])
        converted = subhd.to_zip(body, "subtitles.zip", {"edition": "Show.S01.Complete"}, 1, 2)
        with zipfile.ZipFile(io.BytesIO(converted)) as archive:
            self.assertEqual(archive.namelist(), ["Show.S01E02.chs.srt"])
            self.assertEqual(archive.read(archive.namelist()[0]), SRT)
        raw = subhd.to_zip(SRT, "movie.srt", {"edition": "movie"})
        self.assertEqual(zipfile.ZipFile(io.BytesIO(raw)).namelist(), ["movie.srt"])
        for body, name in [(b"<html>challenge</html>", "movie.srt"), (b"not an archive", "movie.zip")]:
            with self.assertRaises(subhd.SourceError):
                subhd.to_zip(body, name, {"edition": "movie"})

    def test_archive_size_limit(self):
        body = archive_bytes([("movie.srt", SRT * 10)])
        with patch.object(subhd, "MAX_EXPANDED", 20):
            with self.assertRaises(subhd.SourceError) as error:
                subhd.to_zip(body, "movie.zip", {"edition": "movie"})
            self.assertEqual(error.exception.status, 413)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"API_TOKEN": TOKEN})
        self.environment.start()
        self.client = TestClient(app.app)
        app.cached_download.cache_clear()

    def tearDown(self):
        self.environment.stop()
        self.client.close()

    def test_auth_and_validation_make_no_upstream_requests(self):
        with patch.object(subhd, "search") as search:
            self.assertEqual(self.client.post("/api/search", json={"imdbId": "tt4154796"}).status_code, 401)
            self.assertEqual(self.client.post("/api/search", json={"imdbId": "https://internal/"}, headers={"Authorization": "Bearer " + app.module_token()}).status_code, 422)
            self.assertEqual(self.client.post("/api/search", json={"imdbId": "tt4154796", "type": "tv"}, headers={"Authorization": "Bearer " + app.module_token()}).status_code, 422)
            search.assert_not_called()

    def test_management_password_minimum_length(self):
        for token, accepted in [("", False), ("12345", False), ("test6!", True), ("longer-password", True)]:
            with self.subTest(length=len(token)), patch.dict(os.environ, {"API_TOKEN": token}):
                self.assertEqual(self.client.get("/health").json()["configured"], accepted)
                response = self.client.get("/api/admin/overview", headers={"Authorization": "Bearer " + token})
                self.assertEqual(response.status_code, 200 if accepted else 503)
        self.assertIn('minlength="6"', self.client.get("/").text)

    def test_search_ticket_and_download(self):
        with patch.object(subhd, "search", return_value=[{"sid": "Ab12Cd", "title": "Movie", "lang": "zh", "count": 2}]) as search:
            response = self.client.post("/api/search", json={"imdbId": "tt4154796"}, headers={"Authorization": "Bearer " + app.module_token()})
        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["id"], "subhd:Ab12Cd")
        self.assertNotIn(TOKEN, item["url"])
        search.assert_called_once_with("tt4154796", None, None, "zh", 1)
        body = archive_bytes([("movie.srt", SRT)])
        with patch.object(subhd, "download_archive", return_value=body) as download:
            response = self.client.get(item["url"])
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, body)
            self.assertEqual(response.headers["content-type"], "application/zip")
            self.assertEqual(self.client.get(item["url"]).content, body)
            download.assert_called_once_with("Ab12Cd", "tt4154796", None, None)

    def test_ticket_tampering_and_expiry(self):
        context = app.SearchRequest(imdbId="tt4154796")
        ticket = app.make_ticket("Ab12Cd", context)
        with patch.object(subhd, "download_archive") as download:
            for sid, value in [("Other1", ticket), ("Ab12Cd", ticket + "0"), ("Ab12Cd", "invalid")]:
                self.assertEqual(self.client.get(f"/api/download/{sid}.zip", params={"ticket": value}).status_code, 403)
            with patch.object(app.time, "time", return_value=10**12):
                self.assertEqual(self.client.get("/api/download/Ab12Cd.zip", params={"ticket": ticket}).status_code, 403)
            download.assert_not_called()

    def test_widget_contains_origin_not_secret(self):
        self.assertEqual(self.client.get("/widget.js").status_code, 401)
        response = self.client.get("/widget.js", params={"key": app.module_token()})
        self.assertIn('value: "http://testserver"', response.text)
        self.assertNotIn(TOKEN, response.text)
        self.assertNotIn("__BACKEND_URL__", response.text)
        self.assertNotIn("__MODULE_TOKEN__", response.text)
        self.assertIn(app.module_token(), response.text)

    def test_panel_and_module_permissions(self):
        response = self.client.get("/")
        self.assertIn("管理面板", response.text)
        self.assertEqual(response.headers["content-type"], "text/html; charset=utf-8")
        self.assertEqual(self.client.get("/assets/panel.js").status_code, 200)
        headers = {"Authorization": "Bearer " + TOKEN}
        response = self.client.get("/api/admin/overview", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(TOKEN, response.json()["moduleUrl"])
        self.assertEqual(self.client.get(response.json()["moduleUrl"]).status_code, 200)
        module_headers = {"Authorization": "Bearer " + app.module_token()}
        self.assertEqual(self.client.get("/api/admin/overview", headers=module_headers).status_code, 401)
        self.assertEqual(self.client.post("/api/admin/cache/clear", headers=module_headers).status_code, 401)
        self.assertEqual(self.client.post("/api/admin/cache/clear", headers=headers).status_code, 200)


if __name__ == "__main__":
    unittest.main()
