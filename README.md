# YouTube Transcript Search

> [!WARNING] This project is currently incomplete! Do not try to build it.

A cross-platform desktop application built with Python and PySide6 that searches, extracts, and downloads transcripts and metadata from YouTube channels, playlists, and individual videos. It is designed to be fully portable across Windows, macOS, and Linux by bundling all necessary runtime dependencies, including a localized JavaScript engine.

## Features

- **Multi-Source Support:** Search and extract content using exact Channel IDs, Playlist IDs, or handles (`@handle`).
- **Tab-Specific Extraction:** Target specific channel tabs, separating standard uploads from Live Streams and Shorts.
- **Efficient Metadata Scraping:** Uses flat extraction with approximate date parsing to rapidly fetch metadata without downloading full video pages or triggering API rate limits.
- **Age-Restricted Content Bypass:** Supports local browser cookie injection to authenticate and fetch metadata for 18+ restricted videos.
- **Cross-Platform Portability:** Distributed as a standalone application containing the QuickJS runtime and dynamic OS-specific architecture routing.

## Libraries Used

- **PySide6:** Cross-platform graphical user interface.
- **yt-dlp:** Core scraping and extraction engine.
- **youtube_transcript_api:** Fetching and parsing video transcripts.
- **QuickJS:** Lightweight JavaScript engine used by `yt-dlp` to solve YouTube's client-side JavaScript challenges without requiring heavy external runtimes like Node.js or Deno.
- **SQLite3:** Local database management for transcript caching and querying.

## Building and Packaging

This project uses PyInstaller for packaging. To comply with the PySide6 LGPLv3 license, the application must be built using `--onedir` mode rather than `--onefile`. This ensures users can replace the shared Qt libraries if they choose.

Run the build script:

`python build.py`

This script automatically:

- Formats the application for the host OS.
- Bundles the correct QuickJS executable from the `bin/` directory.
- Copies necessary MIT and LGPLv3 license text files to the distribution directory.
- Sets up the localized `_MEIPASS` hooks for runtime data extraction.
