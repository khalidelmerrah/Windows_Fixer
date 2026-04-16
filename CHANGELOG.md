# Changelog

## [1.1.0] - 2026-04-16 (commit: 659257f)
### Added
- Modular architecture: split single-file into `winfixer/` package (constants, utils, commands, translations, sysinfo, ui)
- System Restore point creation before repairs (safety net, on by default)
- Save Log button to export log contents to timestamped `.log` file
- System Info panel showing OS version, CPU, RAM, disk space, and uptime
- Dark/Light theme toggle in File menu, persisted in settings
- `.gitignore` for Python artifacts

### Changed
- CI build updated with `--collect-all winfixer` for PyInstaller package collection
- CLAUDE.md updated to reflect new modular architecture
- Settings schema now includes `theme` field ("light"/"dark")
- Entry point (`windows_fixer.py`) reduced to slim launcher

## [1.0.1] - 2026-04-16 (commit: d41192c)
### Security
- Fixed command injection in CHKDSK fix mode (removed `cmd /c`, use list form + drive regex validation)
- Fixed argument injection in admin relaunch (use `subprocess.list2cmdline`)
- Sanitized version tag from GitHub API update checker (strip non-version characters)
- Added settings file type validation after loading (`_sanitize_settings`)
- Blocked path traversal in `resource_path` (reject `..` and absolute prefixes)
- Replaced `shutil.rmtree(ignore_errors=True)` with `onerror` handler that logs failures
- Narrowed broad `except: pass` blocks to specific exception types with logging
- Replaced bare boolean thread flags with `threading.Event` for thread-safe cancel/skip
- `BUILD_DATE` now reads from `BUILD_DATE` env var (accurate build timestamps in CI)

## [1.0.0] - 2025-02-14
### Added
- Initial release by ilukezippo (BoYaqoub)
- DISM ScanHealth and RestoreHealth
- SFC ScanNow
- CHKDSK with drive selection and scan/fix modes
- Network stack reset (Winsock + TCP/IP)
- Temp file cleanup (user and system)
- Prefetch cleanup
- Recycle Bin emptying
- DNS cache flush
- DISM Component Store cleanup
- Windows Update cache clearing
- English and Arabic language support
- Auto-update checker via GitHub API
- Admin detection with optional auto-elevation
- Progress bar with step tracking
- Live log window with skip/cancel controls
- GitHub Actions CI/CD for automated builds and releases
