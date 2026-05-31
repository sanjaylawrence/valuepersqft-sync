# =================================================================
# cleaners/booking.py — Booking Data Cleaner
# =================================================================
# Reads from Google Sheet "Booking_data_DB"
# Simple cleaning + fuzzy name matching for employee codes
# Primary key = booking_date + associate_name + row_number
# ALL rows from sheet go to Supabase
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
        print(f"    ✅ Loaded {len(lookup)} employees for fuzzy matching")
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
    print(f"    ⚠️  No match found for '{name}' (below {threshold}% threshold)")
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

    print("    🧹 Cleaning booking data...")

    # ── STEP 1: Reset index to get clean row numbers ──────────
    df = df.reset_index(drop=True)

    # ── STEP 2: Basic text cleaning ───────────────────────────
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "": None})

    # ── STEP 3: Title case text columns ──────────────────────
    text_cols = [
        "associate_name", "team_leader", "agm",
        "customer_name", "booking_project", "lead_project",
        "lead_source", "status", "booking_month", "lead_month"
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: str(x).strip().title()
                if x and str(x).strip() not in ("", "nan", "None")
                else None
            )

    # ── STEP 4: Load employee lookup ──────────────────────────
    lookup = get_employee_lookup(supabase) if supabase else {}

    # ── STEP 5: Fuzzy match employee codes ────────────────────
    print("    🔍 Matching associate codes...")
    if lookup:
        df["associate_code"] = df["associate_name"].apply(
            lambda x: fuzzy_match_code(x, lookup)
        )
        df["tl_code"] = df["team_leader"].apply(
            lambda x: fuzzy_match_code(x, lookup)
        )
        df["agm_code"] = df["agm"].apply(
            lambda x: fuzzy_match_code(x, lookup)
        )
    else:
        df["associate_code"] = None
        df["tl_code"]        = None
        df["agm_code"]       = None

    print("    ✅ Employee code matching complete")

    # ── STEP 6: Apply date conversion ─────────────────────────
    date_cols = ["booking_date", "lead_date"]
    for col in date_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_date)

    # ── STEP 7: Apply numeric conversion ─────────────────────
    num_cols = [
        "agreement_value", "rtc", "rtc_management", "rtc_organisation",
        "outflow", "sales_done", "revenue", "revenue_management",
        "revenue_organisation"
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_num)

    # ── STEP 8: Apply string conversion to rest ───────────────
    str_cols = [
        c for c in df.columns
        if c not in date_cols + num_cols + ["booking_id"]
    ]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_str)

    # ── STEP 9: Create booking_id ─────────────────────────────
    # booking_id = booking_date + associate_name + row_number
    # Row number ensures ALL rows are unique
    # ALL 598 rows will go to Supabase
    df["booking_id"] = (
        df["booking_date"].astype(str).str.strip()
        + "_"
        + df["associate_name"].astype(str).str.strip()
        + "_"
        + df.index.astype(str)
    )

    # Clean bad booking_ids
    df["booking_id"] = df["booking_id"].apply(
        lambda x: None if str(x).strip() in ("_", "None_None_0", "__", "") else x
    )

    # ── STEP 10: Drop rows with no booking_id ─────────────────
    df = df[df["booking_id"].notna()]
    print(f"    ✅ Total rows ready for Supabase: {len(df)}")

    # ── STEP 11: Final NaN removal ────────────────────────────
    df = remove_all_nan(df)

    print("    ✅ Booking data cleaned successfully")
    return df