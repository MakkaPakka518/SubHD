"""SubHD public-page parsing and on-demand browser downloads."""

import io
import re
import time
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

import libarchive
from scrapling.fetchers import FetcherSession, StealthySession
from scrapling.parser import Selector

BASE = "https://subhd.tv"
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt", ".ttml", ".dfxp", ".smi"}
MAX_DOWNLOAD = 20 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024


class SourceError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def text(node):
    return node.get_all_text(separator=" ", strip=True) if node is not None else ""


def parse_listing(page):
    items = []
    seen = set()
    for link in page.css('.view-text a[href^="/a/"]'):
        match = re.fullmatch(r"/a/([A-Za-z0-9]{4,12})", link.attrib.get("href", ""))
        if not match or match[1] in seen:
            continue
        seen.add(match[1])
        items.append({"sid": match[1], "edition": text(link)})
    return items


def parse_detail(page, sid):
    actual = page.css(".subtitle-prepare-download::attr(data-sid)").get()
    if actual != sid:
        raise SourceError("SubHD 详情不可用，或页面仍在验证中")
    imdb_ids = set()
    for href in page.css('a[href*="imdb.com/title/"]::attr(href)').getall():
        parsed = urlsplit(href)
        match = re.fullmatch(r"/title/(tt\d{7,10})/?", parsed.path)
        if parsed.hostname in {"imdb.com", "www.imdb.com"} and match:
            imdb_ids.add(match[1])
    edition = text(next(iter(page.css(".subtitle-edition")), None))
    files = page.css(".subtitle-file-name::attr(data-filename)").getall()
    tags = page.css(".subtitle-metadata-tags span")
    languages = " ".join(text(tag) for tag in tags)
    return {"sid": sid, "imdb_ids": imdb_ids, "edition": edition,
            "title": text(next(iter(page.css("h1")), None)),
            "files": files, "languages": languages}


def episode_marks(name):
    """Explicit SxxExx / 1x02 episode markers, including multi-episode ranges."""
    pattern = r"(?<![a-z0-9])(?:s(\d{1,2})[ ._-]*e(\d{1,3})|(\d{1,2})x(\d{1,3}))(?!\d)((?:[ ._]*e\d{1,3}(?!\d))*)"
    marks = set()
    for match in re.finditer(pattern, name, re.I):
        season = int(match[1] or match[3])
        episode = int(match[2] or match[4])
        marks.add((season, episode))
        for extra in re.findall(r"e(\d{1,3})", match[5], re.I):
            marks.add((season, int(extra)))
        tail = name[match.end():]
        end = re.match(r"\s*[-~]\s*(?:e)?(\d{1,3})(?!\d)", tail, re.I)
        if end and episode <= int(end[1]) <= 999:
            marks.update((season, number) for number in range(episode, int(end[1]) + 1))
    return marks


def season_marks(name):
    values = re.findall(r"(?<![a-z0-9])s(\d{1,2})(?!\d)|\bseason[ ._-]*(\d{1,2})(?!\d)", name, re.I)
    seasons = {int(first or second) for first, second in values}
    digits = dict(zip("零一二三四五六七八九", range(10)))
    for value in re.findall(r"第([\d零一二三四五六七八九十]+)季", name):
        if value.isdecimal():
            seasons.add(int(value))
        elif "十" in value:
            tens, ones = value.split("十", 1)
            seasons.add((digits.get(tens, 1) * 10) + digits.get(ones, 0))
        elif value in digits:
            seasons.add(digits[value])
    return seasons


def episode_file_matches(name, season, episode):
    marks = episode_marks(name)
    if marks:
        return (season, episode) in marks
    named_seasons = season_marks(name)
    if named_seasons and season not in named_seasons:
        return False
    episodes = re.findall(r"(?<![a-z0-9])(?:ep?|第)[ ._-]*(\d{1,3})(?:集)?(?!\d)", name, re.I)
    return episode in {int(value) for value in episodes} if episodes else None


