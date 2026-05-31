# =================================================================
# cleaners/employees.py — Employee Data Cleaner
# =================================================================

import pandas as pd


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean employee data.
    Input  → raw DataFrame from Google Sheet
    Output → cleaned DataFrame ready for Supabase
    """

    print("    🧹 Cleaning employee data...")

    def safe_upper(val):
        if val is None or str(val).strip() in ("", "nan", "None"):
            return None
        return str(val).strip().upper()

    def safe_title(val):
        if val is None or str(val).strip() in ("", "nan", "None"):
            return None
        return str(val).strip().title()

    def safe_lower(val):
        if val is None or str(val).strip() in ("", "nan", "None"):
            return None
        return str(val).strip().lower()

    def safe_strip(val):
        if val is None or str(val).strip() in ("", "nan", "None"):
            return None
        return str(val).strip()

    # ── Employee Code → UPPERCASE ──────────────────────────────
    if "employee_code" in df.columns:
        df["employee_code"] = df["employee_code"].apply(safe_upper)

    # ── Full Name → Title Case ─────────────────────────────────
    if "full_name" in df.columns:
        df["full_name"] = df["full_name"].apply(safe_title)

    # ── Gender → Title Case ────────────────────────────────────
    if "gender" in df.columns:
        df["gender"] = df["gender"].apply(safe_title)

    # ── Work Email → Lowercase ─────────────────────────────────
    if "work_email" in df.columns:
        df["work_email"] = df["work_email"].apply(safe_lower)

    # ── Employment Status → Title Case ─────────────────────────
    if "employment_status" in df.columns:
        df["employment_status"] = df["employment_status"].apply(safe_title)

    # ── Department → UPPERCASE ────────────────────────────────
    if "department" in df.columns:
        df["department"] = df["department"].apply(safe_upper)

    # ── Designation → Title Case ──────────────────────────────
    if "designation" in df.columns:
        df["designation"] = df["designation"].apply(safe_title)

    # ── Skill Type → Title Case ───────────────────────────────
    if "skill_type" in df.columns:
        df["skill_type"] = df["skill_type"].apply(safe_title)

    # ── Pay Group → Title Case ────────────────────────────────
    if "pay_group" in df.columns:
        df["pay_group"] = df["pay_group"].apply(safe_title)

    # ── Experience → Strip only ───────────────────────────────
    if "experience" in df.columns:
        df["experience"] = df["experience"].apply(safe_strip)

    print("    ✅ Employee data cleaned successfully")
    return df