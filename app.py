"""Video Downloader window.

Run:  uv run app.py      (or double-click "Video Downloader.lnk")

The window is HTML/CSS (ui/index.html) shown by pywebview; this file does the
downloading with yt-dlp and pushes progress events to the page.
"""

import ctypes
import itertools
import json
import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import darkdetect
import webview
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadCancelled

from download import DEFAULT_OUT, build_options

HERE = Path(__file__).parent
SETTINGS_FILE = HERE / "settings.json"
ICON_FILE = HERE / "assets" / "icon.ico"
TITLE = "Video Downloader"
APP_ID = "local.videodownloader"
QUALITIES = (720, 1080, 1440, 2160)

window: webview.Window | None = None  # kept out of Api so pywebview doesn't expose it


# ---------------- settings ----------------
def load_settings() -> dict[str, Any]:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if data.get("quality") not in QUALITIES:
        data["quality"] = 1080
    data.setdefault("destination", str(DEFAULT_OUT))
    return data


def save_settings(data: dict[str, Any]) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # remembering choices is a convenience, not essential


# ---------------- helpers ----------------
def read_clipboard() -> str:
    """Unicode text from the Windows clipboard ('' if none)."""
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    for _ in range(5):  # another app may hold the clipboard for a moment
        if user32.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        return ""
    try:
        handle = user32.GetClipboardData(13)  # CF_UNICODETEXT
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        try:
            return ctypes.wstring_at(ptr) if ptr else ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def friendly_error(e: Exception) -> str:
    msg = ANSI.sub("", str(e)).strip()
    msg = re.sub(r"^ERROR:\s*", "", msg)
    msg = re.sub(r"^\[[\w:]+\]\s*[\w-]*:\s*", "", msg)  # "[youtube] abc123: "
    if "Unsupported URL" in msg:
        return "This site isn't supported, or the link isn't a video page."
    if "Failed to resolve" in msg or "getaddrinfo failed" in msg:
        return "Couldn't reach the site. Check the link and your internet connection."
    if "Private video" in msg or "Sign in" in msg:
        return "This video needs a login (private, age-restricted or members-only)."
    msg = msg.split(" (caused by")[0]
    return msg[:220] + ("…" if len(msg) > 220 else "")


def fmt_duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def fmt_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return ""


def emit(**event: Any) -> None:
    if window is not None:
        try:
            window.evaluate_js(f"window.onEvent({json.dumps(event)})")
        except Exception:
            pass  # window is closing


class Silent:
    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


# ---------------- download worker ----------------
@dataclass
class Job:
    id: int
    url: str
    dest: Path
    quality: int


class Downloader:
    def __init__(self) -> None:
        self.jobs: queue.Queue[Job] = queue.Queue()
        self.cancelled: set[int] = set()
        self.ids = itertools.count(1)
        threading.Thread(target=self._loop, daemon=True).start()

    def add(self, url: str, dest: Path, quality: int) -> int:
        job = Job(next(self.ids), url, dest, quality)
        self.jobs.put(job)
        return job.id

    def cancel(self, job_id: int) -> None:
        self.cancelled.add(job_id)

    def _loop(self) -> None:
        while True:
            job = self.jobs.get()
            if job.id in self.cancelled:
                emit(id=job.id, state="cancelled", status="Cancelled")
                continue
            try:
                self._run(job)
            except Exception as e:
                if job.id in self.cancelled or isinstance(e, DownloadCancelled):
                    emit(id=job.id, state="cancelled", status="Cancelled", percent=0)
                else:
                    emit(id=job.id, state="error", status=friendly_error(e))

    def _run(self, job: Job) -> None:
        emit(id=job.id, state="fetching", status="Getting video info…")
        job.dest.mkdir(parents=True, exist_ok=True)

        stream_sizes: list[float] = []
        stream_ids: list[str] = []
        last_emit = [0.0]

        def progress(d: dict[str, Any]) -> None:
            if job.id in self.cancelled:
                raise DownloadCancelled()
            if d["status"] != "downloading":
                return
            now = time.monotonic()
            if now - last_emit[0] < 0.15:
                return
            last_emit[0] = now

            # Video and audio download as two streams; show one combined bar.
            fid = (d.get("info_dict") or {}).get("format_id", "")
            idx = stream_ids.index(fid) if fid in stream_ids else 0
            done = d.get("downloaded_bytes") or 0
            size = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if stream_sizes and all(stream_sizes):
                total = sum(stream_sizes)
                pct = (sum(stream_sizes[:idx]) + done) / total * 100
            else:
                n = max(1, len(stream_ids))
                pct = (idx + (done / size if size else 0)) / n * 100
            parts = [f"{min(pct, 99.9):.0f}%"]
            if size:
                parts.append(f"{fmt_size(done)} of {fmt_size(size)}")
            if d.get("speed"):
                parts.append(f"{fmt_size(d['speed'])}/s")
            if d.get("eta") is not None:
                parts.append(f"{fmt_duration(d['eta']) or '0:00'} left")
            emit(id=job.id, state="downloading", percent=min(pct, 99.9), status="  ·  ".join(parts))

        def postprocess(d: dict[str, Any]) -> None:
            if d["status"] == "started" and d.get("postprocessor") in ("Merger", "FFmpegMerger", "VideoConvertor"):
                emit(id=job.id, state="merging", status="Joining video and audio…")

        options = build_options(job.dest, job.quality)
        options.update(
            quiet=True,
            noprogress=True,
            logger=Silent(),
            progress_hooks=[progress],
            postprocessor_hooks=[postprocess],
        )
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(job.url, download=False)
            if job.id in self.cancelled:
                raise DownloadCancelled()

            streams = info.get("requested_formats") or [info]
            stream_ids[:] = [f.get("format_id", "") for f in streams]
            stream_sizes[:] = [f.get("filesize") or f.get("filesize_approx") or 0 for f in streams]
            height = info.get("height")
            meta = " · ".join(
                x for x in (info.get("uploader") or info.get("extractor_key"), f"{height}p" if height else "") if x
            )
            emit(
                id=job.id,
                state="downloading",
                title=info.get("title") or job.url,
                meta=meta,
                thumbnail=info.get("thumbnail") or "",
                duration=fmt_duration(info.get("duration")),
                percent=0,
                status="Starting…",
            )

            result = ydl.process_ie_result(info, download=True)
            downloads = result.get("requested_downloads") or [{}]
            path = downloads[0].get("filepath") or str(Path(ydl.prepare_filename(result)).with_suffix(".mp4"))

        size = Path(path).stat().st_size if Path(path).exists() else 0
        emit(
            id=job.id,
            state="done",
            percent=100,
            path=path,
            status=f"Saved  ·  {fmt_size(size)}" if size else "Saved",
        )


