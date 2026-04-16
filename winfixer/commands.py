import os
import shutil
import ctypes
import subprocess
import threading


def _rmtree_onerror(func, path, exc_info):
    """Collect rmtree errors instead of silently ignoring them."""
    safe_rmtree._errors.append(path)


def safe_rmtree(path: str, log_cb):
    """Safely remove a file or directory tree with error reporting."""
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            safe_rmtree._errors = []
            shutil.rmtree(path, onerror=_rmtree_onerror)
            if safe_rmtree._errors:
                log_cb(f"[WARN] Could not delete {len(safe_rmtree._errors)} item(s) under {path}")
        else:
            try:
                os.remove(path)
            except PermissionError:
                log_cb(f"[WARN] Permission denied: {path}")
            except Exception as e:
                log_cb(f"[WARN] Could not delete {path}: {e}")
    except Exception as e:
        log_cb(f"[WARN] Could not delete {path}: {e}")


def delete_temp_folders(delete_prefetch: bool, log_cb, should_abort):
    """Delete temporary files from user and system temp folders."""
    targets = []
    user_temp = os.environ.get("TEMP") or os.path.join(
        os.environ.get("USERPROFILE", ""), "AppData", "Local", "Temp"
    )
    if user_temp:
        targets.append(user_temp)

    win_temp = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Temp")
    targets.append(win_temp)

    if delete_prefetch:
        targets.append(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Prefetch"))

    for folder in targets:
        if should_abort():
            log_cb("[INFO] Aborted cleanup.")
            return

        if not folder or not os.path.exists(folder):
            log_cb(f"[INFO] Skip (not found): {folder}")
            continue

        log_cb(f"[INFO] Cleaning: {folder}")
        try:
            for name in os.listdir(folder):
                if should_abort():
                    log_cb("[INFO] Aborted cleanup.")
                    return
                safe_rmtree(os.path.join(folder, name), log_cb)
            log_cb(f"[OK] Cleaned: {folder}")
        except PermissionError:
            log_cb(f"[WARN] Permission denied: {folder} (try Admin)")
        except Exception as e:
            log_cb(f"[WARN] Error cleaning {folder}: {e}")


def clear_recycle_bin(log_cb):
    """Empty the Windows Recycle Bin."""
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)
        log_cb("[OK] Recycle Bin cleared (or already empty).")
    except Exception as e:
        log_cb(f"[WARN] Could not clear Recycle Bin: {e}")


def create_restore_point(log_cb):
    """Create a Windows System Restore point before repairs."""
    try:
        ps_cmd = (
            'powershell -Command "Checkpoint-Computer '
            "-Description 'Windows Fixer Auto-Restore' "
            "-RestorePointType 'MODIFY_SETTINGS'\""
        )
        result = subprocess.run(
            ps_cmd, shell=True, capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            log_cb("[OK] System Restore point created successfully.")
            return True
        else:
            stderr = result.stderr.strip()
            if "frequency" in stderr.lower() or "1320" in stderr:
                log_cb("[WARN] Restore point skipped - Windows limits one per 24 hours.")
                return True
            log_cb(f"[WARN] Restore point failed: {stderr}")
            return False
    except subprocess.TimeoutExpired:
        log_cb("[WARN] Restore point creation timed out after 120s.")
        return False
    except Exception as e:
        log_cb(f"[WARN] Could not create restore point: {e}")
        return False


class CommandRunner:
    """Runs system commands with cancel/skip support and output streaming."""

    def __init__(self, log_cb):
        self.log_cb = log_cb
        self.current_proc = None
        self._cancel_all = threading.Event()
        self._skip_step = threading.Event()

    def reset_all(self):
        self._cancel_all.clear()
        self._skip_step.clear()
        self.current_proc = None

    def request_cancel_all(self):
        self._cancel_all.set()
        self._terminate_current("Cancel requested")

    def request_skip_step(self):
        self._skip_step.set()
        self._terminate_current("Skip requested")

    def reset_flags_for_step(self):
        self._skip_step.clear()

    def cancel_all_requested(self) -> bool:
        return self._cancel_all.is_set()

    def skip_requested(self) -> bool:
        return self._skip_step.is_set()

    def _terminate_current(self, reason: str):
        if self.current_proc:
            try:
                self.log_cb(f"[INFO] {reason}. Terminating current command...")
                self.current_proc.terminate()
            except Exception:
                pass

    def run_cmd(self, cmd):
        shown = cmd if isinstance(cmd, str) else " ".join(cmd)
        self.log_cb(f"\n=== RUN: {shown} ===")

        try:
            self.current_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )
        except Exception as e:
            self.log_cb(f"[ERROR] Failed to start command: {e}")
            self.current_proc = None
            return "error"

        try:
            if self.current_proc.stdout:
                for line in self.current_proc.stdout:
                    if self._cancel_all.is_set():
                        self._terminate_current("Cancel requested")
                        break
                    if self._skip_step.is_set():
                        self._terminate_current("Skip requested")
                        break
                    self.log_cb(line.rstrip("\n"))
        finally:
            try:
                if self.current_proc and self.current_proc.stdout:
                    self.current_proc.stdout.close()
            except Exception:
                pass

        try:
            if self.current_proc:
                self.current_proc.wait(timeout=10)
        except Exception:
            try:
                if self.current_proc:
                    self.current_proc.kill()
            except Exception:
                pass

        self.current_proc = None

        if self._cancel_all.is_set():
            self.log_cb("=== STOPPED (cancel) ===\n")
            return "cancel"
        if self._skip_step.is_set():
            self.log_cb("=== SKIPPED ===\n")
            return "skip"

        self.log_cb("=== DONE ===\n")
        return "ok"
