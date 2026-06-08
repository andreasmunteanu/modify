"""
Spotify & YouTube Downloader — Web App Backend
Flask server that handles music downloads via spotdl + yt-dlp.
Serves the PWA frontend.
"""

import os
import sys
import uuid
import shutil
import subprocess
import tempfile
import re
import glob
import threading
import time
import json
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory

app = Flask(__name__)

# ── Job Storage ──────────────────────────────────
jobs = {}
CLEANUP_AFTER_SECONDS = 600  # 10 minutes


# ── URL Validation ───────────────────────────────

def detect_url_type(url: str) -> dict:
    """Detect if URL is Spotify or YouTube and extract info."""
    url = url.strip()

    # Spotify patterns
    spotify_patterns = {
        "track": re.compile(r"https?://open\.spotify\.com/track/([a-zA-Z0-9]+)"),
        "album": re.compile(r"https?://open\.spotify\.com/album/([a-zA-Z0-9]+)"),
        "playlist": re.compile(r"https?://open\.spotify\.com/playlist/([a-zA-Z0-9]+)"),
    }
    for stype, pattern in spotify_patterns.items():
        match = pattern.match(url)
        if match:
            return {"valid": True, "source": "spotify", "type": stype, "id": match.group(1)}

    # YouTube patterns
    yt_patterns = [
        re.compile(r"https?://(www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)"),
        re.compile(r"https?://youtu\.be/([a-zA-Z0-9_-]+)"),
        re.compile(r"https?://music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)"),
        re.compile(r"https?://(www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)"),
    ]
    for pattern in yt_patterns:
        match = pattern.match(url)
        if match:
            vid = match.group(match.lastindex)
            return {"valid": True, "source": "youtube", "type": "video", "id": vid}

    # YouTube playlist
    yt_playlist = re.compile(r"https?://(www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)")
    match = yt_playlist.match(url)
    if match:
        return {"valid": True, "source": "youtube", "type": "playlist", "id": match.group(2)}

    return {"valid": False, "source": None, "type": None, "id": None}


# ── Download Workers ─────────────────────────────

def spotify_download_worker(job_id: str, url: str, audio_format: str):
    """Download from Spotify using spotdl."""
    job = jobs[job_id]
    temp_dir = job["temp_dir"]

    try:
        job["status"] = "downloading"
        job["message"] = "Fetching from Spotify..."

        cmd = [
            sys.executable, "-m", "spotdl",
            "download", url,
            "--output", temp_dir,
            "--format", audio_format,
            "--threads", "4",
        ]

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=temp_dir
        )

        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            job["log"].append(line)
            if any(kw in line for kw in ["Found", "Downloading", "Downloaded", "Skipping"]):
                job["message"] = line

        process.wait()
        _finalize_job(job_id, process.returncode, audio_format)

    except Exception as e:
        job["status"] = "error"
        job["message"] = str(e)
    finally:
        _schedule_cleanup(job_id)


def youtube_download_worker(job_id: str, url: str, audio_format: str):
    """Download from YouTube using yt-dlp."""
    job = jobs[job_id]
    temp_dir = job["temp_dir"]

    try:
        job["status"] = "downloading"
        job["message"] = "Fetching from YouTube..."

        import yt_dlp

        codec_map = {"mp3": "mp3", "flac": "flac", "wav": "wav", "ogg": "vorbis"}
        preferred_codec = codec_map.get(audio_format, "mp3")

        # Find FFmpeg — spotdl installs it to ~/.spotdl/ffmpeg
        ffmpeg_path = os.path.expanduser("~/.spotdl")
        if not os.path.exists(os.path.join(ffmpeg_path, "ffmpeg")):
            ffmpeg_path = None  # Let yt-dlp find it on PATH

        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": preferred_codec,
                "preferredquality": "192",
            }],
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "writethumbnail": True,
            "retries": 5,
            "fragment_retries": 5,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            },
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            "progress_hooks": [lambda d: _yt_progress(job_id, d)],
        }

        if ffmpeg_path:
            ydl_opts["ffmpeg_location"] = ffmpeg_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                job["metadata"] = {
                    "title": info.get("title", "Unknown"),
                    "artist": info.get("uploader", info.get("channel", "Unknown")),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", ""),
                }

        _finalize_job(job_id, 0, audio_format)

    except Exception as e:
        err_msg = str(e)
        # Make common errors more user-friendly
        if "Broken pipe" in err_msg:
            err_msg = "Download failed — YouTube may be blocking this request. Try again in a moment."
        elif "ffmpeg" in err_msg.lower():
            err_msg = "FFmpeg not found. Run: python3.11 -m spotdl --download-ffmpeg"
        job["status"] = "error"
        job["message"] = err_msg
    finally:
        _schedule_cleanup(job_id)


