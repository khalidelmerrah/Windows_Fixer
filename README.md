# Windows Fixer

A lightweight Windows repair and cleanup tool with a modern GUI. Combines common Windows repair commands (DISM, SFC, CHKDSK) with safe cleanup utilities - all in one place, with progress tracking and logging.

> **Forked from [ilukezippo/Windows_Fixer](https://github.com/ilukezippo/Windows_Fixer)** - Original author: [ilukezippo (BoYaqoub)](https://github.com/ilukezippo)

## Download

**[Download Latest Release (EXE)](https://github.com/khalidelmerrah/Windows_Fixer/releases/latest)**

No installation needed - just download, extract, and run. Requires Windows 10/11.

## Features

### Repair Tools
- Check Windows Image Health (DISM ScanHealth)
- Repair Windows Image (DISM RestoreHealth)
- Repair System Files (SFC /scannow)
- Check Disk for errors (CHKDSK) with drive selection and scan/fix modes
- Reset Network Stack (Winsock + TCP/IP)

### Cleanup Tools
- Clean Temporary Files (user + system)
- Clean Prefetch Files
- Empty Recycle Bin
- Flush DNS Cache
- DISM Component Store Cleanup
- Clear Windows Update Download Cache

### Safety
- **System Restore Point** - Automatically creates a restore point before repairs so you can undo changes if needed
- Admin detection with optional "Always Run as Admin"
- Skip or cancel any operation mid-run

### System Info Panel
- OS version and build number
- CPU model
- RAM total, free, and usage percentage
- Disk space total, free, and usage percentage
- System uptime

### User Experience
- **Dark / Light theme** toggle (saved between sessions)
- **Save Log** - Export the full log to a timestamped file
- Select All checkbox for quick operation selection
- Progress bar with step tracking
- Full live log window
- English / Arabic language support

## Screenshots

*Run the app to see the interface - features a clean two-column layout with repair tools on the left and cleanup tools on the right.*

## Requirements

### To run from source
- Windows 10 / 11
- Python 3.9+
- Pillow (for About window graphics)

```bash
pip install pillow
python windows_fixer.py
```

### To build the EXE yourself

```bash
pip install pillow pyinstaller
pyinstaller --onefile --noconsole --name windows_fixer --collect-all winfixer --icon icon.ico --add-data "icon.ico;." --add-data "kuwait.png;." --add-data "Success.wav;." windows_fixer.py
```

Output: `dist/windows_fixer.exe`

## Project Structure

```
windows_fixer.py          Entry point
winfixer/
  constants.py            Version, URLs, dimensions
  utils.py                Resource loading, settings, admin helpers, images, sound
  commands.py             CommandRunner, cleanup functions, restore points
  translations.py         English + Arabic translation dictionaries
  sysinfo.py              System info (OS, CPU, RAM, disk, uptime)
  ui.py                   Main App window, theming, step orchestration
```

## What changed from the original

This fork adds the following on top of the [original project](https://github.com/ilukezippo/Windows_Fixer):

### Security Hardening (v1.0.1)
- Fixed command injection vulnerability in CHKDSK fix mode
- Fixed argument injection in admin relaunch
- Added input validation for drive letters, settings, resource paths, and API responses
- Replaced silent error swallowing with specific exception handling and logging
- Thread-safe cancel/skip signals using `threading.Event`

### New Features (v1.1.0)
- Modular package architecture (split from single 1,150-line file)
- System Restore point creation before repairs
- Save Log button for exporting log contents
- System Info panel (OS, CPU, RAM, disk, uptime)
- Dark/Light theme toggle
- Improved settings validation with schema enforcement

See [CHANGELOG.md](CHANGELOG.md) for full version history.

## Credits

- **Original Author:** [ilukezippo (BoYaqoub)](https://github.com/ilukezippo) - Created the original Windows Fixer
- **Fork Maintainer:** [khalidelmerrah](https://github.com/khalidelmerrah) - Security hardening, new features, modular architecture

## License

Freeware - Same as the original project.
