from __future__ import annotations

import contextlib
import datetime as dt
import logging
import os
import platform
import random
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import requests
import yt_dlp

import database
from models import SearchParams, TranscriptResult, TranscriptSnippet, VideoMetadata

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

logger: logging.Logger = logging.getLogger(__name__)


class JSONDownloadError(ConnectionError):
    """Raised when the json transcript payload fails to download."""

    def __init__(self) -> None:
        """Initialize JSONDownLoadError."""
        super().__init__("Failed to download json transcript")


class UnknownSourceError(ValueError):
    """Raised when an unrecognized source type is parsed."""

    def __init__(self) -> None:
        """Initialize UnknownSourceError."""
        super().__init__("Unknown error occurred.")


class IPBlockedError(ConnectionError):
    """Raised when YouTube rate-limits or blocks the IP."""

    def __init__(self) -> None:
        """Initialize IPBlockedError."""
        super().__init__("YouTube has temporarily blocked your IP address due to too many requests.")


def _get_quickjs_path() -> str | None:
    is_windows: bool = os.name == "nt"
    exe_name: str = "quickjs.exe" if is_windows else "quickjs"

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        qjs_exe: Path = Path(sys._MEIPASS) / exe_name  # noqa: SLF001
    else:
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
        qjs_exe = Path(__file__).parent / "bin" / os_dir / arch_dir / exe_name

    if qjs_exe.exists():
        return str(qjs_exe)

    return None


def _build_url(identifier: str, source_type: str) -> str:
    """Construct a valid YouTube url given the ID and the source type."""
    clean_id: str = identifier.strip()

    if source_type == "Playlist":
        return f"https://www.youtube.com/playlist?list={clean_id}"

    if clean_id.startswith("UC"):
        base_url: str = f"https://www.youtube.com/channel/{clean_id}"
    else:
        handle: str = clean_id if clean_id.startswith("@") else f"@{clean_id}"
        base_url = f"https://www.youtube.com/{handle}"

    if source_type == "Channel (Videos)":
        return f"{base_url}/videos"
    if source_type == "Channel (Live)":
        return f"{base_url}/streams"
    if source_type == "Channel (Shorts)":
        return f"{base_url}/shorts"

    raise UnknownSourceError


def _get_video_count(url: str, start_date: dt.date | None = None, end_date: dt.date | None = None) -> list[str]:
    """Get number of videos from URL with a single yt-dlp request."""
    yt_dlp_metadata_opts: dict[str, object] = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "playlistend": 10000,
        "extractor_args": {"youtubetab": ["approximate_date"]},
    }

    quickjs_path: str | None = _get_quickjs_path()
    if quickjs_path is not None:
        yt_dlp_metadata_opts["js_runtimes"] = {"quickjs": {"path": quickjs_path}}
    else:
        logger.warning("QuickJS binary not found in expected location.")

    if start_date is not None:
        yt_dlp_metadata_opts["dateafter"] = start_date.strftime("%Y%m%d")

    if end_date is not None:
        yt_dlp_metadata_opts["datebefore"] = end_date.strftime("%Y%m%d")

    video_ids: list[str] = []

    with yt_dlp.YoutubeDL(yt_dlp_metadata_opts) as ydl:
        info: dict[str, object] | None = ydl.extract_info(url, download=False)

    if info is None:
        logger.warning("yt-dlp failed to extract metadata for URL: %s", url)
        return video_ids

    try:
        entries: list[dict[str, object]] = info["entries"]
        logger.info("Found %d videos in the target URL matching date criteria.", len(entries))
    except KeyError:
        logger.warning("No 'entries' key found in yt-dlp metadata for %s", url)
        return video_ids

    for entry in entries:
        try:
            video_id: str | None = str(entry.get("id")) if entry.get("id") else None
            if video_id is not None:
                video_ids.append(video_id)
        except AttributeError:
            continue

    return video_ids


