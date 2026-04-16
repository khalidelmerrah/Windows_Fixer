# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Windows Fixer is a single-file Python desktop application (tkinter GUI) that combines Windows system repair commands (DISM, SFC, CHKDSK) with safe cleanup utilities. It targets Windows 10/11 and supports English and Arabic.

## Build & Run Commands

```bash
# Install dependencies (only Pillow is required beyond stdlib; pyinstaller for builds)
pip install pillow pyinstaller

# Run in development
python windows_fixer.py

# Build standalone EXE (matches CI pipeline)
pyinstaller --onefile --noconsole --name windows_fixer --icon icon.ico --add-data "icon.ico;." --add-data "kuwait.png;." --add-data "Success.wav;." windows_fixer.py
# Output: dist/windows_fixer.exe
```

No test suite or linter is configured.

## Architecture

Everything lives in `windows_fixer.py` (~1,125 lines). Key components:

- **`App(tk.Tk)`** (line ~366) - Main application window. Manages UI, settings, language, and coordinates worker threads. Contains `build_steps()` which defines the ordered list of repair/cleanup operations, and 11 `step_*()` methods that execute individual operations.
- **`CommandRunner`** (line ~259) - Wraps `subprocess.Popen` for running system commands (DISM, SFC, etc.) with cancel/skip support. Streams stdout line-by-line to the log queue.
- **Translation** - The `t()` method on `App` returns translated strings. English and Arabic dictionaries are defined inline (~lines 550-635).
- **Threading model** - UI runs on the main thread. Repair operations run on a worker thread. A `queue.Queue` (`log_queue`) bridges thread-safe log messages back to the UI via `after()` polling.
- **Settings** - Persisted as JSON at `%APPDATA%\WindowsFixer\settings.json`. Stores admin preference and language selection.
- **Asset loading** - `resource_path()` (line ~33) resolves assets in three fallback locations: next to the executable, PyInstaller's temp extraction dir (`sys._MEIPASS`), or the current working directory.

## Key Constants

- `APP_VERSION` / `APP_ID` - defined at top of file, used throughout UI and settings path
- `WIN_W` / `WIN_H` - window dimensions (1280x980)
- GitHub URLs for updates, donations, releases

## CI/CD

GitHub Actions workflow (`.github/workflows/build-and-release.yml`):
- Builds on push to `main` or version tags (`v*.*.*`)
- Uses Python 3.11, PyInstaller on `windows-latest` runner
- Tagged pushes create GitHub Releases with zipped EXE + SHA256 checksums

## Platform Constraints

- **Windows-only** - uses `ctypes.windll` for admin detection, DPI awareness, recycle bin operations, and `winsound` for audio
- **Requires Administrator** for most repair operations (DISM, SFC, CHKDSK, network reset, prefetch/update cache cleanup)
- Admin status is detected at startup; the app offers to relaunch elevated via `ShellExecuteW`
