from __future__ import annotations

import calendar
from collections.abc import Callable
from datetime import date
from math import ceil
import tkinter as tk
from tkinter import ttk

from config import (
    ACCENT_BLUE, BACKGROUND_COLOR, BORDER_COLOR, DANGER_COLOR, GOLD_COLOR,
    HEADING_FONT, MUTED_COLOR, SUCCESS_COLOR, TEXT_COLOR, WHITE,
)
from .core import PayrollAppCore, RoundedCard


class DashboardPages(PayrollAppCore):
    """Build dashboards and workforce overview charts."""

    def _build_dashboard(self) -> None:
        page_container = ttk.Frame(self.page_host)
        page_container.grid(row=0, column=0, sticky="nsew")
        page_container.columnconfigure(0, weight=1)
        page_container.rowconfigure(0, weight=1)
        canvas = tk.Canvas(
            page_container,
            background=BACKGROUND_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(page_container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        page = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=page, anchor="nw")
        self.dashboard_canvas = canvas
        page.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(canvas_window, width=event.width),
        )
        page.columnconfigure(0, weight=1)
        page.rowconfigure(4, weight=1)

        today = date.today()
        month_start = today.replace(day=1).isoformat()
        month_end = today.replace(
            day=calendar.monthrange(today.year, today.month)[1]
        ).isoformat()
        is_admin = self.current_user is not None and self.current_user["role"] == "admin"
        is_employee = self.current_user is not None and self.current_user["role"] == "viewer"
        can_manage_payroll = self._role_allows("Payroll")
        if is_employee:
            request_summary = self._fetchone(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS pending "
                "FROM employee_requests WHERE submitted_by = ?",
                (int(self.current_user["id"]),),
            )
            employee_profile = self._fetchone(
                "SELECT d.department_name FROM users u "
                "LEFT JOIN employees e ON e.employee_id = u.employee_id "
                "LEFT JOIN departments d ON d.department_id = e.department_id "
                "WHERE u.id = ?",
                (int(self.current_user["id"]),),
            )
        else:
            employee_count = int(self._fetchone("SELECT COUNT(*) AS count FROM employees WHERE status = 'active'")["count"])
            department_count = int(self._fetchone("SELECT COUNT(*) AS count FROM departments")["count"])
            attendance_count = int(
                self._fetchone("SELECT COUNT(*) AS count FROM attendance WHERE date = ?", (today.isoformat(),))["count"]
            )
        month_payroll = (
            self._fetchone(
                "SELECT COUNT(*) AS count, COALESCE(SUM(net_pay), 0) AS total "
                "FROM payroll WHERE period_start <= ? AND period_end >= ?",
                (month_end, month_start),
            )
            if can_manage_payroll
            else None
        )

        welcome_panel = RoundedCard(
            page,
            padding=(22, 14),
            fill="#EAF3FB",
            content_style="HeroContent.TFrame",
        )
        welcome_panel.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        greeting_name = self.current_user["username"] if self.current_user else "there"
        ttk.Label(
            welcome_panel.content,
            text=f"Welcome back, {greeting_name}",
            style="HeroTitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            welcome_panel.content,
            text=f"Here is your payroll workspace at a glance.  •  {today.strftime('%A, %B %d, %Y')}",
            style="HeroSub.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        metrics = ttk.Frame(page)
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        for column in range(4):
            metrics.columnconfigure(column, weight=1, uniform="metric")
        if is_employee:
            self._metric_card(
                metrics,
                0,
                "My requests",
                f"{int(request_summary['total'] or 0):,}",
                "Requests you have submitted",
            )
            self._metric_card(
                metrics,
                1,
                "Pending requests",
                f"{int(request_summary['pending'] or 0):,}",
                "Awaiting HR or Admin review",
                GOLD_COLOR,
            )
            self._metric_card(
                metrics,
                2,
                "My department",
                str(employee_profile["department_name"] or "Unassigned"),
                "Your employee profile",
                SUCCESS_COLOR,
            )
            self._metric_card(
                metrics,
                3,
                "Next step",
                "Requests",
                "Submit or check your requests",
                ACCENT_BLUE,
            )
        else:
            self._metric_card(metrics, 0, "Active employees", f"{employee_count:,}", "Current active workforce")
            self._metric_card(metrics, 1, "Departments", f"{department_count:,}", "Organization units", ACCENT_BLUE)
            self._metric_card(metrics, 2, "Attendance today", f"{attendance_count:,}", today.strftime("%b %d, %Y"), SUCCESS_COLOR)
        if not is_employee and can_manage_payroll and month_payroll is not None:
            self._metric_card(
                metrics,
                3,
                "Payroll this month",
                self._money(month_payroll["total"]),
                f"{month_payroll['count']} processed records",
                SUCCESS_COLOR,
            )
        elif not is_employee:
            self._metric_card(
                metrics,
                3,
                "Your role",
                self.ROLE_LABELS.get(self.current_user["role"], "Employee") if self.current_user else "Signed out",
                "Available sections",
            )

        if self.current_user and self.current_user["role"] in self.EDIT_ROLES:
            action_panel = self._card(page, padding=12)
            action_panel.grid(row=2, column=0, sticky="ew", pady=(0, 16))
            actions = ttk.Frame(action_panel.content, style="CardContent.TFrame")
            actions.pack(fill="x")
            ttk.Label(actions, text="QUICK ACTIONS", style="MetricBlueTitle.TLabel").pack(side="left", padx=(0, 14))
            ttk.Button(actions, text="+  Add employee", style="Primary.TButton", command=self._open_employee_form).pack(side="left", padx=(0, 8))
            ttk.Button(actions, text="+  Record attendance", style="Secondary.TButton", command=self._open_attendance_form).pack(side="left", padx=4)
            if can_manage_payroll:
                ttk.Button(actions, text="Process payroll  →", style="Secondary.TButton", command=lambda: self._show_page("Payroll")).pack(side="left", padx=4)

        show_dashboard_charts = (
            self.current_user is not None
            and self.current_user["role"] in self.DASHBOARD_CHART_ROLES
        )
        if show_dashboard_charts:
            charts = ttk.Frame(page)
            charts.grid(row=3, column=0, sticky="ew", pady=(0, 16))
            charts.columnconfigure(0, weight=1, uniform="dashboard-chart")
            charts.columnconfigure(1, weight=1, uniform="dashboard-chart")
            chart_months = []
            month_cursor = today.replace(day=1)
            for _ in range(6):
                chart_months.append(month_cursor)
                month_cursor = (
                    month_cursor.replace(year=month_cursor.year - 1, month=12)
                    if month_cursor.month == 1
                    else month_cursor.replace(month=month_cursor.month - 1)
                )
            chart_months.reverse()
            payroll_rows = self._fetchall(
                "SELECT substr(period_start, 1, 7) AS month, COALESCE(SUM(net_pay), 0) AS total "
                "FROM payroll WHERE period_start >= ? AND period_start <= ? "
                "GROUP BY substr(period_start, 1, 7)",
                (chart_months[0].isoformat(), today.isoformat()),
            )
            payroll_by_month = {str(row["month"]): float(row["total"]) for row in payroll_rows}
            self._add_bar_chart(
                charts,
                "Net payroll by month",
                [
                    (month.strftime("%b"), payroll_by_month.get(month.strftime("%Y-%m"), 0.0))
                    for month in chart_months
                ],
                lambda value: f"{self.settings.get('currency_symbol', '₱')}{value / 1000:.0f}k",
                column=0,
            )
            attendance_dates = [
                date.fromordinal(today.toordinal() - offset)
                for offset in range(6, -1, -1)
            ]
            attendance_rows = self._fetchall(
                "SELECT date, COUNT(*) AS count FROM attendance WHERE date >= ? AND date <= ? "
                "GROUP BY date",
                (attendance_dates[0].isoformat(), today.isoformat()),
            )
            attendance_by_date = {str(row["date"]): float(row["count"]) for row in attendance_rows}
            self._add_bar_chart(
                charts,
                "Attendance records · last 7 days",
                [
                    (day.strftime("%a"), attendance_by_date.get(day.isoformat(), 0.0))
                    for day in attendance_dates
                ],
                lambda value: f"{value:.0f}",
                column=1,
                integer_axis=True,
            )

        lower = ttk.Frame(page)
        lower.grid(row=4, column=0, sticky="nsew")
        lower.columnconfigure(0, weight=3)
        lower.columnconfigure(1, weight=2)
        lower.rowconfigure(0, weight=1)

        can_view_payroll = self._role_allows("Payroll")
        recent_card = self._card(lower)
        recent_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        if can_view_payroll:
            recent_header = ttk.Frame(recent_card.content, style="CardContent.TFrame")
            recent_header.pack(fill="x", pady=(0, 12))
            ttk.Label(recent_header, text="Recent payroll", font=HEADING_FONT, background=WHITE, foreground=TEXT_COLOR).pack(side="left")
            ttk.Button(recent_header, text="View all  →", style="Secondary.TButton", command=lambda: self._show_page("Payroll")).pack(side="right")
            tree = self._make_tree(
                recent_card.content,
                ("employee", "period", "gross", "net"),
                {"employee": "EMPLOYEE", "period": "PAY PERIOD", "gross": "GROSS PAY", "net": "NET PAY"},
                {"employee": 190, "period": 115, "gross": 115, "net": 115},
                height=8,
            )
            records = self._fetchall(
                "SELECT e.first_name, e.last_name, p.period_start, p.period_end, p.gross_pay, p.net_pay "
                "FROM payroll p JOIN employees e ON e.employee_id = p.employee_id "
                "ORDER BY p.generated_at DESC, p.payroll_id DESC LIMIT 8"
            )
            for record in records:
                tree.insert("", "end", values=(
                    f"{record['first_name']} {record['last_name']}",
                    f"{record['period_start']} – {record['period_end']}",
                    self._money(record["gross_pay"]),
                    self._money(record["net_pay"]),
                ))
            if not records:
                self._empty_state(recent_card.content, "No payroll has been processed yet.")

        insight = self._card(lower)
        if can_view_payroll:
            insight.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        else:
            recent_card.grid_remove()
            insight.grid(row=0, column=0, columnspan=2, sticky="nsew")
        if is_employee:
            ttk.Label(
                insight.content, text="My request status",
                font=HEADING_FONT,
                background=WHITE,
            ).pack(anchor="w")
            ttk.Label(
                insight.content,
                text="Track requests submitted from your account.",
                style="CardMuted.TLabel",
                wraplength=300,
            ).pack(anchor="w", pady=(4, 14))
            self._snapshot_line(
                insight.content,
                "Pending review",
                str(int(request_summary["pending"] or 0)),
                GOLD_COLOR,
            )
            self._snapshot_line(
                insight.content,
                "All submitted",
                str(int(request_summary["total"] or 0)),
                ACCENT_BLUE,
            )
            ttk.Button(
                insight.content,
                text="Open my requests  →",
                style="Secondary.TButton",
                command=lambda: self._show_page("Requests"),
            ).pack(anchor="w", pady=(16, 0))
        else:
            ttk.Label(insight.content, text="Workspace snapshot", font=HEADING_FONT, background=WHITE, foreground=TEXT_COLOR).pack(anchor="w")
            ttk.Label(
                insight.content,
                text="A quick pulse on records that may need attention.",
                style="CardMuted.TLabel",
                wraplength=300,
            ).pack(anchor="w", pady=(4, 14))
            no_attendance = int(self._fetchone(
                "SELECT COUNT(*) AS count FROM employees e WHERE e.status = 'active' "
                "AND NOT EXISTS (SELECT 1 FROM attendance a WHERE a.employee_id = e.employee_id AND a.date = ?)",
                (today.isoformat(),),
            )["count"])
            self._snapshot_line(insight.content, "Active employees", str(employee_count), ACCENT_BLUE)
            if is_admin:
                missing_salary = int(self._fetchone(
                    "SELECT COUNT(*) AS count FROM employees WHERE status = 'active' "
                    "AND COALESCE(hourly_rate, 0) <= 0"
                )["count"])
                self._snapshot_line(insight.content, "Missing pay rate", str(missing_salary), DANGER_COLOR if missing_salary else SUCCESS_COLOR)
            self._snapshot_line(insight.content, "No record today", str(no_attendance), GOLD_COLOR)
            if self._role_allows("Attendance"):
                ttk.Button(insight.content, text="Review attendance  →", style="Secondary.TButton", command=lambda: self._show_page("Attendance")).pack(anchor="w", pady=(16, 0))

    def _add_bar_chart(
        self,
        parent: ttk.Frame,
        title: str,
        items: list[tuple[str, float]],
        value_label: Callable[[float], str],
        *,
        column: int,
        integer_axis: bool = False,
    ) -> None:
        panel = self._card(parent, padding=16)
        panel.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column == 0 else (8, 0))
        ttk.Label(
            panel.content,
            text=title,
            font=("Segoe UI", 12, "bold"),
            background=WHITE,
            foreground=TEXT_COLOR,
        ).pack(anchor="w", pady=(0, 8))
        chart = tk.Canvas(
            panel.content,
            height=190,
            background=WHITE,
            highlightthickness=0,
        )
        chart.pack(fill="both", expand=True)

        def draw(_event: tk.Event[tk.Misc] | None = None) -> None:
            chart.delete("all")
            grid_color = "#334155" if self.dark_mode else BORDER_COLOR
            muted_color = "#A7B6CA" if self.dark_mode else MUTED_COLOR
            text_color = "#F1F5F9" if self.dark_mode else TEXT_COLOR
            bar_color = "#60A5FA" if self.dark_mode else ACCENT_BLUE
            width = max(chart.winfo_width(), 280)
            height = max(chart.winfo_height(), 160)
            left, right, top, bottom = 48, width - 12, 12, height - 34
            plot_height = bottom - top
            plot_width = right - left
            maximum = max((value for _, value in items), default=0.0)
            maximum = maximum if maximum > 0 else 1.0
            if integer_axis:
                tick_maximum = max(1, ceil(maximum))
                tick_step = max(1, (tick_maximum + 2) // 3)
                tick_values = list(range(0, tick_maximum, tick_step)) + [tick_maximum]
            else:
                tick_values = [maximum * tick / 3 for tick in range(4)]

            for tick_value in tick_values:
                fraction = tick_value / maximum
                y = bottom - fraction * plot_height
                chart.create_line(left, y, right, y, fill=grid_color)
                chart.create_text(
                    left - 7,
                    y,
                    text=value_label(float(tick_value)),
                    anchor="e",
                    fill=muted_color,
                    font=("Segoe UI", 8),
                )

            if not items or not any(value > 0 for _, value in items):
                chart.create_text(
                    (left + right) / 2,
                    top + plot_height / 2,
                    text="No data yet",
                    fill=muted_color,
                    font=("Segoe UI", 10),
                )
            slot = plot_width / max(len(items), 1)
            bar_width = min(34, slot * 0.58)
            for index, (label, value) in enumerate(items):
                center = left + slot * (index + 0.5)
                bar_height = max(0.0, value) / maximum * plot_height
                chart.create_rectangle(
                    center - bar_width / 2,
                    bottom - bar_height,
                    center + bar_width / 2,
                    bottom,
                    fill=bar_color,
                    outline="",
                )
                chart.create_text(
                    center,
                    bottom + 15,
                    text=label[:9],
                    fill=text_color,
                    font=("Segoe UI", 8),
                )

        chart.bind("<Configure>", draw)

    def _snapshot_line(self, parent: ttk.Frame, label: str, value: str, color: str) -> None:
        row = ttk.Frame(parent, style="CardContent.TFrame")
        row.pack(fill="x", pady=7)
        ttk.Label(row, text=label, style="CardMuted.TLabel").pack(side="left")
        ttk.Label(row, text=value, font=("Segoe UI", 13, "bold"), foreground=color, background=WHITE).pack(side="right")