def _get_transcripts(
    video_ids: list[str],
    on_callback: Callable[[], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
    max_retries_per_video: int = 3,
) -> list[TranscriptResult]:
    """Fetch transcripts and metadata for a batch of video IDs."""
    results: list[TranscriptResult] = []

    yt_dlp_transcripts_opts: dict[str, object] = {
        "quiet": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en.*"],
        "subtitlesformat": "json3",
        "cookiesfrombrowser": ("firefox",),
    }

    quickjs_path: str | None = _get_quickjs_path()
    if quickjs_path is not None:
        yt_dlp_transcripts_opts["js_runtimes"] = {"quickjs": {"path": quickjs_path}}
    else:
        logger.warning("QuickJS binary not found in expected location.")

    with yt_dlp.YoutubeDL(yt_dlp_transcripts_opts) as ydl:
        for vid in video_ids:
            if is_cancelled is not None and is_cancelled():
                logger.info("Transcript extraction cancelled by user.")
                break

            try:
                result: TranscriptResult = _get_single_transcript(
                    video_id=vid,
                    ydl=ydl,
                    max_retries=max_retries_per_video,
                )
                results.append(result)
            except Exception:
                logger.exception("Unhandled error for video %s", vid)
                results.append(TranscriptResult(video_id=vid, transcript=None, status="ERROR", metadata=None))

            if on_callback is not None:
                on_callback()

    return results


def _extract_json_url(info: dict[str, object]) -> str | None:
    """Extract the json3 format URL for English subtitles from yt-dlp metadata."""
    subs: dict[str, object] | None = info.get("subtitles")
    auto_subs: dict[str, object] | None = info.get("automatic_captions")

    def _find_en_track(sub_dict: dict[str, object] | None) -> list[dict[str, object]] | None:
        if not sub_dict:
            return None

        if "en" in sub_dict:
            return sub_dict["en"]

        for lang, track in sub_dict.items():
            if lang.startswith("en"):
                return track

        return None

    target_subs: list[dict[str, object]] | None = _find_en_track(subs)

    if target_subs is None:
        target_subs = _find_en_track(auto_subs)

    if target_subs is None:
        avail_subs: list[str] = list((subs or {}).keys())
        avail_auto: list[str] = list((auto_subs or {}).keys())
        logger.warning(
            "No English tracks found. Available manual: %s | Available auto: %s",
            avail_subs,
            avail_auto,
        )
        return None

    for sub_format in target_subs:
        if sub_format.get("ext") == "json3":
            url_val: object = sub_format.get("url")
            if url_val is not None:
                return str(url_val)

    return None


def _fetch_and_parse_json(json_url: str) -> list[dict[str, str | float]] | None:
    """Download and parse YouTube's native json subtitle format into a uniform list."""
    try:
        response: requests.Response = requests.get(json_url, timeout=15)
    except requests.RequestException as e:
        logger.exception("Network error requesting json3")
        raise JSONDownloadError from e

    if response.status_code != requests.codes.ok:
        logger.error("HTTP %s returned for json3 URL: %s", response.status_code, json_url)
        raise JSONDownloadError

    raw_json: dict[str, object] = response.json()
    events: list[dict[str, object]] | None = raw_json.get("events")

    if events is None:
        return None

    parsed_transcript: list[dict[str, str | float]] = []

    for event in events:
        segs: list[dict[str, object]] | None = event.get("segs")
        if segs is None:
            continue

        text: str = "".join([str(seg.get("utf8", "")) for seg in segs]).strip()
        if text:
            parsed_transcript.append(
                {"text": text, "start": float(str(event.get("tStartMs", 0))) / 1000.0},
            )

    return parsed_transcript


def _get_single_transcript(  # noqa: C901, PLR0912
    video_id: str,
    ydl: yt_dlp.YoutubeDL,
    max_retries: int = 3,
) -> TranscriptResult:
    """Fetch one transcript with exponentially increasing delays for rate limits."""
    video_url: str = f"https://www.youtube.com/watch?v={video_id}"

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(random.uniform(1.0, 2.5))

            info: dict[str, object] | None = ydl.extract_info(video_url, download=False)

            if info is None:
                logger.warning("No info extracted for video %s (UNAVAILABLE)", video_id)
                return TranscriptResult(video_id=video_id, transcript=None, status="UNAVAILABLE", metadata=None)

            # --- getting metadata ---
            exact_date: dt.date | None = None
            timestamp: object = info.get("timestamp") or info.get("release_timestamp")
            if timestamp is not None:
                try:
                    exact_date = (
                        dt.datetime.fromtimestamp(
                            int(str(timestamp)),
                            tz=dt.UTC,
                        )
                        .astimezone()
                        .date()
                    )
                except TypeError, ValueError:
                    logger.warning(
                        "Video %s has no UNIX upload date, falling back to basic timestamp reading",
                        video_id,
                    )

            if exact_date is None:
                raw_date_val: object = info.get("upload_date") or info.get("release_date")
                if raw_date_val is not None:
                    raw_date_str: str = str(raw_date_val).replace("-", "")
                    if len(raw_date_str) >= 8:  # noqa: PLR2004
                        with contextlib.suppress(ValueError):
                            exact_date = dt.date(
                                int(raw_date_str[:4]),
                                int(raw_date_str[4:6]),
                                int(raw_date_str[6:8]),
                            )

            try:
                dur_val: object = info.get("duration", 0)
                duration: int | None = int(str(dur_val)) if dur_val else None
            except TypeError, ValueError:
                duration = None

            title_val: object = info.get("title")
            channel_val: object = info.get("channel") or info.get("uploader")
            channel_id_val: object = info.get("channel_id") or info.get("uploader_id")

            full_metadata = VideoMetadata(
                video_id=video_id,
                title=str(title_val) if title_val else None,
                channel=str(channel_val) if channel_val else None,
                channel_id=str(channel_id_val) if channel_id_val else None,
                upload_date=exact_date,
                duration_seconds=duration,
            )
            # ---------------------------------------

            json_url: str | None = _extract_json_url(info)
            if json_url is None:
                logger.warning("No English json3 subtitle track found for %s (NO_CAPTIONS)", video_id)
                return TranscriptResult(
                    video_id=video_id,
                    transcript=None,
                    status="NO_CAPTIONS",
                    metadata=full_metadata,
                )

            parsed_transcript: list[dict[str, str | float]] | None = _fetch_and_parse_json(json_url)
            if parsed_transcript is None:
                return TranscriptResult(
                    video_id=video_id,
                    transcript=None,
                    status="NO_CAPTIONS",
                    metadata=full_metadata,
                )

            time.sleep(random.uniform(1.5, 3.0))
            return TranscriptResult(
                video_id=video_id,
                transcript=parsed_transcript,
                status="SUCCESS",
                metadata=full_metadata,
            )

        except yt_dlp.utils.YoutubeDLError as e:
            err_str: str = str(e).lower()
            if "bot" in err_str or "429" in err_str or "sign in" in err_str:
                logger.warning("Rate limited or IP blocked on video %s: %s", video_id, e)
                return TranscriptResult(video_id=video_id, transcript=None, status="IP_BLOCKED", metadata=None)
            logger.exception("yt-dlp error on video %s", video_id)

        except Exception:
            logger.exception("Unexpected error fetching transcript for %s", video_id)

        time.sleep((2**attempt) + random.uniform(0.5, 1.5))

    return TranscriptResult(video_id=video_id, transcript=None, status="RETRYABLE", metadata=None)


def _build_atomic_blocks(
    raw_segments: list[dict[str, str | float]],
    overlap_seconds: float,
) -> list[list[dict[str, str | float]]]:
    """Group raw segments into discrete atomic time blocks."""
    blocks: list[list[dict[str, str | float]]] = []
    current_block: list[dict[str, str | float]] = []
    block_start: float = float(raw_segments[0].get("start", 0.0))

    for seg in raw_segments:
        seg_start: float = float(seg.get("start", 0.0))

        if seg_start - block_start >= overlap_seconds:
            if current_block:
                blocks.append(current_block)
            current_block = [seg]
            block_start = seg_start
        else:
            current_block.append(seg)

    if current_block:
        blocks.append(current_block)

    return blocks


def _build_sliding_chunks(
    blocks: list[list[dict[str, str | float]]],
    video_id: str,
    window_seconds: float,
    overlap_seconds: float,
) -> list[TranscriptSnippet]:
    """Slide a window over atomic blocks to create overlapping text chunks."""
    blocks_per_window: int = int(window_seconds // overlap_seconds)
    stride: int = max(1, blocks_per_window - 1)
    chunks: list[TranscriptSnippet] = []

    for i in range(0, len(blocks), stride):
        window_blocks: list[list[dict[str, str | float]]] = blocks[i : i + blocks_per_window]

        # at the end, if only one block left,
        # adds the previous block to it to make it longer
        if len(window_blocks) == 1 and i > 0:
            window_blocks.insert(0, blocks[i - 1])

        current_text: list[str] = []
        start_time: float = float(window_blocks[0][0].get("start", 0.0))

        for block in window_blocks:
            for seg in block:
                text: str = str(seg.get("text", "")).strip()
                if text:
                    current_text.append(text)

        if current_text:
            chunks.append(
                TranscriptSnippet(
                    video_id=video_id,
                    start_time=start_time,
                    text=" ".join(current_text),
                ),
            )

    return chunks


def _chunk_transcript_sliding(
    result: TranscriptResult,
    window_seconds: float = 30.0,
    overlap_seconds: float = 10.0,
) -> list[TranscriptSnippet]:
    """Group caption lines using atomic time blocks to simplify overlap math."""
    if result.transcript is None:
        return []

    raw_segments: list[dict[str, str | float]] = result.transcript
    if not raw_segments:
        return []

    blocks: list[list[dict[str, str | float]]] = _build_atomic_blocks(raw_segments, overlap_seconds)

    return _build_sliding_chunks(
        blocks=blocks,
        video_id=result.video_id,
        window_seconds=window_seconds,
        overlap_seconds=overlap_seconds,
    )


def _prepare_batch_data(
    results: list[TranscriptResult],
    video_ids: list[str],
) -> tuple[dict[str, str], list[TranscriptSnippet]]:
    """Transform raw transcript results into database-ready structures."""
    status_map: dict[str, str] = {}
    chunks: list[TranscriptSnippet] = []

    for result in results:
        status_map[result.video_id] = result.status

        if result.status == "SUCCESS":
            try:
                video_chunks: list[TranscriptSnippet] = _chunk_transcript_sliding(result)
                chunks.extend(video_chunks)
            except Exception:
                status_map[result.video_id] = "RETRYABLE"

    for video_id in video_ids:
        if video_id not in status_map:
            status_map[video_id] = "RETRYABLE"

    return status_map, chunks


def _filter_videos(
    conn: sqlite3.Connection,
    video_ids: list[str],
) -> tuple[list[str], int, int]:
    """Filter video IDs by date and database existence, returning missing videos and counts."""
    if not video_ids:
        return [], 0, 0

    existing_ids: set[str] = database.get_existing_video_ids(conn, video_ids)
    missing_ids: list[str] = [vid for vid in video_ids if vid not in existing_ids]

    total_count: int = len(video_ids)
    skipped_count: int = total_count - len(missing_ids)

    return missing_ids, total_count, skipped_count


def _process_batches(  # noqa: C901, PLR0913, PLR0917
    conn: sqlite3.Connection,
    missing_ids: list[str],
    batch_size: int,
    skipped_count: int,
    progress_callback: Callable[[int, int, str], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> None:
    """Iterate through missing IDs to fetch and save transcripts in batches."""
    missing_count: int = len(missing_ids)
    fetched_transcript_count: int = 0

    for i in range(0, missing_count, batch_size):
        if is_cancelled is not None and is_cancelled():
            if progress_callback is not None:
                progress_callback(fetched_transcript_count, missing_count, "Search aborted")
            return

        batch_ids: list[str] = missing_ids[i : i + batch_size]

        def _on_transcript_done() -> None:
            nonlocal fetched_transcript_count
            fetched_transcript_count += 1

            if is_cancelled is not None and is_cancelled():
                return

            if progress_callback is not None:
                progress_callback(
                    fetched_transcript_count,
                    missing_count,
                    f"Fetching transcripts... {fetched_transcript_count}/{missing_count} (Skipped: {skipped_count})",
                )

        batch_transcript_results: list[TranscriptResult] = _get_transcripts(
            video_ids=batch_ids,
            on_callback=_on_transcript_done,
            is_cancelled=is_cancelled,
        )

        batch_status_map: dict[str, str]
        batch_chunks: list[TranscriptSnippet]
        batch_status_map, batch_chunks = _prepare_batch_data(
            results=batch_transcript_results,
            video_ids=batch_ids,
        )

        batch_metadata: list[VideoMetadata] = []
        for result in batch_transcript_results:
            if result.metadata is not None:
                batch_metadata.append(result.metadata)
            else:
                batch_metadata.append(
                    VideoMetadata(
                        video_id=result.video_id,
                        title=None,
                        channel=None,
                        channel_id=None,
                        upload_date=None,
                        duration_seconds=None,
                    ),
                )

        database.batch_insert_videos(
            conn=conn,
            metadata_batch=batch_metadata,
            status_map=batch_status_map,
            chunks=batch_chunks,
        )

        if is_cancelled is not None and is_cancelled():
            if progress_callback is not None:
                progress_callback(fetched_transcript_count, missing_count, "Search aborted")
            return


def process_target(
    conn: sqlite3.Connection,
    search_params: SearchParams,
    batch_size: int = 50,
    progress_callback: Callable[[int, int, str], None] | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> None:
    """Coordinate inserting transcript chunks from url in batches."""
    url: str = _build_url(search_params.target_id, search_params.source_type)

    video_ids: list[str] = _get_video_count(
        url=url,
        start_date=search_params.start_date,
        end_date=search_params.end_date,
    )

    if not video_ids:
        if progress_callback is not None:
            progress_callback(0, 0, f"{search_params.source_type} has no videos")
        return

    missing_ids, total_count, skipped_count = _filter_videos(
        conn=conn,
        video_ids=video_ids,
    )

    if total_count == 0:
        if progress_callback is not None:
            progress_callback(100, 100, f"{search_params.source_type} has no videos within the specified dates")
        return

    if not missing_ids:
        if progress_callback is not None:
            progress_callback(100, 100, "All videos are already processed")
        return

    _process_batches(
        conn=conn,
        missing_ids=missing_ids,
        batch_size=batch_size,
        skipped_count=skipped_count,
        progress_callback=progress_callback,
        is_cancelled=is_cancelled,
    )
