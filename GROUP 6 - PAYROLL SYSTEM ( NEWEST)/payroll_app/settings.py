from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from config import (
    ACCENT_BLUE, BACKGROUND_COLOR, HEADING_FONT, SUCCESS_COLOR, TEXT_COLOR, WHITE,
)
from .payroll import PayrollPages


class SettingsPages(PayrollPages):
    """Build organization settings and database backup controls."""

    def _build_settings(self) -> None:
        if not self._role_allows("Settings"):
            messagebox.showerror(
                "Access denied",
                "Your account does not have access to organization settings.",
                parent=self,
            )
            return
        self._load_settings()
        role = self.current_user["role"] if self.current_user else ""
        is_admin = role in self.DATABASE_ADMIN_ROLES
        page = ttk.Frame(self.page_host)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        self._page_toolbar(
            page,
            "Settings",
            "Manage organization preferences and review company policies.",
        )

        settings_container = ttk.Frame(page)
        settings_container.pack(fill="both", expand=True)
        settings_container.columnconfigure(0, weight=1)
        settings_container.rowconfigure(0, weight=1)
        settings_canvas = tk.Canvas(
            settings_container,
            background=BACKGROUND_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        settings_canvas.grid(row=0, column=0, sticky="nsew")
        settings_scrollbar = ttk.Scrollbar(
            settings_container,
            orient="vertical",
            command=settings_canvas.yview,
        )
        settings_scrollbar.grid(row=0, column=1, sticky="ns")
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        settings_content = ttk.Frame(settings_canvas)
        settings_window = settings_canvas.create_window(
            (0, 0), window=settings_content, anchor="nw"
        )
        self.settings_canvas = settings_canvas
        settings_content.bind(
            "<Configure>",
            lambda _event: settings_canvas.configure(
                scrollregion=settings_canvas.bbox("all")
            ),
        )
        settings_canvas.bind(
            "<Configure>",
            lambda event: settings_canvas.itemconfigure(
                settings_window, width=event.width
            ),
        )
        settings_content.columnconfigure(0, weight=1)

        if is_admin:
            form_panel = self._card(settings_content, padding=24)
            form_panel.pack(fill="x", pady=(0, 16))
            form = form_panel.content
            ttk.Label(form, text="Branding & display", font=HEADING_FONT, background=WHITE, foreground=TEXT_COLOR).grid(row=0, column=0, columnspan=2, sticky="w")
            ttk.Label(form, text="Organization name", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(18, 7), padx=(0, 20))
            organization_var = tk.StringVar(value=self.settings.get("organization_name", ""))
            ttk.Entry(form, textvariable=organization_var, width=36).grid(row=1, column=1, sticky="ew", pady=(18, 7))
            ttk.Label(form, text="Workspace tagline", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=7, padx=(0, 20))
            tagline_var = tk.StringVar(value=self.settings.get("organization_tagline", ""))
            ttk.Entry(form, textvariable=tagline_var, width=36).grid(row=2, column=1, sticky="ew", pady=7)
            ttk.Label(form, text="Currency symbol", style="Muted.TLabel").grid(row=3, column=0, sticky="w", pady=7, padx=(0, 20))
            currency_var = tk.StringVar(value=self.settings.get("currency_symbol", "₱"))
            ttk.Combobox(form, textvariable=currency_var, values=("₱", "$", "€", "£", "¥"), state="readonly", width=33).grid(row=3, column=1, sticky="ew", pady=7)
            ttk.Label(
                form,
                text="Currency changes only the way amounts are displayed; it does not convert stored values.",
                style="CardMuted.TLabel",
                wraplength=440,
            ).grid(row=4, column=1, sticky="w", pady=(4, 0))
            form.columnconfigure(1, weight=1)

        appearance_panel = self._card(settings_content, padding=24)
        appearance_panel.pack(fill="x", pady=(0, 16))
        appearance = appearance_panel.content
        ttk.Label(
            appearance,
            text="Appearance",
            font=HEADING_FONT,
            background=WHITE,
            foreground=TEXT_COLOR,
        ).pack(anchor="w")
        ttk.Label(
            appearance,
            text="Choose the light or dark color theme for the application.",
            style="CardMuted.TLabel",
        ).pack(anchor="w", pady=(6, 12))
        self.theme_button = ttk.Button(
            appearance,
            text="  Light mode" if self.dark_mode else "  Dark mode",
            style="ThemeToggle.TButton",
            command=self._toggle_dark_mode,
        )
        self.theme_button.pack(anchor="w")

        policies_panel = self._card(settings_content, padding=24)
        policies_panel.pack(fill="x", pady=(0, 16))
        policies = policies_panel.content
        policy_heading = ttk.Frame(policies, style="CardContent.TFrame")
        policy_heading.pack(fill="x")
        ttk.Label(
            policy_heading,
            text="Company policies & rules",
            font=HEADING_FONT,
            background=WHITE,
            foreground=TEXT_COLOR,
        ).pack(side="left", anchor="w")
        if is_admin:
            ttk.Label(
                policies,
                text="Add the approved company policies here. HR and Employee accounts can read this section but cannot edit it.",
                style="CardMuted.TLabel",
                wraplength=850,
            ).pack(anchor="w", pady=(6, 12))
        else:
            instructions = (
                "Review the company policies and workplace rules below. Contact HR if anything is unclear."
                if self.settings.get("company_policies", "").strip()
                else "No company policies have been published yet. Please contact HR."
            )
            ttk.Label(
                policies,
                text=instructions,
                style="CardMuted.TLabel",
                wraplength=850,
            ).pack(anchor="w", pady=(6, 12))
        policy_editor = ttk.Frame(policies, style="CardContent.TFrame")
        policy_editor.pack(fill="x")
        policy_editor.columnconfigure(0, weight=1)
        policy_text = tk.Text(
            policy_editor,
            height=14,
            wrap="word",
            padx=10,
            pady=10,
            relief="solid",
            borderwidth=1,
            background=WHITE,
            foreground=TEXT_COLOR,
            insertbackground=TEXT_COLOR,
            font=("Segoe UI", 10),
        )
        policy_scrollbar = ttk.Scrollbar(policy_editor, orient="vertical", command=policy_text.yview)
        policy_text.configure(yscrollcommand=policy_scrollbar.set)
        policy_text.grid(row=0, column=0, sticky="nsew")
        policy_scrollbar.grid(row=0, column=1, sticky="ns")
        existing_policy = self.settings.get("company_policies", "").strip()
        if existing_policy:
            policy_text.insert("1.0", existing_policy)
        if not is_admin:
            policy_text.configure(state="disabled")

        def save() -> None:
            values = {
                "organization_name": organization_var.get().strip(),
                "organization_tagline": tagline_var.get().strip(),
                "currency_symbol": currency_var.get().strip(),
            }
            if not values["organization_name"] or not values["organization_tagline"] or not values["currency_symbol"]:
                messagebox.showerror("Missing settings", "Enter an organization name, tagline, and currency symbol.", parent=self)
                return
            connection = self.db_manager.get_connection()
            try:
                connection.executemany(
                    "INSERT INTO app_settings (setting_key,setting_value) VALUES (?,?) "
                    "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
                    tuple(values.items()),
                )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                messagebox.showerror("Settings were not saved", str(exc), parent=self)
                return
            finally:
                connection.close()
            self.settings.update(values)
            self.brand_label.configure(text=values["organization_name"].upper())
            self.brand_subtitle.configure(text=values["organization_tagline"])
            self.status_var.set("Organization settings saved")
            messagebox.showinfo("Settings saved", "Your organization settings have been updated.", parent=self)

        def publish_policies() -> None:
            if not self._require_roles(("admin",), "publish company policies"):
                return
            policy = policy_text.get("1.0", "end-1c").strip()
            connection = self.db_manager.get_connection()
            try:
                connection.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?) "
                    "ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",
                    ("company_policies", policy),
                )
                connection.commit()
            except sqlite3.Error as exc:
                connection.rollback()
                messagebox.showerror("Policies were not published", str(exc), parent=self)
                return
            finally:
                connection.close()
            self.settings["company_policies"] = policy
            self.status_var.set("Company policies published")
            messagebox.showinfo(
                "Policies published",
                "Company policies are saved and will appear in Settings for HR and Employee accounts.",
                parent=self,
            )

        if is_admin:
            ttk.Button(
                policy_heading,
                text="Publish policies",
                style="Primary.TButton",
                command=publish_policies,
            ).pack(side="right")
            buttons = ttk.Frame(settings_content, style="TFrame")
            buttons.pack(fill="x", pady=(0, 16))
            ttk.Button(buttons, text="Save settings", style="Secondary.TButton", command=save).pack(side="right")

            database_panel = self._card(settings_content, padding=20)
            database_panel.pack(fill="x")
            database = database_panel.content
            ttk.Label(database, text="Database safety", font=HEADING_FONT, background=WHITE, foreground=TEXT_COLOR).pack(anchor="w")
            ttk.Label(
                database,
                text="Backups contain employee and payroll data; store them securely. Restore validates the file and saves a safety copy. Delete permanently removes the active database without creating a backup.",
                style="CardMuted.TLabel",
                wraplength=850,
            ).pack(anchor="w", pady=(6, 10))
            database_actions = ttk.Frame(database, style="CardContent.TFrame")
            database_actions.pack(fill="x")
            ttk.Button(
                database_actions,
                text="Back up database",
                style="Secondary.TButton",
                command=self._backup_database,
            ).pack(side="left", padx=(0, 8))
            ttk.Button(
                database_actions,
                text="Restore backup",
                style="Danger.TButton",
                command=self._restore_database,
            ).pack(side="left")
            ttk.Button(
                database_actions,
                text="Delete database",
                style="Danger.TButton",
                command=self._delete_database,
            ).pack(side="left", padx=(8, 0))

    def _backup_database(self) -> None:
        if not self._require_roles(self.DATABASE_ADMIN_ROLES, "back up the payroll database"):
            return
        destination = filedialog.asksaveasfilename(
            parent=self,
            title="Back up payroll database",
            defaultextension=".sqlite3",
            initialfile=f"payroll-backup-{datetime.now():%Y%m%d-%H%M%S}.sqlite3",
            filetypes=(("SQLite database", "*.sqlite3 *.db"), ("All files", "*.*")),
        )
        if not destination:
            return
        try:
            backup_path = self.db_manager.backup_to(destination)
        except (OSError, sqlite3.Error, ValueError) as exc:
            messagebox.showerror("Database backup failed", str(exc), parent=self)
            return
        self.status_var.set(f"Database backup saved to {backup_path.name}")
        messagebox.showinfo(
            "Backup complete",
            f"A consistent database backup was saved to:\n{backup_path}",
            parent=self,
        )

    def _restore_database(self) -> None:
        if not self._require_roles(self.DATABASE_ADMIN_ROLES, "restore the payroll database"):
            return
        source = filedialog.askopenfilename(
            parent=self,
            title="Select payroll database backup",
            filetypes=(("SQLite database", "*.sqlite3 *.db"), ("All files", "*.*")),
        )
        if not source:
            return
        if not messagebox.askyesno(
            "Restore database backup",
            "Restoring replaces all current payroll data with the selected backup. "
            "A backup of the current database is created first. Continue?",
            parent=self,
        ):
            return
        try:
            safety_backup = self.db_manager.restore_from(source)
        except (OSError, sqlite3.Error, ValueError) as exc:
            messagebox.showerror("Database restore failed", str(exc), parent=self)
            return

        self.settings = {
            "organization_name": "LSPU PAYROLL SYSTEM",
            "organization_tagline": "Human Resource & Payroll Control Center",
            "currency_symbol": "₱",
            "appearance_mode": "light",
        }
        self._load_settings()
        self.dark_mode = self.settings.get("appearance_mode", "light") == "dark"
        self._configure_styles()
        self._apply_widget_theme(self)
        self.status_var.set("Database restored; sign in to continue")
        messagebox.showinfo(
            "Database restored",
            "The selected backup has been restored. You have been signed out; "
            f"sign in with an account from the restored database.\n\n"
            f"Pre-restore safety copy:\n{safety_backup}",
            parent=self,
        )
        self._logout()

    def _delete_database(self) -> None:
        if not self._require_roles(self.DATABASE_ADMIN_ROLES, "delete the payroll database"):
            return
        if not messagebox.askyesno(
            "Delete payroll database",
            "This permanently deletes the active payroll database and its SQLite journal files. "
            "No backup will be created automatically. Existing separately saved backups will "
            "not be deleted, and the application will close. Continue?",
            icon="warning",
            parent=self,
        ):
            return
        try:
            self.db_manager.delete_database()
        except OSError as exc:
            messagebox.showerror("Database deletion failed", str(exc), parent=self)
            return

        messagebox.showinfo(
            "Database deleted",
            "The active payroll database was deleted. The application will now close.",
            parent=self,
        )
        self.destroy()