def matches_context(detail, imdb_id, season=None, episode=None):
    if detail["imdb_ids"] != {imdb_id}:
        return False
    if season is None:
        return True
    for name in (detail["edition"], detail.get("title", "")):
        named_seasons = season_marks(name)
        if named_seasons and season not in named_seasons:
            return False
    edition_marks = episode_marks(detail["edition"])
    if edition_marks and (season, episode) not in edition_marks:
        return False
    file_matches = [episode_file_matches(name, season, episode) for name in detail["files"]]
    return True in file_matches or (bool(edition_marks) and None in file_matches)


def has_language(detail, language):
    markers = ("英语", "英文") if language == "en" else ("简体", "繁体", "中文")
    return any(marker in detail["languages"] for marker in markers)


def checked_page(http, url):
    page = http.get(url)
    if page.status != 200:
        raise SourceError(f"SubHD 返回 HTTP {page.status}")
    if urlsplit(page.url).hostname != "subhd.tv":
        raise SourceError("SubHD 跳转到了不支持的站点")
    return page


def search(imdb_id, season=None, episode=None, language="zh", page_number=1):
    results = []
    deadline = time.monotonic() + 90
    with FetcherSession(impersonate="chrome", timeout=15) as http:
        listing = checked_page(http, f"{BASE}/search/{imdb_id}/{page_number}")
        for candidate in parse_listing(listing):
            if time.monotonic() >= deadline:
                break
            marks = episode_marks(candidate["edition"])
            if season is not None and marks and (season, episode) not in marks:
                continue
            time.sleep(0.3)
            detail = parse_detail(checked_page(http, f"{BASE}/a/{candidate['sid']}"), candidate["sid"])
            if matches_context(detail, imdb_id, season, episode) and has_language(detail, language):
                results.append({"sid": detail["sid"], "title": detail["edition"],
                                "lang": language, "count": len(detail["files"])})
    return results


def download_page_url(value):
    if not isinstance(value, str) or not value.startswith("/down/"):
        raise SourceError("SubHD 没有返回有效的下载页面")
    parsed = urlsplit(urljoin(BASE, value))
    path = unquote(parsed.path)
    if parsed.scheme != "https" or parsed.netloc != "subhd.tv" or parsed.fragment \
            or not path.startswith("/down/") or ".." in path.split("/") or "\\" in path:
        raise SourceError("SubHD 返回了不支持的下载页面")
    return parsed.geturl()


def download_archive(sid, imdb_id, season=None, episode=None):
    prepared = {}
    downloaded = {}
    errors = []

    # Scrapling logs callback exceptions; retain them so the API can return the actual failure.
    def checked_action(action):
        def run(page):
            try:
                action(page)
            except Exception as error:
                errors.append(error)
        return run

    def prepare(page):
        detail = parse_detail(Selector(page.content()), sid)
        if not matches_context(detail, imdb_id, season, episode):
            raise SourceError("字幕与当前影片或剧集不匹配", 422)
        prepared["detail"] = detail
        response = page.evaluate("""async (sid) => {
            const response = await fetch('/api/sub/prepare-download', {
                method: 'POST', headers: {'Content-Type': 'application/json',
                    'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
                body: JSON.stringify({sid}), signal: AbortSignal.timeout(20000)
            });
            return {status: response.status, data: await response.json()};
        }""", sid)
        data = response.get("data") or {}
        if response.get("status") != 200 or data.get("success") is not True:
            raise SourceError("SubHD 准备下载失败，请稍后重试")
        prepared["url"] = download_page_url(data.get("url"))

    def save_download(page):
        enabled = ':not([disabled]):not([aria-disabled="true"]):not(.disabled):visible'
        button = page.locator(', '.join(selector + enabled for selector in (
            'button:has-text("下载字幕文件")', 'a:has-text("下载字幕文件")',
            'input[type="submit"][value*="下载字幕文件"]',
        ))).first
        button.wait_for(state="visible", timeout=30000)
        with page.expect_download(timeout=30000) as event:
            button.click()
        download = event.value
        if download.failure():
            raise SourceError("SubHD 字幕文件下载失败")
        path = Path(download.path())
        if path.stat().st_size > MAX_DOWNLOAD:
            raise SourceError("字幕压缩包超过 20 MB", 413)
        downloaded["body"] = path.read_bytes()
        downloaded["name"] = download.suggested_filename

    try:
        with StealthySession(headless=True, solve_cloudflare=True, block_ads=True,
                             timeout=60000, retries=1, max_pages=1) as session:
            session.fetch(f"{BASE}/a/{sid}", google_search=False, page_action=checked_action(prepare))
            if errors:
                raise errors[0]
            if "url" not in prepared:
                raise SourceError("SubHD 详情验证或准备下载失败")
            session.fetch(prepared["url"], google_search=False, page_action=checked_action(save_download))
            if errors:
                raise errors[0]
    except SourceError:
        raise
    except Exception as error:
        raise SourceError("浏览器下载失败，可能仍需人机验证，请稍后重试", 503) from error
    if "body" not in downloaded:
        raise SourceError("下载页验证尚未完成，未取得字幕文件", 503)
    return to_zip(downloaded["body"], downloaded["name"], prepared["detail"], season, episode)


