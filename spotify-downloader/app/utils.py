"""
Utility functions for the Spotify Downloader application.
URL validation, path helpers, and PyInstaller resource resolution.
"""

import os
import re
import sys
from pathlib import Path


# Regex patterns for Spotify URLs
SPOTIFY_TRACK_PATTERN = re.compile(
    r"https?://open\.spotify\.com/track/([a-zA-Z0-9]+)(\?.*)?$"
)
SPOTIFY_ALBUM_PATTERN = re.compile(
    r"https?://open\.spotify\.com/album/([a-zA-Z0-9]+)(\?.*)?$"
)
SPOTIFY_PLAYLIST_PATTERN = re.compile(
    r"https?://open\.spotify\.com/playlist/([a-zA-Z0-9]+)(\?.*)?$"
)
SPOTIFY_ARTIST_PATTERN = re.compile(
    r"https?://open\.spotify\.com/artist/([a-zA-Z0-9]+)(\?.*)?$"
)


def validate_spotify_url(url: str) -> dict:
    """
    Validate a Spotify URL and return its type and ID.

    Returns:
        dict with keys:
            - valid (bool): Whether the URL is a valid Spotify link
            - type (str): 'track', 'album', 'playlist', 'artist', or None
            - id (str): The Spotify resource ID, or None
            - error (str): Error message if invalid, or None
    """
    url = url.strip()

    if not url:
        return {"valid": False, "type": None, "id": None, "error": "URL cannot be empty"}

    patterns = {
        "track": SPOTIFY_TRACK_PATTERN,
        "album": SPOTIFY_ALBUM_PATTERN,
        "playlist": SPOTIFY_PLAYLIST_PATTERN,
        "artist": SPOTIFY_ARTIST_PATTERN,
    }

    for url_type, pattern in patterns.items():
        match = pattern.match(url)
        if match:
            return {
                "valid": True,
                "type": url_type,
                "id": match.group(1),
                "error": None,
            }

    # Check if it's at least a spotify URL but unsupported
    if "spotify.com" in url:
        return {
            "valid": False,
            "type": None,
            "id": None,
            "error": "Unsupported Spotify URL format. Use a track, album, or playlist link.",
        }

    return {
        "valid": False,
        "type": None,
        "id": None,
        "error": "Not a valid Spotify URL. Example: https://open.spotify.com/track/...",
    }


def get_default_download_path() -> str:
    """Get the default Downloads folder path."""
    downloads = str(Path.home() / "Downloads")
    os.makedirs(downloads, exist_ok=True)
    return downloads


def resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, works for dev and for PyInstaller.
    When bundled by PyInstaller, files are extracted to a temp folder (_MEIPASS).
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def format_file_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def get_type_emoji(url_type: str) -> str:
    """Get an emoji/icon for the Spotify content type."""
    return {
        "track": "🎵",
        "album": "💿",
        "playlist": "📋",
        "artist": "🎤",
    }.get(url_type, "🎶")
