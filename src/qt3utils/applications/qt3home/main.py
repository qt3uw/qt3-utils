"""Launcher that starts QT3 GUI applications in separate processes."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Optional


def _qt3move_working_dir() -> Optional[str]:
    spec = importlib.util.find_spec("qt3utils.applications.qt3move.main")
    if spec is None or not spec.origin:
        return None
    return str(Path(spec.origin).resolve().parent)


def _launch_app(module: str, cwd: Optional[str] = None) -> None:
    cmd = [sys.executable, "-m", module]
    try:
        subprocess.Popen(
            cmd,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as e:
        messagebox.showerror("Could not start application", f"{module}\n{e}")


def main() -> None:
    root = tk.Tk()
    root.title("QT3 Home")
    root.resizable(False, False)
    root.minsize(254, 360)
    root.geometry("254x360")

    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    btn_font = ("Segoe UI", 9) if sys.platform == "win32" else ("TkDefaultFont", 9)
    move_cwd = _qt3move_working_dir()

    body = tk.Frame(root)
    body.grid(row=0, column=0)

    apps = [
        ("Qt3 Move", "qt3utils.applications.qt3move.main", move_cwd),
        ("Qt3 Power", "qt3utils.applications.qt3power.main", None),
        ("Qt3 Santec", "qt3utils.applications.qt3santec.main", None),
        ("Qt3 Scan", "qt3utils.applications.qt3scan.main", None),
        ("Qt3 Scope", "qt3utils.applications.qt3scope.main", None),
        ("Qt3 Mirror", "qt3utils.applications.qt3mirror.main", None),
    ]

    for i, (label, mod, cwd) in enumerate(apps):
        btn = tk.Button(
            body,
            text=label,
            width=14,
            height=2,
            font=btn_font,
            command=lambda m=mod, c=cwd: _launch_app(m, c),
        )
        btn.grid(row=i, column=0, padx=10, pady=5)

    root.mainloop()


if __name__ == "__main__":
    main()
