# Video Downloader

Downloads videos from YouTube and 1,000+ other sites as a single MP4 with sound,
using [yt-dlp](https://github.com/yt-dlp/yt-dlp). Runs on this PC.

## Use

Double-click **`Video Downloader.lnk`** (or run `uv run app.py`).

- **Links:** paste one or more links, one per line (clicking the box pastes a link you
  just copied). **Ctrl+Enter** or **Download** starts.
- **Save to:** where the videos go; **Change** to pick another folder. Remembered.
- **Quality:** the highest resolution to fetch: 720p, 1080p, 1440p or 4K.
- Each download shows its thumbnail, title, a progress bar with speed and time left,
  and **Cancel**. When done: **Play** and **Show in folder**. If one fails, you get the
  reason and **Retry**; the others keep going.

From a terminal:

```
uv run download.py "https://www.youtube.com/watch?v=..."         # into ./downloads
uv run download.py <link> <link> --out D:\Movies --max-height 720
```

## Notes

- Sites send video and sound as separate streams; they are joined into one MP4
  automatically (ffmpeg comes bundled, nothing to install).
- Only the linked video is downloaded, even if it's part of a playlist.
- Private, members-only and some age-restricted videos can't be downloaded.
- If YouTube downloads start failing, update yt-dlp: `uv lock --upgrade-package yt-dlp && uv sync`.
- Only download videos you have the right to use, especially if they'll go on Reelm.

## Setup (once)

```
uv sync
```

The shortcut isn't portable (it holds paths on this PC). To make it again: a shortcut
to `.venv\Scripts\pythonw.exe` with the argument `app.py`, starting in this folder,
with the icon `assets\icon.ico`.

## Files

| File | What it is |
|---|---|
| `app.py` | the window (pywebview) and the download queue |
| `ui/index.html` | the window's page |
| `download.py` | download logic, also usable from the terminal |
| `assets/` | app icon, and `make_icon.py` to redraw it (`uv run --with pillow assets/make_icon.py`) |
| `settings.json` | your saved folder and quality (created automatically) |
