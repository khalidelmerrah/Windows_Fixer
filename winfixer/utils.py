import os
import sys
import json
import ctypes
import subprocess
import tkinter as tk

from winfixer.constants import APP_ID


def resource_path(relative_path: str) -> str:
    """Resolve path to a bundled resource file, with traversal protection."""
    if ".." in relative_path or relative_path.startswith(("/", "\\")):
        raise ValueError(f"Invalid resource path: {relative_path}")
    try:
        if getattr(sys, "frozen", False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))
            # When running as package, go up to project root
            exe_dir = os.path.dirname(exe_dir)
        candidate = os.path.join(exe_dir, relative_path)
        if os.path.exists(candidate):
            return candidate
    except Exception:
        pass

    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def set_app_icon(root):
    """Set the application window icon."""
    ico = resource_path("icon.ico")
    if os.path.exists(ico):
        try:
            root.iconbitmap(ico)
            return ico
        except Exception:
            pass
    return None


def apply_icon_to_tlv(tlv, icon):
    """Apply icon to a Toplevel window."""
    if icon:
        try:
            tlv.iconbitmap(icon)
        except Exception:
            pass


def load_flag_image():
    """Load the Kuwait flag image for the About dialog."""
    png = resource_path("kuwait.png")
    if os.path.exists(png):
        try:
            return tk.PhotoImage(file=png)
        except Exception:
            pass
    return None


def make_donate_image(w=160, h=44):
    """Generate the donate button image programmatically."""
    from io import BytesIO
    from PIL import Image, ImageDraw

    r = h // 2
    top = (255, 187, 71)
    mid = (247, 162, 28)
    bot = (225, 140, 22)

    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)

    for y in range(h):
        if y < h * 0.6:
            t = y / (h * 0.6)
            c = tuple(int(top[i] * (1 - t) + mid[i] * t) for i in range(3)) + (255,)
        else:
            t = (y - h * 0.6) / (h * 0.4)
            c = tuple(int(mid[i] * (1 - t) + bot[i] * t) for i in range(3)) + (255,)
        dr.line([(0, y), (w, y)], fill=c)

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    im.putalpha(mask)

    hl = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    ImageDraw.Draw(hl).rounded_rectangle([2, 2, w - 3, h // 2], radius=r - 2, fill=(255, 255, 255, 70))
    im = Image.alpha_composite(im, hl)

    ImageDraw.Draw(im).rounded_rectangle(
        [0.5, 0.5, w - 1.5, h - 1.5], radius=r, outline=(200, 120, 20, 255), width=2
    )

    bio = BytesIO()
    im.save(bio, format="PNG")
    bio.seek(0)
    return tk.PhotoImage(data=bio.read())


def play_success_sound(log_cb=None):
    """Play success sound or system beep as fallback."""
    import winsound

    wav1 = resource_path("success.wav")
    wav2 = resource_path("Success.wav")
    wav = wav1 if os.path.exists(wav1) else wav2

    if log_cb:
        log_cb(f"[SOUND] Trying: {wav}")

    try:
        if os.path.exists(wav):
            winsound.PlaySound(None, winsound.SND_PURGE)
            winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
            if log_cb:
                log_cb("[SOUND] PlaySound called.")
            return True
        else:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            if log_cb:
                log_cb("[SOUND] WAV not found - played system beep.")
            return False
    except Exception as e:
        if log_cb:
            log_cb(f"[SOUND] Failed: {e}")
        return False


# ---------- Settings ----------

def _settings_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, APP_ID)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")


def _sanitize_settings(data):
    if not isinstance(data, dict):
        return {"always_admin": False, "language": "en", "theme": "light"}
    lang = data.get("language", "en")
    theme = data.get("theme", "light")
    return {
        "always_admin": bool(data.get("always_admin", False)),
        "language": lang if lang in ("en", "ar") else "en",
        "theme": theme if theme in ("light", "dark") else "light",
    }


def load_settings():
    path = _settings_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return _sanitize_settings(json.load(f))
    except (json.JSONDecodeError, OSError, ValueError) as e:
        print(f"[WARN] Failed to load settings: {e}")
    return {"always_admin": False, "language": "en", "theme": "light"}


def save_settings(data: dict):
    path = _settings_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[WARN] Failed to save settings: {e}")


# ---------- Admin & Drives ----------

def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except (AttributeError, OSError):
        return False


def relaunch_as_admin():
    params = subprocess.list2cmdline(sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 0)
    sys.exit(0)


def list_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if bitmask & (1 << i):
            letter = chr(ord("A") + i)
            path = f"{letter}:\\"
            if os.path.exists(path):
                drives.append(f"{letter}:")
    return drives or ["C:"]
