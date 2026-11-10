"""Download videos from YouTube and other sites.

Usage:
    uv run download.py <url> [<url> ...] [--out FOLDER] [--max-height 1080]
    uv run app.py        # same thing with a window

Saves an .mp4 (video + audio merged) into ./downloads by default.
"""

import argparse
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import imageio_ffmpeg
from yt_dlp import YoutubeDL

DEFAULT_OUT = Path(__file__).parent / "downloads"

# Make the bundled deno (needed for YouTube) findable even without `uv run`.
os.environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]


def build_options(out_dir: Path, max_height: int) -> dict[str, Any]:
    h = max_height
    return {
        # Best video up to max height + best audio, merged; fall back to a single file.
        "format": f"bv*[height<={h}]+ba/b[height<={h}]/bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "%(title).150B [%(id)s].%(ext)s"),
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "noplaylist": True,
        "windowsfilenames": True,
    }


def download(
    urls: list[str],
    out_dir: Path,
    max_height: int = 1080,
    *,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
    logger: Any = None,
    on_error: Callable[[str, Exception], None] | None = None,
) -> tuple[list[Path], list[str]]:
    """Download each url into out_dir. Returns (saved files, failed urls)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    options = build_options(out_dir, max_height)
    if progress_hook:
        options["progress_hooks"] = [progress_hook]
    if logger:
        options["logger"] = logger

    saved: list[Path] = []
    failed: list[str] = []
    with YoutubeDL(options) as ydl:
        for url in urls:
            try:
                info = ydl.extract_info(url, download=True)
                saved.append(Path(ydl.prepare_filename(info)).with_suffix(".mp4"))
            except Exception as e:  # keep going with the other links
                failed.append(url)
                if on_error:
                    on_error(url, e)
                else:
                    raise
    return saved, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Download videos from a link.")
    parser.add_argument("urls", nargs="+", help="one or more video links")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="folder to save into")
    parser.add_argument(
        "--max-height",
        type=int,
        default=1080,
        help="highest resolution to fetch, e.g. 720, 1080, 2160 (default: 1080)",
    )
    args = parser.parse_args()

    def report(url: str, e: Exception) -> None:
        print(f"\nFAILED: {url}\n  {e}", file=sys.stderr)

    saved, failed = download(
        args.urls, Path(args.out).expanduser().resolve(), args.max_height, on_error=report
    )
    print()
    for path in saved:
        print(f"Saved: {path}")
    for url in failed:
        print(f"Failed: {url}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
