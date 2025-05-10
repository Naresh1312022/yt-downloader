import yt_dlp
import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, validator
from urllib.parse import urlparse, parse_qs
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse

app = FastAPI()

# Ensure 'downloads' folder exists
os.makedirs('downloads', exist_ok=True)

# Helper function to clean URL
def sanitize_youtube_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        
        if not parsed.scheme:
            url = 'https://' + url
            parsed = urlparse(url)

        if "youtu.be" in parsed.netloc:
            video_id = parsed.path.strip("/")
            if not video_id:
                raise ValueError("No video ID found in URL")
            return f"https://www.youtube.com/watch?v={video_id}"

        elif "youtube.com" in parsed.netloc:
            qs = parse_qs(parsed.query)
            video_id = qs.get("v", [None])[0]
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"

        raise ValueError("Could not extract video ID from URL")
    except Exception as e:
        raise ValueError(f"URL processing error: {str(e)}")

# Data Model
class VideoRequest(BaseModel):
    url: str

    @validator('url')
    def check_valid_youtube_url(cls, v):
        if not v.startswith("https://www.youtube.com") and not v.startswith("https://youtu.be"):
            raise ValueError("Please enter a valid YouTube URL")
        return v

# Serve homepage
@app.get("/", response_class=HTMLResponse)
def serve_homepage():
    try:
        with open("static/index.html", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Homepage not found")


# Mount static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Download Endpoint
@app.post("/download")
def download_video(video: VideoRequest, background: BackgroundTasks):
    try:
        print(f"Received URL: {video.url}")
        
        clean_url = sanitize_youtube_url(video.url)
        print(f"Sanitized URL: {clean_url}")
        
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'socket_timeout': 30,
            'retries': 10,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(clean_url, download=True)
            filename = ydl.prepare_filename(info_dict)

        if not os.path.exists(filename):
            raise HTTPException(status_code=500, detail="Download failed.")

        # Schedule file deletion after serving
        background.add_task(os.remove, filename)

        return FileResponse(path=filename, filename=os.path.basename(filename), media_type="video/mp4")

    except ValueError as e:
        print(f"Validation Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
