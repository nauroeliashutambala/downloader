from pathlib import Path
from typing import Any
import os

from fastapi import FastAPI, HTTPException
from fastapi import Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl
import yt_dlp


BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads")))
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Video Downloader API", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class DownloadRequest(BaseModel):
    url: HttpUrl


class DownloadResponse(BaseModel):
    status: str
    url: str
    title: str | None
    filename: str
    filepath: str
    extractor: str | None
    duration: float | None


def download_video(url: str) -> dict[str, Any]:
    options = {
        "outtmpl": str(DOWNLOAD_DIR / "%(title).150B-%(id)s.%(ext)s"),
        "noplaylist": True,
        "restrictfilenames": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            final_path = Path(ydl.prepare_filename(info))

            if not final_path.exists():
                # Fallback: find probable file by id prefix.
                video_id = info.get("id", "")
                matches = list(DOWNLOAD_DIR.glob(f"*-{video_id}.*")) if video_id else []
                if matches:
                    final_path = matches[0]

            if not final_path.exists():
                raise FileNotFoundError("Downloaded file not found on disk.")

            return {
                "status": "success",
                "url": url,
                "title": info.get("title"),
                "filename": final_path.name,
                "filepath": str(final_path),
                "extractor": info.get("extractor"),
                "duration": info.get("duration"),
            }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Download failed: {exc}") from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/download", response_model=DownloadResponse)
def download(request: DownloadRequest) -> DownloadResponse:
    data = download_video(str(request.url))
    return DownloadResponse(**data)


@app.get("/files/{filename}")
def get_file(filename: str):
    target = (DOWNLOAD_DIR / filename).resolve()
    if DOWNLOAD_DIR.resolve() not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(path=target, filename=target.name, media_type="application/octet-stream")
