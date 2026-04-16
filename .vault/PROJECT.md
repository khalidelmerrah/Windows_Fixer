---
project: Windows Fixer
created: 2026-04-16
---

# Windows Fixer

## Overview
A lightweight Windows repair and cleanup tool with a modern tkinter GUI. Combines DISM, SFC, CHKDSK, and safe cleanup utilities in one interface.

## Tech Stack
- **Language:** Python 3.9+ (developed with 3.11 in CI)
- **GUI:** tkinter + ttk (stdlib)
- **Dependencies:** Pillow (for About dialog graphics)
- **Build:** PyInstaller (standalone EXE)
- **CI/CD:** GitHub Actions

## Architecture
Modular `winfixer/` package with thin `windows_fixer.py` entry point:
- `constants.py` - App metadata, URLs, dimensions
- `utils.py` - Resource loading, settings, admin helpers, image/sound
- `commands.py` - CommandRunner (subprocess wrapper), cleanup functions, restore points
- `translations.py` - English/Arabic dictionaries
- `sysinfo.py` - System info via ctypes/platform
- `ui.py` - Main App class, theming, UI, step orchestration

## Repo
- **Original:** https://github.com/ilukezippo/Windows_Fixer
- **Fork:** https://github.com/khalidelmerrah/Windows_Fixer

## Key Design Decisions
- Single-EXE distribution via PyInstaller (portable, no installer needed)
- All system commands run in a worker thread with cancel/skip signals
- Settings stored in `%APPDATA%\WindowsFixer\settings.json`
- Bilingual: English + Arabic with full UI translation
- Light/dark theme support via ttk style switching
