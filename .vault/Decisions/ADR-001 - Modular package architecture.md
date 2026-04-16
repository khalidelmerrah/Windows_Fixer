---
date: 2026-04-16
project: Windows Fixer
status: accepted
tags: [architecture]
---

Project:: [[PROJECT]]

# ADR-001: Modular Package Architecture

## Context
The original codebase was a single 1,153-line file. Adding 4 new features would push it past 2,000 lines, making it harder to navigate and maintain.

## Decision
Split into a `winfixer/` Python package with focused modules: constants, utils, commands, translations, sysinfo, ui. Keep `windows_fixer.py` as a slim entry point.

## Consequences
- **Good:** Each module has a clear responsibility, easier to read and modify
- **Good:** New features (sysinfo, theming) get their own modules
- **Good:** Translations are centralized and easy to extend
- **Trade-off:** PyInstaller build needs `--collect-all winfixer` flag
- **Trade-off:** `resource_path()` needs to resolve paths relative to project root, not module dir
