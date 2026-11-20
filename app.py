import base64
import hashlib
import hmac
import io
import json
import os
import re
import threading
import time
import platform
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

import subhd

app = FastAPI(title="SubHD for Forward/rex", version="1.0.0", docs_url=None, redoc_url=None)
browser_slot = threading.BoundedSemaphore(1)
WIDGET = Path(__file__).parent / "widgets" / "subhd.js"
STATIC = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=STATIC), name="assets")
stats = {"started": time.time(), "busy": False, "last_download": None, "last_error": None}


class SearchRequest(BaseModel):
    imdbId: str = Field(pattern=r"^tt\d{7,10}$")
    type: Literal["movie", "tv"] = "movie"
    season: int | None = Field(default=None, ge=0, le=99)
    episode: int | None = Field(default=None, ge=1, le=999)
    language: Literal["zh", "en"] = "zh"
    page: int = Field(default=1, ge=1, le=20)

    @model_validator(mode="after")
    def check_episode(self):
        if self.type == "tv" and (self.season is None or self.episode is None):
            raise ValueError("剧集需要提供 season 和 episode")
        if self.type == "movie" and (self.season is not None or self.episode is not None):
            raise ValueError("电影不能携带剧集季数或集数")
        return self


def api_token():
    value = os.environ.get("API_TOKEN", "")
    if len(value) < 24:
        raise HTTPException(503, "请设置至少 24 字符的 API_TOKEN 环境变量")
    return value


def authorize(request):
    supplied = request.headers.get("authorization", "")
    if not hmac.compare_digest(supplied.encode(), ("Bearer " + api_token()).encode()):
        raise HTTPException(401, "API_TOKEN 不正确")


def module_token():
    return hmac.new(api_token().encode(), b"subhd-module-access-v1", hashlib.sha256).hexdigest()


def authorize_module(request):
    supplied = request.headers.get("authorization", "")
    if not hmac.compare_digest(supplied.encode(), ("Bearer " + module_token()).encode()):
        raise HTTPException(401, "模块链接已失效，请从管理面板重新导入")


def make_ticket(sid, context):
    payload = {"sid": sid, "imdbId": context.imdbId, "type": context.type,
               "season": context.season, "episode": context.episode, "exp": int(time.time()) + 3600}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(api_token().encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signature


def read_ticket(ticket, sid):
    if len(ticket) > 1024:
        raise HTTPException(403, "下载凭证无效")
    try:
        encoded, signature = ticket.rsplit(".", 1)
        expected = hmac.new(api_token().encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["sid"] != sid or payload["exp"] <= time.time():
            raise ValueError("expired or wrong subtitle")
        return SearchRequest.model_validate({key: payload[key] for key in ("imdbId", "type", "season", "episode")})
    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError):
        raise HTTPException(403, "下载凭证无效或已过期，请重新搜索字幕") from None


@app.exception_handler(subhd.SourceError)
async def source_error(request, error):
    return JSONResponse({"detail": str(error)}, status_code=error.status,
                        headers={"Cache-Control": "no-store"})


@app.middleware("http")
async def response_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    if request.url.path.startswith("/api/") or request.url.path == "/widget.js":
        response.headers["Cache-Control"] = "private, no-store"
    return response


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"ok": True, "configured": len(os.environ.get("API_TOKEN", "")) >= 24}


@app.get("/widget.js")
def widget(request: Request, key: str = ""):
    if not hmac.compare_digest(key.encode(), module_token().encode()):
        raise HTTPException(401, "请通过管理面板复制模块链接")
    source = WIDGET.read_text(encoding="utf-8")
    source = source.replace('value: "__BACKEND_URL__"', "value: " + json.dumps(str(request.base_url).rstrip("/")))
    source = source.replace('"__MODULE_TOKEN__"', json.dumps(module_token()))
    return Response(source, media_type="application/javascript")


@app.get("/api/admin/overview")
def overview(request: Request):
    authorize(request)
    info = cached_download.cache_info()
    browsers = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/browsers"))
    return {
        "moduleUrl": f"{str(request.base_url).rstrip('/')}/widget.js?key={module_token()}",
        "version": "1.0.0", "python": platform.python_version(),
        "region": os.environ.get("VERCEL_REGION", "local"),
        "browserInstalled": any(browsers.glob("chromium-*/chrome-linux*/chrome")),
        "cache": {"files": info.currsize, "capacity": info.maxsize, "hits": info.hits},
        "uptime": int(time.time() - stats["started"]),
        "busy": stats["busy"], "lastDownload": stats["last_download"], "lastError": stats["last_error"],
    }


@app.post("/api/admin/cache/clear")
def clear_cache(request: Request):
    authorize(request)
    if not browser_slot.acquire(blocking=False):
        raise HTTPException(503, "请等待当前下载结束后再清空缓存")
    try:
        cached_download.cache_clear()
    finally:
        browser_slot.release()
    return {"ok": True}


@app.post("/api/search")
def search(context: SearchRequest, request: Request):
    authorize_module(request)
    items = subhd.search(context.imdbId, context.season, context.episode, context.language, context.page)
    origin = str(request.base_url).rstrip("/")
    return {"items": [{"id": "subhd:" + item["sid"], "title": item["title"],
                       "lang": item["lang"], "count": item["count"],
                       "url": f"{origin}/api/download/{item['sid']}.zip?ticket={quote(make_ticket(item['sid'], context))}"}
                      for item in items]}


# shortcut: 缓存只存在热实例且最多 4 个条目；需要跨冷启动复用时接文件存储。
@lru_cache(maxsize=4)
def cached_download(sid, imdb_id, season, episode, time_bucket):
    return subhd.download_archive(sid, imdb_id, season, episode)


@app.get("/api/download/{sid}.zip")
def download(sid: str, ticket: str):
    if not re.fullmatch(r"[A-Za-z0-9]{4,12}", sid):
        raise HTTPException(400, "字幕 ID 无效")
    context = read_ticket(ticket, sid)
    if not browser_slot.acquire(blocking=False):
        raise HTTPException(503, "浏览器正在下载其他字幕，请稍后重试", headers={"Retry-After": "10"})
    try:
        stats["busy"] = True
        body = cached_download(sid, context.imdbId, context.season, context.episode, int(time.time()) // 600)
        stats["last_download"] = int(time.time())
        stats["last_error"] = None
    except subhd.SourceError as error:
        stats["last_error"] = str(error)
        raise
    finally:
        stats["busy"] = False
        browser_slot.release()
    return StreamingResponse(io.BytesIO(body), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="subhd-{sid}.zip"',
        "Cache-Control": "private, no-store",
        "Content-Length": str(len(body)),
    })
