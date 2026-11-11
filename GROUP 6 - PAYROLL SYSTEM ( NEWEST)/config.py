from __future__ import annotations

from pathlib import Path
from typing import Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent
DATABASE_DIR: Final[Path] = BASE_DIR / "database"
DATABASE_PATH: Final[Path] = DATABASE_DIR / "payroll.db"
ASSETS_DIR: Final[Path] = BASE_DIR / "assets"

APP_NAME: Final[str] = "LSPU PAYROLL SYSTEM"
APP_VERSION: Final[str] = "2.0.0"
UNIVERSITY_NAME: Final[str] = "LSPU"
UNIVERSITY_TAGLINE: Final[str] = "Human Resource & Payroll Control Center"

# ── LSPU Brand Palette ───────────────────────────────────────────────────────
# Primary navy (seal ring, sidebar)
PRIMARY_COLOR: Final[str] = "#123366"
# Bright sky-blue (wave accent, buttons)
ACCENT_BLUE: Final[str] = "#2176C7"
# Light sky used on header/cards
LIGHT_BLUE: Final[str] = "#D6EAF8"
# Gold / yellow used on seal and highlights
GOLD_COLOR: Final[str] = "#D4A017"
GOLD_LIGHT: Final[str] = "#F5D98B"
# Sidebar gradient end
SIDEBAR_END: Final[str] = "#1A3A6B"

# Neutrals
BACKGROUND_COLOR: Final[str] = "#F2F6FC"
SECONDARY_COLOR: Final[str] = "#F8FAFC"
TEXT_COLOR: Final[str] = "#18365E"
MUTED_COLOR: Final[str] = "#65758B"
BORDER_COLOR: Final[str] = "#D9E3F0"
WHITE: Final[str] = "#FFFFFF"

# Semantic
SUCCESS_COLOR: Final[str] = "#16865D"
WARNING_COLOR: Final[str] = "#D4A017"
DANGER_COLOR: Final[str] = "#dc2626"

# ── Typography ────────────────────────────────────────────────────────────────
DEFAULT_FONT: Final[tuple] = ("Segoe UI", 11)
SMALL_FONT: Final[tuple] = ("Segoe UI", 10)
TITLE_FONT: Final[tuple] = ("Segoe UI", 30, "bold")
HEADING_FONT: Final[tuple] = ("Segoe UI", 18, "bold")
SUBHEADING_FONT: Final[tuple] = ("Segoe UI", 11, "bold")
LARGE_NUM_FONT: Final[tuple] = ("Segoe UI", 34, "bold")
SIDEBAR_TITLE_FONT: Final[tuple] = ("Segoe UI", 14, "bold")
SIDEBAR_SUB_FONT: Final[tuple] = ("Segoe UI", 9)


def ensure_directories() -> None:
    """Create the directories required by the application."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
