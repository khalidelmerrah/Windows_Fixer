"""System information gathering for the System Info panel."""

import os
import ctypes
import platform
import subprocess


def get_os_version() -> str:
    """Get Windows version string."""
    edition = platform.win32_edition() if hasattr(platform, "win32_edition") else ""
    ver = platform.version()
    build = platform.win32_ver()[1] if hasattr(platform, "win32_ver") else ""
    return f"Windows {edition} {ver} (Build {build})".strip()


def get_cpu_name() -> str:
    """Get CPU model name from registry."""
    try:
        result = subprocess.run(
            ["wmic", "cpu", "get", "Name", "/value"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().splitlines():
            if line.startswith("Name="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "Unknown"


def get_ram_info() -> str:
    """Get total and available RAM."""
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))

        total_gb = mem.ullTotalPhys / (1024 ** 3)
        avail_gb = mem.ullAvailPhys / (1024 ** 3)
        used_pct = mem.dwMemoryLoad
        return f"{total_gb:.1f} GB total, {avail_gb:.1f} GB free ({used_pct}% used)"
    except Exception:
        return "Unknown"


def get_disk_info(drive: str = "C:") -> str:
    """Get disk space for the specified drive."""
    try:
        free_bytes = ctypes.c_ulonglong(0)
        total_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            f"{drive}\\",
            None,
            ctypes.byref(total_bytes),
            ctypes.byref(free_bytes),
        )
        total_gb = total_bytes.value / (1024 ** 3)
        free_gb = free_bytes.value / (1024 ** 3)
        used_pct = int((1 - free_gb / total_gb) * 100) if total_gb > 0 else 0
        return f"{drive}\\ {total_gb:.0f} GB total, {free_gb:.1f} GB free ({used_pct}% used)"
    except Exception:
        return f"{drive}\\ Unknown"


def get_uptime() -> str:
    """Get system uptime."""
    try:
        ticks = ctypes.windll.kernel32.GetTickCount64()
        seconds = ticks // 1000
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        return " ".join(parts)
    except Exception:
        return "Unknown"
