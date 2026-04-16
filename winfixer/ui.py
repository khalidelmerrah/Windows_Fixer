"""Main application UI for Windows Fixer."""

import os
import re
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
from datetime import datetime

from winfixer.constants import (
    APP_VERSION, BUILD_DATE, WIN_W, WIN_H,
    DONATE_PAGE, GITHUB_PAGE, GITHUB_API_LATEST, GITHUB_RELEASES_PAGE,
)
from winfixer.utils import (
    set_app_icon, apply_icon_to_tlv, load_flag_image, make_donate_image,
    play_success_sound, load_settings, save_settings, is_admin, relaunch_as_admin,
    list_drives,
)
from winfixer.commands import (
    CommandRunner, delete_temp_folders, clear_recycle_bin, create_restore_point,
    safe_rmtree,
)
from winfixer.translations import translate
from winfixer import sysinfo


# ---------- Dark/Light theme colors ----------

THEMES = {
    "light": {
        "bg": "#f0f0f0",
        "fg": "#000000",
        "text_bg": "#ffffff",
        "text_fg": "#000000",
        "desc_fg": "#666666",
        "link_fg": "#1a73e8",
        "accent": "#0078d4",
        "sysinfo_bg": "#e8f0fe",
        "sysinfo_fg": "#1a3a5c",
    },
    "dark": {
        "bg": "#1e1e1e",
        "fg": "#d4d4d4",
        "text_bg": "#252526",
        "text_fg": "#cccccc",
        "desc_fg": "#888888",
        "link_fg": "#569cd6",
        "accent": "#569cd6",
        "sysinfo_bg": "#2d2d30",
        "sysinfo_fg": "#9cdcfe",
    },
}


