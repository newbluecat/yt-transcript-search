import os
import platform
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__


def clean_bloat() -> None:
    """Remove unneeded C++ binaries, platform plugins, and duplicate libraries."""
    # Added platform check so cleanup only runs on Linux where these specific files exist
    if sys.platform != "linux":
        return

    internal_dir: Path = Path("dist/main/_internal")
    if not internal_dir.exists():
        return

    # Expanded bloat_paths to include GTK dependencies, embedded Qt plugins, and base system libs
    bloat_paths: list[Path] = [
        internal_dir / "libicudata.so.78",
        internal_dir / "libicuuc.so.78",
        internal_dir / "libgtk-3.so.0",
        internal_dir / "libgdk-3.so.0",
        internal_dir / "libglycin-2.so.0",
        internal_dir / "libtinysparql-3.0.so.0",
        internal_dir / "libcloudproviders.so.0",
        internal_dir / "libatspi.so.0",
        internal_dir / "libatk-1.0.so.0",
        internal_dir / "libatk-bridge-2.0.so.0",
        internal_dir / "libcairo.so.2",
        internal_dir / "libcairo-gobject.so.2",
        internal_dir / "libpango-1.0.so.0",
        internal_dir / "libpangoft2-1.0.so.0",
        internal_dir / "libpangocairo-1.0.so.0",
        internal_dir / "libstdc++.so.6",
        internal_dir / "libgcc_s.so.1",
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
        internal_dir / "PySide6/Qt/lib/libQt6Network.so.6",
        internal_dir / "PySide6/Qt/translations",
    ]

    for path in bloat_paths:
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except OSError as e:
            error: OSError | None = e
            if error is not None:
                print(f"Failed to remove {path}: {error}")


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
        "--strip",
        f"--add-data={add_data_arg}",
        f"--add-data=LICENSE{separator}.",
        f"--add-data=THIRD-PARTY-NOTICES{separator}.",
        "--copy-metadata=pyside6-essentials",
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
