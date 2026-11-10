# Video Downloader

Downloads videos from YouTube and 1,000+ other sites as a single MP4 with sound,
using [yt-dlp](https://github.com/yt-dlp/yt-dlp), in a simple desktop window.

## Requirements

- **Windows 10 or 11** (64-bit)
- **[uv](https://docs.astral.sh/uv/)**: installs Python 3.12 and all packages for you.
  Install it once with `winget install --id=astral-sh.uv -e`, then open a new terminal.

That's all: ffmpeg (to join video and sound) and Deno (needed for YouTube) come
with the packages, so you don't install them separately.

## Install

```
git clone https://github.com/NRicky25/video-downloader.git
cd video-downloader
.\setup.cmd
```

(Or download the ZIP from GitHub, extract it, and double-click **`setup.cmd`**.)

`setup.cmd` checks for uv, installs everything (`uv sync`) and creates a
**Video Downloader** shortcut in the folder. Run it again after updating
(`git pull`) to pick up new packages.

## Use

Double-click the **Video Downloader** shortcut (or run `uv run app.py`).

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

- Only the linked video is downloaded, even if it's part of a playlist.
- Private, members-only and some age-restricted videos can't be downloaded.
- Only download videos you have the right to use, especially if they'll go on Reelm.

## Troubleshooting

| Problem | Fix |
|---|---|
| `'uv' is not recognized` | Install uv (see Requirements), then open a **new** terminal. |
| YouTube downloads suddenly fail | Sites change often; update yt-dlp: `uv lock --upgrade-package yt-dlp` then `uv sync`. |
| The window is blank | Install the [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) (built into Windows 11). |

## Files

| File | What it is |
|---|---|
| `setup.cmd` | one-click install + shortcut |
| `app.py` | the window (pywebview) and the download queue |
| `ui/index.html` | the window's page |
| `download.py` | download logic, also usable from a terminal |
| `assets/` | app icon, and `make_icon.py` to redraw it (`uv run --with pillow assets/make_icon.py`) |
| `settings.json` | your saved folder and quality (created automatically, not in git) |
