# YouTube Transcript Search

A cross-platform desktop application built with Python and PySide6 that searches, extracts, and downloads transcripts and metadata from YouTube channels, playlists, and individual videos. It is designed to be fully portable across Windows, macOS, and Linux by bundling all necessary runtime dependencies, including a localized JavaScript engine.

## Features

- **Multi-Source Support:** Search and extract content using exact Channel IDs, Playlist IDs, or handles (`@handle`).
- **Tab-Specific Extraction:** Target specific channel tabs, separating standard uploads from Live Streams and Shorts.
- **Efficient Metadata Scraping:** Uses flat extraction with approximate date parsing to rapidly fetch metadata without downloading full video pages or triggering API rate limits.
- **Cross-Platform Portability:** Distributed as a standalone application containing the QuickJS runtime and dynamic OS-specific architecture routing.

## Libraries Used

- **PySide6:** Cross-platform graphical user interface.
- **yt-dlp:** Core scraping and extraction engine.
- **QuickJS:** Lightweight JavaScript engine used by `yt-dlp` to solve YouTube's client-side JavaScript challenges
- **SQLite3:** Local database management for transcript caching and querying.

> [!NOTE]
> The QuickJS versions in this repository use Fabrice Bellard's original QuickJS binary for Linux x86_86 and Windows x86_86. The other platforms use QuickJS-NG instead.
> 
> If this is bothersome, please build the QuickJS binary on your own machine.

## Building and Packaging

This project uses PyInstaller by default, but a Nuitka build script exists as well.

To comply with the PySide6 LGPLv3 license, the application must be built using `--onedir` mode rather than `--onefile`. This ensures users can replace the shared Qt libraries if they choose.

Run the PyInstaller build script with

`python pyinstaller_build.py`

Or the Nuitka build script with

`python nuitka_build.py`

This script automatically:

- Formats the application for the host OS.
- Bundles the correct QuickJS executable from the `bin/` directory.
- Copies necessary MIT and LGPLv3 license text files to the distribution directory.
- Sets up the localized `_MEIPASS` hooks for runtime data extraction.

## Licensing

This project is licensed with the MIT License, placed in LICENSE.txt.

All relevant licenses/copyright notices are placed in the THIRD-PARTY-NOTICES.txt file.