# ---------------- API the page can call ----------------
class Api:
    def __init__(self) -> None:
        self._settings = load_settings()
        self._downloader = Downloader()

    def init(self) -> dict[str, Any]:
        return {"destination": self._settings["destination"], "quality": self._settings["quality"]}

    def paste(self) -> str:
        return read_clipboard()

    def choose_folder(self) -> str | None:
        assert window is not None
        dialog = getattr(getattr(webview, "FileDialog", None), "FOLDER", None)
        if dialog is None:
            dialog = webview.FOLDER_DIALOG
        start = self._settings["destination"]
        picked = window.create_file_dialog(dialog, directory=start if Path(start).is_dir() else str(Path.home()))
        if not picked:
            return None
        folder = picked[0] if isinstance(picked, (list, tuple)) else picked
        self._settings["destination"] = str(Path(folder))
        save_settings(self._settings)
        return self._settings["destination"]

    def set_quality(self, quality: int) -> None:
        if quality in QUALITIES:
            self._settings["quality"] = quality
            save_settings(self._settings)

    def add(self, urls: list[str]) -> list[dict[str, Any]]:
        dest = Path(self._settings["destination"]).expanduser()
        return [
            {"id": self._downloader.add(u, dest, self._settings["quality"]), "url": u}
            for u in urls
        ]

    def cancel(self, job_id: int) -> None:
        self._downloader.cancel(int(job_id))

    def open_folder(self) -> None:
        folder = Path(self._settings["destination"]).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def open_file(self, path: str) -> None:
        if path and Path(path).exists():
            os.startfile(path)

    def reveal(self, path: str) -> None:
        if path and Path(path).exists():
            subprocess.Popen(["explorer", f"/select,{path}"])


# ---------------- native window touches (Windows) ----------------
def style_native_window() -> None:
    """Give the window our icon and a title bar that matches the page."""
    user32 = ctypes.windll.user32
    hwnd = 0
    try:
        hwnd = int(window.native.Handle.ToInt64())  # type: ignore[union-attr]
    except Exception:
        hwnd = user32.FindWindowW(None, TITLE)
    if not hwnd:
        return

    if ICON_FILE.exists():
        user32.LoadImageW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        for which, metric in ((1, 11), (0, 49)):  # ICON_BIG/SM_CXICON, ICON_SMALL/SM_CXSMICON
            px = user32.GetSystemMetrics(metric)
            icon = user32.LoadImageW(None, str(ICON_FILE), 1, px, px, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if icon:
                user32.SendMessageW(hwnd, 0x80, which, icon)  # WM_SETICON

    dark = (darkdetect.theme() or "Light") == "Dark"
    dwm = ctypes.windll.dwmapi
    value = ctypes.c_int(1 if dark else 0)
    dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), 4)  # immersive dark title bar
    caption = ctypes.c_int(0x00140E0E if dark else 0x00F8F5F5)  # page background, as 0x00BBGGRR
    dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption), 4)  # Win11 caption colour


def main(on_ready: Any = None) -> None:
    global window
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)  # own taskbar icon
    except (AttributeError, OSError):
        pass
    dark = (darkdetect.theme() or "Light") == "Dark"
    window = webview.create_window(
        TITLE,
        url=str(HERE / "ui" / "index.html"),
        js_api=Api(),
        width=1000,
        height=780,
        min_size=(720, 600),
        background_color="#0E0E14" if dark else "#F5F5F8",
    )
    window.events.shown += lambda *_: style_native_window()
    webview.start(on_ready, window) if on_ready else webview.start()


if __name__ == "__main__":
    main()
