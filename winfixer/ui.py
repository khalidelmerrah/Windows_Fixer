"""Main application UI for Windows Fixer - built with CustomTkinter."""

import os
import re
import json
import queue
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import webbrowser
from datetime import datetime

from winfixer.constants import (
    APP_VERSION, BUILD_DATE, WIN_W, WIN_H,
    DONATE_PAGE, GITHUB_PAGE_ORIGINAL, GITHUB_PAGE_FORK,
    GITHUB_API_LATEST, GITHUB_RELEASES_PAGE,
)
from winfixer.utils import (
    set_app_icon, apply_icon_to_tlv, load_flag_image,
    play_success_sound, load_settings, save_settings, is_admin, relaunch_as_admin,
    list_drives,
)
from winfixer.commands import (
    CommandRunner, delete_temp_folders, clear_recycle_bin, create_restore_point,
    safe_rmtree,
)
from winfixer.translations import translate
from winfixer import sysinfo


# Color palette
ACCENT_BLUE = "#0078d4"
ACCENT_GREEN = "#10893e"
ACCENT_RED = "#c42b1c"
ACCENT_GOLD = "#d4940a"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = load_settings()
        self.lang = self.settings.get("language", "en")
        theme = self.settings.get("theme", "dark")
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")

        self.icon_path = set_app_icon(self)

        self.log_queue = queue.Queue()
        self.runner = CommandRunner(self.enqueue_log)
        self.worker_thread = None
        self.running = False

        # Repair options
        self.var_restore_point = ctk.BooleanVar(value=True)
        self.var_dism_scan = ctk.BooleanVar(value=False)
        self.var_dism_restore = ctk.BooleanVar(value=True)
        self.var_sfc = ctk.BooleanVar(value=True)
        self.var_chkdsk = ctk.BooleanVar(value=False)
        self.var_chkdsk_mode = ctk.StringVar(value="scan")
        self.var_drive = ctk.StringVar(value="C:")
        self.var_reset_network = ctk.BooleanVar(value=False)

        # Cleanup options
        self.var_temp = ctk.BooleanVar(value=True)
        self.var_prefetch = ctk.BooleanVar(value=False)
        self.var_recycle_bin = ctk.BooleanVar(value=True)
        self.var_flush_dns = ctk.BooleanVar(value=False)
        self.var_dism_component_cleanup = ctk.BooleanVar(value=False)
        self.var_wu_cache = ctk.BooleanVar(value=False)

        self._all_option_vars = [
            self.var_restore_point,
            self.var_dism_scan, self.var_dism_restore, self.var_sfc,
            self.var_chkdsk, self.var_reset_network,
            self.var_temp, self.var_prefetch, self.var_recycle_bin,
            self.var_flush_dns, self.var_dism_component_cleanup, self.var_wu_cache,
        ]

        self.var_select_all = ctk.BooleanVar(value=False)
        self._select_all_guard = False

        self.var_step_text = ctk.StringVar(value="Idle")
        self.total_steps = 0

        self.title(f"Windows Fixer {APP_VERSION}")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(1180, 880)

        self.create_ui()
        self.refresh_drive_list()

        self.var_chkdsk.trace_add("write", lambda *_: self.update_chkdsk_controls())
        self.update_chkdsk_controls()

        for v in self._all_option_vars:
            v.trace_add("write", lambda *_: self.update_select_all_state())
        self.var_select_all.trace_add("write", lambda *_: self.on_select_all_toggled())

        self.after(80, self.flush_log_queue)
        self.apply_language()
        self.update_select_all_state()

        self.after(800, lambda: self.check_latest_app_version_async(show_if_latest=False))

        self.after(50, self._center)

    # ---------- Translation ----------
    def t(self, key: str) -> str:
        return translate(self.lang, key)

    # ---------- Theme ----------
    def toggle_theme(self):
        new = "light" if ctk.get_appearance_mode().lower() == "dark" else "dark"
        ctk.set_appearance_mode(new)
        self.settings["theme"] = new
        save_settings(self.settings)

    # ---------- Center ----------
    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _center_child(self, win):
        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - win.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    # ---------- Update checker ----------
    def _parse_ver_tuple(self, v: str):
        return tuple(int(n) for n in re.findall(r"\d+", v)[:4]) or (0,)

    def check_latest_app_version_async(self, show_if_latest: bool = False):
        import urllib.request

        def worker():
            try:
                req = urllib.request.Request(GITHUB_API_LATEST, headers={"User-Agent": "Windows-Fixer"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode("utf-8", "replace"))
                raw_tag = str(data.get("tag_name") or data.get("name") or "").strip()
                tag = re.sub(r"[^v0-9.]", "", raw_tag)
                if tag and self._parse_ver_tuple(tag) > self._parse_ver_tuple(APP_VERSION):
                    def _ask():
                        msg = self.t("update_available").format(tag=tag)
                        if messagebox.askyesno(self.t("update_title"), msg, parent=self):
                            webbrowser.open(GITHUB_RELEASES_PAGE)
                    self.after(0, _ask)
                elif show_if_latest:
                    self.after(0, lambda: messagebox.showinfo(
                        self.t("update_title"), self.t("update_latest"), parent=self))
            except Exception:
                if show_if_latest:
                    self.after(0, lambda: messagebox.showwarning(
                        self.t("update_title"), self.t("update_failed"), parent=self))

        threading.Thread(target=worker, daemon=True).start()

    # ======================================================================
    # UI CONSTRUCTION
    # ======================================================================
    def create_ui(self):
        # Main scrollable container
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=0)
        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Top bar: admin + theme + language ---
        self._build_topbar()

        # --- System Info ---
        self._build_sysinfo()

        # --- Options (Repair + Cleanup) ---
        self._build_options()

        # --- Progress ---
        self._build_progress()

        # --- Log ---
        self._build_log()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        self.lbl_admin = ctk.CTkLabel(bar, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_admin.pack(side="left")

        # Right side buttons
        self.btn_about = ctk.CTkButton(
            bar, text="About", width=70, height=30,
            fg_color="transparent", border_width=1,
            command=self.show_about,
        )
        self.btn_about.pack(side="right", padx=(6, 0))

        self.btn_theme = ctk.CTkButton(
            bar, text="Theme", width=70, height=30,
            fg_color="transparent", border_width=1,
            command=self.toggle_theme,
        )
        self.btn_theme.pack(side="right", padx=(6, 0))

        self.btn_lang = ctk.CTkButton(
            bar, text="AR / EN", width=70, height=30,
            fg_color="transparent", border_width=1,
            command=self._toggle_language,
        )
        self.btn_lang.pack(side="right", padx=(6, 0))

        self.btn_update = ctk.CTkButton(
            bar, text="Updates", width=80, height=30,
            fg_color="transparent", border_width=1,
            command=lambda: self.check_latest_app_version_async(show_if_latest=True),
        )
        self.btn_update.pack(side="right", padx=(6, 0))

        self.btn_admin = ctk.CTkButton(
            bar, text="", width=120, height=30,
            fg_color=ACCENT_BLUE,
            command=self._on_run_as_admin,
        )
        self.btn_admin.pack(side="right", padx=(6, 0))

    def _build_sysinfo(self):
        self.sysinfo_frame = ctk.CTkFrame(self, corner_radius=8)
        self.sysinfo_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 4))

        self.sysinfo_labels = {}
        keys = ["os_version", "cpu", "ram", "disk_space", "uptime"]
        for i, key in enumerate(keys):
            col = (i % 3) * 2
            row = i // 3
            lbl_k = ctk.CTkLabel(
                self.sysinfo_frame, text="", font=ctk.CTkFont(size=12, weight="bold"),
            )
            lbl_k.grid(row=row, column=col, sticky="w", padx=(16, 4), pady=6)
            lbl_v = ctk.CTkLabel(self.sysinfo_frame, text="", font=ctk.CTkFont(size=12))
            lbl_v.grid(row=row, column=col + 1, sticky="w", padx=(0, 24), pady=6)
            self.sysinfo_labels[key] = (lbl_k, lbl_v)

    def _build_options(self):
        opts = ctk.CTkFrame(self, corner_radius=8)
        opts.grid(row=2, column=0, sticky="ew", padx=16, pady=4)
        opts.grid_columnconfigure(0, weight=1)
        opts.grid_columnconfigure(1, weight=1)

        # Select All
        self.cb_select_all = ctk.CTkCheckBox(
            opts, text="", variable=self.var_select_all,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.cb_select_all.grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 8))

        # --- Left: Repair ---
        left = ctk.CTkFrame(opts, fg_color="transparent")
        left.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=(0, 12))

        self.lbl_repair = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_repair.pack(anchor="w", pady=(0, 6))

        self.cb_restore_point = ctk.CTkCheckBox(left, text="", variable=self.var_restore_point)
        self.cb_restore_point.pack(anchor="w", pady=3)
        self.desc_restore_point = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11), text_color="gray", wraplength=560)
        self.desc_restore_point.pack(anchor="w", padx=(28, 0))

        self.cb_dism_scan = ctk.CTkCheckBox(left, text="", variable=self.var_dism_scan)
        self.cb_dism_scan.pack(anchor="w", pady=(8, 3))
        self.desc_dism_scan = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11), text_color="gray", wraplength=560)
        self.desc_dism_scan.pack(anchor="w", padx=(28, 0))

        self.cb_dism_restore = ctk.CTkCheckBox(left, text="", variable=self.var_dism_restore)
        self.cb_dism_restore.pack(anchor="w", pady=(8, 3))
        self.desc_dism_restore = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11), text_color="gray", wraplength=560)
        self.desc_dism_restore.pack(anchor="w", padx=(28, 0))

        self.cb_sfc = ctk.CTkCheckBox(left, text="", variable=self.var_sfc)
        self.cb_sfc.pack(anchor="w", pady=(8, 3))
        self.desc_sfc = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11), text_color="gray", wraplength=560)
        self.desc_sfc.pack(anchor="w", padx=(28, 0))

        self.cb_chkdsk = ctk.CTkCheckBox(left, text="", variable=self.var_chkdsk)
        self.cb_chkdsk.pack(anchor="w", pady=(8, 3))
        self.desc_chkdsk = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11), text_color="gray", wraplength=560)
        self.desc_chkdsk.pack(anchor="w", padx=(28, 0))

        # CHKDSK sub-controls
        chk_sub = ctk.CTkFrame(left, fg_color="transparent")
        chk_sub.pack(anchor="w", padx=(28, 0), pady=(4, 0))

        self.lbl_drive = ctk.CTkLabel(chk_sub, text="")
        self.lbl_drive.pack(side="left")
        self.drive_combo = ctk.CTkComboBox(chk_sub, width=90, variable=self.var_drive, state="readonly")
        self.drive_combo.pack(side="left", padx=(6, 10))
        self.btn_drive_refresh = ctk.CTkButton(chk_sub, text="", width=70, height=28, command=self.refresh_drive_list)
        self.btn_drive_refresh.pack(side="left")

        mode_sub = ctk.CTkFrame(left, fg_color="transparent")
        mode_sub.pack(anchor="w", padx=(28, 0), pady=(4, 0))
        self.lbl_mode = ctk.CTkLabel(mode_sub, text="")
        self.lbl_mode.pack(side="left")
        self.rb_scan = ctk.CTkRadioButton(mode_sub, text="", value="scan", variable=self.var_chkdsk_mode)
        self.rb_scan.pack(side="left", padx=8)
        self.rb_fix = ctk.CTkRadioButton(mode_sub, text="", value="fix", variable=self.var_chkdsk_mode)
        self.rb_fix.pack(side="left", padx=8)

        self.cb_reset_net = ctk.CTkCheckBox(left, text="", variable=self.var_reset_network)
        self.cb_reset_net.pack(anchor="w", pady=(8, 3))
        self.desc_reset_net = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11), text_color="gray", wraplength=560)
        self.desc_reset_net.pack(anchor="w", padx=(28, 0))

        # --- Right: Cleanup ---
        right = ctk.CTkFrame(opts, fg_color="transparent")
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=(0, 12))

        self.lbl_cleanup = ctk.CTkLabel(right, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_cleanup.pack(anchor="w", pady=(0, 6))

        cleanup_items = [
            ("cb_temp", "desc_temp", self.var_temp),
            ("cb_prefetch", "desc_prefetch", self.var_prefetch),
            ("cb_recycle", "desc_recycle", self.var_recycle_bin),
            ("cb_dns", "desc_dns", self.var_flush_dns),
            ("cb_comp", "desc_comp", self.var_dism_component_cleanup),
            ("cb_wu", "desc_wu", self.var_wu_cache),
        ]
        for cb_attr, desc_attr, var in cleanup_items:
            cb = ctk.CTkCheckBox(right, text="", variable=var)
            cb.pack(anchor="w", pady=(8, 3) if cb_attr != "cb_temp" else 3)
            setattr(self, cb_attr, cb)
            desc = ctk.CTkLabel(right, text="", font=ctk.CTkFont(size=11), text_color="gray", wraplength=480)
            desc.pack(anchor="w", padx=(28, 0))
            setattr(self, desc_attr, desc)

    def _build_progress(self):
        prog_frame = ctk.CTkFrame(self, corner_radius=8)
        prog_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=4)

        top_row = ctk.CTkFrame(prog_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(12, 4))

        self.lbl_step = ctk.CTkLabel(top_row, textvariable=self.var_step_text, font=ctk.CTkFont(size=12))
        self.lbl_step.pack(side="left")

        self.progress = ctk.CTkProgressBar(prog_frame, height=14)
        self.progress.pack(fill="x", padx=16, pady=(0, 4))
        self.progress.set(0)

        # Buttons row
        btn_row = ctk.CTkFrame(prog_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 12))

        self.btn_start = ctk.CTkButton(
            btn_row, text="", width=120, height=36,
            fg_color=ACCENT_GREEN, hover_color="#0e7a35",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.on_start,
        )
        self.btn_start.pack(side="left")

        self.btn_skip = ctk.CTkButton(
            btn_row, text="", width=100, height=36,
            fg_color="transparent", border_width=1,
            command=self.on_skip, state="disabled",
        )
        self.btn_skip.pack(side="left", padx=(8, 0))

        self.btn_cancel = ctk.CTkButton(
            btn_row, text="", width=100, height=36,
            fg_color=ACCENT_RED, hover_color="#a82418",
            command=self.on_cancel, state="disabled",
        )
        self.btn_cancel.pack(side="left", padx=(8, 0))

        self.btn_save_log = ctk.CTkButton(
            btn_row, text="", width=100, height=36,
            fg_color="transparent", border_width=1,
            command=self.on_save_log,
        )
        self.btn_save_log.pack(side="right")

        self.btn_clear = ctk.CTkButton(
            btn_row, text="", width=100, height=36,
            fg_color="transparent", border_width=1,
            command=self.on_clear,
        )
        self.btn_clear.pack(side="right", padx=(0, 8))

    def _build_log(self):
        log_frame = ctk.CTkFrame(self, corner_radius=8)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=16, pady=(4, 12))

        self.lbl_log_title = ctk.CTkLabel(log_frame, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_log_title.pack(anchor="w", padx=16, pady=(10, 4))

        self.txt = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(family="Consolas", size=12), corner_radius=6)
        self.txt.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ======================================================================
    # LANGUAGE
    # ======================================================================
    def _toggle_language(self):
        self.lang = "ar" if self.lang == "en" else "en"
        self.settings["language"] = self.lang
        save_settings(self.settings)
        self.apply_language()

    def apply_language(self):
        self.lbl_admin.configure(text=(self.t("admin_yes") if is_admin() else self.t("admin_no")))
        self.btn_admin.configure(text=self.t("run_admin"))
        self.btn_admin.configure(state="disabled" if is_admin() else "normal")

        self.cb_select_all.configure(text=self.t("select_all"))
        self.lbl_repair.configure(text=self.t("repair"))
        self.lbl_cleanup.configure(text=self.t("cleanup"))

        self.cb_restore_point.configure(text=self.t("opt_restore_point"))
        self.desc_restore_point.configure(text=self.t("desc_restore_point"))
        self.cb_dism_scan.configure(text=self.t("opt_dism_scan"))
        self.desc_dism_scan.configure(text=self.t("desc_dism_scan"))
        self.cb_dism_restore.configure(text=self.t("opt_dism_restore"))
        self.desc_dism_restore.configure(text=self.t("desc_dism_restore"))
        self.cb_sfc.configure(text=self.t("opt_sfc"))
        self.desc_sfc.configure(text=self.t("desc_sfc"))
        self.cb_chkdsk.configure(text=self.t("opt_chkdsk"))
        self.desc_chkdsk.configure(text=self.t("desc_chkdsk"))
        self.cb_reset_net.configure(text=self.t("opt_reset_net"))
        self.desc_reset_net.configure(text=self.t("desc_reset_net"))

        self.lbl_drive.configure(text=self.t("drive"))
        self.btn_drive_refresh.configure(text=self.t("refresh"))
        self.lbl_mode.configure(text=self.t("mode"))
        self.rb_scan.configure(text=self.t("scan_only"))
        self.rb_fix.configure(text=self.t("fix_f"))

        self.cb_temp.configure(text=self.t("opt_temp"))
        self.desc_temp.configure(text=self.t("desc_temp"))
        self.cb_prefetch.configure(text=self.t("opt_prefetch"))
        self.desc_prefetch.configure(text=self.t("desc_prefetch"))
        self.cb_recycle.configure(text=self.t("opt_recycle"))
        self.desc_recycle.configure(text=self.t("desc_recycle"))
        self.cb_dns.configure(text=self.t("opt_dns"))
        self.desc_dns.configure(text=self.t("desc_dns"))
        self.cb_comp.configure(text=self.t("opt_comp"))
        self.desc_comp.configure(text=self.t("desc_comp"))
        self.cb_wu.configure(text=self.t("opt_wu"))
        self.desc_wu.configure(text=self.t("desc_wu"))

        self.btn_start.configure(text=self.t("start"))
        self.btn_skip.configure(text=self.t("skip"))
        self.btn_cancel.configure(text=self.t("cancel"))
        self.btn_clear.configure(text=self.t("clear_log"))
        self.btn_save_log.configure(text=self.t("save_log"))
        self.lbl_log_title.configure(text=self.t("log"))

        self.refresh_sysinfo()

    # ======================================================================
    # SELECT ALL
    # ======================================================================
    def on_select_all_toggled(self):
        if self._select_all_guard:
            return
        self._select_all_guard = True
        try:
            val = bool(self.var_select_all.get())
            for v in self._all_option_vars:
                v.set(val)
        finally:
            self._select_all_guard = False

    def update_select_all_state(self):
        if self._select_all_guard:
            return
        all_on = all(bool(v.get()) for v in self._all_option_vars)
        self._select_all_guard = True
        try:
            self.var_select_all.set(all_on)
        finally:
            self._select_all_guard = False

    # ======================================================================
    # SYSTEM INFO
    # ======================================================================
    def refresh_sysinfo(self):
        info = {
            "os_version": sysinfo.get_os_version(),
            "cpu": sysinfo.get_cpu_name(),
            "ram": sysinfo.get_ram_info(),
            "disk_space": sysinfo.get_disk_info("C:"),
            "uptime": sysinfo.get_uptime(),
        }
        for key, (lbl_k, lbl_v) in self.sysinfo_labels.items():
            lbl_k.configure(text=self.t(key))
            lbl_v.configure(text=info.get(key, ""))

    # ======================================================================
    # CONTROLS
    # ======================================================================
    def update_chkdsk_controls(self):
        enabled = bool(self.var_chkdsk.get())
        state = "normal" if enabled else "disabled"
        self.drive_combo.configure(state=state)
        self.btn_drive_refresh.configure(state=state)
        self.rb_scan.configure(state=state)
        self.rb_fix.configure(state=state)

    def refresh_drive_list(self):
        drives = list_drives()
        self.drive_combo.configure(values=drives)
        if self.var_drive.get() not in drives:
            self.var_drive.set(drives[0])

    # ======================================================================
    # LOG
    # ======================================================================
    def enqueue_log(self, msg: str):
        self.log_queue.put(msg)

    def flush_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.txt.insert("end", msg + "\n")
                self.txt.see("end")
        except queue.Empty:
            pass
        self.after(80, self.flush_log_queue)

    def on_clear(self):
        self.txt.delete("1.0", "end")

    def on_save_log(self):
        content = self.txt.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo(self.t("log"), self.t("log_empty"), parent=self)
            return
        default_name = f"WindowsFixer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".log", initialfile=default_name,
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo(self.t("log"), self.t("log_saved").format(path=path), parent=self)
            except OSError as e:
                messagebox.showerror("Error", str(e), parent=self)

    # ======================================================================
    # RUN / CANCEL / SKIP
    # ======================================================================
    def set_running(self, running: bool):
        self.running = running
        self.btn_start.configure(state="disabled" if running else "normal")
        self.btn_skip.configure(state="normal" if running else "disabled")
        self.btn_cancel.configure(state="normal" if running else "disabled")
        if not running:
            self.btn_admin.configure(state="disabled" if is_admin() else "normal")

    def _on_run_as_admin(self):
        if not is_admin():
            relaunch_as_admin()

    def on_skip(self):
        if self.running:
            self.runner.request_skip_step()

    def on_cancel(self):
        if self.running:
            self.runner.request_cancel_all()

    def should_abort_now(self):
        return self.runner.cancel_all_requested() or self.runner.skip_requested()

    def run_command_step(self, cmd):
        self.runner.reset_flags_for_step()
        return self.runner.run_cmd(cmd)

    # ======================================================================
    # STEPS
    # ======================================================================
    def build_steps(self):
        steps = []
        if self.var_restore_point.get():
            steps.append(("Create Restore Point", self.step_restore_point))
        if self.var_temp.get() or self.var_prefetch.get():
            steps.append(("Cleanup (Temp/Prefetch)", self.step_temp_prefetch))
        if self.var_recycle_bin.get():
            steps.append(("Empty Recycle Bin", self.step_clear_recycle))
        if self.var_flush_dns.get():
            steps.append(("Flush DNS Cache", self.step_flush_dns))
        if self.var_dism_component_cleanup.get():
            steps.append(("DISM Component Cleanup", self.step_dism_component_cleanup))
        if self.var_wu_cache.get():
            steps.append(("Clear Windows Update Cache", self.step_wu_cache))
        if self.var_dism_scan.get():
            steps.append(("DISM ScanHealth", self.step_dism_scanhealth))
        if self.var_dism_restore.get():
            steps.append(("DISM RestoreHealth", self.step_dism_restorehealth))
        if self.var_sfc.get():
            steps.append(("SFC ScanNow", self.step_sfc))
        if self.var_chkdsk.get():
            drive = self.var_drive.get().strip().upper()
            mode = self.var_chkdsk_mode.get()
            steps.append((f"CHKDSK ({drive}, {mode})", self.step_chkdsk))
        if self.var_reset_network.get():
            steps.append(("Reset Network Stack", self.step_reset_network))
        return steps

    def on_start(self):
        if self.running:
            return
        self.runner.reset_all()
        steps = self.build_steps()
        if not steps:
            messagebox.showwarning(self.t("nothing_selected"), self.t("select_task"), parent=self)
            return
        self.total_steps = len(steps)
        self.progress.set(0)
        self.var_step_text.set("Starting...")
        self.set_running(True)
        self.enqueue_log(f"--- Windows Fixer {APP_VERSION} ---")
        self.enqueue_log("Starting...")
        self.worker_thread = threading.Thread(target=self.worker, args=(steps,), daemon=True)
        self.worker_thread.start()

    def set_progress(self, step_index: int, step_name: str):
        pct = 0 if self.total_steps <= 0 else step_index / self.total_steps
        def _ui():
            self.var_step_text.set(f"Step {step_index}/{self.total_steps}: {step_name}")
            self.progress.set(pct)
        self.after(0, _ui)

    def finish_progress(self, msg="Done"):
        def _ui():
            self.var_step_text.set(msg)
            self.progress.set(1.0)
        self.after(0, _ui)

    # ----- Step implementations -----
    def step_restore_point(self):
        self.runner.reset_flags_for_step()
        if not is_admin():
            self.enqueue_log("[WARN] Restore point requires Admin. Skipping.")
            return "ok"
        create_restore_point(self.enqueue_log)
        if self.runner.cancel_all_requested():
            return "cancel"
        return "ok"

    def step_temp_prefetch(self):
        self.runner.reset_flags_for_step()
        delete_temp_folders(self.var_prefetch.get(), self.enqueue_log, self.should_abort_now)
        if self.runner.cancel_all_requested():
            return "cancel"
        if self.runner.skip_requested():
            return "skip"
        return "ok"

    def step_clear_recycle(self):
        self.runner.reset_flags_for_step()
        clear_recycle_bin(self.enqueue_log)
        return "ok"

    def step_flush_dns(self):
        return self.run_command_step(["ipconfig", "/flushdns"])

    def step_dism_component_cleanup(self):
        return self.run_command_step(["DISM", "/Online", "/Cleanup-Image", "/StartComponentCleanup"])

    def step_wu_cache(self):
        self.runner.reset_flags_for_step()
        if not is_admin():
            self.enqueue_log("[WARN] Windows Update cache cleanup needs Admin. Skipping.")
            return "ok"
        r = self.run_command_step(["net", "stop", "wuauserv"])
        if r in ("cancel", "skip"):
            return r
        r = self.run_command_step(["net", "stop", "bits"])
        if r in ("cancel", "skip"):
            return r
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dl = os.path.join(windir, "SoftwareDistribution", "Download")
        self.enqueue_log(f"[INFO] Cleaning: {dl}")
        try:
            if os.path.exists(dl):
                for name in os.listdir(dl):
                    if self.should_abort_now():
                        return "skip" if self.runner.skip_requested() else "cancel"
                    safe_rmtree(os.path.join(dl, name), self.enqueue_log)
                self.enqueue_log("[OK] Windows Update download cache cleaned.")
            else:
                self.enqueue_log("[INFO] Cache folder not found; skip.")
        except Exception as e:
            self.enqueue_log(f"[WARN] Could not clean Windows Update cache: {e}")
        r = self.run_command_step(["net", "start", "bits"])
        if r in ("cancel", "skip"):
            return r
        return self.run_command_step(["net", "start", "wuauserv"])

    def step_dism_scanhealth(self):
        return self.run_command_step(["DISM", "/Online", "/Cleanup-Image", "/ScanHealth"])

    def step_dism_restorehealth(self):
        return self.run_command_step(["DISM", "/Online", "/Cleanup-Image", "/RestoreHealth"])

    def step_sfc(self):
        return self.run_command_step(["sfc", "/scannow"])

    def step_chkdsk(self):
        drive = self.var_drive.get().strip().upper()
        if not re.fullmatch(r"[A-Z]:", drive):
            self.enqueue_log(f"[ERROR] Invalid drive letter: {drive}")
            return "error"
        mode = self.var_chkdsk_mode.get()
        if mode == "scan":
            return self.run_command_step(["chkdsk", drive])
        self.enqueue_log("[INFO] Fix mode may require restart (Windows may ask to schedule it).")
        return self.run_command_step(["chkdsk", drive, "/f"])

    def step_reset_network(self):
        r = self.run_command_step(["netsh", "winsock", "reset"])
        if r in ("cancel", "skip"):
            return r
        return self.run_command_step(["netsh", "int", "ip", "reset"])

    def worker(self, steps):
        try:
            for idx, (name, fn) in enumerate(steps, start=1):
                if self.runner.cancel_all_requested():
                    self.enqueue_log("[INFO] Cancelled. Stopping all steps.")
                    self.finish_progress("Cancelled")
                    return
                self.set_progress(idx, name)
                result = fn()
                if result == "cancel":
                    self.enqueue_log("[INFO] Cancelled. Stopping all steps.")
                    self.finish_progress("Cancelled")
                    return
                if result == "skip":
                    self.enqueue_log(f"[INFO] Step skipped: {name}")
                    continue
            self.finish_progress("Done")
            self.enqueue_log("All selected tasks finished.")
            self.after(200, lambda: play_success_sound(self.enqueue_log))
        except Exception as e:
            self.enqueue_log(f"[ERROR] {e}")
        finally:
            self.after(0, lambda: self.set_running(False))

    # ======================================================================
    # ABOUT DIALOG
    # ======================================================================
    def show_about(self):
        win = ctk.CTkToplevel(self)
        win.title("About" if self.lang == "en" else "حول")
        win.resizable(False, False)
        win.geometry("540x620")
        apply_icon_to_tlv(win, self.icon_path)

        # Header
        ctk.CTkLabel(
            win, text="WINDOWS FIXER",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(pady=(28, 4))

        ctk.CTkLabel(
            win, text=f"{APP_VERSION}  /  Build {BUILD_DATE}",
            font=ctk.CTkFont(size=12), text_color="gray",
        ).pack(pady=(0, 8))

        tagline = (
            "A freeware Windows repair & cleanup tool.\n"
            "SFC, DISM, CHKDSK and safe cleanup - all in one place."
            if self.lang == "en"
            else "أداة مجانية لإصلاح وتنظيف ويندوز.\n"
            "SFC و DISM و CHKDSK مع عمليات تنظيف آمنة."
        )
        ctk.CTkLabel(
            win, text=tagline,
            font=ctk.CTkFont(size=13), text_color="gray",
            wraplength=440, justify="center",
        ).pack(pady=(0, 16))

        # Credits cards in a row
        cards = ctk.CTkFrame(win, fg_color="transparent")
        cards.pack(fill="x", padx=24, pady=(0, 12))
        cards.grid_columnconfigure(0, weight=1)
        cards.grid_columnconfigure(1, weight=1)

        # Original author card
        orig = ctk.CTkFrame(cards, corner_radius=8, border_width=1, border_color=ACCENT_BLUE)
        orig.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(
            orig, text="ORIGINAL AUTHOR" if self.lang == "en" else "المطور الأصلي",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_BLUE,
        ).pack(anchor="w", padx=14, pady=(12, 2))

        orig_name = ctk.CTkFrame(orig, fg_color="transparent")
        orig_name.pack(anchor="w", padx=14, pady=(0, 4))
        ctk.CTkLabel(
            orig_name, text="ilukezippo (BoYaqoub)",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        flag_kw = load_flag_image("kuwait")
        if flag_kw:
            fl = tk.Label(orig_name, image=flag_kw, bd=0, highlightthickness=0)
            fl.pack(side="left", padx=(8, 0))
            win._flag_kw = flag_kw

        orig_link = ctk.CTkButton(
            orig, text="View original project", width=160, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="transparent", border_width=1,
            command=lambda: webbrowser.open(GITHUB_PAGE_ORIGINAL),
        )
        orig_link.pack(anchor="w", padx=14, pady=(0, 12))

        # Fork maintainer card
        fork = ctk.CTkFrame(cards, corner_radius=8, border_width=1, border_color=ACCENT_GREEN)
        fork.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        ctk.CTkLabel(
            fork, text="FORK MAINTAINER" if self.lang == "en" else "مشرف الفورك",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_GREEN,
        ).pack(anchor="w", padx=14, pady=(12, 2))

        fork_name = ctk.CTkFrame(fork, fg_color="transparent")
        fork_name.pack(anchor="w", padx=14, pady=(0, 4))
        ctk.CTkLabel(
            fork_name, text="Khalid El Merrah",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")

        flag_ma = load_flag_image("morocco")
        if flag_ma:
            fl2 = tk.Label(fork_name, image=flag_ma, bd=0, highlightthickness=0)
            fl2.pack(side="left", padx=(8, 0))
            win._flag_ma = flag_ma

        fork_link = ctk.CTkButton(
            fork, text="View fork", width=100, height=26,
            font=ctk.CTkFont(size=11),
            fg_color="transparent", border_width=1,
            command=lambda: webbrowser.open(GITHUB_PAGE_FORK),
        )
        fork_link.pack(anchor="w", padx=14, pady=(0, 12))

        # Feature chips
        ctk.CTkLabel(
            win,
            text="WHAT'S NEW IN THIS FORK" if self.lang == "en" else "ما الجديد في هذا الفورك",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=ACCENT_BLUE,
        ).pack(anchor="w", padx=30, pady=(4, 8))

        chips_data = [
            ("9 Security Fixes", ACCENT_RED),
            ("Restore Points", ACCENT_BLUE),
            ("System Info", ACCENT_GREEN),
            ("Dark Theme", "#5c2d91"),
            ("Log Export", ACCENT_GOLD),
            ("Modular Code", "#567c73"),
        ] if self.lang == "en" else [
            ("9 إصلاحات أمنية", ACCENT_RED),
            ("نقاط استعادة", ACCENT_BLUE),
            ("معلومات النظام", ACCENT_GREEN),
            ("مظهر داكن", "#5c2d91"),
            ("حفظ السجل", ACCENT_GOLD),
            ("كود معياري", "#567c73"),
        ]

        row1 = ctk.CTkFrame(win, fg_color="transparent")
        row1.pack(anchor="w", padx=30, pady=2)
        row2 = ctk.CTkFrame(win, fg_color="transparent")
        row2.pack(anchor="w", padx=30, pady=2)

        for i, (text, color) in enumerate(chips_data):
            parent = row1 if i < 3 else row2
            ctk.CTkButton(
                parent, text=text, height=26, width=len(text) * 9 + 20,
                font=ctk.CTkFont(size=11), text_color=color,
                fg_color="transparent", border_width=1, border_color=color,
                hover=False, corner_radius=12,
            ).pack(side="left", padx=(0, 6))

        # Bottom buttons
        bottom = ctk.CTkFrame(win, fg_color="transparent")
        bottom.pack(pady=(20, 24))

        ctk.CTkButton(
            bottom,
            text="Donate to Original Author" if self.lang == "en" else "تبرع للمطور الأصلي",
            width=200, height=36,
            fg_color=ACCENT_GOLD, hover_color="#b37a08",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: webbrowser.open(DONATE_PAGE),
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            bottom,
            text="Close" if self.lang == "en" else "إغلاق",
            width=80, height=36,
            fg_color="transparent", border_width=1,
            command=win.destroy,
        ).pack(side="left")

        self._center_child(win)
