from pathlib import Path
from typing import Any
import os
import base64

from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl
import yt_dlp


BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads")))
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
RUNTIME_DIR = BASE_DIR / ".runtime"
APP_NAME_SUFFIX = "Nauro-Vidown"
VIDEO_QUALITIES = {"best", "1080", "720", "480", "360"}
AUDIO_QUALITIES = {"320", "192", "128"}

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Video Downloader API", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class DownloadRequest(BaseModel):
    url: HttpUrl
    quality: str | None = None


class DownloadResponse(BaseModel):
    status: str
    media_type: str
    quality: str
    url: str
    title: str | None
    filename: str
    filepath: str
    extractor: str | None
    duration: float | None


class YoutubeSearchItem(BaseModel):
    id: str
    title: str
    channel: str | None
    duration: float | None
    webpage_url: str
    thumbnail: str | None


class YoutubeSearchResponse(BaseModel):
    query: str
    count: int
    items: list[YoutubeSearchItem]


class CookiesTestResponse(BaseModel):
    status: str
    auth_protected: bool
    cookies_configured: bool
    cookiefile: str | None
    cookiefile_exists: bool
    can_extract: bool
    test_url: str
    extractor: str | None
    title: str | None
    detail: str | None


def _resolve_cookies_file() -> str | None:
    cookies_file = os.getenv("YTDLP_COOKIES_FILE")
    if cookies_file:
        path = Path(cookies_file)
        if path.exists() and path.is_file():
            return str(path)

    cookies_b64 = os.getenv("YTDLP_COOKIES_B64")
    if cookies_b64:
        try:
            target = RUNTIME_DIR / "youtube_cookies.txt"
            decoded = base64.b64decode(cookies_b64).decode("utf-8", errors="ignore")
            target.write_text(decoded, encoding="utf-8")
            return str(target)
        except Exception:
            return None

    return None


def _build_ydl_base_options() -> dict[str, Any]:
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "restrictfilenames": True,
        "prefer_ffmpeg": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    cookiefile = _resolve_cookies_file()
    if cookiefile:
        options["cookiefile"] = cookiefile
    return options


def _check_admin_token(admin_token: str | None) -> bool:
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        return False
    if admin_token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True


def _find_output_file(info: dict[str, Any]) -> Path:
    possible_path = info.get("_filename")
    if possible_path:
        candidate = Path(str(possible_path))
        if candidate.exists():
            return candidate

    requested = info.get("requested_downloads")
    if isinstance(requested, list):
        for item in requested:
            if not isinstance(item, dict):
                continue
            filepath = item.get("filepath")
            if filepath:
                candidate = Path(str(filepath))
                if candidate.exists():
                    return candidate

    video_id = str(info.get("id") or "")
    if video_id:
        matches = sorted(
            DOWNLOAD_DIR.glob(f"*-{video_id}*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if matches:
            return matches[0]

    raise FileNotFoundError("Downloaded file not found on disk.")


def _video_format_for_quality(quality: str) -> str:
    if quality == "best":
        return "bestvideo*+bestaudio/best"
    return f"bestvideo*[height<={quality}]+bestaudio/best[height<={quality}]/best[height<={quality}]/best"


def _sanitize_title(value: str) -> str:
    cleaned = value.strip().replace("\n", " ").replace("\r", " ")
    forbidden = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for char in forbidden:
        cleaned = cleaned.replace(char, "")
    return cleaned[:150] or "video"


def _build_branded_filename(info: dict[str, Any], ext: str) -> str:
    raw_title = str(info.get("title") or "video")
    title = _sanitize_title(raw_title)
    app_name = _sanitize_title(APP_NAME_SUFFIX)
    separator = " | " if os.name != "nt" else " - "
    return f"{title}{separator}{app_name}.{ext}"


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for idx in range(1, 1000):
        candidate = parent / f"{stem} ({idx}){suffix}"
        if not candidate.exists():
            return candidate
    return parent / f"{stem}-{os.getpid()}{suffix}"


def download_media(url: str, audio_only: bool = False, quality: str | None = None) -> dict[str, Any]:
    options: dict[str, Any] = _build_ydl_base_options()
    options["outtmpl"] = str(DOWNLOAD_DIR / "%(title).150B-%(id)s.%(ext)s")

    if audio_only:
        selected_quality = quality if quality in AUDIO_QUALITIES else "192"
        options["format"] = "bestaudio/best"
        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": selected_quality,
            }
        ]
    else:
        selected_quality = quality if quality in VIDEO_QUALITIES else "best"
        options["format"] = _video_format_for_quality(selected_quality)
        options["merge_output_format"] = "mp4"

    try:
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as first_exc:
            # Some videos do not expose the requested format; retry with safer defaults.
            first_err = str(first_exc).lower()
            if "requested format is not available" in first_err or "--list-formats" in first_err:
                fallback = _build_ydl_base_options()
                fallback["outtmpl"] = options["outtmpl"]
                if audio_only:
                    fallback["format"] = "bestaudio/best"
                    fallback["postprocessors"] = options.get("postprocessors", [])
                    selected_quality = "192"
                else:
                    fallback["format"] = "bestvideo*+bestaudio/best"
                    fallback["merge_output_format"] = "mp4"
                    selected_quality = "best"
                with yt_dlp.YoutubeDL(fallback) as ydl:
                    info = ydl.extract_info(url, download=True)
            else:
                raise

        final_path = _find_output_file(info)
        final_ext = final_path.suffix.lstrip(".") or str(info.get("ext") or "mp4")
        branded_name = _build_branded_filename(info, final_ext)
        branded_path = _unique_destination(DOWNLOAD_DIR / branded_name)
        if final_path.resolve() != branded_path.resolve():
            final_path = final_path.replace(branded_path)

        return {
            "status": "success",
            "media_type": "audio" if audio_only else "video",
            "quality": selected_quality,
            "url": url,
            "title": info.get("title"),
            "filename": final_path.name,
            "filepath": str(final_path),
            "extractor": info.get("extractor"),
            "duration": info.get("duration"),
        }
    except Exception as exc:
        err = str(exc)
        if "not a bot" in err.lower():
            raise HTTPException(
                status_code=403,
                detail=(
                    "YouTube exige autenticacao. Configure YTDLP_COOKIES_FILE "
                    "ou YTDLP_COOKIES_B64 nas variaveis de ambiente."
                ),
            ) from exc
        raise HTTPException(status_code=400, detail=f"Download failed: {exc}") from exc


