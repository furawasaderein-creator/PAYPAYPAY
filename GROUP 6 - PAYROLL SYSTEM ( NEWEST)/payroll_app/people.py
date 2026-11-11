from __future__ import annotations

from config import ACCENT_BLUE
from config import BACKGROUND_COLOR
from config import BORDER_COLOR
from config import DANGER_COLOR
from config import GOLD_COLOR
from config import HEADING_FONT
from config import MUTED_COLOR
from config import SUCCESS_COLOR
from config import TEXT_COLOR
from config import WHITE
from datetime import date
from datetime import datetime
from decimal import Decimal
from decimal import InvalidOperation
from math import ceil
from tkinter import messagebox
import sqlite3
import tkinter as tk
from tkinter import ttk
from typing import Callable
from .core import DatePicker, RoundedCard, TimePicker
from .dashboard import DashboardPages
from .dsa import ChainedHashMap, linear_search_records, merge_sort_records

class PeoplePages(DashboardPages):
    def _build_employees(self) -> None:
        page = ttk.Frame(self.page_host)
        page.grid(row=0, column=0, sticky="nsew")
        page.rowconfigure(1, weight=1)
        page.columnconfigure(0, weight=1)
        toolbar = self._page_toolbar(page, "Employee directory", "Create and maintain employee profiles and pay rates.")
        if self.current_user and self.current_user["role"] in self.DEPARTMENT_MANAGEMENT_ROLES:
            ttk.Button(
                toolbar,
                text="Manage departments",
                style="Secondary.TButton",
                command=self._manage_departments,
            ).grid(row=0, column=1, rowspan=2, padx=(0, 8), sticky="e")
        if self.current_user and self.current_user["role"] in self.EDIT_ROLES:
            employee_column = 2 if self.current_user["role"] in self.DEPARTMENT_MANAGEMENT_ROLES else 1
            ttk.Button(toolbar, text="+  Add employee", style="Primary.TButton", command=self._open_employee_form).grid(row=0, column=employee_column, rowspan=2, sticky="e")

        controls = ttk.Frame(page)
        controls.pack(fill="both", expand=True)
        controls.rowconfigure(1, weight=1)
        controls.columnconfigure(0, weight=1)
        filter_panel = self._card(controls, padding=10)
        filter_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        filter_row = ttk.Frame(filter_panel.content, style="CardContent.TFrame")
        filter_row.pack(fill="x")
        self.employee_search_var = tk.StringVar()
        search = ttk.Entry(filter_row, textvariable=self.employee_search_var, width=34)
        search.pack(side="left")
        self.employee_search_var.trace_add("write", lambda *_: self._refresh_employees())
        ttk.Label(filter_row, text="Search employees by name, department, or position", style="CardMuted.TLabel").pack(side="left", padx=10)
        if self.current_user and self.current_user["role"] in self.EDIT_ROLES:
            ttk.Button(filter_row, text="Edit selected", style="Secondary.TButton", command=self._edit_selected_employee).pack(side="right", padx=(8, 0))
            ttk.Button(filter_row, text="Activate / deactivate", style="Secondary.TButton", command=self._toggle_employee_status).pack(side="right")
            ttk.Button(filter_row, text="Delete selected", style="Danger.TButton", command=self._delete_selected_employee).pack(side="right", padx=(8, 0))

        sort_row = ttk.Frame(filter_panel.content, style="CardContent.TFrame")
        sort_row.pack(fill="x", pady=(10, 0))
        ttk.Label(sort_row, text="Sort by", style="CardMuted.TLabel").pack(side="left", padx=(0, 5))
        self.employee_sort_by_var = tk.StringVar(value="Name")
        ttk.Combobox(
            sort_row,
            textvariable=self.employee_sort_by_var,
            values=("Employee ID", "Name"),
            state="readonly",
            width=13,
        ).pack(side="left")
        self.employee_sort_order_var = tk.StringVar(value="Ascending")
        ttk.Combobox(
            sort_row,
            textvariable=self.employee_sort_order_var,
            values=("Ascending", "Descending"),
            state="readonly",
            width=12,
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            sort_row,
            text="Sort",
            style="Secondary.TButton",
            command=self._refresh_employees,
        ).pack(side="left", padx=(6, 0))

        self.employee_tree = self._make_tree(
            controls,
            ("id", "name", "department", "position", "rate", "status"),
            {"id": "EMPLOYEE ID", "name": "EMPLOYEE", "department": "DEPARTMENT", "position": "POSITION", "rate": "HOURLY RATE", "status": "STATUS"},
            {"id": 105, "name": 185, "department": 155, "position": 150, "rate": 140, "status": 90},
            use_grid=True,
        )
        self.employee_tree.bind("<Double-1>", lambda _event: self._edit_selected_employee())
        self._refresh_employees()

    def _refresh_employees(self) -> None:
        if not hasattr(self, "employee_tree") or not self.employee_tree.winfo_exists():
            return
        for item in self.employee_tree.get_children():
            self.employee_tree.delete(item)
        records = self._fetchall(
            "SELECT e.employee_id, e.first_name, e.middle_name, e.last_name, e.position, e.hourly_rate, "
            "e.status, COALESCE(d.department_name, 'Unassigned') AS department "
            "FROM employees e LEFT JOIN departments d ON d.department_id = e.department_id"
        )
        self._employee_index: ChainedHashMap[int, sqlite3.Row] = ChainedHashMap()
        for record in records:
            self._employee_index[int(record["employee_id"])] = record
        searchable_rows = linear_search_records(
            records,
            self.employee_search_var.get(),
            lambda row: tuple(
                str(row[field] or "")
                for field in (
                    "first_name",
                    "middle_name",
                    "last_name",
                    "position",
                    "department",
                )
            ),
        )
        sort_by = self.employee_sort_by_var.get()
        reverse = self.employee_sort_order_var.get() == "Descending"
        if sort_by == "Employee ID":
            sort_key = lambda row: int(row["employee_id"])
        else:
            sort_key = lambda row: (
                str(row["last_name"] or "").casefold(),
                str(row["first_name"] or "").casefold(),
                int(row["employee_id"]),
            )
        rows = merge_sort_records(searchable_rows, key=sort_key, reverse=reverse)
        for row in rows:
            full_name = " ".join(part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part)
            hourly_rate = row["hourly_rate"]
            rate = f"{self._money(hourly_rate)} / hr" if hourly_rate is not None else "Not set"
            tag = () if row["status"] == "active" else ("inactive",)
            self.employee_tree.insert("", "end", iid=str(row["employee_id"]), values=(
                self._employee_code(int(row["employee_id"])), full_name, row["department"], row["position"] or "—", rate, row["status"].title()
            ), tags=tag)
        self.status_var.set(f"Showing {len(rows)} employee record(s)")

    def _selected_employee_id(self) -> int | None:
        if not hasattr(self, "employee_tree"):
            return None
        selection = self.employee_tree.selection()
        return int(selection[0]) if selection else None

    def _edit_selected_employee(self) -> None:
        if not self._require_roles(self.EDIT_ROLES, "edit employee records"):
            return
        employee_id = self._selected_employee_id()
        if employee_id is None:
            messagebox.showinfo("Select an employee", "Choose an employee row first.", parent=self)
            return
        self._open_employee_form(employee_id)

    def _toggle_employee_status(self) -> None:
        if not self._require_roles(self.EDIT_ROLES, "change employee status"):
            return
        employee_id = self._selected_employee_id()
        if employee_id is None:
            messagebox.showinfo("Select an employee", "Choose an employee row first.", parent=self)
            return
        row = self._employee_index.get(employee_id) if hasattr(self, "_employee_index") else None
        if row is None:
            row = self._fetchone(
                "SELECT status, first_name, last_name FROM employees WHERE employee_id = ?",
                (employee_id,),
            )
        if row is None:
            messagebox.showerror("Employee not found", "Refresh the directory and try again.", parent=self)
            return
        next_status = "inactive" if row["status"] == "active" else "active"
        if messagebox.askyesno("Update employee status", f"Mark {row['first_name']} {row['last_name']} as {next_status}?", parent=self):
            self._execute("UPDATE employees SET status = ? WHERE employee_id = ?", (next_status, employee_id))
            self._refresh_employees()

    def _delete_selected_employee(self) -> None:
        if not self._require_roles(self.EDIT_ROLES, "delete employee records"):
            return
        employee_id = self._selected_employee_id()
        if employee_id is None:
            messagebox.showinfo("Select an employee", "Choose an employee row first.", parent=self)
            return
        employee = self._fetchone(
            "SELECT first_name, last_name FROM employees WHERE employee_id = ?",
            (employee_id,),
        )
        if employee is None:
            messagebox.showerror("Employee not found", "Refresh the directory and try again.", parent=self)
            self._refresh_employees()
            return
        full_name = f"{employee['first_name']} {employee['last_name']}"
        if not messagebox.askyesno(
            "Delete employee",
            f"Delete {full_name}? This cannot be undone. Employees with related records cannot be deleted.",
            parent=self,
        ):
            return
        try:
            self._execute("DELETE FROM employees WHERE employee_id = ?", (employee_id,))
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Could not delete employee",
                "This employee has related records and cannot be deleted. Deactivate the employee instead.",
                parent=self,
            )
            return
        except sqlite3.Error as exc:
            messagebox.showerror("Could not delete employee", str(exc), parent=self)
            return
        self._refresh_employees()

    def _manage_departments(
        self,
        parent: tk.Misc | None = None,
        on_close: Callable[[], None] | None = None,
        on_positions_changed: Callable[[], None] | None = None,
    ) -> None:
        """Open the department manager (add, rename, delete)."""
        if not self._require_roles(self.DEPARTMENT_MANAGEMENT_ROLES, "manage departments"):
            return
        owner = parent if parent is not None else self
        dialog = tk.Toplevel(owner)
        dialog.title("Manage departments")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(owner.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("580x500")
        dialog.minsize(500, 400)
        body = ttk.Frame(dialog, padding=22)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Manage departments", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text="Add, rename, or remove departments. A department can only be "
            "deleted when no employees are assigned to it.",
            style="Muted.TLabel",
            wraplength=510,
        ).pack(anchor="w", pady=(4, 12))

        buttons = ttk.Frame(body)
        buttons.pack(side="bottom", fill="x", pady=(12, 0))
        tree = self._make_tree(
            body,
            ("department", "employees"),
            {"department": "DEPARTMENT", "employees": "EMPLOYEES"},
            {"department": 340, "employees": 110},
            height=10,
        )

        def refresh() -> None:
            for item in tree.get_children():
                tree.delete(item)
            for row in self._fetchall(
                "SELECT d.department_id, d.department_name, COUNT(e.employee_id) AS total "
                "FROM departments d LEFT JOIN employees e "
                "ON e.department_id = d.department_id "
                "GROUP BY d.department_id, d.department_name "
                "ORDER BY d.department_name COLLATE NOCASE"
            ):
                tree.insert(
                    "",
                    "end",
                    iid=str(row["department_id"]),
                    values=(row["department_name"], row["total"]),
                )

        def changed() -> None:
            refresh()
            if self.current_page == "Employees":
                self._refresh_employees()

        def selected_department() -> tuple[int, str] | None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo(
                    "Select a department", "Choose a department first.", parent=dialog
                )
                return None
            return int(selection[0]), str(tree.item(selection[0], "values")[0])

        def add() -> None:
            self._open_department_form(parent=dialog, on_saved=changed)

        def edit() -> None:
            chosen = selected_department()
            if chosen is not None:
                self._open_department_form(chosen[0], parent=dialog, on_saved=changed)

        def delete() -> None:
            chosen = selected_department()
            if chosen is None:
                return
            department_id, department_name = chosen
            assigned = int(
                self._fetchone(
                    "SELECT COUNT(*) AS total FROM employees WHERE department_id = ?",
                    (department_id,),
                )["total"]
            )
            if assigned:
                messagebox.showerror(
                    "Department is in use",
                    f"{department_name} has {assigned} employee(s) assigned. "
                    "Reassign them to another department before deleting it.",
                    parent=dialog,
                )
                return
            if not messagebox.askyesno(
                "Delete department",
                f"Delete the {department_name} department? This cannot be undone.",
                parent=dialog,
            ):
                return
            try:
                self._execute(
                    "DELETE FROM departments WHERE department_id = ?", (department_id,)
                )
            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Department is in use",
                    "Reassign its employees before deleting this department.",
                    parent=dialog,
                )
                return
            except sqlite3.Error as exc:
                messagebox.showerror("Could not delete department", str(exc), parent=dialog)
                return
            changed()
            self.status_var.set(f"Department deleted: {department_name}")

        def manage_positions() -> None:
            chosen = selected_department()
            if chosen is not None:
                self._manage_department_positions(
                    chosen[0],
                    parent=dialog,
                    on_close=lambda: dialog.grab_set(),
                    on_change=on_positions_changed,
                )

        def close() -> None:
            dialog.grab_release()
            dialog.destroy()
            if on_close is not None:
                on_close()

        ttk.Button(buttons, text="Add department", style="Primary.TButton", command=add).pack(side="left")
        ttk.Button(buttons, text="Edit", style="Secondary.TButton", command=edit).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Delete", style="Danger.TButton", command=delete).pack(side="left", padx=(8, 0))
        if self.current_user and self.current_user["role"] in self.POSITION_MANAGEMENT_ROLES:
            ttk.Button(buttons, text="Manage positions", style="Secondary.TButton", command=manage_positions).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", style="Secondary.TButton", command=close).pack(side="right")
        tree.bind("<Double-1>", lambda _event: edit())
        dialog.protocol("WM_DELETE_WINDOW", close)
        dialog.bind("<Escape>", lambda _event: close())
        refresh()

    def _manage_department_positions(
        self,
        department_id: int,
        *,
        parent: tk.Misc | None = None,
        on_close: Callable[[], None] | None = None,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        if not self._require_roles(self.POSITION_MANAGEMENT_ROLES, "manage department positions"):
            return
        department = self._fetchone(
            "SELECT department_name FROM departments WHERE department_id = ?",
            (department_id,),
        )
        if department is None:
            messagebox.showerror(
                "Department not found",
                "Refresh the department list and try again.",
                parent=parent or self,
            )
            return

        owner = parent if parent is not None else self
        dialog = tk.Toplevel(owner)
        dialog.title(f"Manage positions — {department['department_name']}")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(owner.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("540x440")
        dialog.minsize(460, 360)
        body = ttk.Frame(dialog, padding=22)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=f"Positions — {department['department_name']}", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            body,
            text="Only positions listed here can be assigned to employees in this department.",
            style="Muted.TLabel",
            wraplength=480,
        ).pack(anchor="w", pady=(4, 12))
        buttons = ttk.Frame(body)
        buttons.pack(side="bottom", fill="x", pady=(12, 0))
        tree = self._make_tree(
            body,
            ("position",),
            {"position": "POSITION"},
            {"position": 440},
            height=9,
        )

        def refresh() -> None:
            for item in tree.get_children():
                tree.delete(item)
            for row in self._fetchall(
                "SELECT position_id, position_name FROM department_positions "
                "WHERE department_id = ? ORDER BY position_name COLLATE NOCASE",
                (department_id,),
            ):
                tree.insert("", "end", iid=str(row["position_id"]), values=(row["position_name"],))

        def selected_position() -> tuple[int, str] | None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo(
                    "Select a position", "Choose a position first.", parent=dialog
                )
                return None
            return int(selection[0]), str(tree.item(selection[0], "values")[0])

        def edit_position(position_id: int | None = None, current_name: str = "") -> None:
            position_dialog = tk.Toplevel(dialog)
            position_dialog.title("Edit position" if position_id is not None else "Add position")
            position_dialog.configure(bg=BACKGROUND_COLOR)
            position_dialog.transient(dialog)
            position_dialog.grab_set()
            position_dialog.resizable(False, False)
            form = ttk.Frame(position_dialog, padding=20)
            form.pack(fill="both", expand=True)
            ttk.Label(
                form,
                text="Position name",
                style="Muted.TLabel",
            ).pack(anchor="w", pady=(0, 6))
            name_var = tk.StringVar(value=current_name)
            name_entry = ttk.Entry(form, textvariable=name_var, width=38)
            name_entry.pack(fill="x")
            name_entry.focus_set()
            name_entry.select_range(0, "end")

            def close_position_form() -> None:
                position_dialog.grab_release()
                position_dialog.destroy()
                dialog.grab_set()

            def save_position() -> None:
                name = " ".join(name_var.get().split())
                if not name:
                    messagebox.showerror("Position required", "Enter a position name.", parent=position_dialog)
                    return
                if len(name) > 60:
                    messagebox.showerror("Name too long", "Use 60 characters or fewer.", parent=position_dialog)
                    return
                duplicate = self._fetchone(
                    "SELECT 1 FROM department_positions "
                    "WHERE department_id = ? AND LOWER(position_name) = LOWER(?) "
                    "AND position_id != ?",
                    (department_id, name, position_id if position_id is not None else -1),
                )
                if duplicate:
                    messagebox.showerror(
                        "Position exists",
                        "That position is already listed for this department.",
                        parent=position_dialog,
                    )
                    return
                try:
                    if position_id is None:
                        self._execute(
                            "INSERT INTO department_positions (department_id, position_name) "
                            "VALUES (?, ?)",
                            (department_id, name),
                        )
                    else:
                        self._execute(
                            "UPDATE department_positions SET position_name = ? "
                            "WHERE position_id = ? AND department_id = ?",
                            (name, position_id, department_id),
                        )
                except sqlite3.IntegrityError:
                    messagebox.showerror(
                        "Position exists",
                        "That position is already listed for this department.",
                        parent=position_dialog,
                    )
                    return
                except sqlite3.Error as exc:
                    messagebox.showerror(
                        "Could not save position", str(exc), parent=position_dialog
                    )
                    return
                close_position_form()
                refresh()
                if on_change is not None:
                    on_change()

            actions = ttk.Frame(form)
            actions.pack(fill="x", pady=(14, 0))
            ttk.Button(
                actions,
                text="Cancel",
                style="Secondary.TButton",
                command=close_position_form,
            ).pack(side="right", padx=(8, 0))
            ttk.Button(
                actions,
                text="Save position",
                style="Primary.TButton",
                command=save_position,
            ).pack(side="right")
            position_dialog.protocol("WM_DELETE_WINDOW", close_position_form)
            position_dialog.bind("<Return>", lambda _event: save_position())
            position_dialog.bind("<Escape>", lambda _event: close_position_form())

        def add() -> None:
            edit_position()

        def edit() -> None:
            chosen = selected_position()
            if chosen is not None:
                edit_position(chosen[0], chosen[1])

        def delete() -> None:
            chosen = selected_position()
            if chosen is None:
                return
            position_id, name = chosen
            if not messagebox.askyesno(
                "Delete position",
                f"Remove {name} from the {department['department_name']} department?",
                parent=dialog,
            ):
                return
            try:
                self._execute(
                    "DELETE FROM department_positions "
                    "WHERE position_id = ? AND department_id = ?",
                    (position_id, department_id),
                )
            except sqlite3.Error as exc:
                messagebox.showerror("Could not delete position", str(exc), parent=dialog)
                return
            refresh()
            if on_change is not None:
                on_change()

        def close() -> None:
            dialog.grab_release()
            dialog.destroy()
            if on_close is not None:
                on_close()

        ttk.Button(buttons, text="Add position", style="Primary.TButton", command=add).pack(side="left")
        ttk.Button(buttons, text="Edit", style="Secondary.TButton", command=edit).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Delete", style="Danger.TButton", command=delete).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Close", style="Secondary.TButton", command=close).pack(side="right")
        tree.bind("<Double-1>", lambda _event: edit())
        dialog.protocol("WM_DELETE_WINDOW", close)
        dialog.bind("<Escape>", lambda _event: close())
        refresh()

    def _open_department_form(
        self,
        department_id: int | None = None,
        *,
        parent: tk.Misc | None = None,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        if not self._require_roles(self.DEPARTMENT_MANAGEMENT_ROLES, "manage departments"):
            return
        owner = parent if parent is not None else self
        department = (
            self._fetchone(
                "SELECT department_name FROM departments WHERE department_id = ?",
                (department_id,),
            )
            if department_id is not None
            else None
        )
        if department_id is not None and department is None:
            messagebox.showerror(
                "Department not found",
                "Refresh the department list and try again.",
                parent=owner,
            )
            return
        dialog = tk.Toplevel(owner)
        dialog.title("Edit department" if department else "Add department")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(owner.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=22)
        body.pack(fill="both", expand=True)
        ttk.Label(
            body,
            text="Edit department" if department else "New department",
            style="Title.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            body,
            text="Departments are used to categorize employee profiles.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 13))
        department_var = tk.StringVar(
            value=str(department["department_name"]) if department else ""
        )
        entry = ttk.Entry(body, textvariable=department_var, width=38)
        entry.pack(fill="x")
        entry.focus_set()
        entry.select_range(0, "end")

        def close() -> None:
            dialog.grab_release()
            dialog.destroy()
            if owner is not self:
                try:
                    owner.grab_set()  # give modality back to the department manager
                except tk.TclError:
                    pass

        def save() -> None:
            name = " ".join(department_var.get().split())
            if not name:
                messagebox.showerror("Department required", "Enter a department name.", parent=dialog)
                return
            if len(name) > 60:
                messagebox.showerror("Name too long", "Use 60 characters or fewer.", parent=dialog)
                return
            duplicate = self._fetchone(
                "SELECT 1 FROM departments WHERE LOWER(department_name) = LOWER(?) "
                "AND department_id != ?",
                (name, department_id if department_id is not None else -1),
            )
            if duplicate:
                messagebox.showerror(
                    "Department exists",
                    "A department with that name already exists.",
                    parent=dialog,
                )
                return
            try:
                if department_id is None:
                    self._execute("INSERT INTO departments (department_name) VALUES (?)", (name,))
                else:
                    self._execute(
                        "UPDATE departments SET department_name = ? WHERE department_id = ?",
                        (name, department_id),
                    )
            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Department exists",
                    "A department with that name already exists.",
                    parent=dialog,
                )
                return
            except sqlite3.Error as exc:
                messagebox.showerror("Could not save department", str(exc), parent=dialog)
                return
            close()
            self.status_var.set(
                f"Department {'updated' if department_id is not None else 'added'}: {name}"
            )
            if on_saved:
                on_saved()

        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="Cancel", style="Secondary.TButton", command=close).pack(side="right", padx=(8, 0))
        ttk.Button(
            actions,
            text="Save changes" if department else "Save department",
            style="Primary.TButton",
            command=save,
        ).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", close)
        dialog.bind("<Return>", lambda _event: save())
        dialog.bind("<Escape>", lambda _event: close())
        dialog.update_idletasks()
        dialog.geometry(f"+{owner.winfo_rootx() + 60}+{owner.winfo_rooty() + 80}")

    def _open_employee_form(self, employee_id: int | None = None) -> None:
        if not self._require_roles(self.EDIT_ROLES, "create or edit employee records"):
            return
        employee = (
            self._fetchone("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
            if employee_id is not None
            else None
        )
        departments = self._fetchall("SELECT department_id, department_name FROM departments ORDER BY department_name")
        dialog = tk.Toplevel(self)
        dialog.title("Edit employee" if employee else "Add employee")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Edit employee" if employee else "New employee", style="Title.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 3))
        ttk.Label(body, text="Fields marked * are required. Set the shift start and end in 24-hour time.", style="Muted.TLabel").grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 18))

        fields: dict[str, tk.StringVar | DatePicker] = {}
        def valid_name(proposed: str) -> bool:
            allowed_punctuation = " '-."
            return not proposed or all(
                character.isalpha() or character in allowed_punctuation
                for character in proposed
            )

        def valid_middle_name(proposed: str) -> bool:
            return not proposed or all(
                character.isalpha() or character in " ."
                for character in proposed
            )

        def valid_contact_number(proposed: str) -> bool:
            return len(proposed) <= 11 and all(character in "0123456789" for character in proposed)

        def valid_hourly_rate(proposed: str) -> bool:
            if not proposed:
                return True
            if (
                not proposed.isascii()
                or proposed.count(".") > 1
                or not all(character.isdigit() or character == "." for character in proposed)
            ):
                return False
            fractional_part = proposed.partition(".")[2]
            if len(fractional_part) > 2:
                return False
            if proposed == ".":
                return True
            try:
                return Decimal(proposed) <= Decimal("999.99")
            except InvalidOperation:
                return False

        name_validation = (dialog.register(valid_name), "%P")
        middle_name_validation = (dialog.register(valid_middle_name), "%P")
        contact_number_validation = (
            dialog.register(valid_contact_number),
            "%P",
        )
        hourly_rate_validation = (dialog.register(valid_hourly_rate), "%P")
        position_var = tk.StringVar()
        position_combo: ttk.Combobox | None = None
        position_choices: tuple[str, ...] = ()
        entries = (
            ("first_name", "First name *", 0),
            ("middle_name", "Middle name", 1),
            ("last_name", "Last name *", 2),
            ("gender", "Gender", 3),
            ("birth_date", "Birth date", 4),
            ("position", "Position", 5),
            ("hire_date", "Hire date", 6),
            ("contact_number", "Contact number", 7),
            ("email", "Email", 8),
            ("address", "Address", 9),
        )
        for index, (key, label, row_index) in enumerate(entries):
            column = 0 if index < 5 else 2
            row_index = index + 2 if index < 5 else index - 3
            ttk.Label(body, text=label, style="Muted.TLabel").grid(row=row_index, column=column, sticky="w", padx=(0, 12), pady=5)
            if key in ("birth_date", "hire_date"):
                today = date.today()
                if key == "birth_date":
                    picker_range: dict = {
                        "min_year": 1930,
                        "max_year": today.year - 15,
                        "initial_view": date(today.year - 30, 1, 1),
                    }
                else:
                    picker_range = {"min_year": 1980, "max_year": today.year + 1}
                field: tk.StringVar | DatePicker = DatePicker(
                    body,
                    str(employee[key] or "") if employee else "",
                    allow_empty=True,
                    width=20,
                    **picker_range,
                )
            else:
                field_value = str(employee[key] or "") if employee else ""
                if key == "gender":
                    field_value = field_value.lower()
                    if field_value not in ("male", "female"):
                        field_value = ""
                    else:
                        field_value = field_value.upper()
                if key == "position":
                    position_var.set(field_value)
                    field = position_var
                else:
                    field = tk.StringVar(value=field_value)
            fields[key] = field
            if isinstance(field, DatePicker):
                field.grid(row=row_index, column=column + 1, sticky="ew", pady=5)
            elif key == "gender":
                ttk.Combobox(
                    body,
                    textvariable=field,
                    values=("MALE", "FEMALE"),
                    state="readonly",
                    width=25,
                ).grid(row=row_index, column=column + 1, sticky="ew", pady=5)
            elif key == "position":
                position_combo = ttk.Combobox(
                    body,
                    textvariable=position_var,
                    values=(),
                    state="readonly",
                    width=25,
                )
                position_combo.grid(
                    row=row_index, column=column + 1, sticky="ew", pady=5
                )
            else:
                entry_options = (
                    {"validate": "key", "validatecommand": contact_number_validation}
                    if key == "contact_number"
                    else {"validate": "key", "validatecommand": name_validation}
                    if key in ("first_name", "last_name")
                    else {"validate": "key", "validatecommand": middle_name_validation}
                    if key == "middle_name"
                    else {}
                )
                entry = ttk.Entry(body, textvariable=field, width=27, **entry_options)
                entry.grid(row=row_index, column=column + 1, sticky="ew", pady=5)
        department_names = {str(row["department_name"]): int(row["department_id"]) for row in departments}
        ttk.Label(body, text="Department", style="Muted.TLabel").grid(row=7, column=0, sticky="w", pady=5)
        department_var = tk.StringVar()
        department_combo = ttk.Combobox(body, textvariable=department_var, values=tuple(department_names), state="readonly", width=25)
        department_combo.grid(row=7, column=1, sticky="ew", pady=5)
        if employee and employee["department_id"] is not None:
            department_var.set(next((name for name, value in department_names.items() if value == employee["department_id"]), ""))

        def refresh_position_choices() -> None:
            nonlocal position_choices
            if position_combo is None:
                return
            selected_department_id = department_names.get(department_var.get())
            positions = (
                [
                    str(row["position_name"])
                    for row in self._fetchall(
                        "SELECT position_name FROM department_positions "
                        "WHERE department_id = ? ORDER BY position_name COLLATE NOCASE",
                        (selected_department_id,),
                    )
                ]
                if selected_department_id is not None
                else []
            )
            current_position = position_var.get().strip()
            if (
                employee
                and employee["department_id"] == selected_department_id
                and current_position
                and current_position not in positions
            ):
                positions.append(current_position)
            position_choices = tuple(positions)
            position_combo.configure(values=position_choices)
            if current_position not in positions:
                position_var.set("")

        refresh_position_choices()
        department_combo.bind(
            "<<ComboboxSelected>>", lambda _event: refresh_position_choices()
        )

        def refresh_department_choices() -> None:
            selected_id = department_names.get(department_var.get())
            rows = self._fetchall(
                "SELECT department_id, department_name FROM departments "
                "ORDER BY department_name COLLATE NOCASE"
            )
            department_names.clear()
            department_names.update(
                {str(row["department_name"]): int(row["department_id"]) for row in rows}
            )
            department_combo.configure(values=tuple(department_names))
            department_var.set(
                next((name for name, value in department_names.items() if value == selected_id), "")
            )
            refresh_position_choices()

        def open_department_manager() -> None:
            self._manage_departments(
                parent=dialog,
                on_close=lambda: (refresh_department_choices(), dialog.grab_set()),
                on_positions_changed=refresh_position_choices,
            )

        ttk.Label(body, text="Hourly rate *", style="Muted.TLabel").grid(row=8, column=0, sticky="w", pady=5)
        hourly_rate_value = employee["hourly_rate"] if employee else None
        hourly_rate_text = ""
        if hourly_rate_value is not None:
            numeric_hourly_rate = float(hourly_rate_value)
            hourly_rate_text = (
                str(int(numeric_hourly_rate))
                if numeric_hourly_rate.is_integer()
                else str(hourly_rate_value)
            )
        hourly_var = tk.StringVar(value=hourly_rate_text)
        ttk.Entry(
            body,
            textvariable=hourly_var,
            width=27,
            validate="key",
            validatecommand=hourly_rate_validation,
        ).grid(row=8, column=1, sticky="ew", pady=5)
        ttk.Label(body, text="Status", style="Muted.TLabel").grid(row=8, column=2, sticky="w", padx=(18, 12), pady=5)
        status_var = tk.StringVar(value=(employee["status"] or "active").title() if employee else "Active")
        ttk.Combobox(body, textvariable=status_var, values=("Active", "Inactive"), state="readonly", width=25).grid(row=8, column=3, sticky="ew", pady=5)
        shift_time_pickers: dict[str, TimePicker] = {}
        schedule_fields = (
            (
                "scheduled_start_time",
                "Shift starts *",
                str(employee["scheduled_start_time"] or "09:00") if employee else "09:00",
                0,
                1,
            ),
            (
                "scheduled_end_time",
                "Shift ends *",
                str(employee["scheduled_end_time"] or "17:00") if employee else "17:00",
                2,
                3,
            ),
        )
        for key, label, value, label_column, field_column in schedule_fields:
            try:
                normalized_time = datetime.strptime(value, "%H:%M").strftime("%H:%M")
            except ValueError:
                messagebox.showerror(
                    "Invalid schedule",
                    f"This employee has an invalid {label.lower()} time. Correct it in the database before editing the profile.",
                    parent=self,
                )
                dialog.destroy()
                return
            ttk.Label(body, text=label, style="Muted.TLabel").grid(
                row=9, column=label_column, sticky="w", pady=5,
                padx=(18, 12) if label_column else 0,
            )
            time_picker = TimePicker(body, normalized_time)
            time_picker.grid(row=9, column=field_column, sticky="w", pady=5)
            shift_time_pickers[key] = time_picker

        body.columnconfigure(1, weight=1)
        body.columnconfigure(3, weight=1)

        def save() -> None:
            first_name = fields["first_name"].get().strip()
            middle_name = fields["middle_name"].get().strip()
            last_name = fields["last_name"].get().strip()
            if not first_name or not last_name:
                messagebox.showerror("Required information", "First name and last name are required.", parent=dialog)
                return
            if not valid_name(first_name) or not valid_name(last_name):
                messagebox.showerror(
                    "Invalid name",
                    "First and last names can contain letters, spaces, apostrophes, hyphens, and periods only.",
                    parent=dialog,
                )
                return
            if not valid_middle_name(middle_name):
                messagebox.showerror(
                    "Invalid middle name",
                    "Middle names can contain letters, spaces, and periods only.",
                    parent=dialog,
                )
                return
            email = fields["email"].get().strip()
            if email and "@" not in email:
                messagebox.showerror(
                    "Invalid email",
                    "Email must contain an '@' symbol.",
                    parent=dialog,
                )
                return
            contact_number = fields["contact_number"].get().strip()
            if contact_number and not (
                len(contact_number) == 11 and valid_contact_number(contact_number)
            ):
                messagebox.showerror(
                    "Invalid contact number",
                    "Enter exactly 11 digits for the contact number.",
                    parent=dialog,
                )
                return
            try:
                hourly_rate_text = hourly_var.get()
                if not valid_hourly_rate(hourly_rate_text):
                    raise ValueError
                hourly_rate = float(hourly_rate_text)
                if hourly_rate <= 0:
                    raise ValueError
                scheduled_start_time = shift_time_pickers["scheduled_start_time"].get()
                scheduled_end_time = shift_time_pickers["scheduled_end_time"].get()
                if scheduled_start_time == scheduled_end_time:
                    raise ValueError
                for key in ("birth_date", "hire_date"):
                    if fields[key].get().strip():
                        date.fromisoformat(fields[key].get().strip())
            except ValueError:
                messagebox.showerror(
                    "Invalid information",
                    "Select valid dates, enter an hourly rate greater than 0 and no more than 999.99 with at most two decimal places, and choose different valid shift start and end times.",
                    parent=dialog,
                )
                return
            selected_department_id = department_names.get(department_var.get())
            selected_position = position_var.get().strip()
            if selected_position and selected_department_id is None:
                messagebox.showerror(
                    "Department required",
                    "Choose a department before assigning a position.",
                    parent=dialog,
                )
                return
            if selected_position and (
                position_combo is None or selected_position not in position_choices
            ):
                messagebox.showerror(
                    "Position required",
                    "Choose a position listed for the selected department.",
                    parent=dialog,
                )
                return
            values = (
                first_name,
                last_name,
                middle_name or None,
                fields["gender"].get().strip().lower() or None,
                fields["birth_date"].get().strip() or None,
                selected_department_id,
                selected_position or None,
                "hourly",
                None,
                None,
                hourly_rate,
                scheduled_start_time,
                scheduled_end_time,
                fields["hire_date"].get().strip() or None,
                contact_number or None,
                email or None,
                fields["address"].get().strip() or None,
                status_var.get().lower(),
            )
            try:
                if employee_id is None:
                    self._execute(
                        "INSERT INTO employees (first_name,last_name,middle_name,gender,birth_date,department_id,position,"
                        "salary_type,daily_rate,monthly_salary,hourly_rate,scheduled_start_time,scheduled_end_time,hire_date,contact_number,email,address,status) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        values,
                    )
                else:
                    self._execute(
                        "UPDATE employees SET first_name=?,last_name=?,middle_name=?,gender=?,birth_date=?,department_id=?,"
                        "position=?,salary_type=?,daily_rate=?,monthly_salary=?,hourly_rate=?,scheduled_start_time=?,scheduled_end_time=?,hire_date=?,contact_number=?,email=?,address=?,status=? "
                        "WHERE employee_id=?",
                        values + (employee_id,),
                    )
            except sqlite3.Error as exc:
                messagebox.showerror("Could not save employee", str(exc), parent=dialog)
                return
            dialog.destroy()
            if self.current_page == "Employees":
                self._refresh_employees()
            else:
                self._show_page(self.current_page)
            self.status_var.set("Employee profile saved")

        buttons = ttk.Frame(body)
        buttons.grid(row=11, column=0, columnspan=4, sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="Cancel", style="Secondary.TButton", command=dialog.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save employee", style="Primary.TButton", command=save).pack(side="left")
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 180}+{self.winfo_rooty() + 90}")