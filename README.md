# bluecat's YouTube Transcript Search

A cross-platform desktop application built with Python and PySide6 that searches, extracts, and downloads transcripts and metadata from YouTube channels and playlists. It is designed to be fully portable across Windows, macOS, and Linux by bundling all necessary runtime dependencies, even embedding a small Javascript engine.

## Features

- **Multi-Source Support:** Search and extract content from arbitrary playlists or channels.
- **Tab-Specific Extraction:** Target specific channel tabs, with support for Videos, Live, and Shorts.
- **Export as a CSV:** Download lists of searches as a CSV, for use in other applications or for saving.
- **Date Filtering:** Filter and organize searches by date.
- **Cross-Platform Portability:** Distributed as a standalone application containing the QuickJS runtime and dynamic OS-specific architecture routing.

## Libraries Used/Dependencies

- **PySide6:** Cross-platform graphical user interface.
- **yt-dlp:** Core scraping and extraction engine.
- **QuickJS:** Lightweight JavaScript engine used by `yt-dlp` to solve YouTube's client-side JavaScript challenges.
- **SQLite3:** Local database management for transcript caching and querying.
- A working web browser that you use YouTube with (for cookies)
- SQLite3 FTS5 extension
    - Windows and MacOS should have it, but some minimal Linux distros may not.

> [!NOTE]
> The QuickJS versions in this repository use Fabrice Bellard's original QuickJS binary for Linux x86_64 and Windows x86_64. The other platforms use QuickJS-NG instead.
> 
> If this is bothersome, you can build the QuickJS binary on your own machine.

## Building and Packaging

This project uses PyInstaller by default, but a Nuitka build script exists as well. Run the PyInstaller build script with:

`python3 pyinstaller_build.py`

Or the Nuitka build script with:

`python3 nuitka_build.py`

> [!WARNING]
> You will have to set up the environment and install Nuitka yourself, as Nuitka is not included as a dependency.

This script automatically:

- Formats the application for the host OS.
- Bundles the correct QuickJS executable from the `bin/` directory.
- Copies necessary MIT and LGPLv3 license text files to the distribution directory.
- Sets up the localized `_MEIPASS` hooks for runtime data extraction.

## Licensing

To comply with the PySide6 LGPLv3 license, the application was built with `--onedir` mode rather than `--onefile`. This ensures users can easily replace the shared Qt libraries if they choose.

This project is licensed with the MIT License, placed in LICENSE.txt.

All relevant licenses/copyright notices are placed in the THIRD-PARTY-NOTICES.txt file.
