from pathlib import Path
from typing import Any
import os

from fastapi import FastAPI, HTTPException
from fastapi import Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl
import yt_dlp


BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads")))
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
BRAND_SUFFIX = "| https://nauro-vidown.up.railway.app"
APP_NAME_SUFFIX = "Nauro-Vidown"
VIDEO_QUALITIES = {"best", "1080", "720", "480", "360"}
AUDIO_QUALITIES = {"320", "192", "128"}
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

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


def _find_output_file(ydl: yt_dlp.YoutubeDL, info: dict[str, Any]) -> Path:
    prepared = Path(ydl.prepare_filename(info))
    if prepared.exists():
        return prepared

    possible_path = info.get("_filename")
    if possible_path:
        file_from_info = Path(possible_path)
        if file_from_info.exists():
            return file_from_info

    video_id = info.get("id", "")
    if video_id:
        matches = list(DOWNLOAD_DIR.glob(f"*-{video_id}*"))
        if matches:
            return matches[0]

    raise FileNotFoundError("Downloaded file not found on disk.")


def _video_format_for_quality(quality: str) -> str:
    if quality == "best":
        return "bestvideo*+bestaudio/best"
    return f"bestvideo*[height<={quality}]+bestaudio/best[height<={quality}]/best[height<={quality}]/best"


def _sanitize_title(title: str) -> str:
    cleaned = title.strip().replace("\n", " ").replace("\r", " ")
    forbidden = ['\\', '/', ':', '*', '?', '"', '<', '>']
    for char in forbidden:
        cleaned = cleaned.replace(char, "")
    return cleaned[:150] or "video"


def _build_branded_filename(info: dict[str, Any], ext: str) -> str:
    raw_title = str(info.get("title") or "video")
    title = _sanitize_title(raw_title)
    separator = " | " if os.name != "nt" else " - "
    return f"{title}{separator}{APP_NAME_SUFFIX} - {BRAND_SUFFIX}.{ext}"


def download_media(url: str, audio_only: bool = False, quality: str | None = None) -> dict[str, Any]:
    options: dict[str, Any] = {
        "outtmpl": str(DOWNLOAD_DIR / "%(title).150B-%(id)s.%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "prefer_ffmpeg": True,
    }
    selected_quality = ""
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
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            final_path = _find_output_file(ydl, info)
            final_ext = final_path.suffix.lstrip(".") or str(info.get("ext") or "mp4")
            branded_name = _build_branded_filename(info, final_ext)
            branded_path = DOWNLOAD_DIR / branded_name
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
        raise HTTPException(status_code=400, detail=f"Download failed: {exc}") from exc


def youtube_search(query: str, limit: int = 10) -> YoutubeSearchResponse:
    safe_limit = max(1, min(limit, 20))
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            data = ydl.extract_info(f"ytsearch{safe_limit}:{query}", download=False)
        entries = data.get("entries", []) if isinstance(data, dict) else []
        items: list[YoutubeSearchItem] = []
        for entry in entries:
            if not entry:
                continue
            video_id = str(entry.get("id") or "")
            url = entry.get("webpage_url") or (f"https://www.youtube.com/watch?v={video_id}" if video_id else "")
            if not url:
                continue
            items.append(
                YoutubeSearchItem(
                    id=video_id,
                    title=str(entry.get("title") or "Sem titulo"),
                    channel=entry.get("channel") or entry.get("uploader"),
                    duration=entry.get("duration"),
                    webpage_url=url,
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
