"""Windows Fixer - Entry point."""

import ctypes
from winfixer.utils import load_settings, is_admin, relaunch_as_admin
from winfixer.ui import App


if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    settings = load_settings()
    if bool(settings.get("always_admin", False)) and not is_admin():
        relaunch_as_admin()

    App().mainloop()
