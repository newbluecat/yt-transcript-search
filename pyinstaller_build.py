import os
import platform
import sys
from pathlib import Path

import PyInstaller.__main__


def build_app() -> None:
    """Build the application for targeted operating system."""
    is_windows: bool = os.name == "nt"
    exe_name: str = "quickjs.exe" if is_windows else "quickjs"

    if is_windows:
        os_dir: str = "win"
    elif sys.platform == "darwin":
        os_dir = "mac"
    else:
        os_dir = "linux"

    arch: str = platform.machine().lower()

    arch_map: dict[str, str] = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }

    arch_dir: str = arch_map.get(arch, arch)
    bin_path: Path = Path("bin") / os_dir / arch_dir / exe_name

    if not bin_path.exists():
        sys.exit(f"Missing binary: {bin_path}")

    separator: str = ";" if is_windows else ":"
    add_data_arg: str = f"{bin_path}{separator}."

    pyinstaller_args: list[str] = [
        "src/yt_transcript_search/main.py",
        "--noconsole",
        "--onedir",
        f"--add-data={add_data_arg}",
        f"--add-data=LICENSE.txt{separator}.",
        f"--add-data=THIRD-PARTY-NOTICES.txt{separator}.",
        "--copy-metadata=PySide6",
        "--copy-metadata=yt_dlp",
        "--copy-metadata=requests",
        "--collect-data=yt_dlp",
        "--collect-data=yt_dlp_ejs",
        "--exclude-module=tkinter",
        "--exclude-module=unittest",
        "--exclude-module=PySide6.QtWebEngineCore",
        "--exclude-module=PySide6.QtWebEngineWidgets",
        "--exclude-module=PySide6.QtNetwork",
        "--exclude-module=PySide6.QtQml",
    ]

    PyInstaller.__main__.run(pyinstaller_args)


if __name__ == "__main__":
    build_app()
