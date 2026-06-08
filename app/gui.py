"""
Spotify Downloader — Modern Dark-Themed GUI
Built with CustomTkinter for a premium look and feel.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from app.downloader import SpotifyDownloader, DownloadProgress
from app.utils import validate_spotify_url, get_default_download_path, get_type_emoji


# ──────────────────────────────────────────────
# Color Palette — Spotify-inspired dark theme
# ──────────────────────────────────────────────
COLORS = {
    "bg_dark": "#0a0a0f",
    "bg_card": "#12121a",
    "bg_card_hover": "#1a1a25",
    "bg_input": "#1e1e2e",
    "bg_input_focus": "#252538",
    "accent": "#1DB954",         # Spotify green
    "accent_hover": "#1ed760",
    "accent_dim": "#158a3e",
    "accent_glow": "#0f3a1f",
    "text_primary": "#f0f0f5",
    "text_secondary": "#8888a0",
    "text_muted": "#555570",
    "error": "#ff4466",
    "error_dim": "#3d1520",
    "warning": "#ffaa33",
    "success": "#1DB954",
    "border": "#2a2a3a",
    "border_focus": "#1DB954",
    "progress_bg": "#1a1a2a",
    "progress_fill": "#1DB954",
    "scrollbar": "#333345",
}

FONTS = {
    "title": ("Segoe UI", 28, "bold"),
    "subtitle": ("Segoe UI", 13),
    "body": ("Segoe UI", 12),
    "body_bold": ("Segoe UI", 12, "bold"),
    "small": ("Segoe UI", 10),
    "tiny": ("Segoe UI", 9),
    "mono": ("Cascadia Code", 11),
    "input": ("Segoe UI", 13),
    "button": ("Segoe UI", 13, "bold"),
    "icon": ("Segoe UI", 18),
}


class AnimatedProgressBar(ctk.CTkFrame):
    """Custom animated progress bar with glow effect."""

    def __init__(self, master, **kwargs):
        super().__init__(master, height=8, fg_color=COLORS["progress_bg"],
                         corner_radius=4, **kwargs)
        self._progress = 0.0
        self._target_progress = 0.0
        self._animating = False

        self.fill = ctk.CTkFrame(
            self, height=8, fg_color=COLORS["progress_fill"],
            corner_radius=4, width=0
        )
        self.fill.place(x=0, y=0, relheight=1.0)

        # Glow overlay
        self.glow = ctk.CTkFrame(
            self, height=8, fg_color=COLORS["accent_hover"],
            corner_radius=4, width=0
        )
        self.glow.place(x=0, y=0, relheight=1.0)

    def set_progress(self, value: float, animate: bool = True):
        """Set progress from 0.0 to 1.0."""
        self._target_progress = max(0.0, min(1.0, value))
        if animate and not self._animating:
            self._animate()
        elif not animate:
            self._progress = self._target_progress
            self._update_visual()

    def _animate(self):
        """Smoothly animate towards target progress."""
        self._animating = True
        diff = self._target_progress - self._progress
        if abs(diff) < 0.002:
            self._progress = self._target_progress
            self._update_visual()
            self._animating = False
            return

        # Ease towards target
        self._progress += diff * 0.15
        self._update_visual()
        self.after(16, self._animate)  # ~60fps

    def _update_visual(self):
        """Update the visual width of the progress bar."""
        try:
            total_width = self.winfo_width()
            if total_width <= 1:
                total_width = 500  # fallback
            fill_width = max(0, int(total_width * self._progress))
            glow_width = max(0, int(total_width * self._progress * 0.98))
            self.fill.configure(width=fill_width)
            self.glow.configure(width=glow_width)
        except Exception:
            pass

    def reset(self):
        """Reset the progress bar."""
        self._progress = 0.0
        self._target_progress = 0.0
        self._update_visual()


class HistoryItem(ctk.CTkFrame):
    """A single item in the download history list."""

    def __init__(self, master, title: str, subtitle: str, status: str = "done", **kwargs):
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=10,
                         height=56, **kwargs)

        self.grid_columnconfigure(1, weight=1)

        # Status indicator dot
        dot_color = COLORS["success"] if status == "done" else COLORS["error"]
        self.dot = ctk.CTkFrame(self, width=8, height=8, corner_radius=4,
                                fg_color=dot_color)
        self.dot.grid(row=0, column=0, rowspan=2, padx=(16, 10), pady=12)

        # Title
        self.title_label = ctk.CTkLabel(
            self, text=title, font=FONTS["body_bold"],
            text_color=COLORS["text_primary"], anchor="w"
        )
        self.title_label.grid(row=0, column=1, sticky="sw", padx=(0, 16), pady=(10, 0))

        # Subtitle
        self.sub_label = ctk.CTkLabel(
            self, text=subtitle, font=FONTS["tiny"],
            text_color=COLORS["text_muted"], anchor="w"
        )
        self.sub_label.grid(row=1, column=1, sticky="nw", padx=(0, 16), pady=(0, 10))


class SpotifyDownloaderApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # ── Window Setup ──────────────────────────
        self.title("Spotify Downloader")
        self.geometry("680x820")
        self.minsize(580, 700)
        self.configure(fg_color=COLORS["bg_dark"])

        # Center on screen
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - 680) // 2
        y = (screen_h - 820) // 2
        self.geometry(f"680x820+{x}+{y}")

        # State
        self.download_dir = get_default_download_path()
        self.downloader: Optional[SpotifyDownloader] = None
        self.is_downloading = False
        self.history_items: list = []

        # Build UI
        self._build_ui()

    def _build_ui(self):
        """Construct the entire UI."""
        # Main scrollable container
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=24, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)

        row = 0

        # ── Header ──────────────────────────────
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame, text="🎵  Spotify Downloader",
            font=FONTS["title"], text_color=COLORS["text_primary"], anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w")

        subtitle = ctk.CTkLabel(
            header_frame,
            text="Download tracks, albums & playlists from Spotify",
            font=FONTS["subtitle"], text_color=COLORS["text_secondary"], anchor="w"
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

        row += 1

        # ── Divider ───────────────────────────────
        divider = ctk.CTkFrame(self.main_frame, height=1, fg_color=COLORS["border"])
        divider.grid(row=row, column=0, sticky="ew", pady=(16, 20))
        row += 1

        # ── URL Input Card ───────────────────────
        url_card = ctk.CTkFrame(self.main_frame, fg_color=COLORS["bg_card"],
                                corner_radius=16, border_width=1,
                                border_color=COLORS["border"])
        url_card.grid(row=row, column=0, sticky="ew", pady=(0, 16))
        url_card.grid_columnconfigure(0, weight=1)
        row += 1

        url_label = ctk.CTkLabel(
            url_card, text="Spotify URL", font=FONTS["body_bold"],
            text_color=COLORS["text_primary"], anchor="w"
        )
        url_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 6))

        url_hint = ctk.CTkLabel(
            url_card,
            text="Paste a track, album, or playlist link",
            font=FONTS["small"], text_color=COLORS["text_muted"], anchor="w"
        )
        url_hint.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        # URL input with paste button
        url_input_frame = ctk.CTkFrame(url_card, fg_color="transparent")
        url_input_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        url_input_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            url_input_frame, placeholder_text="https://open.spotify.com/track/...",
            font=FONTS["input"], height=48, corner_radius=12,
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            border_width=1, text_color=COLORS["text_primary"],
            placeholder_text_color=COLORS["text_muted"]
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.url_entry.bind("<Return>", lambda e: self._start_download())
        self.url_entry.bind("<KeyRelease>", self._on_url_change)

        paste_btn = ctk.CTkButton(
            url_input_frame, text="📋", width=48, height=48,
            corner_radius=12, font=FONTS["icon"],
            fg_color=COLORS["bg_input"], hover_color=COLORS["bg_input_focus"],
            border_width=1, border_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            command=self._paste_url
        )
        paste_btn.grid(row=0, column=1)

        # URL validation feedback
        self.url_feedback = ctk.CTkLabel(
            url_card, text="", font=FONTS["small"],
            text_color=COLORS["text_muted"], anchor="w"
        )
        self.url_feedback.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 12))
        self.url_feedback.grid_remove()  # Hidden by default

        # ── Settings Card ────────────────────────
        settings_card = ctk.CTkFrame(self.main_frame, fg_color=COLORS["bg_card"],
                                     corner_radius=16, border_width=1,
                                     border_color=COLORS["border"])
        settings_card.grid(row=row, column=0, sticky="ew", pady=(0, 16))
        settings_card.grid_columnconfigure(1, weight=1)
        row += 1

        # Format selector
        format_label = ctk.CTkLabel(
            settings_card, text="Format", font=FONTS["body_bold"],
            text_color=COLORS["text_primary"], anchor="w"
        )
        format_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        self.format_var = ctk.StringVar(value="mp3")
        self.format_menu = ctk.CTkSegmentedButton(
            settings_card, values=["mp3", "flac", "wav", "ogg"],
            variable=self.format_var, font=FONTS["body"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["bg_input"],
            unselected_hover_color=COLORS["bg_input_focus"],
            text_color=COLORS["text_primary"],
            text_color_disabled=COLORS["text_muted"],
            corner_radius=10, height=36,
        )
        self.format_menu.grid(row=0, column=1, sticky="e", padx=20, pady=(20, 10))

        # Output folder
        folder_label = ctk.CTkLabel(
            settings_card, text="Save to", font=FONTS["body_bold"],
            text_color=COLORS["text_primary"], anchor="w"
        )
        folder_label.grid(row=1, column=0, sticky="w", padx=20, pady=(10, 20))

        folder_frame = ctk.CTkFrame(settings_card, fg_color="transparent")
        folder_frame.grid(row=1, column=1, sticky="ew", padx=20, pady=(10, 20))
        folder_frame.grid_columnconfigure(0, weight=1)

        self.folder_label = ctk.CTkLabel(
            folder_frame, text=self._shorten_path(self.download_dir),
            font=FONTS["small"], text_color=COLORS["text_secondary"],
            anchor="e"
        )
        self.folder_label.grid(row=0, column=0, sticky="e", padx=(0, 10))

        browse_btn = ctk.CTkButton(
            folder_frame, text="Browse", width=80, height=32,
            corner_radius=8, font=FONTS["small"],
            fg_color=COLORS["bg_input"], hover_color=COLORS["bg_input_focus"],
            border_width=1, border_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            command=self._browse_folder
        )
        browse_btn.grid(row=0, column=1)

        # ── Download Button ──────────────────────
        self.download_btn = ctk.CTkButton(
            self.main_frame, text="⬇  Download", font=FONTS["button"],
            height=56, corner_radius=14,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#000000",
            command=self._start_download
        )
        self.download_btn.grid(row=row, column=0, sticky="ew", pady=(0, 16))
        row += 1

        # ── Progress Section ─────────────────────
        self.progress_card = ctk.CTkFrame(
            self.main_frame, fg_color=COLORS["bg_card"],
            corner_radius=16, border_width=1, border_color=COLORS["border"]
        )
        self.progress_card.grid(row=row, column=0, sticky="ew", pady=(0, 16))
        self.progress_card.grid_columnconfigure(0, weight=1)
        self.progress_card.grid_remove()  # Hidden until download starts
        row += 1

        self.status_label = ctk.CTkLabel(
            self.progress_card, text="Preparing...",
            font=FONTS["body_bold"], text_color=COLORS["text_primary"], anchor="w"
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        self.progress_bar = AnimatedProgressBar(self.progress_card)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))

        self.progress_pct = ctk.CTkLabel(
            self.progress_card, text="0%",
            font=FONTS["small"], text_color=COLORS["accent"], anchor="e"
        )
        self.progress_pct.grid(row=2, column=0, sticky="e", padx=20, pady=(0, 6))

        self.progress_detail = ctk.CTkLabel(
            self.progress_card, text="",
            font=FONTS["tiny"], text_color=COLORS["text_muted"], anchor="w",
            wraplength=580
        )
        self.progress_detail.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 16))

        # Cancel button (inside progress card)
        self.cancel_btn = ctk.CTkButton(
            self.progress_card, text="Cancel", width=100, height=32,
            corner_radius=8, font=FONTS["small"],
            fg_color=COLORS["error_dim"], hover_color=COLORS["error"],
            text_color=COLORS["text_primary"], border_width=1,
            border_color=COLORS["error"],
            command=self._cancel_download
        )
        self.cancel_btn.grid(row=4, column=0, sticky="e", padx=20, pady=(0, 16))

        # ── History Section ──────────────────────
        history_header = ctk.CTkLabel(
            self.main_frame, text="Download History",
            font=FONTS["body_bold"], text_color=COLORS["text_secondary"], anchor="w"
        )
        history_header.grid(row=row, column=0, sticky="w", pady=(8, 8))
        row += 1

        self.history_frame = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="transparent",
            height=200, corner_radius=0,
            scrollbar_button_color=COLORS["scrollbar"],
            scrollbar_button_hover_color=COLORS["text_muted"]
        )
        self.history_frame.grid(row=row, column=0, sticky="nsew", pady=(0, 8))
        self.history_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(row, weight=1)
        row += 1

        # Empty state
        self.empty_label = ctk.CTkLabel(
            self.history_frame,
            text="No downloads yet.\nPaste a Spotify link above to get started!",
            font=FONTS["small"], text_color=COLORS["text_muted"],
            justify="center"
        )
        self.empty_label.grid(row=0, column=0, pady=40)

        # ── Footer ───────────────────────────────
        footer = ctk.CTkLabel(
            self.main_frame,
            text="Powered by spotdl  •  Audio sourced from YouTube",
            font=FONTS["tiny"], text_color=COLORS["text_muted"]
        )
        footer.grid(row=row, column=0, pady=(4, 0))

    # ──────────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────────

    def _paste_url(self):
        """Paste URL from clipboard."""
        try:
            clipboard = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, clipboard.strip())
            self._on_url_change(None)
        except Exception:
            pass

    def _on_url_change(self, event):
        """Validate URL as user types."""
        url = self.url_entry.get().strip()
        if not url:
            self.url_feedback.grid_remove()
            return

        result = validate_spotify_url(url)
        self.url_feedback.grid()

        if result["valid"]:
            emoji = get_type_emoji(result["type"])
            self.url_feedback.configure(
                text=f"{emoji}  Detected: Spotify {result['type'].capitalize()}",
                text_color=COLORS["accent"]
            )
        else:
            self.url_feedback.configure(
                text=f"⚠  {result['error']}",
                text_color=COLORS["warning"]
            )

    def _browse_folder(self):
        """Open folder picker dialog."""
        folder = filedialog.askdirectory(
            title="Choose Download Folder",
            initialdir=self.download_dir
        )
        if folder:
            self.download_dir = folder
            self.folder_label.configure(text=self._shorten_path(folder))

    def _shorten_path(self, path: str, max_len: int = 40) -> str:
        """Shorten a path for display."""
        if len(path) <= max_len:
            return path
        parts = path.split(os.sep)
        if len(parts) <= 3:
            return path
        return os.sep.join(parts[:2]) + os.sep + "..." + os.sep + os.sep.join(parts[-2:])

    def _start_download(self):
        """Validate and start the download."""
        url = self.url_entry.get().strip()
        result = validate_spotify_url(url)

        if not result["valid"]:
            self.url_feedback.grid()
            self.url_feedback.configure(
                text=f"⚠  {result['error']}",
                text_color=COLORS["error"]
            )
            return

        # Show progress UI
        self.is_downloading = True
        self.progress_card.grid()
        self.progress_bar.reset()
        self.status_label.configure(text="🔍  Fetching song info...",
                                    text_color=COLORS["text_primary"])
        self.progress_pct.configure(text="0%")
        self.progress_detail.configure(text="Connecting to Spotify...")
        self.download_btn.configure(state="disabled", text="Downloading...",
                                    fg_color=COLORS["accent_dim"])

        # Create downloader and start
        audio_format = self.format_var.get()
        self.downloader = SpotifyDownloader(self.download_dir, audio_format)
        self.downloader.download(
            url=url,
            on_progress=self._on_progress,
            on_complete=self._on_complete,
        )

    def _on_progress(self, progress: DownloadProgress):
        """Handle progress updates from the download thread (thread-safe)."""
        self.after(0, self._update_progress_ui, progress)

    def _update_progress_ui(self, progress: DownloadProgress):
        """Update UI with progress info (runs on main thread)."""
        try:
            pct = int(progress.progress * 100)
            self.progress_pct.configure(text=f"{pct}%")
            self.progress_bar.set_progress(progress.progress)

            status_map = {
                "fetching": "🔍  Fetching song info...",
                "downloading": f"⬇  Downloading... ({progress.completed_songs}/{progress.total_songs or '?'})",
                "converting": "🔄  Converting audio...",
                "done": "✅  Download complete!",
                "error": "❌  Download failed",
            }
            status_text = status_map.get(progress.status, progress.status)
            self.status_label.configure(text=status_text)

            if progress.status == "error":
                self.status_label.configure(text_color=COLORS["error"])
            elif progress.status == "done":
                self.status_label.configure(text_color=COLORS["success"])

            # Show latest output line
            if progress.output_lines:
                last_line = progress.output_lines[-1]
                if len(last_line) > 80:
                    last_line = last_line[:77] + "..."
                self.progress_detail.configure(text=last_line)
        except Exception:
            pass

    def _on_complete(self, success: bool, message: str):
        """Handle download completion (thread-safe)."""
        self.after(0, self._on_complete_ui, success, message)

    def _on_complete_ui(self, success: bool, message: str):
        """Update UI after download completes (runs on main thread)."""
        self.is_downloading = False
        self.download_btn.configure(state="normal", text="⬇  Download",
                                    fg_color=COLORS["accent"])

        if success:
            self.status_label.configure(text=f"✅  {message}",
                                        text_color=COLORS["success"])
            self.progress_bar.set_progress(1.0)
            self.progress_pct.configure(text="100%")

            # Add to history
            url = self.url_entry.get().strip()
            result = validate_spotify_url(url)
            type_str = result.get("type", "track") or "track"
            timestamp = datetime.now().strftime("%I:%M %p")
            self._add_history_item(
                title=f"{get_type_emoji(type_str)}  Spotify {type_str.capitalize()}",
                subtitle=f"Downloaded to {self._shorten_path(self.download_dir, 50)} • {timestamp}",
                status="done"
            )

            # Clear the URL input
            self.url_entry.delete(0, "end")
            self.url_feedback.grid_remove()
        else:
            self.status_label.configure(text=f"❌  {message}",
                                        text_color=COLORS["error"])
            self._add_history_item(
                title=f"❌  Download Failed",
                subtitle=message[:80],
                status="error"
            )

        # Auto-clear the progress card after 3 seconds
        self.after(3000, self._clear_progress)

    def _clear_progress(self):
        """Hide the progress card and reset it for the next download."""
        if not self.is_downloading:
            self.progress_card.grid_remove()
            self.progress_bar.reset()
            self.progress_pct.configure(text="0%")
            self.status_label.configure(text="Preparing...",
                                        text_color=COLORS["text_primary"])
            self.progress_detail.configure(text="")

    def _cancel_download(self):
        """Cancel the current download."""
        if self.downloader:
            self.downloader.cancel()
        self.is_downloading = False
        self.download_btn.configure(state="normal", text="⬇  Download",
                                    fg_color=COLORS["accent"])
        self.status_label.configure(text="⛔  Cancelled",
                                    text_color=COLORS["warning"])

    def _add_history_item(self, title: str, subtitle: str, status: str):
        """Add an item to the download history."""
        # Remove empty state label
        if self.empty_label.winfo_exists():
            self.empty_label.grid_remove()

        item = HistoryItem(self.history_frame, title=title, subtitle=subtitle,
                           status=status)
        item.grid(row=len(self.history_items), column=0, sticky="ew", pady=(0, 8))
        self.history_items.append(item)