def _yt_progress(job_id, d):
    """Progress hook for yt-dlp."""
    job = jobs.get(job_id)
    if not job:
        return
    if d["status"] == "downloading":
        pct = d.get("_percent_str", "").strip()
        job["message"] = f"Downloading... {pct}"
    elif d["status"] == "finished":
        job["message"] = "Converting audio..."


def _finalize_job(job_id: str, return_code: int, audio_format: str):
    """Check for downloaded files and update job status."""
    job = jobs[job_id]
    temp_dir = job["temp_dir"]

    if return_code == 0:
        extensions = ["*.mp3", "*.flac", "*.wav", "*.ogg", "*.m4a", "*.opus"]
        files = []
        for ext in extensions:
            files.extend(glob.glob(os.path.join(temp_dir, ext)))

        if files:
            if len(files) == 1:
                job["status"] = "done"
                job["file_path"] = files[0]
                job["file_name"] = os.path.basename(files[0])
                job["message"] = f"Ready: {job['file_name']}"

                # Try to get metadata from spotdl output
                if not job.get("metadata"):
                    name = os.path.splitext(job["file_name"])[0]
                    parts = name.split(" - ", 1)
                    job["metadata"] = {
                        "title": parts[-1] if len(parts) > 1 else name,
                        "artist": parts[0] if len(parts) > 1 else "Unknown Artist",
                        "duration": 0,
                        "thumbnail": "",
                    }
            else:
                # Multiple files — zip them
                import zipfile
                zip_path = os.path.join(temp_dir, "download.zip")
                with zipfile.ZipFile(zip_path, "w") as zf:
                    for f in files:
                        zf.write(f, os.path.basename(f))
                job["status"] = "done"
                job["file_path"] = zip_path
                job["file_name"] = "download.zip"
                job["message"] = f"Ready: {len(files)} songs (zipped)"
                job["metadata"] = {
                    "title": f"{len(files)} Songs",
                    "artist": "Various",
                    "duration": 0,
                    "thumbnail": "",
                }
        else:
            job["status"] = "error"
            job["message"] = "No audio files found after download."
    else:
        job["status"] = "error"
        last_lines = job["log"][-3:] if job["log"] else ["Unknown error"]
        job["message"] = " | ".join(last_lines)


def _schedule_cleanup(job_id: str):
    """Schedule temp file cleanup."""
    def cleanup():
        time.sleep(CLEANUP_AFTER_SECONDS)
        job = jobs.pop(job_id, None)
        if job:
            temp = job.get("temp_dir")
            if temp and os.path.exists(temp):
                shutil.rmtree(temp, ignore_errors=True)
    threading.Thread(target=cleanup, daemon=True).start()


# ── Routes ───────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


@app.route("/api/download", methods=["POST"])
def start_download():
    """Start a download job."""
    data = request.get_json()
    url = data.get("url", "").strip()
    audio_format = data.get("format", "mp3")

    result = detect_url_type(url)
    if not result["valid"]:
        return jsonify({"error": "Invalid URL. Paste a Spotify or YouTube link."}), 400

    if audio_format not in ("mp3", "flac", "wav", "ogg"):
        audio_format = "mp3"

    job_id = str(uuid.uuid4())[:8]
    temp_dir = tempfile.mkdtemp(prefix="music_dl_")

    jobs[job_id] = {
        "status": "queued",
        "message": "Starting...",
        "source": result["source"],
        "type": result["type"],
        "temp_dir": temp_dir,
        "file_path": None,
        "file_name": None,
        "metadata": None,
        "log": [],
        "created_at": time.time(),
    }

    if result["source"] == "spotify":
        worker = spotify_download_worker
    else:
        worker = youtube_download_worker

    threading.Thread(target=worker, args=(job_id, url, audio_format), daemon=True).start()
    return jsonify({"job_id": job_id, "source": result["source"], "type": result["type"]})


@app.route("/api/status/<job_id>")
def get_status(job_id):
    """Check download status."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify({
        "status": job["status"],
        "message": job["message"],
        "file_name": job.get("file_name"),
        "metadata": job.get("metadata"),
        "source": job.get("source"),
    })


@app.route("/api/file/<job_id>")
def get_file(job_id):
    """Download the completed file."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] != "done":
        return jsonify({"error": "Not ready"}), 400
    if not job.get("file_path") or not os.path.exists(job["file_path"]):
        return jsonify({"error": "File not found"}), 404

    return send_file(
        job["file_path"],
        as_attachment=True,
        download_name=job["file_name"]
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