def safe_subtitle_path(name):
    if not isinstance(name, str) or "\x00" in name or "\\" in name:
        return None
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or re.match(r"^[a-z]:", name, re.I):
        return None
    return str(path) if path.suffix.lower() in SUBTITLE_EXTENSIONS else None


def looks_like_subtitle(body, name):
    encoding = "utf-16" if body[:2] in {b"\xff\xfe", b"\xfe\xff"} else "utf-8-sig"
    head = body[:8192].decode(encoding, errors="replace")
    extension = PurePosixPath(name).suffix.lower()
    if extension in {".ass", ".ssa"}:
        return bool(re.search(r"\[(?:Script Info|Events|V4\+? Styles)\]", head, re.I))
    if extension == ".srt":
        return bool(re.search(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->", head))
    if extension == ".vtt":
        return head.lstrip().startswith("WEBVTT")
    if extension in {".ttml", ".dfxp"}:
        return bool(re.search(r"<(?:\w+:)?tt(?:\s|>)", head))
    return bool(re.search(r"<sami(?:\s|>)", head, re.I))


def to_zip(body, filename, detail, season=None, episode=None):
    if not body or len(body) > MAX_DOWNLOAD:
        raise SourceError("字幕下载内容为空或过大", 413)
    entries = []
    raw_name = safe_subtitle_path(filename)
    if raw_name:
        entries = [(raw_name, body)]
    else:
        try:
            total = 0
            with libarchive.memory_reader(body) as archive:
                for index, entry in enumerate(archive):
                    if index >= 1000:
                        raise SourceError("字幕压缩包文件数量过多", 413)
                    name = safe_subtitle_path(entry.pathname)
                    if not name or not entry.isfile:
                        continue
                    if entry.size > MAX_EXPANDED - total:
                        raise SourceError("字幕压缩包解压内容过大", 413)
                    data = bytearray()
                    for block in entry.get_blocks():
                        total += len(block)
                        if total > MAX_EXPANDED:
                            raise SourceError("字幕压缩包解压内容过大", 413)
                        data.extend(block)
                    entries.append((name, bytes(data)))
        except SourceError:
            raise
        except Exception as error:
            raise SourceError("下载内容不是可读取的字幕压缩包", 422) from error
    if season is not None:
        edition_matches = (season, episode) in episode_marks(detail["edition"])
        entries = [(name, data) for name, data in entries
                   if episode_file_matches(name, season, episode) is True
                   or (episode_file_matches(name, season, episode) is None and edition_matches)]
    entries = [(name, data) for name, data in entries if looks_like_subtitle(data, name)]
    if not entries:
        raise SourceError("压缩包中没有匹配当前影片或集数的字幕", 422)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return output.getvalue()