def add_option_with_desc(parent, text, desc, variable, wrap=560, desc_fg="#666666"):
    row = ttk.Frame(parent)
    row.pack(fill="x", anchor="w", pady=(6, 0))

    cb = ttk.Checkbutton(row, text=text, variable=variable)
    cb.pack(anchor="w")

    lbl = ttk.Label(row, text=desc, foreground=desc_fg, wraplength=wrap)
    lbl.pack(anchor="w", padx=(26, 0))
    return cb, lbl


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.withdraw()

        self.settings = load_settings()
        self.lang = self.settings.get("language", "en")
        self.current_theme = self.settings.get("theme", "light")
        self.var_always_admin = tk.BooleanVar(value=bool(self.settings.get("always_admin", False)))

        self.icon_path = set_app_icon(self)

        self.log_queue = queue.Queue()
        self.runner = CommandRunner(self.enqueue_log)
        self.worker_thread = None
        self.running = False

        self.var_select_all = tk.BooleanVar(value=False)
        self._select_all_guard = False

        # Repair options
        self.var_restore_point = tk.BooleanVar(value=True)
        self.var_dism_scan = tk.BooleanVar(value=False)
        self.var_dism_restore = tk.BooleanVar(value=True)
        self.var_sfc = tk.BooleanVar(value=True)
        self.var_chkdsk = tk.BooleanVar(value=False)
        self.var_chkdsk_mode = tk.StringVar(value="scan")
        self.var_drive = tk.StringVar(value="C:")
        self.var_reset_network = tk.BooleanVar(value=False)

        # Cleanup options
        self.var_temp = tk.BooleanVar(value=True)
        self.var_prefetch = tk.BooleanVar(value=False)
        self.var_recycle_bin = tk.BooleanVar(value=True)
        self.var_flush_dns = tk.BooleanVar(value=False)
        self.var_dism_component_cleanup = tk.BooleanVar(value=False)
        self.var_wu_cache = tk.BooleanVar(value=False)

        self._all_option_vars = [
            self.var_restore_point,
            self.var_dism_scan,
            self.var_dism_restore,
            self.var_sfc,
            self.var_chkdsk,
            self.var_reset_network,
            self.var_temp,
            self.var_prefetch,
            self.var_recycle_bin,
            self.var_flush_dns,
            self.var_dism_component_cleanup,
            self.var_wu_cache,
        ]

        self.var_step_text = tk.StringVar(value="Idle")
        self.total_steps = 0

        self.title(f"Windows Fixer {APP_VERSION}")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(1180, 880)

        self.create_menu()
        self.create_ui()
        self.refresh_drive_list()

        self.var_chkdsk.trace_add("write", lambda *_: self.update_chkdsk_controls())
        self.update_chkdsk_controls()

        for v in self._all_option_vars:
            v.trace_add("write", lambda *_: self.update_select_all_state())

        self.var_select_all.trace_add("write", lambda *_: self.on_select_all_toggled())

        self.after(80, self.flush_log_queue)
        self.apply_language()
        self.apply_theme()
        self.update_select_all_state()

        self.after(800, lambda: self.check_latest_app_version_async(show_if_latest=False))

        self.deiconify()
        self.after(50, self.center_window)
        self.lift()
        self.focus_force()

    # ---------- Translation helper ----------
    def t(self, key: str) -> str:
        return translate(self.lang, key)

    # ---------- Theme ----------
    def apply_theme(self):
        colors = THEMES[self.current_theme]

        self.configure(bg=colors["bg"])

        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background=colors["bg"], foreground=colors["fg"])
        style.configure("TFrame", background=colors["bg"])
        style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        style.configure("TLabelframe", background=colors["bg"], foreground=colors["fg"])
        style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg"])
        style.configure("TCheckbutton", background=colors["bg"], foreground=colors["fg"])
        style.configure("TRadiobutton", background=colors["bg"], foreground=colors["fg"])
        style.configure("TButton", background=colors["bg"], foreground=colors["fg"])
        style.configure("Desc.TLabel", background=colors["bg"], foreground=colors["desc_fg"])
        style.configure("SysInfo.TLabel", background=colors["sysinfo_bg"], foreground=colors["sysinfo_fg"])
        style.configure("SysInfo.TFrame", background=colors["sysinfo_bg"])

        if hasattr(self, "txt"):
            self.txt.configure(bg=colors["text_bg"], fg=colors["text_fg"],
                               insertbackground=colors["text_fg"])

        # Update desc labels to use theme color
        if hasattr(self, "desc_dism_scan"):
            for attr_name in dir(self):
                if attr_name.startswith("desc_"):
                    widget = getattr(self, attr_name, None)
                    if isinstance(widget, (ttk.Label, tk.Label)):
                        try:
                            widget.configure(foreground=colors["desc_fg"])
                        except Exception:
                            pass

        # Update sysinfo panel
        if hasattr(self, "sysinfo_frame"):
            self.sysinfo_frame.configure(style="SysInfo.TFrame")
            for child in self.sysinfo_frame.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(style="SysInfo.TLabel")

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.settings["theme"] = self.current_theme
        save_settings(self.settings)
        self.apply_theme()

    # ---------- Update checker ----------
    def _parse_ver_tuple(self, v: str):
        return tuple(int(n) for n in re.findall(r"\d+", v)[:4]) or (0,)

    def manual_check_for_update(self):
        self.check_latest_app_version_async(show_if_latest=True)

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
                else:
                    if show_if_latest:
                        def _info():
                            messagebox.showinfo(self.t("update_title"), self.t("update_latest"), parent=self)
                        self.after(0, _info)

            except Exception:
                if show_if_latest:
                    def _err():
                        messagebox.showwarning(self.t("update_title"), self.t("update_failed"), parent=self)
                    self.after(0, _err)

        threading.Thread(target=worker, daemon=True).start()

    # ---------- Center ----------
    def center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def center_child(self, tlv):
        tlv.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - tlv.winfo_width()) // 2
        y = self.winfo_y() + (self.winfo_height() - tlv.winfo_height()) // 2
        tlv.geometry(f"+{x}+{y}")

    # ---------- Menu ----------
    def create_menu(self):
        menubar = tk.Menu(self)

        self.file_menu = tk.Menu(menubar, tearoff=0)
        self.file_menu.add_checkbutton(
            label=("Always run as admin" if self.lang == "en" else "تشغيل دائم كمسؤول"),
            variable=self.var_always_admin,
            command=self.on_toggle_always_admin,
        )
        self.file_menu.add_separator()

        self.lang_menu = tk.Menu(self.file_menu, tearoff=0)
        self.lang_var = tk.StringVar(value=self.lang)
        self.lang_menu.add_radiobutton(label="English", value="en", variable=self.lang_var, command=self.on_change_language)
        self.lang_menu.add_radiobutton(label="العربية", value="ar", variable=self.lang_var, command=self.on_change_language)
        self.file_menu.add_cascade(label=self.t("theme"), menu=self.lang_menu)

        # Theme submenu
        self.theme_menu = tk.Menu(self.file_menu, tearoff=0)
        self.theme_var = tk.StringVar(value=self.current_theme)
        self.theme_menu.add_radiobutton(
            label=self.t("theme_light"), value="light",
            variable=self.theme_var, command=self.on_change_theme,
        )
        self.theme_menu.add_radiobutton(
            label=self.t("theme_dark"), value="dark",
            variable=self.theme_var, command=self.on_change_theme,
        )

        # Fix: language cascade label should be Language, not Theme
        self.file_menu.delete(2)  # remove the wrongly-labeled cascade
        self.file_menu.add_cascade(label=("Language" if self.lang == "en" else "اللغة"), menu=self.lang_menu)
        self.file_menu.add_cascade(label=self.t("theme"), menu=self.theme_menu)

        self.file_menu.add_separator()
        self.file_menu.add_command(label=("Check for Updates" if self.lang == "en" else "التحقق من التحديثات"), command=self.manual_check_for_update)
        self.file_menu.add_command(label=("About" if self.lang == "en" else "حول"), command=self.show_about)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=("Exit" if self.lang == "en" else "خروج"), command=self.destroy)

        menubar.add_cascade(label=("File" if self.lang == "en" else "ملف"), menu=self.file_menu)
        self.config(menu=menubar)

    def on_toggle_always_admin(self):
        self.settings["always_admin"] = bool(self.var_always_admin.get())
        save_settings(self.settings)
        if self.var_always_admin.get() and not is_admin():
            relaunch_as_admin()

    def on_change_language(self):
        self.lang = self.lang_var.get()
        self.settings["language"] = self.lang
        save_settings(self.settings)
        self.create_menu()
        self.apply_language()

    def on_change_theme(self):
        self.current_theme = self.theme_var.get()
        self.settings["theme"] = self.current_theme
        save_settings(self.settings)
        self.apply_theme()

    # ---------- Language ----------
    def apply_language(self):
        self.lbl_admin.config(text=(self.t("admin_yes") if is_admin() else self.t("admin_no")))
        self.btn_admin.config(text=self.t("run_admin"))
        self.opts_group.config(text=self.t("choose_fix"))
        self.cb_select_all.config(text=self.t("select_all"))
        self.lbl_repair.config(text=self.t("repair"))
        self.lbl_cleanup.config(text=self.t("cleanup"))
        self.cb_restore_point.config(text=self.t("opt_restore_point"))
        self.desc_restore_point.config(text=self.t("desc_restore_point"))
        self.cb_dism_scan.config(text=self.t("opt_dism_scan"))
        self.desc_dism_scan.config(text=self.t("desc_dism_scan"))
        self.cb_dism_restore.config(text=self.t("opt_dism_restore"))
        self.desc_dism_restore.config(text=self.t("desc_dism_restore"))
        self.cb_sfc.config(text=self.t("opt_sfc"))
        self.desc_sfc.config(text=self.t("desc_sfc"))
        self.cb_chkdsk.config(text=self.t("opt_chkdsk"))
        self.desc_chkdsk.config(text=self.t("desc_chkdsk"))
        self.cb_reset_net.config(text=self.t("opt_reset_net"))
        self.desc_reset_net.config(text=self.t("desc_reset_net"))
        self.lbl_drive.config(text=self.t("drive"))
        self.btn_drive_refresh.config(text=self.t("refresh"))
        self.lbl_mode.config(text=self.t("mode"))
        self.rb_scan.config(text=self.t("scan_only"))
        self.rb_fix.config(text=self.t("fix_f"))
        self.cb_temp.config(text=self.t("opt_temp"))
        self.desc_temp.config(text=self.t("desc_temp"))
        self.cb_prefetch.config(text=self.t("opt_prefetch"))
        self.desc_prefetch.config(text=self.t("desc_prefetch"))
        self.cb_recycle.config(text=self.t("opt_recycle"))
        self.desc_recycle.config(text=self.t("desc_recycle"))
        self.cb_dns.config(text=self.t("opt_dns"))
        self.desc_dns.config(text=self.t("desc_dns"))
        self.cb_comp.config(text=self.t("opt_comp"))
        self.desc_comp.config(text=self.t("desc_comp"))
        self.cb_wu.config(text=self.t("opt_wu"))
        self.desc_wu.config(text=self.t("desc_wu"))
        self.prog_group.config(text=self.t("progress"))
        self.log_group.config(text=self.t("log"))
        self.btn_start.config(text=self.t("start"))
        self.btn_skip.config(text=self.t("skip"))
        self.btn_cancel.config(text=self.t("cancel"))
        self.btn_clear.config(text=self.t("clear_log"))
        self.btn_save_log.config(text=self.t("save_log"))
        self.sysinfo_group.config(text=self.t("sys_info"))
        self.refresh_admin_ui()
        self.refresh_sysinfo()

    # ---------- Select All ----------
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

    # ---------- UI ----------
    def create_ui(self):
        # Top bar: admin status
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")

        self.lbl_admin = ttk.Label(top, text="")
        self.lbl_admin.pack(side="left")

        self.btn_admin = ttk.Button(top, text="", command=self.on_run_as_admin)
        self.btn_admin.pack(side="right")

        # System Info panel
        self.sysinfo_group = ttk.LabelFrame(self, text="", padding=8)
        self.sysinfo_group.pack(fill="x", padx=12, pady=(0, 8))

        self.sysinfo_frame = ttk.Frame(self.sysinfo_group, style="SysInfo.TFrame")
        self.sysinfo_frame.pack(fill="x", padx=4, pady=4)

        self.sysinfo_labels = {}
        for i, key in enumerate(["os_version", "cpu", "ram", "disk_space", "uptime"]):
            lbl_key = ttk.Label(self.sysinfo_frame, text="", style="SysInfo.TLabel", font=("Segoe UI", 9, "bold"))
            lbl_key.grid(row=i // 3, column=(i % 3) * 2, sticky="w", padx=(8, 4), pady=2)
            lbl_val = ttk.Label(self.sysinfo_frame, text="", style="SysInfo.TLabel", font=("Segoe UI", 9))
            lbl_val.grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=(0, 20), pady=2)
            self.sysinfo_labels[key] = (lbl_key, lbl_val)

        # Options group
        self.opts_group = ttk.LabelFrame(self, text="", padding=12)
        self.opts_group.pack(fill="x", padx=12, pady=8)

        sa_row = ttk.Frame(self.opts_group)
        sa_row.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.cb_select_all = ttk.Checkbutton(sa_row, text="", variable=self.var_select_all)
        self.cb_select_all.pack(anchor="w")

        left = ttk.Frame(self.opts_group)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 18))

        right = ttk.Frame(self.opts_group)
        right.grid(row=1, column=1, sticky="nsew")

        # Left column: Repair
        self.lbl_repair = ttk.Label(left, text="", font=("Segoe UI", 10, "bold"))
        self.lbl_repair.pack(anchor="w")

        self.cb_restore_point, self.desc_restore_point = add_option_with_desc(left, "", "", self.var_restore_point, wrap=640)
        self.cb_dism_scan, self.desc_dism_scan = add_option_with_desc(left, "", "", self.var_dism_scan, wrap=640)
        self.cb_dism_restore, self.desc_dism_restore = add_option_with_desc(left, "", "", self.var_dism_restore, wrap=640)
        self.cb_sfc, self.desc_sfc = add_option_with_desc(left, "", "", self.var_sfc, wrap=640)

        ch_row = ttk.Frame(left)
        ch_row.pack(fill="x", anchor="w", pady=(6, 0))
        self.cb_chkdsk = ttk.Checkbutton(ch_row, text="", variable=self.var_chkdsk)
        self.cb_chkdsk.pack(anchor="w")
        self.desc_chkdsk = ttk.Label(ch_row, text="", foreground="#666666", wraplength=640)
        self.desc_chkdsk.pack(anchor="w", padx=(26, 0))

        sub = ttk.Frame(left)
        sub.pack(anchor="w", pady=(6, 0), padx=(26, 0))
        self.lbl_drive = ttk.Label(sub, text="")
        self.lbl_drive.pack(side="left")

        self.drive_combo = ttk.Combobox(sub, width=8, textvariable=self.var_drive, state="readonly")
        self.drive_combo.pack(side="left", padx=(6, 10))

        self.btn_drive_refresh = ttk.Button(sub, text="", command=self.refresh_drive_list)
        self.btn_drive_refresh.pack(side="left")

        mode = ttk.Frame(left)
        mode.pack(anchor="w", pady=(6, 0), padx=(26, 0))
        self.lbl_mode = ttk.Label(mode, text="")
        self.lbl_mode.pack(side="left")

        self.rb_scan = ttk.Radiobutton(mode, text="", value="scan", variable=self.var_chkdsk_mode)
        self.rb_scan.pack(side="left", padx=8)

        self.rb_fix = ttk.Radiobutton(mode, text="", value="fix", variable=self.var_chkdsk_mode)
        self.rb_fix.pack(side="left", padx=8)

        self.cb_reset_net, self.desc_reset_net = add_option_with_desc(left, "", "", self.var_reset_network, wrap=640)

        # Right column: Cleanup
        self.lbl_cleanup = ttk.Label(right, text="", font=("Segoe UI", 10, "bold"))
        self.lbl_cleanup.pack(anchor="w")

        self.cb_temp, self.desc_temp = add_option_with_desc(right, "", "", self.var_temp, wrap=520)
        self.cb_prefetch, self.desc_prefetch = add_option_with_desc(right, "", "", self.var_prefetch, wrap=520)
        self.cb_recycle, self.desc_recycle = add_option_with_desc(right, "", "", self.var_recycle_bin, wrap=520)
        self.cb_dns, self.desc_dns = add_option_with_desc(right, "", "", self.var_flush_dns, wrap=520)
        self.cb_comp, self.desc_comp = add_option_with_desc(right, "", "", self.var_dism_component_cleanup, wrap=520)
        self.cb_wu, self.desc_wu = add_option_with_desc(right, "", "", self.var_wu_cache, wrap=520)

        self.opts_group.grid_columnconfigure(0, weight=1)
        self.opts_group.grid_columnconfigure(1, weight=1)

        # Progress
        self.prog_group = ttk.LabelFrame(self, text="", padding=10)
        self.prog_group.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(self.prog_group, textvariable=self.var_step_text).pack(anchor="w")
        self.progress = ttk.Progressbar(self.prog_group, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill="x", pady=6)

        # Buttons
        btns = ttk.Frame(self, padding=(12, 0, 12, 0))
        btns.pack(fill="x")

        self.btn_start = ttk.Button(btns, text="", command=self.on_start)
        self.btn_start.pack(side="left")

        self.btn_skip = ttk.Button(btns, text="", command=self.on_skip, state="disabled")
        self.btn_skip.pack(side="left", padx=8)

        self.btn_cancel = ttk.Button(btns, text="", command=self.on_cancel, state="disabled")
        self.btn_cancel.pack(side="left")

        self.btn_save_log = ttk.Button(btns, text="", command=self.on_save_log)
        self.btn_save_log.pack(side="right")

        self.btn_clear = ttk.Button(btns, text="", command=self.on_clear)
        self.btn_clear.pack(side="right", padx=(0, 8))

        # Log area
        self.log_group = ttk.LabelFrame(self, text="", padding=8)
        self.log_group.pack(fill="both", expand=True, padx=12, pady=10)

        self.txt = tk.Text(self.log_group, wrap="word")
        self.txt.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(self.log_group, orient="vertical", command=self.txt.yview)
        sb.pack(side="right", fill="y")
        self.txt.config(yscrollcommand=sb.set)

    # ---------- System Info ----------
    def refresh_sysinfo(self):
        info = {
            "os_version": sysinfo.get_os_version(),
            "cpu": sysinfo.get_cpu_name(),
            "ram": sysinfo.get_ram_info(),
            "disk_space": sysinfo.get_disk_info("C:"),
            "uptime": sysinfo.get_uptime(),
        }
        for key, (lbl_key, lbl_val) in self.sysinfo_labels.items():
            lbl_key.config(text=self.t(key))
            lbl_val.config(text=info.get(key, ""))

    def refresh_admin_ui(self):
        self.btn_admin.config(state="disabled" if is_admin() else "normal")

    def update_chkdsk_controls(self):
        enabled = bool(self.var_chkdsk.get())
        self.drive_combo.config(state=("readonly" if enabled else "disabled"))
        self.btn_drive_refresh.config(state=("normal" if enabled else "disabled"))
        self.rb_scan.config(state=("normal" if enabled else "disabled"))
        self.rb_fix.config(state=("normal" if enabled else "disabled"))

    def refresh_drive_list(self):
        drives = list_drives()
        self.drive_combo["values"] = drives
        if self.var_drive.get() not in drives:
            self.var_drive.set(drives[0])

    # ---------- Log ----------
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
            parent=self,
            defaultextension=".log",
            initialfile=default_name,
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo(self.t("log"), self.t("log_saved").format(path=path), parent=self)
            except OSError as e:
                messagebox.showerror("Error", str(e), parent=self)

    # ---------- Run/Cancel/Skip ----------
    def set_running(self, running: bool):
        self.running = running
        self.btn_start.config(state="disabled" if running else "normal")
        self.btn_skip.config(state="normal" if running else "disabled")
        self.btn_cancel.config(state="normal" if running else "disabled")
        if not running:
            self.refresh_admin_ui()

    def on_run_as_admin(self):
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

    # ---------- Steps ----------
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
            messagebox.showwarning(
                self.t("nothing_selected"),
                self.t("select_task"),
                parent=self,
            )
            return

        self.total_steps = len(steps)
        self.progress["value"] = 0
        self.var_step_text.set("Starting...")

        self.set_running(True)
        self.enqueue_log(f"--- Windows Fixer {APP_VERSION} ---")
        self.enqueue_log("Starting...")

        self.worker_thread = threading.Thread(target=self.worker, args=(steps,), daemon=True)
        self.worker_thread.start()

    def set_progress(self, step_index: int, step_name: str):
        pct = 0 if self.total_steps <= 0 else int((step_index / self.total_steps) * 100)

        def _ui():
            self.var_step_text.set(f"Step {step_index}/{self.total_steps}: {step_name}")
            self.progress["value"] = pct

        self.after(0, _ui)

    def finish_progress(self, msg="Done"):
        def _ui():
            self.var_step_text.set(msg)
            self.progress["value"] = 100

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

    # ---------- About ----------
    def show_about(self):
        win = tk.Toplevel(self)
        win.title("About" if self.lang == "en" else "حول")
        win.resizable(False, False)
        apply_icon_to_tlv(win, self.icon_path)

        frame = ttk.Frame(win, padding=16)
        frame.pack(fill="both", expand=True)

        title = "Windows Fixer"
        sub = (
            "is a freeware Windows repair & cleanup tool.\nRuns SFC, DISM, CHKDSK and safe cleanup tasks."
            if self.lang == "en"
            else "أداة مجانية لإصلاح وتنظيف ويندوز.\nتشغل SFC و DISM و CHKDSK مع عمليات تنظيف آمنة."
        )

        tk.Label(frame, text=title, font=("Segoe UI", 14, "bold")).pack(pady=(0, 4))
        tk.Label(frame, text=sub, wraplength=520, justify="center").pack(pady=(0, 8))
        tk.Label(frame, text=f"Version {APP_VERSION} - {BUILD_DATE}").pack(pady=(0, 10))

        row = ttk.Frame(frame)
        row.pack()
        tk.Label(row, text="Author: ilukezippo (BoYaqoub)").pack(side="left")

        flag = load_flag_image()
        if flag:
            tk.Label(row, image=flag).pack(side="left", padx=(6, 0))
            win._flag = flag

        link_row = ttk.Frame(frame)
        link_row.pack(pady=(8, 0))
        tk.Label(link_row, text=("Info and Latest Updates at " if self.lang == "en" else "المعلومات وآخر التحديثات: ")).pack(
            side="left"
        )
        link = tk.Label(
            link_row,
            text=GITHUB_PAGE,
            fg=THEMES[self.current_theme]["link_fg"],
            cursor="hand2",
            font=("Segoe UI", 9, "underline"),
        )
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: webbrowser.open(GITHUB_PAGE))

        donate_img = make_donate_image(160, 44)
        win._don = donate_img
        tk.Button(
            frame,
            image=donate_img,
            text=("Donate" if self.lang == "en" else "تبرع"),
            compound="center",
            font=("Segoe UI", 11, "bold"),
            fg="#0f3462",
            activeforeground="#0f3462",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            relief="flat",
            command=lambda: webbrowser.open(DONATE_PAGE),
        ).pack(pady=(12, 0))

        ttk.Button(frame, text=("Close" if self.lang == "en" else "إغلاق"), command=win.destroy).pack(pady=(10, 0))
        self.center_child(win)
