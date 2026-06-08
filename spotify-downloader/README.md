# 🎵 Spotify Downloader

A modern, dark-themed desktop app that downloads Spotify songs, albums, and playlists as MP3/FLAC/WAV/OGG files.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- 🎨 **Dark Spotify-themed UI** — Premium look with smooth animations
- 📥 **Download tracks, albums & playlists** — Paste any Spotify link
- 🎛️ **Multiple formats** — MP3, FLAC, WAV, OGG
- 📊 **Real-time progress** — Animated progress bar with status updates
- 📋 **Download history** — Track all your downloads
- 📁 **Custom save location** — Choose your output folder
- 🏗️ **Builds to .exe** — Standalone Windows executable via GitHub Actions

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install FFmpeg (required for audio conversion)

```bash
# macOS
brew install ffmpeg

# Windows
choco install ffmpeg

# Or let spotdl handle it:
python -m spotdl --download-ffmpeg
```

### 3. Run the app

```bash
python main.py
```

### 4. Use it

1. Copy a Spotify link (track, album, or playlist)
2. Paste it into the URL field
3. Choose your format (MP3, FLAC, WAV, OGG)
4. Click **Download**
5. Find your files in the Downloads folder!

## Building the .exe

### Option A: GitHub Actions (Recommended)

1. Push this project to a GitHub repository
2. The workflow at `.github/workflows/build.yml` will automatically build the `.exe`
3. Download the artifact from the Actions tab

### Option B: Build locally on Windows

```bash
pip install -r requirements.txt
pyinstaller build.spec
```

The executable will be in `dist/SpotifyDownloader/`.

## How It Works

This app uses [spotdl](https://github.com/spotDL/spotify-downloader) under the hood:

1. **Fetches metadata** from Spotify (title, artist, album art)
2. **Matches audio** from YouTube using the song metadata
3. **Downloads & converts** to your chosen format
4. **Embeds metadata** (ID3 tags + album artwork) into the file

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| GUI | CustomTkinter |
| Audio Engine | spotdl + yt-dlp |
| Packaging | PyInstaller |
| CI/CD | GitHub Actions |

## License

MIT License — Use freely, give credit if you share.
