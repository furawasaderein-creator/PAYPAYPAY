from __future__ import annotations

import calendar
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from config import BACKGROUND_COLOR, WHITE


class DatePicker(ttk.Frame):
    """A date field that opens a month calendar with month and year selectors.

    ``min_year`` / ``max_year`` control which years appear in the year dropdown.
    ``initial_view`` is the month shown when the field is empty (for example a
    birth-date field can open around 30 years ago instead of today).
    """

    def __init__(
        self,
        master: tk.Misc,
        value: str = "",
        *,
        allow_empty: bool = False,
        on_change: Callable[[], None] | None = None,
        width: int = 18,
        min_year: int | None = None,
        max_year: int | None = None,
        initial_view: date | None = None,
    ) -> None:
        super().__init__(master)
        today = date.today()
        self.min_year = max(1, today.year - 30 if min_year is None else min_year)
        self.max_year = min(9999, today.year + 10 if max_year is None else max_year)
        if self.min_year > self.max_year:
            raise ValueError("min_year cannot be after max_year.")
        self.allow_empty = allow_empty
        self.on_change = on_change
        self.initial_view = initial_view
        self._value = ""
        self._popup: tk.Toplevel | None = None
        self._calendar_year = today.year
        self._calendar_month = today.month
        self._years: tuple[int, ...] = ()
        self.button = ttk.Button(
            self, width=width, style="Secondary.TButton", command=self._open_calendar
        )
        self.button.pack(fill="x")
        self.set(value)

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        value = value.strip()
        if value:
            parsed = date.fromisoformat(value)
            self._value = parsed.isoformat()
            display = parsed.strftime("%B %d, %Y")
        else:
            self._value = ""
            display = "Select date"
        self.button.configure(text=display)

    def _open_calendar(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.lift()
            return

        if self._value:
            view = date.fromisoformat(self._value)
            year = view.year
        else:
            view = self.initial_view or date.today()
            year = min(max(view.year, self.min_year), self.max_year)
        self._calendar_year, self._calendar_month = year, view.month
        # Always offer the year being shown, even if it is outside the usual range
        # (for example an old value loaded from the database).
        first_year = min(self.min_year, year)
        last_year = max(self.max_year, year)
        self._years = tuple(range(first_year, last_year + 1))

        popup = tk.Toplevel(self.winfo_toplevel())
        self._popup = popup
        popup.title("Select date")
        popup.transient(self.winfo_toplevel())
        popup.resizable(False, False)
        body = ttk.Frame(popup, padding=10)
        body.pack()

        header = ttk.Frame(body)
        header.pack(fill="x", pady=(0, 6))
        ttk.Button(
            header, text="‹", width=3, command=lambda: self._change_month(-1)
        ).pack(side="left")
        ttk.Button(
            header, text="›", width=3, command=lambda: self._change_month(1)
        ).pack(side="right")
        selectors = ttk.Frame(header)
        selectors.pack(side="left", expand=True)
        self._month_var = tk.StringVar(master=popup)
        self._year_var = tk.StringVar(master=popup)
        month_combo = ttk.Combobox(
            selectors,
            textvariable=self._month_var,
            values=tuple(calendar.month_name)[1:],
            state="readonly",
            width=10,
        )
        month_combo.pack(side="left", padx=(0, 4))
        year_combo = ttk.Combobox(
            selectors,
            textvariable=self._year_var,
            values=tuple(str(item) for item in self._years),
            state="readonly",
            width=6,
            height=12,
        )
        year_combo.pack(side="left")
        month_combo.bind("<<ComboboxSelected>>", self._on_month_year_selected)
        year_combo.bind("<<ComboboxSelected>>", self._on_month_year_selected)

        self._days_frame = ttk.Frame(body)
        self._days_frame.pack()
        if self.allow_empty:
            ttk.Button(
                body,
                text="Clear date",
                command=lambda: self._select_date(""),
            ).pack(anchor="e", pady=(6, 0))

        self._render_calendar()
        popup.update_idletasks()
        popup.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height()}")
        popup.protocol("WM_DELETE_WINDOW", self._close_calendar)
        popup.bind("<Escape>", lambda _event: self._close_calendar())

    def _on_month_year_selected(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        months = tuple(calendar.month_name)[1:]
        try:
            self._calendar_month = months.index(self._month_var.get()) + 1
            self._calendar_year = int(self._year_var.get())
        except ValueError:
            return
        self._render_calendar()

    def _change_month(self, offset: int) -> None:
        month_index = self._calendar_year * 12 + self._calendar_month - 1 + offset
        year, month = divmod(month_index, 12)
        if not self._years or not self._years[0] <= year <= self._years[-1]:
            return
        self._calendar_year = year
        self._calendar_month = month + 1
        self._render_calendar()

    def _render_calendar(self) -> None:
        self._month_var.set(calendar.month_name[self._calendar_month])
        self._year_var.set(str(self._calendar_year))
        for child in self._days_frame.winfo_children():
            child.destroy()
        for column, weekday in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            ttk.Label(self._days_frame, text=weekday, anchor="center", width=4).grid(
                row=0, column=column, padx=1, pady=1
            )
        for row_index, week in enumerate(
            calendar.monthcalendar(self._calendar_year, self._calendar_month), start=1
        ):
            for column, day_number in enumerate(week):
                if not day_number:
                    continue
                iso_value = date(
                    self._calendar_year, self._calendar_month, day_number
                ).isoformat()
                ttk.Button(
                    self._days_frame,
                    text=str(day_number),
                    width=3,
                    style="Primary.TButton" if iso_value == self._value else "TButton",
                    command=lambda value=iso_value: self._select_date(value),
                ).grid(row=row_index, column=column, padx=1, pady=1)

    def _select_date(self, value: str) -> None:
        self.set(value)
        self._close_calendar()
        if self.on_change is not None:
            self.on_change()

    def _close_calendar(self) -> None:
        if self._popup is not None and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None


class TimePicker(ttk.Frame):
    """A time selector with hour, minute, and AM/PM dropdowns."""

    def __init__(
        self,
        master: tk.Misc,
        value: str = "",
        *,
        allow_empty: bool = False,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.allow_empty = allow_empty
        self.on_change = on_change
        self._hour_var = tk.StringVar(value="—")
        self._minute_var = tk.StringVar(value="—")
        self._period_var = tk.StringVar(value="—")
        ttk.Combobox(
            self,
            textvariable=self._hour_var,
            values=("—", *(f"{hour:02d}" for hour in range(1, 13))),
            state="readonly",
            width=4,
        ).pack(side="left")
        ttk.Label(self, text=":").pack(side="left", padx=3)
        ttk.Combobox(
            self,
            textvariable=self._minute_var,
            values=("—", *(f"{minute:02d}" for minute in range(60))),
            state="readonly",
            width=4,
        ).pack(side="left")
        ttk.Combobox(
            self,
            textvariable=self._period_var,
            values=("—", "AM", "PM"),
            state="readonly",
            width=4,
        ).pack(side="left", padx=(6, 0))
        self._hour_var.trace_add("write", self._notify_change)
        self._minute_var.trace_add("write", self._notify_change)
        self._period_var.trace_add("write", self._notify_change)
        self.set(value)

    def get(self) -> str:
        hour = self._hour_var.get()
        minute = self._minute_var.get()
        period = self._period_var.get()
        if hour == minute == period == "—" and self.allow_empty:
            return ""
        if "—" in (hour, minute, period):
            raise ValueError("Select an hour, minute, and AM/PM.")
        return datetime.strptime(f"{hour}:{minute} {period}", "%I:%M %p").strftime(
            "%H:%M"
        )

    def set(self, value: str) -> None:
        value = value.strip()
        if value:
            parsed = datetime.strptime(value, "%H:%M")
            self._hour_var.set(parsed.strftime("%I"))
            self._minute_var.set(parsed.strftime("%M"))
            self._period_var.set(parsed.strftime("%p"))
        else:
            self._hour_var.set("—")
            self._minute_var.set("—")
            self._period_var.set("—")

    def _notify_change(self, *_args: str) -> None:
        if self.on_change is not None:
            self.on_change()


class RoundedCard(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        padding: int = 18,
        fill: str = WHITE,
        content_style: str = "CardContent.TFrame",
    ) -> None:
        super().__init__(master, background=BACKGROUND_COLOR, borderwidth=0, highlightthickness=0)
        self._fill = fill
        self._outline = "#D9E3F0"
        self._canvas = tk.Canvas(
            self,
            background=BACKGROUND_COLOR,
            borderwidth=0,
            highlightthickness=0,
            takefocus=False,
        )
        self._canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.content = ttk.Frame(self, style=content_style, padding=padding)
        self.content.pack(fill="both", expand=True, padx=6, pady=6)
        self.bind("<Configure>", self._draw_background)

    def _draw_background(self, _event: tk.Event[tk.Misc]) -> None:
        width, height = self.winfo_width(), self.winfo_height()
        self._canvas.delete("card")
        if width < 2 or height < 2:
            return
        radius = min(9, width // 2, height // 2)
        points = (
            radius, 0, width - radius, 0, width, 0, width, radius,
            width, height - radius, width, height, width - radius, height,
            radius, height, 0, height, 0, height - radius, 0, radius, 0, 0,
        )
        self._canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill=self._fill,
            outline=self._outline,
            width=1,
            tags="card",
        )


class PayrollTreeview(ttk.Treeview):
    def __init__(self, master: tk.Misc, *, dark_mode: bool = False, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self._hovered_item = ""
        self.tag_configure("row-even", background="#FFFFFF" if not dark_mode else "#1F2937")
        self.tag_configure("row-odd", background="#F7F9FC" if not dark_mode else "#222F40")
        self.tag_configure("row-hover", background="#EAF3FB" if not dark_mode else "#29394D")
        self.bind("<Motion>", self._highlight_hovered_row, add="+")
        self.bind("<Leave>", self._clear_hovered_row, add="+")

    def insert(
        self,
        parent: str,
        index: str | int,
        iid: str | None = None,
        **kwargs: Any,
    ) -> str:
        tags = list(kwargs.get("tags", ()))
        if "row-even" not in tags and "row-odd" not in tags:
            row_tag = "row-even" if len(self.get_children(parent)) % 2 == 0 else "row-odd"
            tags.append(row_tag)
        kwargs["tags"] = tuple(tags)
        return super().insert(parent, index, iid=iid, **kwargs)

    def _highlight_hovered_row(self, event: tk.Event[tk.Misc]) -> None:
        item = self.identify_row(event.y)
        if item == self._hovered_item:
            return
        self._clear_hovered_row()
        if item:
            tags = tuple(tag for tag in self.item(item, "tags") if tag != "row-hover")
            self.item(item, tags=(*tags, "row-hover"))
            self._hovered_item = item

    def _clear_hovered_row(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        if self._hovered_item and self.exists(self._hovered_item):
            tags = tuple(tag for tag in self.item(self._hovered_item, "tags") if tag != "row-hover")
            self.item(self._hovered_item, tags=tags)
        self._hovered_item = ""