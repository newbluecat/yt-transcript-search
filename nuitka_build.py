import os
import platform
import subprocess
import sys
from pathlib import Path


def build_app() -> None:
    """Build the application for targeted operating system."""
    is_windows: bool = os.name == "nt"
    is_macos: bool = sys.platform == "darwin"
    exe_name: str = "quickjs.exe" if is_windows else "quickjs"

    if is_windows:
        os_dir: str = "win"
    elif is_macos:
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
        "--output-filename=yt-transcript-search",
        "--jobs=1",
        "--low-memory",
        f"--include-data-files={bin_path}={exe_name}",
        "--include-data-files=LICENSE.txt=LICENSE",
        "--include-data-files=THIRD-PARTY-NOTICES.txt=THIRD-PARTY-NOTICES",
        "--enable-plugin=pyside6",
        "--include-package=yt_dlp",
        "--include-package=yt_dlp_ejs",
        "--include-package-data=requests",
        "--include-package-data=certifi",
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=unittest",
        "--nofollow-import-to=PyInstaller",
        "--nofollow-import-to=nuitka",
        "src/yt_transcript_search/main.py",
    ]

    if is_macos:
        nuitka_args.append("--macos-create-app-bundle")

    nuitka_args.append("src/yt_transcript_search/__main__.py")

    subprocess.run(nuitka_args, check=True)


if __name__ == "__main__":
    build_app()
