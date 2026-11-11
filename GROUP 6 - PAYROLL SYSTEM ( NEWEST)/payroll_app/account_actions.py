from __future__ import annotations

import base64
import sqlite3
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from config import BACKGROUND_COLOR
from database.database import hash_password, verify_password


class AccountActionsMixin:
    """Provide sign-in, account management, and logout actions."""

    PROFILE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
    PROFILE_IMAGE_MAX_DIMENSION = 4096
    PROFILE_IMAGE_FILETYPES = (
        ("Supported images", "*.png *.gif *.ppm *.pgm"),
        ("PNG images", "*.png"),
        ("GIF images", "*.gif"),
        ("PPM images", "*.ppm"),
        ("PGM images", "*.pgm"),
    )

    def _show_login(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Sign in")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", self.destroy)

        body = ttk.Frame(dialog, padding=28)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Welcome back!", style="Title.TLabel").pack(anchor="w")
        ttk.Label(body, text="Sign in to access the payroll workspace.", style="Muted.TLabel").pack(
            anchor="w", pady=(4, 18)
        )

        username_var = tk.StringVar()
        password_var = tk.StringVar()
        ttk.Label(body, text="Username", style="Muted.TLabel").pack(anchor="w")
        username_entry = ttk.Entry(body, textvariable=username_var, width=34)
        username_entry.pack(fill="x", pady=(4, 12))
        ttk.Label(body, text="Password", style="Muted.TLabel").pack(anchor="w")
        password_row = ttk.Frame(body)
        password_row.pack(fill="x", pady=(4, 10))
        password_row.columnconfigure(0, weight=1)
        password_entry = ttk.Entry(password_row, textvariable=password_var, show="•", width=28)
        password_entry.grid(row=0, column=0, sticky="ew")
        reveal_text = tk.StringVar(value="Show")

        def hide_password() -> None:
            password_entry.configure(show="•")
            reveal_text.set("Show")

        def toggle_password() -> None:
            if password_entry.cget("show"):
                password_entry.configure(show="")
                reveal_text.set("Hide")
            else:
                hide_password()
            password_entry.focus_set()
            password_entry.icursor("end")

        ttk.Button(
            password_row,
            textvariable=reveal_text,
            style="Secondary.TButton",
            width=6,
            takefocus=False,
            command=toggle_password,
        ).grid(row=0, column=1, padx=(6, 0))
        ttk.Label(
            body,
            text="Default admin login: Admin / Admin123.",
            style="Muted.TLabel",
            wraplength=300,
        ).pack(anchor="w", pady=(0, 14))

        def sign_in() -> None:
            username = username_var.get().strip()
            try:
                user = self._fetchone(
                    "SELECT id, username, password_hash, role, profile_image "
                    "FROM users WHERE username = ?",
                    (username,),
                ) if username else None
                if user is None or not verify_password(password_var.get(), str(user["password_hash"])):
                    messagebox.showerror("Sign-in failed", "The username or password is incorrect.", parent=dialog)
                    password_var.set("")
                    hide_password()
                    password_entry.focus_set()
                    return
                stored_hash = str(user["password_hash"])
                if not stored_hash.startswith("pbkdf2_sha256$"):
                    self._execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (hash_password(password_var.get()), user["id"]),
                    )
            except sqlite3.Error as exc:
                messagebox.showerror("Sign-in failed", f"Could not verify the account:\n{exc}", parent=dialog)
                return

            self.current_user = {
                "id": str(user["id"]),
                "username": str(user["username"]),
                "role": str(user["role"]),
            }
            if self.current_user["role"] not in self.ROLE_PAGES:
                self.current_user = None
                messagebox.showerror(
                    "Sign-in failed",
                    "This account has an unsupported role. Ask an administrator to update it.",
                    parent=dialog,
                )
                return
            self.account_button.configure(
                text=f"Accounts  •  {self.current_user['username']}"
            )
            try:
                profile_image = (
                    bytes(user["profile_image"]) if user["profile_image"] else None
                )
                self._set_account_profile_photo(profile_image)
            except tk.TclError as exc:
                self._set_account_profile_photo(None)
                messagebox.showerror(
                    "Could not display profile photo",
                    f"Your account photo could not be displayed:\n{exc}",
                    parent=self,
                )
            self.header_user_var.set(
                f"{self.current_user['username']}  ·  {self.ROLE_LABELS[self.current_user['role']]}"
            )
            dialog.grab_release()
            dialog.destroy()
            self.deiconify()
            self._update_role_navigation()
            self._show_page("Dashboard")

        ttk.Button(body, text="Sign in", style="Primary.TButton", command=sign_in).pack(
            fill="x"
        )
        dialog.bind("<Return>", lambda _event: sign_in())
        dialog.update_idletasks()
        dialog_width = dialog.winfo_reqwidth()
        dialog_height = dialog.winfo_reqheight()
        screen_x = max(0, (dialog.winfo_screenwidth() - dialog_width) // 2)
        screen_y = max(0, (dialog.winfo_screenheight() - dialog_height) // 2)
        dialog.geometry(f"+{screen_x}+{screen_y}")
        self._apply_widget_theme(dialog)
        username_entry.focus_set()

    def _open_account_menu(self) -> None:
        if self.current_user is None:
            return
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Profile management", command=self._show_account_details)
        menu.add_command(label="Change password", command=self._change_password)
        if self.current_user["role"] == "admin":
            menu.add_command(label="Create user account", command=self._create_user_account)
            menu.add_command(
                label="Link employee account",
                command=self._link_employee_account,
            )
        menu.add_separator()
        menu.add_command(label="Log out", command=self._logout)
        try:
            menu.update_idletasks()
            menu_y = self.account_button.winfo_rooty() - menu.winfo_reqheight()
            menu.tk_popup(
                self.account_button.winfo_rootx(),
                max(0, menu_y),
            )
        finally:
            menu.grab_release()

    def _show_account_details(self) -> None:
        if self.current_user is None:
            return
        try:
            user = self._fetchone(
                "SELECT username, role, profile_image FROM users WHERE id = ?",
                (int(self.current_user["id"]),),
            )
        except sqlite3.Error as exc:
            messagebox.showerror("Could not load profile", str(exc), parent=self)
            return
        if user is None:
            messagebox.showerror(
                "Could not load profile",
                "The signed-in account could not be found.",
                parent=self,
            )
            return

        dialog = tk.Toplevel(self)
        dialog.title("Profile management")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Profile management", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text=f"Username: {user['username']}\nRole: {self.ROLE_LABELS[str(user['role'])]}",
            style="Muted.TLabel",
            justify="left",
        ).pack(anchor="w", pady=(6, 14))
        photo_label = ttk.Label(body, text="No profile photo", style="Muted.TLabel")
        photo_label.pack(anchor="w", pady=(0, 14))

        def display_photo(image_data: bytes | None) -> None:
            if not image_data:
                photo_label.configure(image="", text="No profile photo")
                photo_label.image = None
                return
            preview = self._make_profile_photo(image_data, dialog)
            photo_label.configure(image=preview, text="")
            photo_label.image = preview

        try:
            image_data = bytes(user["profile_image"]) if user["profile_image"] else None
            display_photo(image_data)
        except tk.TclError as exc:
            messagebox.showerror(
                "Could not display profile photo",
                f"The saved profile image is invalid or unsupported:\n{exc}",
                parent=dialog,
            )
            image_data = None
            display_photo(None)

        def change_photo() -> None:
            nonlocal image_data
            selected = self._select_profile_image(dialog)
            if selected is None:
                return
            photo_data, _filename = selected
            try:
                self._execute(
                    "UPDATE users SET profile_image = ? WHERE id = ?",
                    (sqlite3.Binary(photo_data), int(self.current_user["id"])),
                )
                display_photo(photo_data)
            except (sqlite3.Error, tk.TclError, ValueError) as exc:
                messagebox.showerror(
                    "Could not update profile photo", str(exc), parent=dialog
                )
                return
            image_data = photo_data
            self._set_account_profile_photo(photo_data)
            self.status_var.set("Profile photo updated")

        def remove_photo() -> None:
            nonlocal image_data
            if image_data is None:
                return
            if not messagebox.askyesno(
                "Remove profile photo",
                "Remove the profile photo from your account?",
                parent=dialog,
            ):
                return
            try:
                self._execute(
                    "UPDATE users SET profile_image = NULL WHERE id = ?",
                    (int(self.current_user["id"]),),
                )
            except sqlite3.Error as exc:
                messagebox.showerror(
                    "Could not remove profile photo", str(exc), parent=dialog
                )
                return
            image_data = None
            display_photo(None)
            self._set_account_profile_photo(None)
            self.status_var.set("Profile photo removed")

        buttons = ttk.Frame(body)
        buttons.pack(fill="x")
        ttk.Button(
            buttons,
            text="Choose photo",
            style="Primary.TButton",
            command=change_photo,
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Remove photo",
            style="Secondary.TButton",
            command=remove_photo,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            buttons, text="Close", style="Secondary.TButton", command=dialog.destroy
        ).pack(side="right")
        self._apply_widget_theme(dialog)

    def _select_profile_image(
        self, parent: tk.Misc
    ) -> tuple[bytes, str] | None:
        filename = filedialog.askopenfilename(
            parent=parent,
            title="Select profile photo",
            filetypes=self.PROFILE_IMAGE_FILETYPES,
        )
        if not filename:
            return None
        try:
            image_path = Path(filename)
            with image_path.open("rb") as image_file:
                image_data = image_file.read(self.PROFILE_IMAGE_MAX_BYTES + 1)
            if len(image_data) > self.PROFILE_IMAGE_MAX_BYTES:
                raise ValueError("Choose an image smaller than 5 MB.")
            image = tk.PhotoImage(
                master=parent,
                data=base64.b64encode(image_data),
            )
            if (
                image.width() > self.PROFILE_IMAGE_MAX_DIMENSION
                or image.height() > self.PROFILE_IMAGE_MAX_DIMENSION
            ):
                raise ValueError("Image dimensions must not exceed 4096 by 4096 pixels.")
        except (OSError, tk.TclError, ValueError) as exc:
            messagebox.showerror(
                "Unsupported profile photo",
                f"Choose a valid PNG, GIF, PPM, or PGM image under 5 MB.\n\n{exc}",
                parent=parent,
            )
            return None
        return image_data, image_path.name

    def _make_profile_photo(
        self, image_data: bytes, parent: tk.Misc, size: int = 128
    ) -> tk.PhotoImage:
        source = tk.PhotoImage(
            master=parent,
            data=base64.b64encode(image_data),
        )
        crop_size = min(source.width(), source.height())
        left = (source.width() - crop_size) // 2
        top = (source.height() - crop_size) // 2
        cropped = tk.PhotoImage(
            master=parent,
            width=crop_size,
            height=crop_size,
        )
        cropped.tk.call(
            cropped,
            "copy",
            source,
            "-from",
            left,
            top,
            left + crop_size,
            top + crop_size,
        )
        scale = max(1, (crop_size + size - 1) // size)
        resized = cropped.subsample(scale, scale) if scale > 1 else cropped
        width, height = resized.width(), resized.height()
        center_x, center_y = (width - 1) / 2, (height - 1) / 2
        radius = min(width, height) / 2
        inner_radius = max(0, radius - max(1, round(width / 48)))
        border_color = "#D4A017"
        circular = tk.PhotoImage(master=parent, width=width, height=height)

        for y in range(height):
            row = []
            for x in range(width):
                distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                if distance <= inner_radius:
                    red, green, blue = resized.get(x, y)
                    row.append(f"#{red:02x}{green:02x}{blue:02x}")
                else:
                    row.append(border_color)
            circular.put("{" + " ".join(row) + "}", to=(0, y))
            for x in range(width):
                if ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5 > radius:
                    circular.transparency_set(x, y, True)
        return circular

    def _set_account_profile_photo(self, image_data: bytes | None) -> None:
        if not image_data:
            self.profile_photo = None
            self.account_button.configure(image="", compound="none")
            return
        photo = self._make_profile_photo(image_data, self, size=40)
        self.profile_photo = photo
        self.account_button.configure(image=photo, compound="left")

    def _create_user_account(self) -> None:
        if not self._require_roles(("admin",), "create user accounts"):
            return
        dialog = tk.Toplevel(self)
        dialog.title("Create user account")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Create user account", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
        )
        ttk.Label(
            body,
            text="New accounts start with Employee access. You can link an employee profile now or later.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        username_var = tk.StringVar()
        password_var = tk.StringVar()
        confirm_var = tk.StringVar()
        role_var = tk.StringVar(value="Employee")
        employees = self._fetchall(
            "SELECT e.employee_id, e.first_name, e.last_name FROM employees e "
            "WHERE e.status = 'active' AND NOT EXISTS "
            "(SELECT 1 FROM users u WHERE u.employee_id = e.employee_id) "
            "ORDER BY e.last_name, e.first_name"
        )
        employee_options = {
            f"{row['last_name']}, {row['first_name']} ({self._employee_code(int(row['employee_id']))})":
            int(row["employee_id"])
            for row in employees
        }
        employee_options["Link later"] = None
        employee_var = tk.StringVar()
        selected_image_data: bytes | None = None
        image_preview = ttk.Label(body, text="No photo selected", style="Muted.TLabel")
        employee_combo = ttk.Combobox(
            body,
            textvariable=employee_var,
            values=tuple(employee_options),
            state="readonly",
            width=29,
        )
        employee_var.set(next(
            (label for label, employee_id in employee_options.items() if employee_id is not None),
            "Link later",
        ))
        fields = (
            ("Username", ttk.Entry(body, textvariable=username_var, width=32)),
            ("Password", ttk.Entry(body, textvariable=password_var, show="•", width=32)),
            ("Confirm password", ttk.Entry(body, textvariable=confirm_var, show="•", width=32)),
            (
                "Role",
                ttk.Combobox(
                    body,
                    textvariable=role_var,
                    values=("Employee", "HR", "Admin"),
                    state="readonly",
                    width=29,
                ),
            ),
            ("Employee profile (optional)", employee_combo),
        )
        for row, (label, widget) in enumerate(fields, start=2):
            ttk.Label(body, text=label, style="Muted.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=6
            )
            widget.grid(row=row, column=1, sticky="ew", pady=6)
        body.columnconfigure(1, weight=1)

        def update_employee_link(*_args: str) -> None:
            employee_combo.configure(
                state="readonly" if role_var.get() == "Employee" else "disabled"
            )

        role_var.trace_add("write", update_employee_link)
        update_employee_link()

        def choose_profile_image() -> None:
            nonlocal selected_image_data
            selected = self._select_profile_image(dialog)
            if selected is None:
                return
            selected_image_data, _filename = selected
            try:
                preview = self._make_profile_photo(selected_image_data, dialog)
            except tk.TclError as exc:
                selected_image_data = None
                messagebox.showerror(
                    "Could not preview profile photo", str(exc), parent=dialog
                )
                return
            image_preview.configure(image=preview, text="")
            image_preview.image = preview

        ttk.Label(body, text="Profile photo (optional)", style="Muted.TLabel").grid(
            row=7, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Button(
            body,
            text="Choose photo",
            style="Secondary.TButton",
            command=choose_profile_image,
        ).grid(row=7, column=1, sticky="w", pady=6)
        image_preview.grid(row=8, column=1, sticky="w", pady=6)

        def save() -> None:
            username = username_var.get().strip()
            password = password_var.get()
            role = next(
                (key for key, label in self.ROLE_LABELS.items() if label == role_var.get()),
                "",
            )
            if not username:
                messagebox.showerror("Username required", "Enter a username.", parent=dialog)
                return
            if len(password) < 8:
                messagebox.showerror(
                    "Password too short",
                    "Use at least 8 characters for the password.",
                    parent=dialog,
                )
                return
            if not any(character.isupper() for character in password):
                messagebox.showerror(
                    "Uppercase letter required",
                    "Include at least one uppercase letter in the password.",
                    parent=dialog,
                )
                return
            if not any(character.isdigit() for character in password):
                messagebox.showerror(
                    "Number required",
                    "Include at least one number in the password.",
                    parent=dialog,
                )
                return
            if password != confirm_var.get():
                messagebox.showerror(
                    "Passwords do not match",
                    "Enter the same password in both fields.",
                    parent=dialog,
                )
                return
            if role not in self.ROLE_PAGES:
                messagebox.showerror("Invalid role", "Select a valid account role.", parent=dialog)
                return
            employee_id = employee_options.get(employee_var.get())
            try:
                self._execute(
                    "INSERT INTO users "
                    "(username, password_hash, role, employee_id, profile_image) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        username,
                        hash_password(password),
                        role,
                        employee_id if role == "viewer" else None,
                        sqlite3.Binary(selected_image_data)
                        if selected_image_data is not None
                        else None,
                    ),
                )
            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Username already exists",
                    "Choose a different username.",
                    parent=dialog,
                )
                return
            except sqlite3.Error as exc:
                messagebox.showerror(
                    "Could not create account", str(exc), parent=dialog
                )
                return
            dialog.destroy()
            self.status_var.set(f"Created {self.ROLE_LABELS[role]} account: {username}")
            messagebox.showinfo(
                "Account created",
                f"{self.ROLE_LABELS[role]} account '{username}' is ready to sign in.",
                parent=self,
            )

        buttons = ttk.Frame(body)
        buttons.grid(row=9, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(
            buttons, text="Cancel", style="Secondary.TButton", command=dialog.destroy
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            buttons, text="Create account", style="Primary.TButton", command=save
        ).pack(side="right")
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 340}+{self.winfo_rooty() + 210}")

    def _link_employee_account(self) -> None:
        if not self._require_roles(("admin",), "link employee accounts"):
            return
        accounts = self._fetchall(
            "SELECT id, username FROM users WHERE role = 'viewer' AND employee_id IS NULL "
            "ORDER BY username"
        )
        employees = self._fetchall(
            "SELECT e.employee_id, e.first_name, e.last_name FROM employees e "
            "WHERE e.status = 'active' AND NOT EXISTS "
            "(SELECT 1 FROM users u WHERE u.employee_id = e.employee_id) "
            "ORDER BY e.last_name, e.first_name"
        )
        if not accounts or not employees:
            reasons = []
            if not accounts:
                reasons.append(
                    "There are no unlinked Employee accounts. Create an Employee account "
                    "and choose 'Link later' to link it here."
                )
            if not employees:
                reasons.append(
                    "There are no unlinked active employee profiles. Add or activate an "
                    "employee profile first."
                )
            messagebox.showinfo(
                "No accounts to link",
                "\n\n".join(reasons),
                parent=self,
            )
            return
        account_options = {str(row["username"]): int(row["id"]) for row in accounts}
        employee_options = {
            f"{row['last_name']}, {row['first_name']} ({self._employee_code(int(row['employee_id']))})":
            int(row["employee_id"])
            for row in employees
        }
        dialog = tk.Toplevel(self)
        dialog.title("Link employee account")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Link employee account", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        account_var = tk.StringVar(value=next(iter(account_options)))
        employee_var = tk.StringVar(value=next(iter(employee_options)))
        for row, (label, variable, values) in enumerate(
            (
                ("Employee account", account_var, tuple(account_options)),
                ("Employee profile", employee_var, tuple(employee_options)),
            ),
            start=1,
        ):
            ttk.Label(body, text=label, style="Muted.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=6
            )
            ttk.Combobox(
                body, textvariable=variable, values=values, state="readonly", width=38
            ).grid(row=row, column=1, sticky="ew", pady=6)
        body.columnconfigure(1, weight=1)

        def save() -> None:
            account_id = account_options[account_var.get()]
            employee_id = employee_options[employee_var.get()]
            try:
                connection = self.db_manager.get_connection()
                try:
                    cursor = connection.execute(
                        "UPDATE users SET employee_id = ? "
                        "WHERE id = ? AND role = 'viewer' AND employee_id IS NULL "
                        "AND EXISTS ("
                        "SELECT 1 FROM employees e WHERE e.employee_id = ? "
                        "AND e.status = 'active' AND NOT EXISTS ("
                        "SELECT 1 FROM users linked WHERE linked.employee_id = e.employee_id"
                        "))",
                        (employee_id, account_id, employee_id),
                    )
                    if cursor.rowcount != 1:
                        messagebox.showerror(
                            "Could not link employee account",
                            "The account or employee profile is no longer available to link. "
                            "Close this dialog and reopen it to refresh the list.",
                            parent=dialog,
                        )
                        return
                    connection.commit()
                finally:
                    connection.close()
            except sqlite3.Error as exc:
                messagebox.showerror(
                    "Could not link employee account", str(exc), parent=dialog
                )
                return
            dialog.destroy()
            self.status_var.set(f"Linked employee account: {account_var.get()}")
            messagebox.showinfo(
                "Account linked",
                "This employee account can now submit and track requests.",
                parent=self,
            )

        buttons = ttk.Frame(body)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(
            buttons, text="Cancel", style="Secondary.TButton", command=dialog.destroy
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            buttons, text="Link account", style="Primary.TButton", command=save
        ).pack(side="right")
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 320}+{self.winfo_rooty() + 220}")

    def _change_password(self) -> None:
        if self.current_user is None:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Change password")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Change password", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )
        current_var = tk.StringVar()
        new_var = tk.StringVar()
        confirm_var = tk.StringVar()
        password_fields = (
            ("Current password", current_var),
            ("New password", new_var),
            ("Confirm password", confirm_var),
        )
        for row, (label, variable) in enumerate(password_fields, start=1):
            ttk.Label(body, text=label, style="Muted.TLabel").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=6
            )
            ttk.Entry(body, textvariable=variable, show="•", width=30).grid(
                row=row, column=1, sticky="ew", pady=6
            )
        body.columnconfigure(1, weight=1)

        def save_password() -> None:
            if len(new_var.get()) < 8:
                messagebox.showerror(
                    "Password too short",
                    "Use at least 8 characters for the new password.",
                    parent=dialog,
                )
                return
            if new_var.get() != confirm_var.get():
                messagebox.showerror(
                    "Passwords do not match",
                    "Enter the same new password in both fields.",
                    parent=dialog,
                )
                return
            try:
                user = self._fetchone(
                    "SELECT password_hash FROM users WHERE id = ?",
                    (self.current_user["id"],),
                )
                if user is None or not verify_password(
                    current_var.get(), str(user["password_hash"])
                ):
                    messagebox.showerror(
                        "Current password incorrect",
                        "Check your current password and try again.",
                        parent=dialog,
                    )
                    return
                self._execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hash_password(new_var.get()), self.current_user["id"]),
                )
            except sqlite3.Error as exc:
                messagebox.showerror(
                    "Password was not changed", str(exc), parent=dialog
                )
                return
            dialog.destroy()
            messagebox.showinfo(
                "Password changed", "Your password has been updated.", parent=self
            )

        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(
            buttons, text="Cancel", style="Secondary.TButton", command=dialog.destroy
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            buttons, text="Save password", style="Primary.TButton", command=save_password
        ).pack(side="right")
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 360}+{self.winfo_rooty() + 230}")

    def _logout(self) -> None:
        if self.current_user is None:
            return
        self.current_user = None
        self._set_account_profile_photo(None)
        self.account_button.configure(text="Accounts  •  Sign in")
        self.header_user_var.set("Sign in to continue")
        self._update_role_navigation()
        for child in self.page_host.winfo_children():
            child.destroy()
        self._show_login()