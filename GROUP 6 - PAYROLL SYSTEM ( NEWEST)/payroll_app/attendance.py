from __future__ import annotations

from typing import Any
from config import BACKGROUND_COLOR
from datetime import date
from datetime import datetime
from tkinter import messagebox
import sqlite3
import tkinter as tk
from tkinter import ttk
from .core import PayrollAppCore, DatePicker, TimePicker, calculate_attendance_hours, calculate_late_minutes
from .people import PeoplePages

class AttendancePages(PeoplePages):
    def _build_attendance(self) -> None:
        page = ttk.Frame(self.page_host)
        page.grid(row=0, column=0, sticky="nsew")
        page.rowconfigure(1, weight=1)
        page.columnconfigure(0, weight=1)
        toolbar = self._page_toolbar(page, "Attendance records", "Record hours worked and overtime for each employee.")
        if self.current_user and self.current_user["role"] in self.EDIT_ROLES:
            ttk.Button(toolbar, text="+  Record attendance", style="Primary.TButton", command=self._open_attendance_form).grid(row=0, column=1, rowspan=2, sticky="e")

        controls = ttk.Frame(page)
        controls.pack(fill="both", expand=True)
        controls.rowconfigure(1, weight=1)
        controls.columnconfigure(0, weight=1)
        filter_row = ttk.Frame(controls)
        filter_row.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(filter_row, text="Work date", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        self.attendance_date_picker = DatePicker(
            filter_row,
            date.today().isoformat(),
            allow_empty=True,
            on_change=self._refresh_attendance,
            width=17,
        )
        self.attendance_date_picker.pack(side="left")
        ttk.Button(filter_row, text="Show all", style="Secondary.TButton", command=self._show_all_attendance).pack(side="left", padx=8)
        if self.current_user and self.current_user["role"] in self.EDIT_ROLES:
            ttk.Button(filter_row, text="Edit selected", style="Secondary.TButton", command=self._edit_selected_attendance).pack(side="right")
            ttk.Button(filter_row, text="Delete selected", style="Danger.TButton", command=self._delete_selected_attendance).pack(side="right", padx=(0, 8))
        self.attendance_tree = self._make_tree(
            controls,
            ("id", "date", "employee", "department", "in", "out", "hours", "overtime", "late"),
            {"id": "ID", "date": "DATE", "employee": "EMPLOYEE ID", "department": "DEPARTMENT", "in": "TIME IN", "out": "TIME OUT", "hours": "HOURS", "overtime": "OVERTIME", "late": "LATE (MIN)"},
            {"id": 55, "date": 105, "employee": 110, "department": 145, "in": 90, "out": 90, "hours": 85, "overtime": 90, "late": 90},
            use_grid=True,
        )
        self._refresh_attendance()

    def _show_all_attendance(self) -> None:
        self.attendance_date_picker.set("")
        self._refresh_attendance()

    def _refresh_attendance(self) -> None:
        if not hasattr(self, "attendance_tree") or not self.attendance_tree.winfo_exists():
            return
        for item in self.attendance_tree.get_children():
            self.attendance_tree.delete(item)
        filter_date = self.attendance_date_picker.get()
        if filter_date:
            try:
                date.fromisoformat(filter_date)
            except ValueError:
                messagebox.showerror("Invalid date", "Select a valid work date.", parent=self)
                return
        query = (
            "SELECT a.attendance_id, a.date, a.employee_id, d.department_name, "
            "a.time_in, a.time_out, a.hours_worked, a.overtime_hours, a.late_minutes FROM attendance a "
            "JOIN employees e ON e.employee_id = a.employee_id "
            "LEFT JOIN departments d ON d.department_id = e.department_id "
        )
        parameters: tuple[Any, ...] = ()
        if filter_date:
            query += "WHERE a.date = ? "
            parameters = (filter_date,)
        query += "ORDER BY a.date DESC, e.last_name, e.first_name"
        rows = self._fetchall(query, parameters)
        for row in rows:
            self.attendance_tree.insert("", "end", iid=str(row["attendance_id"]), values=(
                row["attendance_id"], row["date"], self._employee_code(int(row["employee_id"])),
                row["department_name"] or "Unassigned", row["time_in"] or "—", row["time_out"] or "—",
                f"{float(row['hours_worked'] or 0):.2f}", f"{float(row['overtime_hours'] or 0):.2f}",
                int(row["late_minutes"] or 0),
            ))
        self.status_var.set(f"Showing {len(rows)} attendance record(s)")

    def _open_attendance_form(self, attendance_id: int | None = None) -> None:
        if not self._require_roles(self.EDIT_ROLES, "create or edit attendance records"):
            return
        record = self._fetchone("SELECT * FROM attendance WHERE attendance_id = ?", (attendance_id,)) if attendance_id else None
        employees = self._fetchall(
            "SELECT employee_id, first_name, last_name, scheduled_start_time, scheduled_end_time "
            "FROM employees WHERE status = 'active' ORDER BY last_name, first_name"
        )
        if not employees:
            messagebox.showinfo("No active employees", "Add an active employee before recording attendance.", parent=self)
            return
        employee_options = {
            f"{row['last_name']}, {row['first_name']}  ({self._employee_code(int(row['employee_id']))})": int(row["employee_id"])
            for row in employees
        }
        employee_schedules = {
            int(row["employee_id"]): (
                str(row["scheduled_start_time"] or "09:00"),
                str(row["scheduled_end_time"] or "17:00"),
            )
            for row in employees
        }
        dialog = tk.Toplevel(self)
        dialog.title("Edit attendance" if record else "Record attendance")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Attendance entry", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(body, text="Select the hour, minute, and AM/PM. Overtime starts after the employee's scheduled shift ends.", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 15))
        employee_var = tk.StringVar()
        employee_combo = ttk.Combobox(body, textvariable=employee_var, values=tuple(employee_options), state="readonly", width=36)
        if record:
            employee_var.set(next((name for name, value in employee_options.items() if value == record["employee_id"]), ""))
        else:
            employee_var.set(next(iter(employee_options)))
        date_picker = DatePicker(body, str(record["date"]) if record else date.today().isoformat(), width=20)
        time_in_picker = TimePicker(body, str(record["time_in"] or "") if record else "", allow_empty=True)
        time_out_picker = TimePicker(body, str(record["time_out"] or "") if record else "", allow_empty=True)
        hours_var = tk.StringVar(value="—")
        overtime_var = tk.StringVar(value="—")
        schedule_var = tk.StringVar()
        fields = (
            ("Employee", employee_combo),
            ("Work date", date_picker),
            ("Time in", time_in_picker),
            ("Time out", time_out_picker),
            ("Total hours worked", ttk.Entry(body, textvariable=hours_var, width=16, state="readonly")),
            ("Overtime hours", ttk.Entry(body, textvariable=overtime_var, width=16, state="readonly")),
        )
        for row_index, (label, widget) in enumerate(fields, start=2):
            ttk.Label(body, text=label, style="Muted.TLabel").grid(row=row_index, column=0, sticky="w", pady=6, padx=(0, 15))
            widget.grid(row=row_index, column=1, sticky="ew", pady=6)
        body.columnconfigure(1, weight=1)

        def refresh_calculation(*_args: str) -> None:
            selected_employee = employee_options.get(employee_var.get())
            if selected_employee is None:
                schedule_var.set("Select an employee to see their shift.")
                hours_var.set("—")
                overtime_var.set("—")
                return
            scheduled_start, scheduled_end = employee_schedules[selected_employee]
            try:
                display_start = datetime.strptime(scheduled_start, "%H:%M").strftime("%I:%M %p").lstrip("0")
                display_end = datetime.strptime(scheduled_end, "%H:%M").strftime("%I:%M %p").lstrip("0")
                schedule_var.set(f"Schedule: {display_start} – {display_end}")
                time_in_value = time_in_picker.get()
                time_out_value = time_out_picker.get()
                if not time_in_value or not time_out_value:
                    hours_var.set("—")
                    overtime_var.set("—")
                    return
                hours, overtime = calculate_attendance_hours(
                    time_in_value,
                    time_out_value,
                    scheduled_start,
                    scheduled_end,
                )
            except ValueError:
                schedule_var.set("Select the hour, minute, and AM/PM for each time.")
                hours_var.set("—")
                overtime_var.set("—")
                return
            hours_var.set(f"{hours:.2f}")
            overtime_var.set(f"{overtime:.2f}")

        time_in_picker.on_change = refresh_calculation
        time_out_picker.on_change = refresh_calculation
        employee_combo.bind("<<ComboboxSelected>>", refresh_calculation)
        ttk.Label(body, textvariable=schedule_var, style="Muted.TLabel").grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        refresh_calculation()

        def save() -> None:
            if not employee_var.get():
                messagebox.showerror("Missing employee", "Select an employee.", parent=dialog)
                return
            employee_id = employee_options[employee_var.get()]
            try:
                date.fromisoformat(date_picker.get())
                time_in_value = time_in_picker.get()
                time_out_value = time_out_picker.get()
                time_in_value = time_in_value or None
                time_out_value = time_out_value or None
            except ValueError:
                messagebox.showerror(
                    "Invalid attendance",
                    "Select a valid work date and the hour, minute, and AM/PM for each time.",
                    parent=dialog,
                )
                return
            employee_schedule = self._fetchone(
                "SELECT scheduled_start_time, scheduled_end_time FROM employees WHERE employee_id = ?",
                (employee_id,),
            )
            if employee_schedule is None:
                messagebox.showerror("Employee not found", "Select an active employee and try again.", parent=dialog)
                return
            try:
                scheduled_start = str(employee_schedule["scheduled_start_time"] or "09:00")
                scheduled_end = str(employee_schedule["scheduled_end_time"] or "17:00")
                hours, overtime = calculate_attendance_hours(
                    time_in_value,
                    time_out_value,
                    scheduled_start,
                    scheduled_end,
                )
                late_minutes = calculate_late_minutes(
                    scheduled_start,
                    time_in_value,
                )
            except ValueError:
                messagebox.showerror(
                    "Invalid schedule or time",
                    "Update this employee's shift schedule to valid HH:MM times before recording attendance.",
                    parent=dialog,
                )
                return
            values = (
                employee_id,
                date_picker.get(),
                time_in_value,
                time_out_value,
                hours,
                overtime,
                late_minutes,
            )
            try:
                duplicate = self._fetchone(
                    "SELECT attendance_id FROM attendance WHERE employee_id = ? AND date = ? AND attendance_id != ?",
                    (employee_id, date_picker.get(), attendance_id or -1),
                )
                if duplicate:
                    messagebox.showerror("Duplicate record", "This employee already has an attendance record for that date.", parent=dialog)
                    return
                if attendance_id:
                    self._execute(
                        "UPDATE attendance SET employee_id=?,date=?,time_in=?,time_out=?,hours_worked=?,overtime_hours=?,late_minutes=? WHERE attendance_id=?",
                        values + (attendance_id,),
                    )
                else:
                    self._execute(
                        "INSERT INTO attendance (employee_id,date,time_in,time_out,hours_worked,overtime_hours,late_minutes) VALUES (?,?,?,?,?,?,?)",
                        values,
                    )
            except sqlite3.Error as exc:
                messagebox.showerror("Could not save attendance", str(exc), parent=dialog)
                return
            dialog.destroy()
            if self.current_page == "Attendance":
                self._refresh_attendance()
            else:
                self._show_page(self.current_page)
            self.status_var.set("Attendance record saved")

        actions = ttk.Frame(body)
        actions.grid(row=9, column=0, columnspan=2, sticky="e", pady=(15, 0))
        ttk.Button(actions, text="Cancel", style="Secondary.TButton", command=dialog.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Save record", style="Primary.TButton", command=save).pack(side="left")
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 260}+{self.winfo_rooty() + 150}")

    def _edit_selected_attendance(self) -> None:
        if not self._require_roles(self.EDIT_ROLES, "edit attendance records"):
            return
        selection = self.attendance_tree.selection()
        if not selection:
            messagebox.showinfo("Select a record", "Choose an attendance row first.", parent=self)
            return
        self._open_attendance_form(int(selection[0]))

    def _delete_selected_attendance(self) -> None:
        if not self._require_roles(self.EDIT_ROLES, "delete attendance records"):
            return
        selection = self.attendance_tree.selection()
        if not selection:
            messagebox.showinfo("Select a record", "Choose an attendance row first.", parent=self)
            return
        record = self._fetchone(
            "SELECT date FROM attendance WHERE attendance_id = ?", (int(selection[0]),)
        )
        if record is None:
            messagebox.showerror("Record not found", "Refresh the attendance list and try again.", parent=self)
            self._refresh_attendance()
            return
        if not messagebox.askyesno(
            "Delete attendance record",
            f"Delete the attendance record for {record['date']}? Payroll calculations for future runs will no longer include it.",
            parent=self,
        ):
            return
        try:
            self._execute("DELETE FROM attendance WHERE attendance_id = ?", (int(selection[0]),))
        except sqlite3.Error as exc:
            messagebox.showerror("Could not delete attendance", str(exc), parent=self)
            return
        self._refresh_attendance()

    def _build_leaves(self) -> None:
        if not self._require_roles(self.EDIT_ROLES, "manage leave and travel records"):
            return
        page = ttk.Frame(self.page_host)
        page.grid(row=0, column=0, sticky="nsew")
        page.rowconfigure(1, weight=1)
        page.columnconfigure(0, weight=1)
        toolbar = self._page_toolbar(
            page,
            "Approved leave records",
            "Approved leave and travel records used for payroll. Request decisions remain in Requests.",
        )
        ttk.Button(
            toolbar,
            text="+  Add approved record",
            style="Primary.TButton",
            command=self._open_leave_form,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 0))
        action_row = ttk.Frame(page)
        action_row.pack(fill="x", pady=(0, 10))
        ttk.Button(
            action_row,
            text="Delete selected",
            style="Danger.TButton",
            command=self._delete_selected_leave,
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            action_row,
            text="Edit selected",
            style="Secondary.TButton",
            command=self._edit_selected_leave,
        ).pack(side="right")
        self.leave_tree = self._make_tree(
            page,
            ("id", "employee", "type", "start", "end", "notes"),
            {"id": "ID", "employee": "EMPLOYEE", "type": "TYPE", "start": "FROM", "end": "TO", "notes": "NOTES"},
            {"id": 55, "employee": 180, "type": 145, "start": 110, "end": 110, "notes": 340},
        )
        self._refresh_leaves()

    def _refresh_leaves(self) -> None:
        if not hasattr(self, "leave_tree") or not self.leave_tree.winfo_exists():
            return
        for item in self.leave_tree.get_children():
            self.leave_tree.delete(item)
        rows = self._fetchall(
            "SELECT l.leave_id,e.first_name,e.last_name,l.leave_type,l.start_date,l.end_date,"
            "l.notes FROM leave_records l JOIN employees e ON e.employee_id=l.employee_id "
            "WHERE l.status='Approved' "
            "ORDER BY l.start_date DESC,e.last_name,e.first_name"
        )
        for row in rows:
            self.leave_tree.insert(
                "",
                "end",
                iid=str(row["leave_id"]),
                values=(
                    row["leave_id"],
                    f"{row['first_name']} {row['last_name']}",
                    row["leave_type"],
                    row["start_date"],
                    row["end_date"],
                    row["notes"] or "",
                ),
            )
        self.status_var.set(f"Showing {len(rows)} approved leave and travel record(s)")

    def _edit_selected_leave(self) -> None:
        if not self._require_roles(self.EDIT_ROLES, "edit leave and travel records"):
            return
        selection = self.leave_tree.selection()
        if not selection:
            messagebox.showinfo("Select a record", "Choose a leave or travel row first.", parent=self)
            return
        self._open_leave_form(int(selection[0]))

    def _delete_selected_leave(self) -> None:
        if not self._require_roles(self.EDIT_ROLES, "delete leave and travel records"):
            return
        selection = self.leave_tree.selection()
        if not selection:
            messagebox.showinfo("Select a record", "Choose a leave or travel row first.", parent=self)
            return
        leave_id = int(selection[0])
        record = self._fetchone(
            "SELECT leave_type,start_date,end_date FROM leave_records WHERE leave_id = ?",
            (leave_id,),
        )
        if record is None:
            messagebox.showerror("Record not found", "Refresh the leave list and try again.", parent=self)
            self._refresh_leaves()
            return
        if not messagebox.askyesno(
            "Delete leave / travel record",
            f"Delete this {record['leave_type'].lower()} record ({record['start_date']} to {record['end_date']})?",
            parent=self,
        ):
            return
        try:
            self._execute("DELETE FROM leave_records WHERE leave_id = ?", (leave_id,))
        except sqlite3.Error as exc:
            messagebox.showerror("Could not delete leave record", str(exc), parent=self)
            return
        self._refresh_leaves()

    def _open_leave_form(self, leave_id: int | None = None) -> None:
        if not self._require_roles(self.EDIT_ROLES, "create or edit leave and travel records"):
            return
        employees = self._fetchall(
            "SELECT employee_id,first_name,last_name,gender FROM employees "
            "WHERE status='active' ORDER BY last_name,first_name"
        )
        if not employees:
            messagebox.showinfo(
                "No active employees",
                "Add an active employee before recording leave or travel.",
                parent=self,
            )
            return
        record = (
            self._fetchone("SELECT * FROM leave_records WHERE leave_id = ?", (leave_id,))
            if leave_id is not None
            else None
        )
        employee_options = {
            f"{row['last_name']}, {row['first_name']} ({self._employee_code(int(row['employee_id']))})": int(row["employee_id"])
            for row in employees
        }
        employee_genders = {
            int(row["employee_id"]): str(row["gender"] or "").strip().lower()
            for row in employees
        }
        selected_employee = next(
            (
                name
                for name, employee_option_id in employee_options.items()
                if record and employee_option_id == int(record["employee_id"])
            ),
            next(iter(employee_options)),
        )
        dialog = tk.Toplevel(self)
        dialog.title("Edit approved record" if record else "Add approved record")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(
            body,
            text="Approved leave or travel record",
            style="Title.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            body,
            text="Approved records appear here. Leave requests and their approval decisions are managed in Requests.",
            style="Muted.TLabel",
            wraplength=460,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))

        fields: list[tuple[str, ttk.Widget]] = []
        employee_var = tk.StringVar(value=selected_employee)
        employee_combo = ttk.Combobox(
            body,
            textvariable=employee_var,
            values=tuple(employee_options),
            state="readonly",
            width=36,
        )
        fields.append(("Employee", employee_combo))
        type_var = tk.StringVar(value=str(record["leave_type"]) if record else "Paid leave")
        leave_types_combo = ttk.Combobox(
            body,
            textvariable=type_var,
            state="readonly",
            width=36,
        )
        fields.append(
            (
                "Type",
                leave_types_combo,
            )
        )

        def update_leave_types(*_args: str) -> None:
            employee_id_value = employee_options.get(employee_var.get())
            employee_gender = employee_genders.get(employee_id_value, "")
            leave_types = ["Paid leave", "Sick Leave", "Forced Leave", "Travel order"]
            if employee_gender == "female":
                leave_types.append("Maternity leave")
            elif employee_gender == "male":
                leave_types.append("Paternity leave")
            leave_types_combo.configure(values=tuple(leave_types))
            if type_var.get() not in leave_types:
                type_var.set("Paid leave")

        update_leave_types()
        employee_combo.bind("<<ComboboxSelected>>", update_leave_types)
        default_start = str(record["start_date"]) if record else date.today().isoformat()
        default_end = str(record["end_date"]) if record else date.today().isoformat()
        start_picker = DatePicker(body, default_start, width=18)
        end_picker = DatePicker(body, default_end, width=18)
        fields.extend((("Start date", start_picker), ("End date", end_picker)))
        notes_var = tk.StringVar(value=str(record["notes"] or "") if record else "")
        fields.append(("Notes", ttk.Entry(body, textvariable=notes_var, width=39)))
        for row_index, (label, widget) in enumerate(fields, start=2):
            ttk.Label(body, text=label, style="Muted.TLabel").grid(
                row=row_index, column=0, sticky="w", padx=(0, 12), pady=6
            )
            widget.grid(row=row_index, column=1, sticky="ew", pady=6)
        body.columnconfigure(1, weight=1)

        def save() -> None:
            employee_id_value = employee_options.get(employee_var.get())
            try:
                start_value = date.fromisoformat(start_picker.get())
                end_value = date.fromisoformat(end_picker.get())
                if end_value < start_value or employee_id_value is None:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Invalid leave dates",
                    "Choose an employee and valid dates. The end date cannot be before the start date.",
                    parent=dialog,
                )
                return
            employee_gender = employee_genders.get(employee_id_value, "")
            if (
                type_var.get() == "Maternity leave" and employee_gender != "female"
            ) or (
                type_var.get() == "Paternity leave" and employee_gender != "male"
            ):
                messagebox.showerror(
                    "Leave type not available",
                    "Maternity leave is available only to employees registered as female; paternity leave is available only to employees registered as male.",
                    parent=dialog,
                )
                return
            overlap = self._fetchone(
                "SELECT leave_id FROM leave_records WHERE employee_id=? AND status!='Rejected' "
                "AND start_date<=? AND end_date>=? AND leave_id!=?",
                (
                    employee_id_value,
                    end_value.isoformat(),
                    start_value.isoformat(),
                    leave_id or -1,
                ),
            )
            if overlap:
                messagebox.showerror(
                    "Overlapping record",
                    "This employee already has a non-rejected leave or travel record during those dates.",
                    parent=dialog,
                )
                return
            values = (
                employee_id_value,
                type_var.get(),
                start_value.isoformat(),
                end_value.isoformat(),
                "Approved",
                notes_var.get().strip() or None,
            )
            try:
                if leave_id is None:
                    self._execute(
                        "INSERT INTO leave_records "
                        "(employee_id,leave_type,start_date,end_date,status,notes) VALUES (?,?,?,?,?,?)",
                        values,
                    )
                else:
                    self._execute(
                        "UPDATE leave_records SET employee_id=?,leave_type=?,start_date=?,end_date=?,"
                        "status=?,notes=? WHERE leave_id=?",
                        values + (leave_id,),
                    )
            except sqlite3.Error as exc:
                messagebox.showerror("Could not save leave record", str(exc), parent=dialog)
                return
            dialog.destroy()
            self._refresh_leaves()

        actions = ttk.Frame(body)
        actions.grid(row=7, column=0, columnspan=2, sticky="e", pady=(15, 0))
        ttk.Button(
            actions, text="Cancel", style="Secondary.TButton", command=dialog.destroy
        ).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Save approved record", style="Primary.TButton", command=save).pack(
            side="left"
        )
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 240}+{self.winfo_rooty() + 130}")
