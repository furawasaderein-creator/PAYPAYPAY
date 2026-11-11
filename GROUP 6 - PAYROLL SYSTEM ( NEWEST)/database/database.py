from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH, ensure_directories
from database.schema import SCHEMA_STATEMENTS

REQUEST_TYPES = (
    "Leave",
    "Travel Order",
    "Accomplishment Report",
    "Clearance",
    "Pass Slip",
    "Certificate of Employment (COE)",
)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
            iteration_count = int(iterations)
            if not 100_000 <= iteration_count <= 2_000_000:
                return False
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), iteration_count
            )
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)


class DatabaseManager:
    """Manage SQLite connectivity and initial application setup."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else DATABASE_PATH

    def connect(self) -> sqlite3.Connection:
        """Create a SQLite connection with row factory support."""
        ensure_directories()
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        """Create tables and seed default records if absent."""
        connection = self.connect()
        try:
            with connection:
                for statement in SCHEMA_STATEMENTS:
                    connection.execute(statement)
                user_columns = {
                    str(row["name"])
                    for row in connection.execute("PRAGMA table_info(users)").fetchall()
                }
                if "employee_id" not in user_columns:
                    connection.execute(
                        "ALTER TABLE users ADD COLUMN employee_id INTEGER "
                        "REFERENCES employees(employee_id)"
                    )
                if "profile_image" not in user_columns:
                    connection.execute("ALTER TABLE users ADD COLUMN profile_image BLOB")
                connection.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_employee_id "
                    "ON users(employee_id) WHERE employee_id IS NOT NULL"
                )
                leave_table_sql = str(
                    connection.execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name='leave_records'"
                    ).fetchone()["sql"]
                )
                supported_leave_types = (
                    "Sick Leave",
                    "Forced Leave",
                    "Paternity leave",
                )
                if not all(leave_type in leave_table_sql for leave_type in supported_leave_types):
                    connection.execute(
                        "CREATE TABLE leave_records_updated ("
                        "leave_id INTEGER PRIMARY KEY AUTOINCREMENT,"
                        "employee_id INTEGER NOT NULL,"
                        "leave_type TEXT NOT NULL CHECK (leave_type IN "
                        "('Paid leave','Sick Leave','Forced Leave','Maternity leave','Paternity leave','Travel order')),"
                        "start_date TEXT NOT NULL,"
                        "end_date TEXT NOT NULL,"
                        "status TEXT NOT NULL DEFAULT 'Pending' CHECK "
                        "(status IN ('Pending','Approved','Rejected')),"
                        "notes TEXT,"
                        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
                        "FOREIGN KEY (employee_id) REFERENCES employees(employee_id))"
                    )
                    connection.execute(
                        "INSERT INTO leave_records_updated "
                        "(leave_id,employee_id,leave_type,start_date,end_date,status,notes,created_at) "
                        "SELECT leave_id,employee_id,leave_type,start_date,end_date,status,notes,created_at "
                        "FROM leave_records"
                    )
                    connection.execute("DROP TABLE leave_records")
                    connection.execute(
                        "ALTER TABLE leave_records_updated RENAME TO leave_records"
                    )
                employee_columns = {
                    str(row["name"])
                    for row in connection.execute("PRAGMA table_info(employees)").fetchall()
                }
                if "hourly_rate" not in employee_columns:
                    connection.execute("ALTER TABLE employees ADD COLUMN hourly_rate REAL")
                if "scheduled_start_time" not in employee_columns:
                    connection.execute(
                        "ALTER TABLE employees ADD COLUMN scheduled_start_time TEXT NOT NULL DEFAULT '09:00'"
                    )
                if "scheduled_end_time" not in employee_columns:
                    connection.execute(
                        "ALTER TABLE employees ADD COLUMN scheduled_end_time TEXT NOT NULL DEFAULT '17:00'"
                    )
                attendance_columns = {
                    str(row["name"])
                    for row in connection.execute("PRAGMA table_info(attendance)").fetchall()
                }
                if "late_minutes" not in attendance_columns:
                    connection.execute(
                        "ALTER TABLE attendance ADD COLUMN late_minutes INTEGER NOT NULL DEFAULT 0"
                    )
                    connection.execute(
                        "UPDATE attendance SET late_minutes = MAX(0, "
                        "(CAST(substr(time_in, 1, instr(time_in, ':') - 1) AS INTEGER) * 60 + "
                        "CAST(substr(time_in, instr(time_in, ':') + 1, 2) AS INTEGER)) - "
                        "(CAST(substr(e.scheduled_start_time, 1, 2) AS INTEGER) * 60 + "
                        "CAST(substr(e.scheduled_start_time, 4, 2) AS INTEGER))) "
                        "FROM employees e WHERE attendance.employee_id = e.employee_id "
                        "AND time_in IS NOT NULL AND length(time_in) >= 4 AND instr(time_in, ':') > 0"
                    )
                payroll_columns = {
                    str(row["name"])
                    for row in connection.execute("PRAGMA table_info(payroll)").fetchall()
                }
                has_legacy_payroll_deductions = not any(
                    column in payroll_columns
                    for column in (
                        "sss_deduction",
                        "philhealth_deduction",
                        "pagibig_deduction",
                        "tax_withheld",
                        "other_deductions",
                        "paid_leave_hours",
                    )
                )
                for column in (
                    "sss_deduction",
                    "philhealth_deduction",
                    "pagibig_deduction",
                    "tax_withheld",
                    "other_deductions",
                    "paid_leave_hours",
                ):
                    if column not in payroll_columns:
                        connection.execute(
                            f"ALTER TABLE payroll ADD COLUMN {column} REAL NOT NULL DEFAULT 0"
                        )
                        if column == "other_deductions" and has_legacy_payroll_deductions:
                            connection.execute(
                                "UPDATE payroll SET other_deductions = deductions"
                            )
                if "tardiness_deduction" not in payroll_columns:
                    connection.execute(
                        "ALTER TABLE payroll ADD COLUMN tardiness_deduction REAL NOT NULL DEFAULT 0"
                    )
                if "tardiness_minutes" not in payroll_columns:
                    connection.execute(
                        "ALTER TABLE payroll ADD COLUMN tardiness_minutes INTEGER NOT NULL DEFAULT 0"
                    )
                connection.execute(
                    "UPDATE employees SET "
                    "hourly_rate = CASE "
                    "WHEN LOWER(salary_type) = 'monthly' THEN monthly_salary / 176.0 "
                    "WHEN LOWER(salary_type) = 'daily' THEN daily_rate / 8.0 "
                    "ELSE hourly_rate END, "
                    "salary_type = 'hourly' "
                    "WHERE LOWER(salary_type) IN ('monthly', 'daily')"
                )
                self._seed_default_data(connection)
        finally:
            connection.close()

    def _seed_default_data(self, connection: sqlite3.Connection) -> None:
        """Create an admin user and basic departments when the database is empty."""
        user_exists = connection.execute(
            "SELECT 1 FROM users WHERE username = ?",
            ("Admin",),
        ).fetchone()
        if user_exists is None:
            password_hash = hash_password("Admin123")
            connection.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("Admin", password_hash, "admin"),
            )

        department_exists = connection.execute(
            "SELECT 1 FROM departments WHERE department_name = ?",
            ("Administration",),
        ).fetchone()
        if department_exists is None:
            connection.execute(
                "INSERT INTO departments (department_name) VALUES (?)",
                ("Administration",),
            )

    def get_connection(self) -> sqlite3.Connection:
        """Return a connected SQLite session for use by controllers."""
        return self.connect()

    def submit_employee_request(self, user_id: int, request_type: str, details: dict[str, str]) -> int:
        if request_type not in REQUEST_TYPES:
            raise ValueError("Choose a supported request type.")
        if not isinstance(details, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in details.items()
        ):
            raise ValueError("Request details must contain text fields.")
        if any(not value.strip() for value in details.values()):
            raise ValueError("Complete all request fields before submitting.")

        required_fields = {
            "Leave": ("leave_type", "start_date", "end_date", "reason"),
            "Travel Order": ("destination", "start_date", "end_date", "purpose"),
            "Accomplishment Report": ("period_start", "period_end", "report"),
            "Clearance": ("purpose", "details"),
            "Pass Slip": ("date", "time_out", "time_in", "reason"),
            "Certificate of Employment (COE)": ("purpose", "details"),
        }[request_type]
        if any(not details.get(field, "").strip() for field in required_fields):
            raise ValueError("Complete all request fields before submitting.")

        date_fields = {
            "Leave": ("start_date", "end_date"),
            "Travel Order": ("start_date", "end_date"),
            "Accomplishment Report": ("period_start", "period_end"),
            "Pass Slip": ("date",),
        }.get(request_type, ())
        try:
            parsed_dates = [datetime.strptime(details[field], "%Y-%m-%d").date() for field in date_fields]
        except ValueError as exc:
            raise ValueError("Enter valid request dates.") from exc
        if len(parsed_dates) == 2 and parsed_dates[1] < parsed_dates[0]:
            raise ValueError("The end date cannot be before the start date.")
        if request_type == "Leave" and details["leave_type"] not in (
            "Paid leave",
            "Sick Leave",
            "Forced Leave",
            "Maternity leave",
            "Paternity leave",
        ):
            raise ValueError("Choose a supported leave type.")
        try:
            if request_type == "Pass Slip":
                datetime.strptime(details["time_out"], "%H:%M")
                datetime.strptime(details["time_in"], "%H:%M")
        except ValueError as exc:
            raise ValueError("Enter valid pass slip times.") from exc

        with closing(self.connect()) as connection:
            with connection:
                user = connection.execute(
                    "SELECT u.role, u.employee_id, e.gender FROM users u "
                    "LEFT JOIN employees e ON e.employee_id = u.employee_id "
                    "WHERE u.id = ?",
                    (user_id,),
                ).fetchone()
                if user is None or user["role"] != "viewer":
                    raise ValueError("Only employee accounts can submit employee requests.")
                if user["employee_id"] is None:
                    raise ValueError("Your account is not linked to an employee profile. Contact an administrator.")
                if request_type == "Leave":
                    employee_gender = str(user["gender"] or "").strip().lower()
                    leave_type = details["leave_type"]
                    if leave_type == "Maternity leave" and employee_gender != "female":
                        raise ValueError("Maternity leave is available only to employees registered as female.")
                    if leave_type == "Paternity leave" and employee_gender != "male":
                        raise ValueError("Paternity leave is available only to employees registered as male.")
                cursor = connection.execute(
                    "INSERT INTO employee_requests "
                    "(employee_id, submitted_by, request_type, details) VALUES (?, ?, ?, ?)",
                    (
                        int(user["employee_id"]),
                        user_id,
                        request_type,
                        json.dumps(details, ensure_ascii=False),
                    ),
                )
                return int(cursor.lastrowid)

    def review_employee_request(
        self, request_id: int, reviewer_id: int, status: str, review_note: str = ""
    ) -> None:
        if status not in ("Approved", "Rejected"):
            raise ValueError("Request status must be Approved or Rejected.")
        with closing(self.connect()) as connection:
            with connection:
                reviewer = connection.execute(
                    "SELECT role FROM users WHERE id = ?", (reviewer_id,)
                ).fetchone()
                if reviewer is None or reviewer["role"] not in ("admin", "hr"):
                    raise ValueError("Only HR and Admin accounts can review requests.")
                request = connection.execute(
                    "SELECT employee_id, request_type, details, status FROM employee_requests "
                    "WHERE request_id = ?",
                    (request_id,),
                ).fetchone()
                if request is None:
                    raise ValueError("Request not found. Refresh the list and try again.")
                if request["status"] != "Pending":
                    raise ValueError("This request has already been reviewed.")

                if status == "Approved" and request["request_type"] in ("Leave", "Travel Order"):
                    details = json.loads(str(request["details"]))
                    leave_type = (
                        details["leave_type"]
                        if request["request_type"] == "Leave"
                        else "Travel order"
                    )
                    start_date = details["start_date"]
                    end_date = details["end_date"]
                    overlap = connection.execute(
                        "SELECT 1 FROM leave_records WHERE employee_id = ? "
                        "AND status != 'Rejected' AND start_date <= ? AND end_date >= ?",
                        (int(request["employee_id"]), end_date, start_date),
                    ).fetchone()
                    if overlap:
                        raise ValueError(
                            "This request overlaps an existing non-rejected leave or travel record."
                        )
                    notes = details.get("reason") or details.get("purpose", "")
                    connection.execute(
                        "INSERT INTO leave_records "
                        "(employee_id, leave_type, start_date, end_date, status, notes) "
                        "VALUES (?, ?, ?, ?, 'Approved', ?)",
                        (
                            int(request["employee_id"]),
                            leave_type,
                            start_date,
                            end_date,
                            notes,
                        ),
                    )

                connection.execute(
                    "UPDATE employee_requests SET status = ?, reviewed_by = ?, "
                    "reviewed_at = CURRENT_TIMESTAMP, review_note = ? "
                    "WHERE request_id = ? AND status = 'Pending'",
                    (status, reviewer_id, review_note.strip() or None, request_id),
                )

    def backup_to(self, destination: str | Path) -> Path:
        """Write a consistent SQLite snapshot to destination."""
        destination_path = Path(destination).expanduser().resolve()
        if destination_path == self.db_path.resolve():
            raise ValueError("Choose a different file from the active database.")
        if not destination_path.parent.is_dir():
            raise FileNotFoundError(
                f"Backup folder does not exist: {destination_path.parent}"
            )

        with closing(self.connect()) as source_connection:
            with closing(sqlite3.connect(destination_path)) as backup_connection:
                source_connection.backup(backup_connection)
        return destination_path

    def restore_from(self, source: str | Path) -> Path:
        """Validate a database snapshot, back up the current DB, and restore it."""
        source_path = Path(source).expanduser().resolve()
        database_path = self.db_path.resolve()
        if source_path == database_path:
            raise ValueError("Choose a backup file, not the active database.")
        if not source_path.is_file():
            raise FileNotFoundError(f"Backup file does not exist: {source_path}")

        self._validate_backup(source_path)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        safety_backup = database_path.with_name(
            f"{database_path.stem}.before-restore-{timestamp}{database_path.suffix}"
        )
        self.backup_to(safety_backup)

        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{database_path.stem}-restore-",
            suffix=database_path.suffix or ".sqlite3",
            dir=database_path.parent,
        )
        os.close(file_descriptor)
        temporary_path = Path(temporary_name)
        try:
            with closing(sqlite3.connect(source_path)) as source_connection:
                with closing(sqlite3.connect(temporary_path)) as restored_connection:
                    source_connection.backup(restored_connection)
            DatabaseManager(temporary_path).initialize()
            self._validate_backup(temporary_path)
            os.replace(temporary_path, database_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return safety_backup

    def delete_database(self) -> None:
        """Permanently remove the active database and any SQLite journal files."""
        database_path = self.db_path.resolve()
        if not database_path.is_file():
            raise FileNotFoundError(f"Active database file does not exist: {database_path}")

        database_path.unlink()
        for suffix in ("-wal", "-shm", "-journal"):
            sidecar_path = database_path.with_name(database_path.name + suffix)
            sidecar_path.unlink(missing_ok=True)

    @staticmethod
    def _validate_backup(path: Path) -> None:
        try:
            with closing(sqlite3.connect(path)) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
                if integrity is None or integrity[0] != "ok":
                    raise ValueError(f"Database integrity check failed: {path}")

                tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                required_tables = {
                    "users",
                    "departments",
                    "employees",
                    "attendance",
                    "deductions",
                    "leave_records",
                    "payroll",
                    "app_settings",
                }
                missing_tables = required_tables - tables
                if missing_tables:
                    raise ValueError(
                        "The selected file is not a payroll database; "
                        f"missing tables: {', '.join(sorted(missing_tables))}."
                    )

                foreign_key_errors = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchone()
                if foreign_key_errors is not None:
                    raise ValueError(
                        "The selected database contains broken employee or record references."
                    )
        except sqlite3.DatabaseError as exc:
            raise ValueError(f"Could not read a valid SQLite backup: {exc}") from exc
