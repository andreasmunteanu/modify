"""
Spotify Downloader — Entry Point
Launches the CustomTkinter GUI application.
"""

import customtkinter as ctk
from app.gui import SpotifyDownloaderApp


def main():
    # Set global appearance
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    app = SpotifyDownloaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
