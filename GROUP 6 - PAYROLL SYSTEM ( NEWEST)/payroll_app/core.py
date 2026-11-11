from __future__ import annotations

import sqlite3
import sys
from collections.abc import Collection
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk
from typing import Any

from config import (
    ACCENT_BLUE,
    ASSETS_DIR,
    APP_NAME,
    APP_VERSION,
    BACKGROUND_COLOR,
    DEFAULT_FONT,
    DANGER_COLOR,
    GOLD_COLOR,
    HEADING_FONT,
    LARGE_NUM_FONT,
    MUTED_COLOR,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
    SUCCESS_COLOR,
    TEXT_COLOR,
    TITLE_FONT,
    WHITE,
)
from database.database import DatabaseManager
from .calculations import (
    calculate_attendance_hours,
    calculate_hourly_gross,
    calculate_late_minutes,
    calculate_paid_leave_hours,
    calculate_philippine_deductions,
    is_full_calendar_month,
)
from .widgets import DatePicker, PayrollTreeview, RoundedCard, TimePicker
from .account_actions import AccountActionsMixin

class PayrollAppCore(AccountActionsMixin, tk.Tk):
    """Main application window for the payroll system."""

    ROLE_PAGES = {
        "admin": frozenset(("Dashboard", "Employees", "Attendance", "Leaves", "Payroll", "Reports", "Requests", "Settings")),
        "hr": frozenset(("Dashboard", "Employees", "Attendance", "Leaves", "Payroll", "Reports", "Requests", "Settings")),
        "viewer": frozenset(("Dashboard", "Requests", "Settings")),
    }
    ROLE_LABELS = {"admin": "Admin", "hr": "HR", "viewer": "Employee"}
    DATABASE_ADMIN_ROLES = frozenset(("admin",))
    PAYROLL_MANAGEMENT_ROLES = frozenset(("admin", "hr"))
    DASHBOARD_CHART_ROLES = frozenset(("admin", "hr"))
    EDIT_ROLES = frozenset(("admin", "hr"))
    DEPARTMENT_MANAGEMENT_ROLES = frozenset(("admin",))
    POSITION_MANAGEMENT_ROLES = frozenset(("admin",))

    NAV_ITEMS = (
        ("Dashboard", "Overview"),
        ("Employees", "People directory"),
        ("Attendance", "Daily time records"),
        ("Leaves", "Approved leave records"),
        ("Payroll", "Payroll processing"),
        ("Reports", "Payroll & workforce reports"),
        ("Requests", "Employee requests"),
        ("Settings", "Organization preferences"),
    )
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self._set_window_icon()
        self.geometry("1360x860")
        self.minsize(960, 680)
        self.state("zoomed")
        self.fullscreen = False
        self.configure(bg=BACKGROUND_COLOR)
        self.bind_all("<F11>", self._toggle_fullscreen, add="+")
        self.bind_all("<Escape>", self._exit_fullscreen, add="+")

        self.db_manager = DatabaseManager()
        self.current_page = "Dashboard"
        self.current_user: dict[str, str] | None = None
        self.theme_button: ttk.Button | None = None
        self.profile_photo: tk.PhotoImage | None = None
        self.dark_mode = False
        self.settings: dict[str, str] = {
            "organization_name": "LSPU PAYROLL SYSTEM",
            "organization_tagline": "Human Resource & Payroll Control Center",
            "currency_symbol": "₱",
            "appearance_mode": "light",
            "company_policies": "",
        }
        self._configure_styles()
        self._build_shell()
        self.bind_all("<Map>", self._theme_new_toplevel, add="+")

        try:
            self.db_manager.initialize()
            self._load_settings()
            self.dark_mode = self.settings.get("appearance_mode", "light") == "dark"
            self._configure_styles()
            self._apply_widget_theme(self)
            self.status_var.set("Ready  •  Database connected")
            self._show_login()
        except (sqlite3.Error, OSError) as exc:
            self.status_var.set(f"Database initialization failed: {exc}")
            messagebox.showerror("Initialization Error", str(exc), parent=self)

    def _set_window_icon(self) -> None:
        """Use assets/app.ico (Windows) or assets/app.png as the window icon if present."""
        if sys.platform == "win32":
            try:
                import ctypes

                # Lets Windows show this app's icon in the taskbar instead of Python's.
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "bnu.payroll.management"
                )
            except (AttributeError, OSError):
                pass
            icon_file = ASSETS_DIR / "app.ico"
            if icon_file.is_file():
                try:
                    self.iconbitmap(default=str(icon_file))
                    return
                except tk.TclError:
                    pass
        png_file = ASSETS_DIR / "app.png"
        if png_file.is_file():
            try:
                self._window_icon = tk.PhotoImage(file=str(png_file))  # keep a reference
                self.iconphoto(True, self._window_icon)
            except tk.TclError:
                pass

    def _toggle_fullscreen(self, _event: tk.Event[tk.Misc] | None = None) -> str:
        self.fullscreen = not self.fullscreen
        self.attributes("-fullscreen", self.fullscreen)
        if not self.fullscreen:
            self.state("zoomed")
        return "break"

    def _exit_fullscreen(self, _event: tk.Event[tk.Misc] | None = None) -> str | None:
        if not self.fullscreen:
            return None
        self.fullscreen = False
        self.attributes("-fullscreen", False)
        self.state("zoomed")
        return "break"

    def _configure_styles(self) -> None:
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.configure(bg=BACKGROUND_COLOR)
        self.style.configure("TFrame", background=BACKGROUND_COLOR)
        self.style.configure(
            "Card.TFrame",
            background=WHITE,
            relief="solid",
            borderwidth=1,
            bordercolor="#D9E3F0",
        )
        self.style.configure("CardContent.TFrame", background=WHITE)
        self.style.configure("Header.TFrame", background=WHITE)
        self.style.configure("HeaderAccent.TFrame", background=ACCENT_BLUE)
        self.style.configure("HeroContent.TFrame", background="#EAF3FB")
        self.style.configure("MetricBlue.TFrame", background="#F1F7FD", relief="solid", borderwidth=1, bordercolor="#D9E3F0")
        self.style.configure("MetricGreen.TFrame", background="#ECF8F2", relief="solid", borderwidth=1, bordercolor="#D9E3F0")
        self.style.configure("MetricBlueContent.TFrame", background="#F1F7FD")
        self.style.configure("MetricGreenContent.TFrame", background="#ECF8F2")
        self.style.configure("Sidebar.TFrame", background=PRIMARY_COLOR)
        self.style.configure("SidebarAccent.TFrame", background=GOLD_COLOR)
        self.style.configure("TLabel", font=DEFAULT_FONT, background=BACKGROUND_COLOR, foreground=TEXT_COLOR)
        self.style.configure("Title.TLabel", font=TITLE_FONT, background=BACKGROUND_COLOR, foreground=PRIMARY_COLOR)
        self.style.configure("HeaderTitle.TLabel", font=("Segoe UI", 30, "bold"), background=WHITE, foreground=PRIMARY_COLOR)
        self.style.configure("Section.TLabel", font=HEADING_FONT, background=BACKGROUND_COLOR, foreground=TEXT_COLOR)
        self.style.configure("CardTitle.TLabel", font=("Segoe UI", 10, "bold"), background=WHITE, foreground=MUTED_COLOR)
        self.style.configure("Muted.TLabel", font=("Segoe UI", 10), background=BACKGROUND_COLOR, foreground=MUTED_COLOR)
        self.style.configure("CardMuted.TLabel", font=("Segoe UI", 10), background=WHITE, foreground=MUTED_COLOR)
        self.style.configure("MetricBlueTitle.TLabel", font=("Segoe UI", 9, "bold"), background="#F1F7FD", foreground=MUTED_COLOR)
        self.style.configure("MetricGreenTitle.TLabel", font=("Segoe UI", 9, "bold"), background="#ECF8F2", foreground=MUTED_COLOR)
        self.style.configure("MetricBlueValue.TLabel", font=LARGE_NUM_FONT, background="#F1F7FD", foreground=ACCENT_BLUE)
        self.style.configure("MetricGreenValue.TLabel", font=LARGE_NUM_FONT, background="#ECF8F2", foreground=SUCCESS_COLOR)
        self.style.configure("MetricBlueDetail.TLabel", font=("Segoe UI", 9), background="#F1F7FD", foreground=MUTED_COLOR)
        self.style.configure("MetricGreenDetail.TLabel", font=("Segoe UI", 9), background="#ECF8F2", foreground=MUTED_COLOR)
        self.style.configure("SidebarTitle.TLabel", font=("Segoe UI", 15, "bold"), background=PRIMARY_COLOR, foreground=WHITE)
        self.style.configure("SidebarSub.TLabel", font=("Segoe UI", 9), background=PRIMARY_COLOR, foreground="#B9CAE2")
        self.style.configure("SidebarSection.TLabel", font=("Segoe UI", 8, "bold"), background=PRIMARY_COLOR, foreground="#8FA9CA")
        self.style.configure("HeaderDate.TLabel", font=("Segoe UI", 9), background=WHITE, foreground=MUTED_COLOR)
        self.style.configure("HeaderAccount.TLabel", font=("Segoe UI", 10, "bold"), background="#EAF3FB", foreground=PRIMARY_COLOR, padding=(12, 7))
        self.style.configure("ThemeToggle.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8), background="#1A3A6B", foreground="#EAF3FB", anchor="w")
        self.style.map("ThemeToggle.TButton", background=[("active", "#274A78"), ("pressed", "#0B2448")], foreground=[("active", WHITE)])
        self.style.configure("HeroTitle.TLabel", font=("Segoe UI", 16, "bold"), background="#EAF3FB", foreground=PRIMARY_COLOR)
        self.style.configure("HeroSub.TLabel", font=("Segoe UI", 10), background="#EAF3FB", foreground=MUTED_COLOR)
        self.style.configure("TButton", font=DEFAULT_FONT, padding=(12, 8), borderwidth=0, relief="flat")
        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8), background=ACCENT_BLUE, foreground=WHITE)
        self.style.map("Primary.TButton", background=[("active", "#1A64A8"), ("pressed", PRIMARY_COLOR), ("disabled", "#9EB4CC")])
        self.style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(12, 8), background="#E8F0FA", foreground=PRIMARY_COLOR)
        self.style.map("Secondary.TButton", background=[("active", "#D6E5F6"), ("pressed", "#C8D9ED")])
        self.style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8), background=ACCENT_BLUE, foreground=WHITE)
        self.style.map("Danger.TButton", background=[("active", "#1A64A8"), ("pressed", PRIMARY_COLOR)])
        self.style.configure("Nav.TButton", font=("Segoe UI", 10), padding=(13, 10), anchor="w", background=PRIMARY_COLOR, foreground="#D9E5F5", focuscolor=PRIMARY_COLOR, borderwidth=0)
        self.style.map("Nav.TButton", background=[("active", "#1A3A6B"), ("pressed", "#0B2448")], foreground=[("active", WHITE)])
        self.style.configure("NavChild.TButton", font=("Segoe UI", 9), padding=(12, 8), anchor="w", background=PRIMARY_COLOR, foreground="#B9CAE2", focuscolor=PRIMARY_COLOR, borderwidth=0)
        self.style.map("NavChild.TButton", background=[("active", "#1A3A6B"), ("pressed", "#0B2448")], foreground=[("active", WHITE)])
        self.style.configure("NavActive.TButton", font=("Segoe UI", 10, "bold"), padding=(13, 10), anchor="w", background=ACCENT_BLUE, foreground=WHITE, focuscolor=ACCENT_BLUE, borderwidth=0)
        self.style.map("NavActive.TButton", background=[("active", ACCENT_BLUE)], foreground=[("active", WHITE)])
        self.style.configure("NavChildActive.TButton", font=("Segoe UI", 9), padding=(12, 8), anchor="w", background="#1A3A6B", foreground=WHITE, focuscolor="#1A3A6B", borderwidth=0)
        self.style.map("NavChildActive.TButton", background=[("active", "#1A3A6B")], foreground=[("active", WHITE)])
        self.style.configure(
            "Treeview",
            background=WHITE,
            fieldbackground=WHITE,
            foreground=TEXT_COLOR,
            rowheight=38,
            font=("Segoe UI", 10),
            borderwidth=0,
            relief="flat",
        )
        self.style.configure(
            "Treeview.Heading",
            background="#E8F0F8",
            foreground=PRIMARY_COLOR,
            font=("Segoe UI", 9, "bold"),
            padding=(10, 10),
            relief="flat",
        )
        self.style.map("Treeview", background=[("selected", "#D6EAF8")], foreground=[("selected", PRIMARY_COLOR)])
        self.style.configure(
            "TEntry",
            padding=(9, 8),
            fieldbackground=WHITE,
            foreground=TEXT_COLOR,
            insertcolor=TEXT_COLOR,
            bordercolor="#C8D6E5",
        )
        self.style.configure(
            "TCombobox",
            padding=(8, 6),
            fieldbackground=WHITE,
            foreground=TEXT_COLOR,
            bordercolor="#C8D6E5",
        )
        self.style.configure(
            "TSpinbox",
            fieldbackground=WHITE,
            foreground=TEXT_COLOR,
            insertcolor=TEXT_COLOR,
            bordercolor="#C8D6E5",
        )
        self.style.configure("TScrollbar", width=8, arrowsize=8, borderwidth=0, relief="flat")
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", WHITE)],
            foreground=[("readonly", TEXT_COLOR)],
            selectbackground=[("readonly", "#D6EAF8")],
            selectforeground=[("readonly", TEXT_COLOR)],
        )
        if self.dark_mode:
            self._configure_dark_styles()

    def _configure_dark_styles(self) -> None:
        background = "#111827"
        surface = "#1F2937"
        elevated = "#263548"
        foreground = "#F1F5F9"
        muted = "#A7B6CA"
        border = "#334155"
        self.configure(bg=background)
        self.style.configure("TFrame", background=background)
        self.style.configure("Card.TFrame", background=surface, bordercolor=border)
        self.style.configure("CardContent.TFrame", background=surface)
        self.style.configure("Header.TFrame", background=surface)
        self.style.configure("HeaderAccent.TFrame", background="#3B82F6")
        self.style.configure("HeroContent.TFrame", background="#1E3A5F")
        self.style.configure("MetricBlue.TFrame", background=elevated, bordercolor=border)
        self.style.configure("MetricGreen.TFrame", background="#15352C", bordercolor="#285341")
        self.style.configure("MetricBlueContent.TFrame", background=elevated)
        self.style.configure("MetricGreenContent.TFrame", background="#15352C")
        self.style.configure("Sidebar.TFrame", background="#0B1220")
        self.style.configure("TLabel", background=background, foreground=foreground)
        self.style.configure("Title.TLabel", background=background, foreground="#DCEBFF")
        self.style.configure("HeaderTitle.TLabel", background=surface, foreground="#F3F4F6")
        self.style.configure("Section.TLabel", background=background, foreground=foreground)
        self.style.configure("CardTitle.TLabel", background=surface, foreground=muted)
        self.style.configure("Muted.TLabel", background=background, foreground=muted)
        self.style.configure("CardMuted.TLabel", background=surface, foreground=muted)
        self.style.configure("MetricBlueTitle.TLabel", background=elevated, foreground=muted)
        self.style.configure("MetricGreenTitle.TLabel", background="#15352C", foreground="#A9C8B5")
        self.style.configure("MetricBlueValue.TLabel", background=elevated, foreground="#60A5FA")
        self.style.configure("MetricGreenValue.TLabel", background="#15352C", foreground="#34D399")
        self.style.configure("MetricBlueDetail.TLabel", background=elevated, foreground=muted)
        self.style.configure("MetricGreenDetail.TLabel", background="#15352C", foreground="#A7B6CA")
        self.style.configure("SidebarTitle.TLabel", background="#0B1220", foreground=WHITE)
        self.style.configure("SidebarSub.TLabel", background="#0B1220", foreground="#B9CAE2")
        self.style.configure("SidebarSection.TLabel", background="#0B1220", foreground="#8FA9CA")
        self.style.configure("HeaderDate.TLabel", background=surface, foreground=muted)
        self.style.configure("HeaderAccount.TLabel", background="#263548", foreground="#DCEBFF")
        self.style.configure("ThemeToggle.TButton", background="#1E293B", foreground="#DCEBFF")
        self.style.map("ThemeToggle.TButton", background=[("active", "#334155")], foreground=[("active", WHITE)])
        self.style.configure("HeroTitle.TLabel", background="#1E3A5F", foreground="#EAF3FB")
        self.style.configure("HeroSub.TLabel", background="#1E3A5F", foreground="#C2D3E5")
        self.style.configure("Primary.TButton", background="#2563EB", foreground=WHITE)
        self.style.map("Primary.TButton", background=[("active", "#1D4ED8"), ("disabled", "#4B5563")])
        self.style.configure("Secondary.TButton", background="#334155", foreground="#E2E8F0")
        self.style.map("Secondary.TButton", background=[("active", "#475569")])
        self.style.configure("Danger.TButton", background="#2563EB", foreground=WHITE)
        self.style.configure("Nav.TButton", background="#0B1220", foreground="#D9E5F5", focuscolor="#0B1220")
        self.style.map("Nav.TButton", background=[("active", "#1E293B")], foreground=[("active", WHITE)])
        self.style.configure("NavChild.TButton", background="#0B1220", foreground="#B9CAE2", focuscolor="#0B1220")
        self.style.map("NavChild.TButton", background=[("active", "#1E293B")], foreground=[("active", WHITE)])
        self.style.configure("NavActive.TButton", background="#2563EB", foreground=WHITE, focuscolor="#2563EB")
        self.style.map("NavActive.TButton", background=[("active", "#2563EB")], foreground=[("active", WHITE)])
        self.style.configure("NavChildActive.TButton", background="#1E3A5F", foreground=WHITE, focuscolor="#1E3A5F")
        self.style.map("NavChildActive.TButton", background=[("active", "#1E3A5F")], foreground=[("active", WHITE)])
        self.style.configure("Treeview", background=surface, fieldbackground=surface, foreground=foreground)
        self.style.configure("Treeview.Heading", background="#263548", foreground="#DCEBFF")
        self.style.map("Treeview", background=[("selected", "#1D4ED8")], foreground=[("selected", WHITE)])
        self.style.configure("TEntry", fieldbackground="#111827", foreground=foreground, insertcolor=foreground, bordercolor=border)
        self.style.configure("TCombobox", fieldbackground="#111827", foreground=foreground, bordercolor=border)
        self.style.configure("TSpinbox", fieldbackground="#111827", foreground=foreground, arrowsize=14)
        self.style.configure("TCheckbutton", background=background, foreground=foreground)
        self.style.map("TCheckbutton", background=[("active", background)], foreground=[("active", foreground)])
        self.style.configure("TRadiobutton", background=background, foreground=foreground)
        self.style.map("TRadiobutton", background=[("active", background)], foreground=[("active", foreground)])
        self.style.configure("TScrollbar", width=8, arrowsize=8, borderwidth=0, relief="flat", background="#334155", troughcolor=background, bordercolor=background, arrowcolor=foreground)
        self.style.configure("TSeparator", background=border)
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#111827")],
            foreground=[("readonly", foreground)],
            selectbackground=[("readonly", "#1D4ED8")],
            selectforeground=[("readonly", WHITE)],
        )

    def _theme_color(self, color: str, option: str) -> str:
        if option == "background":
            light_colors = {
                BACKGROUND_COLOR: "#111827",
                WHITE: "#1F2937",
                SECONDARY_COLOR: "#17212F",
                PRIMARY_COLOR: "#0B1220",
                ACCENT_BLUE: "#2563EB",
                "#EAF3FB": "#1E3A5F",
                "#F1F7FD": "#263548",
                "#ECF8F2": "#15352C",
                "#DFEAF5": "#374151",
                "#D8EEE2": "#285341",
                "#D9E3F0": "#334155",
                "#EDF3F9": "#263548",
                "#E8F0FA": "#334155",
                "#D6E5F6": "#475569",
                "#EAF6F0": "#15352C",
                "#C8D6E5": "#374151",
            }
        else:
            light_colors = {
                TEXT_COLOR: "#F1F5F9",
                MUTED_COLOR: "#A7B6CA",
                PRIMARY_COLOR: "#DCEBFF",
                ACCENT_BLUE: "#60A5FA",
                SUCCESS_COLOR: "#34D399",
                DANGER_COLOR: "#F87171",
                "#126B4E": "#6EE7B7",
                "#C8D7EE": "#B9CAE2",
            }
        dark_colors = {dark: light for light, dark in light_colors.items()}
        return light_colors.get(color, color) if self.dark_mode else dark_colors.get(color, color)

    def _apply_widget_theme(self, root: tk.Misc) -> None:
        if isinstance(root, RoundedCard):
            root._fill = self._theme_color(root._fill, "background")
            root._outline = self._theme_color(root._outline, "background")
        for option in ("background", "foreground"):
            try:
                current = str(root.cget(option))
            except tk.TclError:
                continue
            updated = self._theme_color(current, option)
            if updated != current:
                try:
                    root.configure(**{option: updated})
                except tk.TclError:
                    continue
        if isinstance(root, RoundedCard):
            root._canvas.configure(
                background=self._theme_color(BACKGROUND_COLOR, "background")
            )
            root._draw_background(None)
        for child in root.winfo_children():
            self._apply_widget_theme(child)

    def _theme_new_toplevel(self, event: tk.Event[tk.Misc]) -> None:
        if self.dark_mode and isinstance(event.widget, tk.Toplevel):
            self.after_idle(lambda window=event.widget: self._apply_widget_theme(window))

    def _toggle_dark_mode(self) -> None:
        new_mode = "light" if self.dark_mode else "dark"
        try:
            self._execute(
                "INSERT INTO app_settings (setting_key,setting_value) VALUES (?,?) "
                "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
                ("appearance_mode", new_mode),
            )
        except sqlite3.Error as exc:
            messagebox.showerror(
                "Could not change appearance",
                str(exc),
                parent=self,
            )
            return
        self.settings["appearance_mode"] = new_mode
        self.dark_mode = new_mode == "dark"
        self._configure_styles()
        if self.theme_button is not None:
            self.theme_button.configure(
                text="  Light mode" if self.dark_mode else "  Dark mode"
            )
        self._show_page(self.current_page)
        self.status_var.set(f"{new_mode.title()} mode enabled")

    def _build_shell(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        self.sidebar = ttk.Frame(self, style="Sidebar.TFrame", padding=(18, 22))
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="ns")
        self.sidebar.configure(width=246)
        self.sidebar.grid_propagate(False)

        self.brand_label = ttk.Label(
            self.sidebar,
            text="LSPU PAYROLL SYSTEM",
            style="SidebarTitle.TLabel",
            wraplength=205,
        )
        ttk.Frame(self.sidebar, style="SidebarAccent.TFrame", height=4).pack(
            anchor="w", fill="x", padx=(0, 150), pady=(0, 12)
        )
        self.brand_label.pack(anchor="w", pady=(0, 3))
        self.brand_subtitle = ttk.Label(
            self.sidebar,
            text=self.settings["organization_tagline"],
            style="SidebarSub.TLabel",
            wraplength=205,
        )
        self.brand_subtitle.pack(anchor="w", pady=(0, 28))
        ttk.Label(
            self.sidebar,
            text="WORKSPACE",
            style="SidebarSection.TLabel",
        ).pack(anchor="w", pady=(0, 9))

        self.navigation = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        self.navigation.pack(fill="x")
        self.navigation.columnconfigure(0, weight=1)
        self.nav_buttons: dict[str, ttk.Button] = {}
        self.employee_nav_expanded = True
        employee_pages = {"Employees", "Attendance", "Leaves", "Requests"}
        nav_icons = {
            "Dashboard": "⌂",
            "Employees": "●",
            "Attendance": "◷",
            "Leaves": "▣",
            "Payroll": "₱",
            "Reports": "▤",
            "Requests": "✉",
            "Settings": "⚙",
        }
        nav_row = 0
        for title, _ in self.NAV_ITEMS:
            if title in employee_pages:
                if title == "Employees":
                    self.employee_nav_group = ttk.Frame(
                        self.navigation, style="Sidebar.TFrame"
                    )
                    self.employee_nav_group.grid(
                        row=nav_row, column=0, sticky="ew", pady=3
                    )
                    self.employee_nav_button = ttk.Button(
                        self.employee_nav_group,
                        text="  PEOPLE & TIME   v",
                        style="Nav.TButton",
                        command=self._toggle_employee_navigation,
                    )
                    self.employee_nav_button.pack(fill="x")
                    self.employee_navigation = ttk.Frame(
                        self.employee_nav_group, style="Sidebar.TFrame"
                    )
                    self.employee_navigation.pack(fill="x", padx=(12, 0))
                    for employee_page in (
                        "Employees",
                        "Attendance",
                        "Leaves",
                        "Requests",
                    ):
                        icon = nav_icons[employee_page]
                        label = (
                            "Leave Records"
                            if employee_page == "Leaves"
                            else employee_page
                        )
                        employee_button = ttk.Button(
                            self.employee_navigation,
                            text=f"{icon}   {label}",
                            style="NavChild.TButton",
                            command=lambda page=employee_page: self._show_page(page),
                        )
                        employee_button.pack(fill="x", pady=2)
                        self.nav_buttons[employee_page] = employee_button
                    nav_row += 1
                continue
            button = ttk.Button(
                self.navigation,
                text=f"{nav_icons[title]}   {title}",
                style="Nav.TButton",
                command=lambda page=title: self._show_page(page),
            )
            button.grid(row=nav_row, column=0, sticky="ew", pady=3)
            self.nav_buttons[title] = button
            nav_row += 1

        self.sidebar_footer = ttk.Frame(self.sidebar, style="Sidebar.TFrame")
        self.sidebar_footer.pack(side="bottom", fill="x")
        ttk.Separator(self.sidebar_footer).grid(row=0, column=0, sticky="ew", pady=(0, 13))
        ttk.Label(
            self.sidebar_footer, text=f"Version {APP_VERSION}", style="SidebarSub.TLabel"
        ).grid(row=1, column=0, sticky="w")
        ttk.Label(
            self.sidebar_footer, text="Secure local workspace", style="SidebarSub.TLabel"
        ).grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.account_button = ttk.Button(
            self.sidebar_footer,
            text="Accounts  •  Sign in",
            style="Nav.TButton",
            command=self._open_account_menu,
        )
        self.account_button.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.sidebar_footer.columnconfigure(0, weight=1)
        ttk.Frame(self.sidebar, style="Sidebar.TFrame").pack(fill="both", expand=True)

        self.header = ttk.Frame(self, style="Header.TFrame", padding=(32, 20, 32, 18))
        self.header.grid(row=0, column=1, sticky="ew")
        self.header.columnconfigure(0, weight=1)
        self.page_title_var = tk.StringVar(value="Dashboard")
        self.page_subtitle_var = tk.StringVar(value="Your payroll operations at a glance.")
        ttk.Label(self.header, textvariable=self.page_title_var, style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            self.header,
            textvariable=self.page_subtitle_var,
            font=("Segoe UI", 10),
            foreground=MUTED_COLOR,
            background=WHITE,
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.header_user_var = tk.StringVar(value="Sign in to continue")
        header_context = ttk.Frame(self.header, style="Header.TFrame")
        header_context.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))
        ttk.Label(
            header_context,
            text=date.today().strftime("%A, %B %d, %Y"),
            style="HeaderDate.TLabel",
        ).pack(anchor="e", pady=(0, 5))
        ttk.Label(
            header_context,
            textvariable=self.header_user_var,
            style="HeaderAccount.TLabel",
        ).pack(anchor="e")
        ttk.Frame(self.header, style="HeaderAccent.TFrame", height=2).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(17, 0)
        )

        self.page_host = ttk.Frame(self, padding=(28, 0, 28, 20))
        self.page_host.grid(row=1, column=1, sticky="nsew")
        self.page_host.columnconfigure(0, weight=1)
        self.page_host.rowconfigure(0, weight=1)
        self.bind_all("<MouseWheel>", self._scroll_page, add="+")
        self.bind_all("<Button-4>", self._scroll_page, add="+")
        self.bind_all("<Button-5>", self._scroll_page, add="+")
        self.status_var = tk.StringVar(value="Initializing database...")
        ttk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            padding=(18, 9),
            background=SECONDARY_COLOR,
            foreground=MUTED_COLOR,
            font=("Segoe UI", 9),
        ).grid(row=2, column=1, sticky="ew")

    def _role_allows(self, page: str) -> bool:
        return bool(
            self.current_user
            and page in self.ROLE_PAGES.get(self.current_user["role"], frozenset())
        )

    def _require_roles(self, roles: Collection[str], action: str) -> bool:
        if self.current_user and self.current_user["role"] in roles:
            return True
        messagebox.showerror(
            "Access denied",
            f"Your account does not have permission to {action}.",
            parent=self,
        )
        return False

    def _update_role_navigation(self) -> None:
        for title, button in self.nav_buttons.items():
            if title in ("Employees", "Attendance", "Leaves", "Requests"):
                button.pack_forget()
                if self._role_allows(title):
                    button.pack(fill="x", pady=2)
            else:
                button.grid_remove()
                if self._role_allows(title):
                    button.grid()
        employee_pages_allowed = any(
            self._role_allows(page)
            for page in ("Employees", "Attendance", "Leaves", "Requests")
        )
        self.employee_nav_group.grid_remove()
        if employee_pages_allowed:
            self.employee_nav_group.grid()

    def _fetchall(self, query: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        connection = self.db_manager.get_connection()
        try:
            return list(connection.execute(query, parameters).fetchall())
        finally:
            connection.close()

    def _fetchone(self, query: str, parameters: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        connection = self.db_manager.get_connection()
        try:
            return connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

    def _execute(self, query: str, parameters: tuple[Any, ...] = ()) -> int:
        connection = self.db_manager.get_connection()
        try:
            cursor = connection.execute(query, parameters)
            connection.commit()
            return int(cursor.lastrowid or 0)
        finally:
            connection.close()

    def _load_settings(self) -> None:
        rows = self._fetchall("SELECT setting_key, setting_value FROM app_settings")
        self.settings.update({str(row["setting_key"]): str(row["setting_value"]) for row in rows})
        if self.settings.get("organization_name") == "Biringan National University":
            self.settings["organization_name"] = APP_NAME
            self._execute(
                "UPDATE app_settings SET setting_value = ? WHERE setting_key = ?",
                (APP_NAME, "organization_name"),
            )
        self.brand_label.configure(text=self.settings.get("organization_name", APP_NAME).upper())
        self.brand_subtitle.configure(text=self.settings.get("organization_tagline", "Payroll Control Center"))

    def _show_page(self, page: str) -> None:
        builders = {
            "Dashboard": (self._build_dashboard, "Your payroll operations at a glance."),
            "Employees": (self._build_employees, "Manage employee records, departments, and compensation."),
            "Attendance": (self._build_attendance, "Review time records and keep daily attendance up to date."),
            "Leaves": (
                self._build_leaves,
                "View approved leave and travel records used for payroll. Request decisions stay in Requests.",
            ),
            "Payroll": (self._build_payroll, "Calculate pay from employee rates, attendance, and deductions."),
            "Reports": (self._build_reports, "Explore payroll totals and export period reports."),
            "Requests": (self._build_requests, "Submit and track employee requests or review requests from employees."),
            "Settings": (self._build_settings, "Set the organization details and currency used across the app."),
        }
        if page not in builders:
            return
        if not self._role_allows(page):
            messagebox.showerror(
                "Access denied",
                "Your account does not have access to that section.",
                parent=self,
            )
            return
        builder, subtitle = builders[page]
        self.current_page = page
        self.page_title_var.set("Leave Records" if page == "Leaves" else page)
        self.page_subtitle_var.set(subtitle)
        for title, button in self.nav_buttons.items():
            active = title == page
            is_employee_page = title in (
                "Employees",
                "Attendance",
                "Leaves",
                "Requests",
            )
            button.configure(
                style=(
                    "NavChildActive.TButton"
                    if active and is_employee_page
                    else "NavChild.TButton"
                    if is_employee_page
                    else "NavActive.TButton"
                    if active
                    else "Nav.TButton"
                )
            )
        self.employee_nav_button.configure(
            style="NavActive.TButton"
            if page in ("Employees", "Attendance", "Leaves", "Requests")
            else "Nav.TButton"
        )
        for child in self.page_host.winfo_children():
            child.destroy()
        builder()
        self._apply_widget_theme(self)

    def _scroll_page(self, event: tk.Event[tk.Misc]) -> str | None:
        canvas_name = {"Dashboard": "dashboard_canvas", "Settings": "settings_canvas"}.get(
            self.current_page
        )
        canvas = getattr(self, canvas_name, None) if canvas_name else None
        if canvas is None or not canvas.winfo_exists():
            return None

        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None and widget is not canvas:
            widget = widget.master
        if widget is None:
            return None

        if event.num == 4:
            amount = -1
        elif event.num == 5:
            amount = 1
        else:
            amount = -int(event.delta / 120)
        if amount:
            canvas.yview_scroll(amount, "units")
        return "break"

    def _toggle_employee_navigation(self) -> None:
        self.employee_nav_expanded = not self.employee_nav_expanded
        if self.employee_nav_expanded:
            self.employee_navigation.pack(fill="x", padx=(12, 0))
            self.employee_nav_button.configure(text="  PEOPLE & TIME   v")
        else:
            self.employee_navigation.pack_forget()
            self.employee_nav_button.configure(text="  PEOPLE & TIME   >")

    def _money(self, amount: float | int | None) -> str:
        symbol = self.settings.get("currency_symbol", "₱")
        return f"{symbol}{float(amount or 0):,.2f}"

    def _employee_code(self, employee_id: int) -> str:
        return f"EMP-{employee_id:04d}"

    def _card(self, parent: ttk.Frame, padding: int = 18) -> RoundedCard:
        return RoundedCard(parent, padding=padding)

    def _page_toolbar(self, parent: ttk.Frame, title: str, subtitle: str | None = None) -> ttk.Frame:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 15))
        toolbar.columnconfigure(0, weight=1)
        ttk.Label(toolbar, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w")
        if subtitle:
            ttk.Label(toolbar, text=subtitle, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(3, 0))
        return toolbar

    def _make_tree(
        self,
        parent: ttk.Frame,
        columns: tuple[str, ...],
        headings: dict[str, str],
        widths: dict[str, int],
        *,
        height: int = 12,
        use_grid: bool = False,
    ) -> ttk.Treeview:
        wrapper = ttk.Frame(parent, style="Card.TFrame")
        if use_grid:
            wrapper.grid(row=1, column=0, sticky="nsew")
        else:
            wrapper.pack(fill="both", expand=True)
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)
        tree = PayrollTreeview(
            wrapper,
            columns=columns,
            show="headings",
            height=height,
            selectmode="browse",
            dark_mode=self.dark_mode,
        )
        vertical = ttk.Scrollbar(wrapper, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(wrapper, orient="horizontal", command=tree.xview)

        def update_horizontal_scrollbar(first: str, last: str) -> None:
            horizontal.set(first, last)
            if float(first) <= 0 and float(last) >= 1:
                horizontal.grid_remove()
            else:
                horizontal.grid(row=1, column=0, sticky="ew")

        tree.configure(yscrollcommand=vertical.set, xscrollcommand=update_horizontal_scrollbar)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        horizontal.grid_remove()
        for column in columns:
            tree.heading(
                column,
                text=headings.get(column, column),
                anchor="center",
            )
            tree.column(
                column,
                width=widths.get(column, 130),
                anchor="center",
                stretch=True,
            )
        tree.tag_configure("inactive", foreground=MUTED_COLOR)
        return tree

    def _empty_state(self, parent: ttk.Frame, message: str) -> None:
        ttk.Label(parent, text=message, style="Muted.TLabel", padding=(18, 24)).pack(anchor="center")

    def _metric_card(self, parent: ttk.Frame, column: int, title: str, value: str, detail: str, accent: str = ACCENT_BLUE) -> None:
        is_green = accent == SUCCESS_COLOR
        content_style = "MetricGreenContent.TFrame" if is_green else "MetricBlueContent.TFrame"
        label_variant = "MetricGreen" if is_green else "MetricBlue"
        card = RoundedCard(
            parent,
            padding=0,
            fill="#ECF8F2" if is_green else "#F1F7FD",
            content_style=content_style,
        )
        card.grid(
            row=0,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 8, 0 if column == 3 else 8),
        )
        tk.Frame(card.content, background=accent, width=5).pack(side="left", fill="y")
        content = ttk.Frame(card.content, style=content_style, padding=(16, 15))
        content.pack(side="left", fill="both", expand=True)
        ttk.Label(content, text=title.upper(), style=f"{label_variant}Title.TLabel").pack(anchor="w")
        ttk.Label(content, text=value, style=f"{label_variant}Value.TLabel").pack(anchor="w", pady=(8, 1))
        ttk.Label(content, text=detail, style=f"{label_variant}Detail.TLabel").pack(anchor="w")
        self._apply_widget_theme(card)

    def _build_dashboard(self) -> None:
        raise NotImplementedError
    def _build_employees(self) -> None:
        raise NotImplementedError
    def _build_attendance(self) -> None:
        raise NotImplementedError
    def _build_leaves(self) -> None:
        raise NotImplementedError
    def _build_payroll(self) -> None:
        raise NotImplementedError
    def _build_reports(self) -> None:
        raise NotImplementedError
    def _build_settings(self) -> None:
        raise NotImplementedError