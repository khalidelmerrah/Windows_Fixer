# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Windows Fixer is a Python desktop application (tkinter GUI) that combines Windows system repair commands (DISM, SFC, CHKDSK) with safe cleanup utilities. It targets Windows 10/11 and supports English/Arabic with light/dark themes.

## Build & Run Commands

```bash
# Install dependencies
pip install pillow pyinstaller

# Run in development
python windows_fixer.py

# Build standalone EXE (matches CI pipeline)
pyinstaller --onefile --noconsole --name windows_fixer --collect-all winfixer --icon icon.ico --add-data "icon.ico;." --add-data "kuwait.png;." --add-data "Success.wav;." windows_fixer.py
# Output: dist/windows_fixer.exe
```

No test suite or linter is configured.

## Architecture

The codebase is organized as a `winfixer/` package with a thin entry point:

- **`windows_fixer.py`** - Entry point. DPI setup, admin auto-relaunch, launches `App`.
- **`winfixer/constants.py`** - Version, URLs, window dimensions.
- **`winfixer/utils.py`** - `resource_path()` (asset resolution with traversal protection), settings load/save with schema validation, admin detection (`is_admin`, `relaunch_as_admin`), drive listing, icon/image helpers, sound playback.
- **`winfixer/commands.py`** - `CommandRunner` class (subprocess wrapper with cancel/skip via `threading.Event`), cleanup functions (`delete_temp_folders`, `clear_recycle_bin`, `safe_rmtree`), `create_restore_point()`.
- **`winfixer/translations.py`** - `EN` and `AR` dictionaries with `translate(lang, key)` function. All UI strings live here.
- **`winfixer/sysinfo.py`** - System info gathering via `ctypes`/`platform`/`wmic`: OS version, CPU, RAM, disk space, uptime.
- **`winfixer/ui.py`** - `App(tk.Tk)` main window. Contains all UI creation, theming (light/dark via `THEMES` dict + ttk styles), step orchestration, log export, and the About dialog.

## Threading Model

UI runs on the main thread. Repair operations run on a daemon worker thread. `queue.Queue` (`log_queue`) bridges log messages to the UI via `after()` polling at 80ms intervals. Cancel/skip signals use `threading.Event` for thread-safe cross-thread communication.

## Settings

Persisted as JSON at `%APPDATA%\WindowsFixer\settings.json`. Schema-validated on load: `always_admin` (bool), `language` ("en"/"ar"), `theme` ("light"/"dark").

## CI/CD

GitHub Actions workflow (`.github/workflows/build-and-release.yml`):
- Builds on push to `main` or version tags (`v*.*.*`)
- Uses Python 3.11, PyInstaller with `--collect-all winfixer` on `windows-latest`
- Tagged pushes create GitHub Releases with zipped EXE + SHA256 checksums

## Platform Constraints

- **Windows-only** - uses `ctypes.windll` for admin detection, DPI awareness, RAM/disk queries, recycle bin, restore points, and `winsound` for audio
- **Requires Administrator** for most repair operations (DISM, SFC, CHKDSK, network reset, restore points, prefetch/update cache cleanup)
