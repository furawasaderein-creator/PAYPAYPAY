from __future__ import annotations

import json
import sqlite3
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any

from config import BACKGROUND_COLOR, HEADING_FONT, TEXT_COLOR, WHITE
from database.database import REQUEST_TYPES
from .core import DatePicker, TimePicker
from .settings import SettingsPages


class RequestPages(SettingsPages):
    REQUEST_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
        "Leave": (
            ("Leave type", "leave_type"),
            ("Start date", "start_date"),
            ("End date", "end_date"),
            ("Reason", "reason"),
        ),
        "Travel Order": (
            ("Destination", "destination"),
            ("Start date", "start_date"),
            ("End date", "end_date"),
            ("Purpose", "purpose"),
        ),
        "Accomplishment Report": (
            ("Period start", "period_start"),
            ("Period end", "period_end"),
            ("Report", "report"),
        ),
        "Clearance": (("Purpose", "purpose"), ("Details", "details")),
        "Pass Slip": (
            ("Date", "date"),
            ("Time out", "time_out"),
            ("Expected time in", "time_in"),
            ("Reason", "reason"),
        ),
        "Certificate of Employment (COE)": (
            ("Purpose", "purpose"),
            ("Details", "details"),
        ),
    }

    def _build_requests(self) -> None:
        if not self._role_allows("Requests"):
            messagebox.showerror(
                "Access denied",
                "Your account does not have access to employee requests.",
                parent=self,
            )
            return
        is_employee = bool(
            self.current_user and self.current_user["role"] == "viewer"
        )
        page = ttk.Frame(self.page_host)
        page.grid(row=0, column=0, sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)
        toolbar = self._page_toolbar(
            page,
            "Employee requests",
            "Submit and track requests, or review requests from employees.",
        )
        if is_employee:
            account = self._fetchone(
                "SELECT employee_id FROM users WHERE id = ?",
                (int(self.current_user["id"]),),
            )
            linked = account is not None and account["employee_id"] is not None
            ttk.Button(
                toolbar,
                text="+  New request",
                style="Primary.TButton",
                command=self._open_request_form,
                state="normal" if linked else "disabled",
            ).grid(row=0, column=1, rowspan=2, sticky="e")
            if not linked:
                ttk.Label(
                    page,
                    text="Your account is not linked to an employee profile. Contact an administrator to link it before submitting requests.",
                    style="Muted.TLabel",
                    wraplength=850,
                ).pack(anchor="w", pady=(0, 10))
        else:
            action_row = ttk.Frame(page)
            action_row.pack(fill="x", pady=(0, 10))
            ttk.Button(
                action_row,
                text="Reject selected",
                style="Danger.TButton",
                command=lambda: self._review_selected_request("Rejected"),
            ).pack(side="right")
            ttk.Button(
                action_row,
                text="Approve selected",
                style="Primary.TButton",
                command=lambda: self._review_selected_request("Approved"),
            ).pack(side="right", padx=(0, 8))

        self.request_tree = self._make_tree(
            page,
            ("id", "employee", "department", "type", "submitted", "status"),
            {
                "id": "ID",
                "employee": "EMPLOYEE",
                "department": "DEPARTMENT",
                "type": "REQUEST",
                "submitted": "SUBMITTED",
                "status": "STATUS",
            },
            {
                "id": 55,
                "employee": 165,
                "department": 145,
                "type": 215,
                "submitted": 145,
                "status": 95,
            },
        )
        self.request_tree.bind(
            "<<TreeviewSelect>>", self._show_selected_request_details
        )
        details_panel = self._card(page, padding=14)
        details_panel.pack(fill="x", pady=(10, 0))
        ttk.Label(
            details_panel.content,
            text="Request details",
            font=HEADING_FONT,
            background=WHITE,
            foreground=TEXT_COLOR,
        ).pack(anchor="w", pady=(0, 6))
        detail_frame = ttk.Frame(details_panel.content, style="CardContent.TFrame")
        detail_frame.pack(fill="both", expand=True)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)
        self.request_detail_text = tk.Text(
            detail_frame,
            height=7,
            wrap="word",
            padx=8,
            pady=6,
            relief="flat",
            background=WHITE,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 10),
            state="disabled",
        )
        self.request_detail_text.grid(row=0, column=0, sticky="nsew")
        detail_scrollbar = ttk.Scrollbar(
            detail_frame,
            orient="vertical",
            command=self.request_detail_text.yview,
        )
        detail_scrollbar.grid(row=0, column=1, sticky="ns")
        self.request_detail_text.configure(yscrollcommand=detail_scrollbar.set)
        self._refresh_requests()

    def _refresh_requests(self) -> None:
        if not hasattr(self, "request_tree") or not self.request_tree.winfo_exists():
            return
        for item in self.request_tree.get_children():
            self.request_tree.delete(item)
        self._request_details: dict[str, tuple[str, str | None]] = {}
        is_employee = bool(
            self.current_user and self.current_user["role"] == "viewer"
        )
        query = (
            "SELECT r.request_id, r.request_type, r.details, r.status, "
            "r.submitted_at, r.review_note, e.first_name, e.last_name, "
            "d.department_name FROM employee_requests r "
            "JOIN employees e ON e.employee_id = r.employee_id "
            "LEFT JOIN departments d ON d.department_id = e.department_id "
        )
        parameters: tuple[Any, ...] = ()
        if is_employee:
            query += "WHERE r.submitted_by = ? "
            parameters = (int(self.current_user["id"]),)
        query += "ORDER BY r.submitted_at DESC, r.request_id DESC"
        rows = self._fetchall(query, parameters)
        for row in rows:
            request_id = str(row["request_id"])
            self.request_tree.insert(
                "",
                "end",
                iid=request_id,
                values=(
                    request_id,
                    f"{row['first_name']} {row['last_name']}",
                    row["department_name"] or "Unassigned",
                    row["request_type"],
                    row["submitted_at"],
                    row["status"],
                ),
            )
            self._request_details[request_id] = (
                str(row["details"]),
                str(row["review_note"]) if row["review_note"] else None,
            )
        self._set_request_detail_text(
            f"Showing {len(rows)} request(s). Select a row to view its details."
        )
        self.status_var.set(f"Showing {len(rows)} employee request(s)")

    def _set_request_detail_text(self, text: str) -> None:
        self.request_detail_text.configure(state="normal")
        self.request_detail_text.delete("1.0", "end")
        self.request_detail_text.insert("1.0", text)
        self.request_detail_text.configure(state="disabled")

    def _show_selected_request_details(self, _event: tk.Event[tk.Misc]) -> None:
        selection = self.request_tree.selection()
        if not selection:
            return
        details_json, review_note = self._request_details[selection[0]]
        try:
            details = json.loads(details_json)
        except json.JSONDecodeError as exc:
            messagebox.showerror(
                "Could not read request details",
                f"The stored request details are invalid:\n{exc}",
                parent=self,
            )
            return
        if not isinstance(details, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in details.items()
        ):
            messagebox.showerror(
                "Could not read request details",
                "The stored request details have an invalid format.",
                parent=self,
            )
            return
        lines = [f"{key.replace('_', ' ').title()}: {value}" for key, value in details.items()]
        if review_note:
            lines.extend(("", f"Reviewer note: {review_note}"))
        self._set_request_detail_text("\n".join(lines))

    def _open_request_form(self) -> None:
        if not self._require_roles(("viewer",), "submit employee requests"):
            return
        account = self._fetchone(
            "SELECT e.gender FROM users u "
            "LEFT JOIN employees e ON e.employee_id = u.employee_id "
            "WHERE u.id = ?",
            (int(self.current_user["id"]),),
        )
        employee_gender = (
            str(account["gender"] or "").strip().lower() if account else ""
        )
        dialog = tk.Toplevel(self)
        dialog.title("New employee request")
        dialog.configure(bg=BACKGROUND_COLOR)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="New employee request", style="Title.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(
            body,
            text="Your request will be sent to HR and Admin for review.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))
        request_type_var = tk.StringVar(value=REQUEST_TYPES[0])
        ttk.Label(body, text="Request type", style="Muted.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Combobox(
            body,
            textvariable=request_type_var,
            values=REQUEST_TYPES,
            state="readonly",
            width=38,
        ).grid(row=2, column=1, sticky="ew", pady=6)
        fields_frame = ttk.Frame(body)
        fields_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        fields_frame.columnconfigure(1, weight=1)
        active_widgets: dict[str, tk.Widget] = {}

        def render_fields(*_args: str) -> None:
            for child in fields_frame.winfo_children():
                child.destroy()
            active_widgets.clear()
            request_type = request_type_var.get()
            for row, (label, key) in enumerate(
                self.REQUEST_FIELDS[request_type]
            ):
                ttk.Label(fields_frame, text=label, style="Muted.TLabel").grid(
                    row=row, column=0, sticky="nw", padx=(0, 12), pady=6
                )
                if key == "leave_type":
                    leave_types = ["Paid leave", "Sick Leave", "Forced Leave"]
                    if employee_gender == "female":
                        leave_types.append("Maternity leave")
                    elif employee_gender == "male":
                        leave_types.append("Paternity leave")
                    leave_type_combo = ttk.Combobox(
                        fields_frame,
                        values=tuple(leave_types),
                        state="readonly",
                        width=38,
                    )
                    leave_type_combo.set("Paid leave")
                    widget: tk.Widget = leave_type_combo
                elif key in ("start_date", "end_date", "period_start", "period_end", "date"):
                    widget = DatePicker(
                        fields_frame,
                        date.today().isoformat(),
                        width=18,
                    )
                elif key in ("time_out", "time_in"):
                    widget = TimePicker(fields_frame)
                elif key in ("reason", "purpose", "report", "details"):
                    text_frame = ttk.Frame(fields_frame)
                    text_frame.columnconfigure(0, weight=1)
                    text_frame.rowconfigure(0, weight=1)
                    text_widget = tk.Text(
                        text_frame,
                        height=4 if key in ("report", "details") else 3,
                        width=38,
                        wrap="word",
                        padx=7,
                        pady=5,
                    )
                    text_widget.grid(row=0, column=0, sticky="nsew")
                    text_scrollbar = ttk.Scrollbar(
                        text_frame,
                        orient="vertical",
                        command=text_widget.yview,
                    )
                    text_scrollbar.grid(row=0, column=1, sticky="ns")
                    text_widget.configure(yscrollcommand=text_scrollbar.set)
                    text_frame.grid(row=row, column=1, sticky="ew", pady=6)
                    active_widgets[key] = text_widget
                    continue
                else:
                    widget = ttk.Entry(fields_frame, width=41)
                widget.grid(row=row, column=1, sticky="ew", pady=6)
                active_widgets[key] = widget

        render_fields()
        request_type_var.trace_add("write", render_fields)
        body.columnconfigure(1, weight=1)

        def collect_details() -> dict[str, str]:
            details: dict[str, str] = {}
            for key, widget in active_widgets.items():
                if isinstance(widget, (DatePicker, TimePicker)):
                    details[key] = widget.get()
                elif isinstance(widget, tk.Text):
                    details[key] = widget.get("1.0", "end-1c").strip()
                elif isinstance(widget, ttk.Combobox):
                    details[key] = widget.get().strip()
                elif isinstance(widget, ttk.Entry):
                    details[key] = widget.get().strip()
                else:
                    raise TypeError(f"Unsupported request form field: {key}")
            return details

        def submit() -> None:
            try:
                details = collect_details()
                request_id = self.db_manager.submit_employee_request(
                    int(self.current_user["id"]),
                    request_type_var.get(),
                    details,
                )
            except (OSError, sqlite3.Error, ValueError) as exc:
                messagebox.showerror(
                    "Could not submit request", str(exc), parent=dialog
                )
                return
            dialog.destroy()
            self._refresh_requests()
            self.status_var.set(f"Submitted {request_type_var.get()} request")
            messagebox.showinfo(
                "Request submitted",
                f"Request #{request_id} was sent to HR and Admin for review.",
                parent=self,
            )

        buttons = ttk.Frame(body)
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(
            buttons, text="Cancel", style="Secondary.TButton", command=dialog.destroy
        ).pack(side="right", padx=(8, 0))
        ttk.Button(
            buttons, text="Submit request", style="Primary.TButton", command=submit
        ).pack(side="right")
        dialog.update_idletasks()
        dialog.geometry(f"+{self.winfo_rootx() + 300}+{self.winfo_rooty() + 100}")

    def _review_selected_request(self, status: str) -> None:
        if not self._require_roles(("admin", "hr"), "review employee requests"):
            return
        selection = self.request_tree.selection()
        if not selection:
            messagebox.showinfo(
                "Select a request", "Choose a request row first.", parent=self
            )
            return
        request_id = int(selection[0])
        if not messagebox.askyesno(
            f"{status} request",
            f"{status} request #{request_id}?",
            parent=self,
        ):
            return
        try:
            self.db_manager.review_employee_request(
                request_id,
                int(self.current_user["id"]),
                status,
            )
        except (OSError, sqlite3.Error, ValueError) as exc:
            messagebox.showerror(
                "Could not review request", str(exc), parent=self
            )
            self._refresh_requests()
            return
        self._refresh_requests()
        self.status_var.set(f"Request #{request_id} {status.lower()}")
