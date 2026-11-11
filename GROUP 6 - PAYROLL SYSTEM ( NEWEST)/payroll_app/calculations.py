from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from math import isfinite


def calculate_hourly_gross(
    hourly_rate: float, regular_hours: float, overtime_hours: float
) -> float:
    if (
        not all(isfinite(value) for value in (hourly_rate, regular_hours, overtime_hours))
        or hourly_rate <= 0
        or regular_hours < 0
        or overtime_hours < 0
    ):
        raise ValueError(
            "Hourly pay inputs must be finite and non-negative, with a positive rate."
        )
    gross = hourly_rate * (regular_hours + overtime_hours * 1.5)
    if not isfinite(gross):
        raise ValueError("Calculated gross pay is not finite.")
    return gross


def calculate_philippine_deductions(
    monthly_basic_pay: float, gross_pay: float
) -> tuple[float, float, float, float]:
    if (
        not all(isfinite(value) for value in (monthly_basic_pay, gross_pay))
        or monthly_basic_pay < 0
        or gross_pay < 0
    ):
        raise ValueError(
            "Monthly basic pay and gross pay must be finite and non-negative."
        )
    if gross_pay == 0:
        return 0.0, 0.0, 0.0, 0.0

    salary_credit = min(35_000, max(5_000, int((monthly_basic_pay + 250) // 500) * 500))
    sss = round(salary_credit * 0.05, 2)

    philhealth_base = min(100_000, max(10_000, monthly_basic_pay))
    philhealth = round(philhealth_base * 0.025, 2)

    pagibig_base = min(10_000, monthly_basic_pay)
    pagibig_rate = 0.01 if monthly_basic_pay <= 1_500 else 0.02
    pagibig = round(pagibig_base * pagibig_rate, 2)

    taxable_compensation = max(0.0, gross_pay - sss - philhealth - pagibig)
    if taxable_compensation <= 20_833:
        tax = 0.0
    elif taxable_compensation <= 33_333:
        tax = (taxable_compensation - 20_833) * 0.15
    elif taxable_compensation <= 66_667:
        tax = 1_875 + (taxable_compensation - 33_333) * 0.20
    elif taxable_compensation <= 166_667:
        tax = 8_541.67 + (taxable_compensation - 66_667) * 0.25
    elif taxable_compensation <= 666_667:
        tax = 33_541.67 + (taxable_compensation - 166_667) * 0.30
    else:
        tax = 183_541.67 + (taxable_compensation - 666_667) * 0.35

    return sss, philhealth, pagibig, round(max(0.0, tax), 2)


def calculate_late_minutes(scheduled_start: str, time_in: str | None) -> int:
    if not time_in:
        return 0
    scheduled = datetime.strptime(scheduled_start, "%H:%M").time()
    actual = datetime.strptime(time_in, "%H:%M").time()
    scheduled_minutes = scheduled.hour * 60 + scheduled.minute
    actual_minutes = actual.hour * 60 + actual.minute
    return max(0, actual_minutes - scheduled_minutes)


def calculate_attendance_hours(
    time_in: str | None,
    time_out: str | None,
    scheduled_start: str,
    scheduled_end: str,
) -> tuple[float, float]:
    if not time_in or not time_out:
        return 0.0, 0.0

    actual_start = datetime.strptime(time_in, "%H:%M")
    actual_end = datetime.strptime(time_out, "%H:%M")
    shift_start = datetime.strptime(scheduled_start, "%H:%M")
    shift_end = datetime.strptime(scheduled_end, "%H:%M")

    if shift_end.hour == shift_start.hour and shift_end.minute == shift_start.minute:
        raise ValueError("Scheduled shift start and end must differ.")

    worked_minutes = (actual_end.hour * 60 + actual_end.minute) - (
        actual_start.hour * 60 + actual_start.minute
    )
    if worked_minutes == 0:
        raise ValueError("Time out must differ from time in.")
    if worked_minutes < 0:
        worked_minutes += 24 * 60

    shift_end_minutes = shift_end.hour * 60 + shift_end.minute
    if shift_end_minutes < shift_start.hour * 60 + shift_start.minute:
        shift_end_minutes += 24 * 60

    actual_end_minutes = actual_end.hour * 60 + actual_end.minute
    if actual_end_minutes < actual_start.hour * 60 + actual_start.minute:
        actual_end_minutes += 24 * 60
    overtime_minutes = min(worked_minutes, max(0, actual_end_minutes - shift_end_minutes))
    return round(worked_minutes / 60, 2), round(overtime_minutes / 60, 2)


def is_full_calendar_month(period_start: date, period_end: date) -> bool:
    return (
        period_start.day == 1
        and period_start.year == period_end.year
        and period_start.month == period_end.month
        and period_end.day
        == calendar.monthrange(period_start.year, period_start.month)[1]
    )


def calculate_paid_leave_hours(
    leave_records: list[tuple[str, str]],
    attendance_dates: set[str],
    period_start: date,
    period_end: date,
) -> float:
    paid_dates: set[date] = set()
    for start_value, end_value in leave_records:
        current = max(date.fromisoformat(start_value), period_start)
        end = min(date.fromisoformat(end_value), period_end)
        while current <= end:
            if current.weekday() < 5 and current.isoformat() not in attendance_dates:
                paid_dates.add(current)
            current += timedelta(days=1)
    return float(len(paid_dates) * 8)
