"""
Spotify download engine — wraps spotdl to handle downloading
with progress callbacks and error handling.
"""

import os
import subprocess
import sys
import threading
import re
from pathlib import Path
from typing import Callable, Optional


class DownloadProgress:
    """Tracks download progress for a single download job."""

    def __init__(self):
        self.status = "idle"  # idle, fetching, downloading, converting, done, error
        self.progress = 0.0  # 0.0 to 1.0
        self.current_song = ""
        self.total_songs = 0
        self.completed_songs = 0
        self.error_message = ""
        self.output_lines = []


class SpotifyDownloader:
    """
    Downloads Spotify content using spotdl CLI.
    Parses stdout/stderr for real-time progress updates.
    """

    def __init__(self, output_dir: str, audio_format: str = "mp3"):
        self.output_dir = output_dir
        self.audio_format = audio_format
        self._process: Optional[subprocess.Popen] = None
        self._cancel_flag = False

    def download(
        self,
        url: str,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
        on_complete: Optional[Callable[[bool, str], None]] = None,
    ):
        """
        Start a download in a background thread.

        Args:
            url: Spotify URL (track, album, or playlist)
            on_progress: Callback fired with DownloadProgress updates
            on_complete: Callback fired when done — (success: bool, message: str)
        """
        self._cancel_flag = False
        thread = threading.Thread(
            target=self._download_worker,
            args=(url, on_progress, on_complete),
            daemon=True,
        )
        thread.start()

    def cancel(self):
        """Cancel an in-progress download."""
        self._cancel_flag = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def _download_worker(
        self,
        url: str,
        on_progress: Optional[Callable[[DownloadProgress], None]],
        on_complete: Optional[Callable[[bool, str], None]],
    ):
        """Worker thread that runs the spotdl subprocess."""
        progress = DownloadProgress()
        progress.status = "fetching"
        progress.progress = 0.05
        if on_progress:
            on_progress(progress)

        # Build the spotdl command
        cmd = [
            sys.executable, "-m", "spotdl",
            "download", url,
            "--output", self.output_dir,
            "--format", self.audio_format,
            "--threads", "4",
        ]

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=self.output_dir,
            )

            progress.status = "downloading"
            if on_progress:
                on_progress(progress)

            # Parse output line by line for progress
            song_count = 0
            found_count = 0

            for line in iter(self._process.stdout.readline, ""):
                if self._cancel_flag:
                    self._process.terminate()
                    progress.status = "error"
                    progress.error_message = "Download cancelled by user"
                    if on_progress:
                        on_progress(progress)
                    if on_complete:
                        on_complete(False, "Cancelled")
                    return

                line = line.strip()
                if not line:
                    continue

                progress.output_lines.append(line)

                # Parse spotdl output for progress information
                # "Found X songs in ..."
                found_match = re.search(r"Found (\d+) song", line)
                if found_match:
                    found_count = int(found_match.group(1))
                    progress.total_songs = found_count
                    progress.progress = 0.1

                # "Downloading ... | ... "
                if "Downloading" in line or "Downloaded" in line:
                    song_count += 1
                    progress.completed_songs = song_count
                    progress.current_song = line
                    if found_count > 0:
                        progress.progress = 0.1 + 0.85 * (song_count / found_count)
                    else:
                        progress.progress = min(0.1 + 0.15 * song_count, 0.95)
                    progress.status = "downloading"

                # "Skipping ... (already downloaded)"
                if "Skipping" in line or "already exists" in line.lower():
                    song_count += 1
                    progress.completed_songs = song_count
                    if found_count > 0:
                        progress.progress = 0.1 + 0.85 * (song_count / found_count)

                if on_progress:
                    on_progress(progress)

            self._process.wait()
            exit_code = self._process.returncode

            if exit_code == 0:
                progress.status = "done"
                progress.progress = 1.0
                if on_progress:
                    on_progress(progress)
                if on_complete:
                    songs_text = f"{progress.completed_songs} song(s)" if progress.completed_songs > 0 else "song(s)"
                    on_complete(True, f"Successfully downloaded {songs_text}!")
            else:
                # Collect error output
                error_text = "\n".join(progress.output_lines[-5:]) if progress.output_lines else "Unknown error"
                progress.status = "error"
                progress.error_message = error_text
                if on_progress:
                    on_progress(progress)
                if on_complete:
                    on_complete(False, f"Download failed: {error_text}")

        except FileNotFoundError:
            progress.status = "error"
            progress.error_message = (
                "spotdl is not installed. Install it with: pip install spotdl"
            )
            if on_progress:
                on_progress(progress)
            if on_complete:
                on_complete(False, progress.error_message)

        except Exception as e:
            progress.status = "error"
            progress.error_message = str(e)
            if on_progress:
                on_progress(progress)
            if on_complete:
                on_complete(False, f"Error: {e}")

        finally:
            self._process = None
