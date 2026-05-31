# =================================================================
# cleaners/associate_sv.py — Associate SV Data Cleaner
# =================================================================
# Reads from Google Sheet "Associate_SV_Data" → "Associate_sv" tab
# Simple cleaning + employee code lookup
# Primary key = month + week + associate
# (No row_number — delete works correctly)
# =================================================================

import pandas as pd
import numpy as np
from thefuzz import process as fuzz_process


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────

FUZZY_THRESHOLD = 80


# ─────────────────────────────────────────────────────────────────
# EMPLOYEE LOOKUP FROM SUPABASE
# ─────────────────────────────────────────────────────────────────

def get_employee_lookup(supabase):
    try:
        response = supabase.table("employees_data")\
            .select("employee_code, full_name")\
            .execute()
        lookup = {
            str(row["full_name"]).strip().title(): row["employee_code"]
            for row in response.data
            if row.get("full_name") and row.get("employee_code")
        }
        print(f"    ✅ Loaded {len(lookup)} employees for lookup")
        return lookup
    except Exception as e:
        print(f"    ⚠️  Could not load employee lookup: {e}")
        return {}


def fuzzy_match_code(name, lookup, threshold=FUZZY_THRESHOLD):
    if not name or not lookup or str(name).strip() in ("", "nan", "None"):
        return None
    name = str(name).strip().title()
    if name in lookup:
        return lookup[name]
    result = fuzz_process.extractOne(name, lookup.keys())
    if result and result[1] >= threshold:
        print(f"    🔍 Fuzzy: '{name}' → '{result[0]}' ({result[1]}%)")
        return lookup[result[0]]
    print(f"    ⚠️  No match for '{name}'")
    return None


# ─────────────────────────────────────────────────────────────────
# SAFE VALUE HELPERS
# ─────────────────────────────────────────────────────────────────

def safe_str(val):
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    s = str(val).strip()
    if s in ("", "nan", "None", "NaT", "NaN"):
        return None
    return s


def safe_num(val):
    if val is None:
        return None
    try:
        f = float(str(val).replace(",", ""))
        return None if np.isnan(f) else f
    except (ValueError, TypeError):
        return None


def safe_date(val):
    if val is None:
        return None
    try:
        d = pd.to_datetime(val, errors='coerce', dayfirst=True, format='mixed')
        if pd.isna(d):
            return None
        return d.strftime('%Y-%m-%d')
    except Exception:
        return None


def remove_all_nan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace({np.nan: None, float('inf'): None, float('-inf'): None})
    df = df.where(pd.notnull(df), None)
    return df


# ─────────────────────────────────────────────────────────────────
# MAIN CLEAN FUNCTION
# ─────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame, supabase=None) -> pd.DataFrame:

    print("    🧹 Cleaning associate SV data...")

    # ── STEP 1: Reset index ───────────────────────────────────
    df = df.reset_index(drop=True)

    # ── STEP 2: Basic text cleaning ───────────────────────────
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "": None})

    # ── STEP 3: Title case text columns ──────────────────────
    title_cols = ["agm", "team_leader", "associate", "month", "week"]
    for col in title_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: str(x).strip().title()
                if x and str(x).strip() not in ("", "nan", "None")
                else None
            )

    # ── STEP 4: Date column ───────────────────────────────────
    if "date" in df.columns:
        df["date"] = df["date"].apply(safe_date)

    # ── STEP 5: Numeric columns ───────────────────────────────
    if "visit_count" in df.columns:
        df["visit_count"] = df["visit_count"].apply(safe_num)

    # ── STEP 6: Employee code lookup ──────────────────────────
    print("    🔍 Looking up associate codes...")
    lookup = get_employee_lookup(supabase) if supabase else {}
    if lookup:
        df["associate_code"] = df["associate"].apply(
            lambda x: fuzzy_match_code(x, lookup)
        )
    else:
        df["associate_code"] = None
    print("    ✅ Associate code lookup complete")

    # ── STEP 7: String columns ────────────────────────────────
    str_cols = [c for c in df.columns
                if c not in ["visit_count", "sv_id", "date"]]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_str)

    # ── STEP 8: Create sv_id ──────────────────────────────────
    # No row_number — stable ID enables correct soft delete
    df["sv_id"] = (
        df["month"].astype(str).str.strip()
        + "_"
        + df["week"].astype(str).str.strip()
        + "_"
        + df["associate"].astype(str).str.strip()
    )

    df["sv_id"] = df["sv_id"].apply(
        lambda x: None if str(x).strip() in (
            "_", "__", "___", "None_None_None", ""
        ) else x
    )

    # ── STEP 9: Drop rows with no sv_id ──────────────────────
    df = df[df["sv_id"].notna()]
    print(f"    ✅ Total rows ready: {len(df)}")

    # ── STEP 10: Final NaN removal ────────────────────────────
    df = remove_all_nan(df)

    print("    ✅ Associate SV data cleaned successfully")
    return df