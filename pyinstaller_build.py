import os
import platform
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__


def clean_bloat(dist_dir: Path) -> None:
    """Remove unneeded Qt plugins and translations on Linux."""
    if sys.platform != "linux":
        return

    internal_dir: Path = dist_dir / "_internal"
    if not internal_dir.exists():
        return

    bloat_paths: list[Path] = [
        internal_dir / "PySide6/Qt/plugins/egldeviceintegrations",
        internal_dir / "PySide6/Qt/plugins/platforms/libqlinuxfb.so",
        internal_dir / "PySide6/Qt/plugins/platforms/libqminimal.so",
        internal_dir / "PySide6/Qt/plugins/platforms/libqminimalegl.so",
        internal_dir / "PySide6/Qt/plugins/platforms/libqoffscreen.so",
        internal_dir / "PySide6/Qt/plugins/platforms/libqvnc.so",
        internal_dir / "PySide6/Qt/plugins/platforms/libqvkkhrdisplay.so",
        internal_dir / "PySide6/Qt/plugins/platforms/libqeglfs.so",
        internal_dir / "PySide6/Qt/lib/libQt6EglFSDeviceIntegration.so.6",
        internal_dir / "PySide6/Qt/lib/libQt6EglFsKmsSupport.so.6",
        internal_dir / "PySide6/Qt/translations",
    ]

    for path in bloat_paths:
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except OSError as e:
            print(f"Failed to remove {path}: {e}")


def build_app() -> None:
    """Build the application for targeted operating system."""
    is_windows: bool = os.name == "nt"
    exe_name: str = "quickjs.exe" if is_windows else "quickjs"
    app_name: str = "yt-transcript-search"

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
        "src/yt_transcript_search/__main__.py",
        f"--name={app_name}",
        "--noconsole",
        "--onedir",
        f"--add-data={add_data_arg}",
        f"--add-data=LICENSE{separator}.",
        f"--add-data=THIRD-PARTY-NOTICES{separator}.",
        "--copy-metadata=pyside6-essentials",
        "--copy-metadata=yt_dlp",
        "--copy-metadata=requests",
        "--collect-data=yt_dlp",
        "--collect-data=yt_dlp_ejs",
        "--collect-data=certifi",
        "--exclude-module=tkinter",
        "--exclude-module=unittest",
        "--exclude-module=PySide6.QtWebEngineCore",
        "--exclude-module=PySide6.QtWebEngineWidgets",
        "--exclude-module=PySide6.QtNetwork",
        "--exclude-module=PySide6.QtQml",
    ]

    if not is_windows:
        pyinstaller_args.append("--strip")

    PyInstaller.__main__.run(pyinstaller_args)
    clean_bloat(Path("dist") / app_name)


if __name__ == "__main__":
    build_app()
