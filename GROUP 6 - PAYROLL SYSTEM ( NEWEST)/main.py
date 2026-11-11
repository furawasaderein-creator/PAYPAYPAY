from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import messagebox

from config import ensure_directories
from payroll_app.application import PayrollApp


def main() -> None:
    """Launch the payroll application."""
    try:
        app = PayrollApp()
        app.mainloop()
    except (tk.TclError, sqlite3.Error, OSError) as exc:  # pragma: no cover - top-level UI guard
        messagebox.showerror("Application Error", str(exc))

if __name__ == "__main__":
    ensure_directories()
    main()