def youtube_search(query: str, limit: int = 10) -> YoutubeSearchResponse:
    safe_limit = max(1, min(limit, 20))
    options: dict[str, Any] = _build_ydl_base_options()
    options["skip_download"] = True
    options["extract_flat"] = False

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            data = ydl.extract_info(f"ytsearch{safe_limit}:{query}", download=False)

        entries = data.get("entries", []) if isinstance(data, dict) else []
        items: list[YoutubeSearchItem] = []
        for entry in entries:
            if not entry:
                continue
            video_id = str(entry.get("id") or "")
            webpage_url = entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else "")
            if not webpage_url:
                continue
            items.append(
                YoutubeSearchItem(
                    id=video_id,
                    title=str(entry.get("title") or "Sem titulo"),
                    channel=entry.get("channel") or entry.get("uploader"),
                    duration=entry.get("duration"),
                    webpage_url=webpage_url,
                    thumbnail=entry.get("thumbnail"),
                )
            )

        return YoutubeSearchResponse(query=query, count=len(items), items=items)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Search failed: {exc}") from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search/youtube", response_model=YoutubeSearchResponse)
def search_youtube(q: str = Query(..., min_length=2), limit: int = Query(10, ge=1, le=20)):
    return youtube_search(query=q, limit=limit)


@app.post("/admin/cookies/test", response_model=CookiesTestResponse)
def admin_test_cookies(
    test_url: str = Query("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
):
    auth_protected = bool(os.getenv("ADMIN_TOKEN"))
    _check_admin_token(x_admin_token)

    options = _build_ydl_base_options()
    options["skip_download"] = True
    options["extract_flat"] = False
    cookiefile = options.get("cookiefile")
    cookiefile_exists = bool(cookiefile and Path(cookiefile).exists())
    cookies_configured = bool(cookiefile)

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(test_url, download=False)
        return CookiesTestResponse(
            status="ok",
            auth_protected=auth_protected,
            cookies_configured=cookies_configured,
            cookiefile=str(cookiefile) if cookiefile else None,
            cookiefile_exists=cookiefile_exists,
            can_extract=True,
            test_url=test_url,
            extractor=info.get("extractor"),
            title=info.get("title"),
            detail=None,
        )
    except Exception as exc:
        return CookiesTestResponse(
            status="error",
            auth_protected=auth_protected,
            cookies_configured=cookies_configured,
            cookiefile=str(cookiefile) if cookiefile else None,
            cookiefile_exists=cookiefile_exists,
            can_extract=False,
            test_url=test_url,
            extractor=None,
            title=None,
            detail=str(exc),
        )


@app.get("/")
def home(request: Request):
    base_url = os.getenv("PUBLIC_BASE_URL", str(request.base_url).rstrip("/"))
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"api_base": base_url},
    )


@app.post("/download", response_model=DownloadResponse)
def download(request: DownloadRequest) -> DownloadResponse:
    data = download_media(str(request.url), audio_only=False, quality=request.quality)
    return DownloadResponse(**data)


@app.post("/download/video", response_model=DownloadResponse)
def download_video(request: DownloadRequest) -> DownloadResponse:
    data = download_media(str(request.url), audio_only=False, quality=request.quality)
    return DownloadResponse(**data)


@app.post("/download/audio", response_model=DownloadResponse)
def download_audio(request: DownloadRequest) -> DownloadResponse:
    data = download_media(str(request.url), audio_only=True, quality=request.quality)
    return DownloadResponse(**data)


@app.get("/files/{filename}")
def get_file(filename: str):
    target = (DOWNLOAD_DIR / filename).resolve()
    if DOWNLOAD_DIR.resolve() not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=target, filename=target.name, media_type="application/octet-stream")
