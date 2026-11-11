from __future__ import annotations

from config import ACCENT_BLUE
from config import BACKGROUND_COLOR
from config import HEADING_FONT
from pathlib import Path
from config import SUCCESS_COLOR
from config import TEXT_COLOR
from config import WHITE
import calendar
import csv
from datetime import date
from tkinter import filedialog
from math import isfinite
from tkinter import messagebox
import sqlite3
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from .core import PayrollAppCore, DatePicker, calculate_hourly_gross, calculate_paid_leave_hours, calculate_philippine_deductions, is_full_calendar_month
from .attendance import AttendancePages

class PayrollPages(AttendancePages):
    def _build_payroll(self) -> None:
        if not self._require_roles(self.PAYROLL_MANAGEMENT_ROLES, "access payroll"):
            return
        page = ttk.Frame(self.page_host)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)
        toolbar = self._page_toolbar(page, "Payroll", "Review processed payroll records and payroll calculations.")
        can_manage_payroll = bool(
            self.current_user
            and self.current_user["role"] in self.PAYROLL_MANAGEMENT_ROLES
        )
        if can_manage_payroll:
            ttk.Button(toolbar, text="Other deductions", style="Secondary.TButton", command=self._open_deductions_form).grid(row=0, column=1, rowspan=2, padx=(0, 8))

        if can_manage_payroll:
            process_panel = self._card(page, padding=18)
            process_panel.pack(fill="x", pady=(0, 16))
            process_card = process_panel.content
            ttk.Label(process_card, text="New payroll run", font=HEADING_FONT, background=WHITE, foreground=TEXT_COLOR).grid(row=0, column=0, columnspan=4, sticky="w")
            ttk.Label(
                process_card,
                text="Run one full calendar month at a time. Regular hours are paid at the hourly rate, overtime at 1.5×, and Philippine employee contributions and withholding tax are calculated automatically. Employer shares are not deducted.",
                style="CardMuted.TLabel",
                wraplength=860,
            ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 14))
            ttk.Label(
                process_card,
                text="SSS's latest table located is for 2025. The estimate does not handle annual tax reconciliation or special-pay exemptions; confirm current agency rules before remitting.",
                style="CardMuted.TLabel",
                wraplength=860,
            ).grid(row=3, column=0, columnspan=5, sticky="w", pady=(10, 0))
            today = date.today()
            period_start_picker = DatePicker(process_card, today.replace(day=1).isoformat(), width=18)
            period_end_picker = DatePicker(
                process_card,
                today.replace(day=calendar.monthrange(today.year, today.month)[1]).isoformat(),
                width=18,
            )
            ttk.Label(process_card, text="Period start", style="Muted.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 8))
            period_start_picker.grid(row=2, column=1, sticky="w", padx=(0, 18))
            ttk.Label(process_card, text="Period end", style="Muted.TLabel").grid(row=2, column=2, sticky="w", padx=(0, 8))
            period_end_picker.grid(row=2, column=3, sticky="w")
            ttk.Button(
                process_card,
                text="Review & process payroll  →",
                style="Primary.TButton",
                command=lambda: self._process_payroll(period_start_picker.get(), period_end_picker.get()),
            ).grid(row=2, column=4, sticky="e", padx=(20, 0))
            process_card.columnconfigure(4, weight=1)
        history_panel = self._card(page)
        history_panel.pack(fill="both", expand=True)
        history_card = history_panel.content
        history_heading = ttk.Frame(history_card, style="CardContent.TFrame")
        history_heading.pack(fill="x", pady=(0, 12))
        ttk.Label(
            history_heading,
            text="Payroll history",
            font=HEADING_FONT,
            background=WHITE,
            foreground=TEXT_COLOR,
        ).pack(side="left")
        if can_manage_payroll:
            ttk.Button(
                history_heading,
                text="Delete selected",
                style="Danger.TButton",
                command=self._delete_selected_payroll,
            ).pack(side="right")
        self.payroll_tree = self._make_tree(
            history_card,
            ("id", "employee", "period", "gross", "leave_hours", "late_minutes", "late_deduction", "deductions", "net", "generated"),
            {"id": "ID", "employee": "EMPLOYEE", "period": "PAY PERIOD", "gross": "GROSS PAY", "leave_hours": "PAID LEAVE HRS", "late_minutes": "LATE MIN", "late_deduction": "TARDINESS", "deductions": "STATUTORY + OTHER", "net": "NET PAY", "generated": "PROCESSED"},
            {"id": 50, "employee": 150, "period": 165, "gross": 105, "leave_hours": 105, "late_minutes": 85, "late_deduction": 105, "deductions": 115, "net": 105, "generated": 120},
        )
        self._refresh_payroll()

    def _refresh_payroll(self) -> None:
        if not hasattr(self, "payroll_tree") or not self.payroll_tree.winfo_exists():
            return
        for item in self.payroll_tree.get_children():
            self.payroll_tree.delete(item)
        rows = self._fetchall(
            "SELECT p.payroll_id, e.first_name, e.last_name, p.period_start, p.period_end, p.gross_pay, "
            "p.tardiness_minutes, p.tardiness_deduction, p.deductions, p.sss_deduction, "
            "p.philhealth_deduction, p.pagibig_deduction, p.tax_withheld, p.other_deductions,p.paid_leave_hours, "
            "p.net_pay, p.generated_at FROM payroll p "
            "JOIN employees e ON e.employee_id = p.employee_id "
            "ORDER BY p.period_end DESC, p.generated_at DESC, p.payroll_id DESC"
        )
        for row in rows:
            self.payroll_tree.insert("", "end", iid=str(row["payroll_id"]), values=(
                row["payroll_id"], f"{row['first_name']} {row['last_name']}",
                f"{row['period_start']} – {row['period_end']}", self._money(row["gross_pay"]),
                f"{float(row['paid_leave_hours'] or 0):.2f}",
                int(row["tardiness_minutes"]), self._money(row["tardiness_deduction"]),
                self._money(row["deductions"]),
                self._money(row["net_pay"]), str(row["generated_at"])[:16],
            ))
        self.status_var.set(f"{len(rows)} payroll record(s)")

    def _delete_selected_payroll(self) -> None:
        if not self._require_roles(self.PAYROLL_MANAGEMENT_ROLES, "delete payroll history"):
            return
        selection = self.payroll_tree.selection()
        if not selection:
            messagebox.showinfo("Select a payroll record", "Choose a payroll history row first.", parent=self)
            return
        payroll_id = int(selection[0])
        record = self._fetchone(
            "SELECT e.first_name,e.last_name,p.period_start,p.period_end FROM payroll p "
            "JOIN employees e ON e.employee_id=p.employee_id WHERE p.payroll_id=?",
            (payroll_id,),
        )
        if record is None:
            messagebox.showerror("Payroll record not found", "Refresh payroll history and try again.", parent=self)
            self._refresh_payroll()
            return
        if not messagebox.askyesno(
            "Delete payroll record",
            f"Delete payroll for {record['first_name']} {record['last_name']} "
            f"({record['period_start']} to {record['period_end']})? "
            "This removes it from payroll history and report totals. You can process the period again afterward.",
            parent=self,
        ):
            return
        try:
            self._execute("DELETE FROM payroll WHERE payroll_id = ?", (payroll_id,))
        except sqlite3.Error as exc:
            messagebox.showerror("Could not delete payroll record", str(exc), parent=self)
            return
        self._refresh_payroll()
        self.status_var.set("Payroll record deleted; report totals will reflect the change.")

    def _process_payroll(self, period_start: str, period_end: str) -> None:
        if not self._require_roles(self.PAYROLL_MANAGEMENT_ROLES, "process payroll"):
            return
        try:
            start = date.fromisoformat(period_start.strip())
            end = date.fromisoformat(period_end.strip())
            if end < start:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid payroll period", "Select valid start and end dates. The end date cannot be before the start date.", parent=self)
            return
        if not is_full_calendar_month(start, end):
            messagebox.showerror(
                "Full month required",
                "Statutory contributions are calculated monthly. Select the first and last day of one calendar month.",
                parent=self,
            )
            return
        employees = self._fetchall(
            "SELECT employee_id, first_name, last_name, hourly_rate "
            "FROM employees WHERE status = 'active' ORDER BY last_name, first_name"
        )
        if not employees:
            messagebox.showinfo("No active employees", "Add an active employee before processing payroll.", parent=self)
            return
        overlapping_period = self._fetchone(
            "SELECT period_start, period_end FROM payroll "
            "WHERE period_start <= ? AND period_end >= ? LIMIT 1",
            (end.isoformat(), start.isoformat()),
        )
        if overlapping_period:
            messagebox.showerror(
                "Payroll period overlaps",
                "An existing payroll period "
                f"({overlapping_period['period_start']} to {overlapping_period['period_end']}) overlaps these dates. "
                "No duplicate payroll was created.",
                parent=self,
            )
            return

        preview: list[tuple[int, float, float, int, float, float, float, float, float, float, float, float]] = []
        skipped: list[str] = []
        for employee in employees:
            name = f"{employee['first_name']} {employee['last_name']}"
            hourly_rate = float(employee["hourly_rate"] or 0)
            if not isfinite(hourly_rate) or hourly_rate <= 0:
                skipped.append(f"{name} (hourly rate not configured)")
                continue
            hours = self._fetchone(
                "SELECT "
                "COALESCE(SUM(CASE WHEN COALESCE(hours_worked, 0) > COALESCE(overtime_hours, 0) "
                "THEN COALESCE(hours_worked, 0) - COALESCE(overtime_hours, 0) ELSE 0 END), 0) AS regular_hours, "
                "COALESCE(SUM(MIN(COALESCE(overtime_hours, 0), COALESCE(hours_worked, 0))), 0) AS overtime_hours, "
                "COALESCE(SUM(late_minutes), 0) AS late_minutes "
                "FROM attendance WHERE employee_id = ? AND date BETWEEN ? AND ?",
                (employee["employee_id"], start.isoformat(), end.isoformat()),
            )
            regular_hours = float(hours["regular_hours"] or 0)
            overtime_hours = float(hours["overtime_hours"] or 0)
            attendance_rows = self._fetchall(
                "SELECT date FROM attendance WHERE employee_id=? AND date BETWEEN ? AND ?",
                (employee["employee_id"], start.isoformat(), end.isoformat()),
            )
            attendance_dates = {str(row["date"]) for row in attendance_rows}
            approved_leave_rows = self._fetchall(
                "SELECT start_date,end_date FROM leave_records WHERE employee_id=? "
                "AND leave_type IN ('Paid leave','Sick Leave','Forced Leave','Travel order') "
                "AND status='Approved' "
                "AND start_date<=? AND end_date>=?",
                (employee["employee_id"], end.isoformat(), start.isoformat()),
            )
            paid_leave_hours = calculate_paid_leave_hours(
                [
                    (str(row["start_date"]), str(row["end_date"]))
                    for row in approved_leave_rows
                ],
                attendance_dates,
                start,
                end,
            )
            regular_hours += paid_leave_hours
            try:
                gross = round(
                    calculate_hourly_gross(hourly_rate, regular_hours, overtime_hours), 2
                )
            except ValueError:
                skipped.append(f"{name} (invalid hourly rate or attendance hours)")
                continue
            if gross <= 0:
                skipped.append(f"{name} (hourly rate or attendance missing)")
                continue
            late_minutes = int(hours["late_minutes"] or 0)
            tardiness_deduction = round(hourly_rate * late_minutes / 60, 2)
            statutory = calculate_philippine_deductions(
                regular_hours * hourly_rate,
                gross,
            )
            other_deduction = self._fetchone(
                "SELECT COALESCE(other,0) AS total "
                "FROM deductions WHERE employee_id = ? ORDER BY deduction_id DESC LIMIT 1",
                (employee["employee_id"],),
            )
            other_amount = float(other_deduction["total"]) if other_deduction else 0.0
            sss, philhealth, pagibig, tax = statutory
            deductions = round(sss + philhealth + pagibig + tax + other_amount, 2)
            if not isfinite(deductions) or not isfinite(other_amount) or other_amount < 0:
                skipped.append(f"{name} (invalid deduction values)")
                continue
            if deductions + tardiness_deduction > gross:
                skipped.append(f"{name} (deductions exceed gross pay)")
                continue
            preview.append((
                int(employee["employee_id"]),
                gross,
                paid_leave_hours,
                late_minutes,
                tardiness_deduction,
                sss,
                philhealth,
                pagibig,
                tax,
                other_amount,
                deductions,
                gross - deductions - tardiness_deduction,
            ))

        if not preview:
            details = "\n".join(skipped[:8]) or "No eligible employees found."
            messagebox.showwarning("Nothing to process", f"No payroll records can be generated.\n\n{details}", parent=self)
            return
        total_gross = sum(item[1] for item in preview)
        total_paid_leave_hours = sum(item[2] for item in preview)
        total_tardiness = sum(item[4] for item in preview)
        total_sss = sum(item[5] for item in preview)
        total_philhealth = sum(item[6] for item in preview)
        total_pagibig = sum(item[7] for item in preview)
        total_tax = sum(item[8] for item in preview)
        total_other = sum(item[9] for item in preview)
        total_net = sum(item[11] for item in preview)
        skipped_detail = f"\n\nSkipped {len(skipped)} employee(s): " + "; ".join(skipped[:4]) if skipped else ""
        confirmation = (
            f"Period: {start.isoformat()} to {end.isoformat()}\n"
            f"Employees included: {len(preview)}\n"
            f"Gross total: {self._money(total_gross)}\n"
            f"Paid leave / travel hours: {total_paid_leave_hours:.2f}\n"
            f"Late minutes: {sum(item[3] for item in preview)}\n"
            f"Tardiness deduction: {self._money(total_tardiness)}\n"
            f"SSS: {self._money(total_sss)}  •  PhilHealth: {self._money(total_philhealth)}\n"
            f"Pag-IBIG: {self._money(total_pagibig)}  •  Withholding tax: {self._money(total_tax)}\n"
            f"Optional other deductions: {self._money(total_other)}\n"
            f"Net total: {self._money(total_net)}"
            f"{skipped_detail}\n\nProcess this run?"
        )
        if not messagebox.askyesno("Review payroll", confirmation, parent=self):
            return
        connection = self.db_manager.get_connection()
        try:
            connection.executemany(
                "INSERT INTO payroll (employee_id,period_start,period_end,gross_pay,deductions,"
                "sss_deduction,philhealth_deduction,pagibig_deduction,tax_withheld,other_deductions,"
                "paid_leave_hours,tardiness_minutes,tardiness_deduction,net_pay) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        employee_id,
                        start.isoformat(),
                        end.isoformat(),
                        gross,
                        deductions,
                        sss,
                        philhealth,
                        pagibig,
                        tax,
                        other_amount,
                        paid_leave_hours,
                        late_minutes,
                        tardiness_deduction,
                        net,
                    )
                    for (
                        employee_id, gross, paid_leave_hours, late_minutes, tardiness_deduction,
                        sss, philhealth, pagibig, tax, other_amount, deductions, net,
                    ) in preview
                ],
            )
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            messagebox.showerror("Payroll was not saved", str(exc), parent=self)
            return
        finally:
            connection.close()
        self._refresh_payroll()
        self.status_var.set(f"Processed payroll for {len(preview)} employee(s); skipped {len(skipped)}")
        messagebox.showinfo("Payroll processed", f"Created {len(preview)} payroll record(s).\nNet payroll total: {self._money(total_net)}", parent=self)

    def _open_deductions_form(self) -> None:
        if not self._require_roles(self.PAYROLL_MANAGEMENT_ROLES, "manage deductions"):
            return
        employees = self._fetchall(
            "SELECT employee_id, first_name, last_name FROM employees WHERE status = 'active' ORDER BY last_name, first_name"
        )
        if not employees:
            messagebox.showinfo("No active employees", "Add an active employee before configuring deductions.", parent=self)
            return
        options = {
            f"{row['last_name']}, {row['first_name']}  ({self._employee_code(int(row['employee_id']))})":
            int(row["employee_id"])
            for row in employees
        }
        dialog = tk.Toplevel(self)
        dialog.title("Optional other deductions")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Optional other deductions", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            body,
            text="SSS, PhilHealth, Pag-IBIG, and withholding tax are calculated automatically. Set an optional recurring amount here for loans or other deductions.",
            style="Muted.TLabel",
            wraplength=460,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))
        employee_var = tk.StringVar(value=next(iter(options)))
        combo = ttk.Combobox(body, textvariable=employee_var, values=tuple(options), state="readonly", width=35)
        ttk.Label(body, text="Employee", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=5)
        combo.grid(row=2, column=1, sticky="ew", pady=5)
        other_var = tk.StringVar(value="0.00")
        ttk.Label(body, text="Other amount per month", style="Muted.TLabel").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(body, textvariable=other_var, width=38).grid(row=3, column=1, sticky="ew", pady=5)

        def load_current(*_args: object) -> None:
            employee_id = options.get(employee_var.get())
            if employee_id is None:
                return
            current = self._fetchone(
                "SELECT other FROM deductions WHERE employee_id = ? ORDER BY deduction_id DESC LIMIT 1",
                (employee_id,),
            )
            other_var.set(f"{float(current['other'] or 0):.2f}" if current else "0.00")

        combo.bind("<<ComboboxSelected>>", load_current)
        load_current()
        body.columnconfigure(1, weight=1)

        def save() -> None:
            try:
                other_amount = float(other_var.get())
                if not isfinite(other_amount) or other_amount < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Invalid deduction", "Enter a non-negative amount for other deductions.", parent=dialog)
                return
            employee_id = options[employee_var.get()]
            try:
                connection = self.db_manager.get_connection()
                try:
                    connection.execute("DELETE FROM deductions WHERE employee_id = ?", (employee_id,))
                    connection.execute(
                        "INSERT INTO deductions (employee_id,sss,philhealth,pagibig,tax,other) VALUES (?,?,?,?,?,?)",
                        (employee_id, 0, 0, 0, 0, other_amount),
                    )
                    connection.commit()
                finally:
                    connection.close()
            except sqlite3.Error as exc:
                messagebox.showerror("Could not save deductions", str(exc), parent=dialog)
                return
            dialog.destroy()
            self.status_var.set("Deduction defaults saved")

        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(15, 0))
        ttk.Button(buttons, text="Cancel", style="Secondary.TButton", command=dialog.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save other deduction", style="Primary.TButton", command=save).pack(side="left")
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 280}+{self.winfo_rooty() + 160}")

    def _build_reports(self) -> None:
        page = ttk.Frame(self.page_host)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)
        toolbar = self._page_toolbar(page, "Reports & exports", "Review payroll totals for a date range and export the underlying records.")
        ttk.Button(toolbar, text="Export payroll CSV", style="Primary.TButton", command=self._export_payroll_csv).grid(row=0, column=1, rowspan=2, sticky="e")

        filter_panel = self._card(page, padding=16)
        filter_panel.pack(fill="x", pady=(0, 16))
        filter_card = filter_panel.content
        today = date.today()
        start_picker = DatePicker(filter_card, today.replace(day=1).isoformat(), width=18)
        end_picker = DatePicker(filter_card, today.isoformat(), width=18)
        ttk.Label(filter_card, text="From", style="Muted.TLabel").pack(side="left", padx=(0, 7))
        start_picker.pack(side="left")
        ttk.Label(filter_card, text="To", style="Muted.TLabel").pack(side="left", padx=(18, 7))
        end_picker.pack(side="left")
        ttk.Button(filter_card, text="Run report  →", style="Primary.TButton", command=lambda: self._refresh_report(start_picker.get(), end_picker.get())).pack(side="left", padx=10)

        body = ttk.Frame(page)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(1, weight=1)
        self.report_metrics = ttk.Frame(body)
        self.report_metrics.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        self.report_table_panel = self._card(body)
        self.report_table_panel.grid(row=1, column=0, sticky="nsew")
        self.report_table_host = self.report_table_panel.content
        self._refresh_report(start_picker.get(), end_picker.get())

    def _refresh_report(self, start_value: str, end_value: str) -> None:
        try:
            start = date.fromisoformat(start_value.strip())
            end = date.fromisoformat(end_value.strip())
            if end < start:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid report period", "Select valid start and end dates. The end date cannot be before the start date.", parent=self)
            return
        summary = self._fetchone(
            "SELECT COUNT(*) AS records, COUNT(DISTINCT employee_id) AS employees, "
            "COALESCE(SUM(gross_pay),0) AS gross, "
            "COALESCE(SUM(deductions + tardiness_deduction),0) AS deductions, "
            "COALESCE(SUM(tardiness_deduction),0) AS tardiness, "
            "COALESCE(SUM(tardiness_minutes),0) AS late_minutes, "
            "COALESCE(SUM(net_pay),0) AS net FROM payroll WHERE period_start >= ? AND period_end <= ?",
            (start.isoformat(), end.isoformat()),
        )
        for child in self.report_metrics.winfo_children():
            child.destroy()
        for column in range(4):
            self.report_metrics.columnconfigure(column, weight=1, uniform="report")
        cards = (
            ("Payroll records", str(summary["records"]), f"{summary['employees']} employees"),
            ("Gross payroll", self._money(summary["gross"]), "Before deductions"),
            (
                "All deductions",
                self._money(summary["deductions"]),
                f"Includes {summary['late_minutes']} late minutes",
            ),
            ("Net payroll", self._money(summary["net"]), "Take-home total"),
        )
        for column, (title, value, detail) in enumerate(cards):
            self._metric_card(self.report_metrics, column, title, value, detail, SUCCESS_COLOR if column == 3 else ACCENT_BLUE)

        for child in self.report_table_host.winfo_children():
            child.destroy()
        ttk.Label(
            self.report_table_host,
            text="Payroll detail",
            font=HEADING_FONT,
            style="CardTitle.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        tree = self._make_tree(
            self.report_table_host,
            ("employee", "period", "gross", "leave_hours", "sss", "philhealth", "pagibig", "tax", "other", "tardiness", "net"),
            {"employee": "EMPLOYEE", "period": "PERIOD", "gross": "GROSS PAY", "leave_hours": "PAID LEAVE HRS", "sss": "SSS", "philhealth": "PHILHEALTH", "pagibig": "PAG-IBIG", "tax": "TAX", "other": "OTHER", "tardiness": "TARDINESS", "net": "NET PAY"},
            {"employee": 155, "period": 150, "gross": 100, "leave_hours": 100, "sss": 85, "philhealth": 100, "pagibig": 95, "tax": 85, "other": 90, "tardiness": 100, "net": 100},
        )
        rows = self._fetchall(
            "SELECT e.first_name,e.last_name,p.period_start,p.period_end,p.gross_pay,"
            "p.sss_deduction,p.philhealth_deduction,p.pagibig_deduction,p.tax_withheld,"
            "p.other_deductions,p.paid_leave_hours,p.tardiness_minutes,p.tardiness_deduction,p.net_pay "
            "FROM payroll p JOIN employees e ON e.employee_id=p.employee_id "
            "WHERE p.period_start >= ? AND p.period_end <= ? ORDER BY p.period_end,e.last_name,e.first_name",
            (start.isoformat(), end.isoformat()),
        )
        for row in rows:
            tree.insert("", "end", values=(
                f"{row['first_name']} {row['last_name']}",
                f"{row['period_start']} – {row['period_end']}",
                self._money(row["gross_pay"]), f"{float(row['paid_leave_hours'] or 0):.2f}",
                self._money(row["sss_deduction"]),
                self._money(row["philhealth_deduction"]), self._money(row["pagibig_deduction"]),
                self._money(row["tax_withheld"]), self._money(row["other_deductions"]),
                self._money(row["tardiness_deduction"]),
                self._money(row["net_pay"]),
            ))
        if not rows:
            self._empty_state(self.report_table_host, "No payroll records found for this date range.")
        self.report_period = (start.isoformat(), end.isoformat())
        self.status_var.set(f"Report: {len(rows)} payroll record(s) from {start.isoformat()} to {end.isoformat()}")

    def _export_payroll_csv(self) -> None:
        if not self._role_allows("Reports"):
            messagebox.showerror(
                "Access denied",
                "Your account does not have permission to export payroll reports.",
                parent=self,
            )
            return
        period = getattr(self, "report_period", None)
        if period is None:
            messagebox.showinfo("Run a report first", "Set a date range and run the report before exporting.", parent=self)
            return
        rows = self._fetchall(
            "SELECT e.employee_id,e.first_name,e.middle_name,e.last_name,p.period_start,p.period_end,"
            "p.gross_pay,p.sss_deduction,p.philhealth_deduction,p.pagibig_deduction,p.tax_withheld,"
            "p.other_deductions,p.paid_leave_hours,p.tardiness_minutes,p.tardiness_deduction,"
            "p.deductions,p.net_pay,p.generated_at FROM payroll p "
            "JOIN employees e ON e.employee_id=p.employee_id "
            "WHERE p.period_start >= ? AND p.period_end <= ? ORDER BY p.period_end,e.last_name,e.first_name",
            period,
        )
        if not rows:
            messagebox.showinfo("Nothing to export", "There are no payroll records in this report range.", parent=self)
            return
        filename = filedialog.asksaveasfilename(
            parent=self,
            title="Export payroll report",
            defaultextension=".csv",
            initialfile=f"payroll-{period[0]}-to-{period[1]}.csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
        )
        if not filename:
            return
        output = Path(filename)
        try:
            with output.open("w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(("Employee ID", "First name", "Middle name", "Last name", "Period start", "Period end", "Gross pay", "SSS", "PhilHealth", "Pag-IBIG", "Withholding tax", "Other deductions", "Paid leave and travel hours", "Tardiness minutes", "Tardiness deduction", "Total statutory and other deductions", "Net pay", "Generated at"))
                for row in rows:
                    writer.writerow(
                        (self._employee_code(int(row["employee_id"])), *tuple(row)[1:])
                    )
        except OSError as exc:
            messagebox.showerror("Export failed", f"Could not write the report:\n{exc}", parent=self)
            return
        self.status_var.set(f"Exported {len(rows)} payroll record(s) to {output.name}")
        messagebox.showinfo("Export complete", f"Saved {len(rows)} payroll record(s) to:\n{output}", parent=self)
