# Windows Fixer - Windows Repair & Cleanup Tool

[![Download](https://img.shields.io/github/v/release/khalidelmerrah/Windows_Fixer?label=Download&style=for-the-badge&color=0078d4)](https://github.com/khalidelmerrah/Windows_Fixer/releases/latest)
[![License](https://img.shields.io/badge/License-Freeware-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue?style=for-the-badge)](https://github.com/khalidelmerrah/Windows_Fixer/releases/latest)

A free, open-source Windows system repair and PC cleanup utility with a modern dark GUI. Fix Windows errors, repair corrupted system files, clean temp files, reset network, and check disk health - all from one tool with no installation required.

Runs **DISM**, **SFC /scannow**, **CHKDSK**, **Winsock reset**, **DNS flush**, and safe cleanup operations with real-time progress tracking and logging.

> Forked from [ilukezippo/Windows_Fixer](https://github.com/ilukezippo/Windows_Fixer) - Original author: [ilukezippo (BoYaqoub)](https://github.com/ilukezippo)

## Download

**[Download WindowsFixer.exe (latest release)](https://github.com/khalidelmerrah/Windows_Fixer/releases/latest)** - No installation needed. Just download and run.

## Why use Windows Fixer?

- **One-click Windows repair** - No need to memorize DISM, SFC, or CHKDSK commands
- **Safe** - Creates a System Restore point before making any changes
- **Modern UI** - Dark/light theme, progress tracking, live log output
- **Portable** - Single EXE, no installation, no dependencies
- **Free and open source** - No ads, no telemetry, no premium tier

## Features

### Windows Repair Tools
- **DISM ScanHealth** - Check Windows image integrity for corruption
- **DISM RestoreHealth** - Repair corrupted Windows system image using Windows Update
- **SFC /scannow** - Scan and repair protected Windows system files
- **CHKDSK** - Check disk for file system errors with scan-only or fix mode
- **Network Reset** - Reset Winsock and TCP/IP stack to fix network issues

### PC Cleanup Tools
- **Clean Temp Files** - Delete user and system temporary files
- **Clean Prefetch** - Clear Windows Prefetch cache
- **Empty Recycle Bin** - Free disk space by clearing deleted files
- **Flush DNS Cache** - Reset DNS resolver cache to fix browsing issues
- **DISM Component Cleanup** - Remove superseded Windows component versions
- **Clear Windows Update Cache** - Stop update services and clean downloaded update files

### Safety & Recovery
- **System Restore Point** - Automatically creates a restore point before any repair operation
- **Admin detection** - Detects privilege level and offers elevation when needed
- **Skip / Cancel** - Stop or skip any operation mid-run

### System Information
- Windows version and build number
- CPU model and architecture
- RAM total, available, and usage percentage
- Disk space total, free, and usage percentage
- System uptime

### User Experience
- **Modern CustomTkinter UI** - Clean dark theme with rounded corners and styled controls
- **Dark / Light theme** toggle saved between sessions
- **Save Log** - Export the full operation log to a timestamped file
- **English / Arabic** language support
- **Progress bar** with step-by-step tracking

## Requirements

### Download and run (recommended)
- Windows 10 or Windows 11
- That's it - the EXE is self-contained

### Run from source
```bash
pip install pillow customtkinter
python windows_fixer.py
```

### Build the EXE yourself
```bash
pip install pillow customtkinter pyinstaller
pyinstaller --onefile --noconsole --name WindowsFixer --collect-all winfixer --collect-all customtkinter --icon icon.ico --add-data "icon.ico;." --add-data "kuwait.png;." --add-data "Success.wav;." windows_fixer.py
```

## Project Structure

```
windows_fixer.py          Entry point
winfixer/
  constants.py            Version, URLs, dimensions
  utils.py                Resource loading, settings, admin helpers
  commands.py             CommandRunner, cleanup functions, restore points
  translations.py         English + Arabic translation dictionaries
  sysinfo.py              System info (OS, CPU, RAM, disk, uptime)
  ui.py                   Main App window, theming, step orchestration
```

## What changed from the original

This fork builds on the [original project](https://github.com/ilukezippo/Windows_Fixer) with:

### Security Hardening
- Fixed command injection vulnerability in CHKDSK
- Fixed argument injection in admin relaunch
- Input validation for drive letters, settings, resource paths, API responses
- Thread-safe cancel/skip signals using `threading.Event`
- Specific exception handling instead of silent error swallowing

### New Features
- Complete UI redesign with CustomTkinter (modern dark theme)
- System Restore point creation before repairs
- System Info panel (OS, CPU, RAM, disk, uptime)
- Save Log to file
- Dark/Light theme toggle
- Modular package architecture

See [CHANGELOG.md](CHANGELOG.md) for full version history.

## Credits

- **Original Author:** [ilukezippo (BoYaqoub)](https://github.com/ilukezippo) - Created the original Windows Fixer
- **Fork Maintainer:** [khalidelmerrah](https://github.com/khalidelmerrah) - Security hardening, CustomTkinter UI, new features

## License

Freeware - Same as the original project.
