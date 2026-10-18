import os
import platform
import subprocess
import sys
from pathlib import Path


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

    nuitka_args: list[str] = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--disable-console",
        "--jobs=1",
        f"--include-data-files={bin_path}={exe_name}",
        "--include-data-files=LICENSE.txt=LICENSE.txt",
        "--include-data-files=THIRD-PARTY-NOTICES.txt=THIRD-PARTY-NOTICES.txt",
        "--enable-plugin=pyside6",
        "--include-package=yt_dlp",
        "--include-package=yt_dlp_ejs",
        "--include-package-data=requests",
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=unittest",
        "--nofollow-import-to=PySide6.QtWebEngineCore",
        "--nofollow-import-to=PySide6.QtWebEngineWidgets",
        "--nofollow-import-to=PySide6.QtNetwork",
        "--nofollow-import-to=PySide6.QtQml",
        "--nofollow-import-to=PyInstaller",
        "--nofollow-import-to=nuitka",
        "src/yt_transcript_search/main.py",
    ]

    subprocess.run(nuitka_args, check=True)


if __name__ == "__main__":
    build_app()
