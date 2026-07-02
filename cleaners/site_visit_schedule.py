# =================================================================
# cleaners/site_visit_schedule.py — Site Visit Schedule Cleaner
# =================================================================
# Reads from Google Sheet "Site Visit Form — Valuepersqft (Responses)"
# Tab: "Form Responses 1"
# Primary key = timestamp + associate (sv_schedule_key)
# Derives month_name and month_year from Today's Date
# =================================================================

import pandas as pd
import numpy as np


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

    print("    🧹 Cleaning site visit schedule data...")

    # ── STEP 1: Reset index ───────────────────────────────────
    df = df.reset_index(drop=True)

    # ── STEP 2: Strip whitespace from column headers ──────────
    df.columns = df.columns.str.strip()

    # ── STEP 3: Basic text cleaning ───────────────────────────
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "": None})

    # ── STEP 4: Rename columns to match Supabase ─────────────
    rename_map = {
        "Timestamp"          : "timestamp",
        "Today's Date"       : "today_date",
        "Associate"          : "associate",
        "Team Leader"        : "team_leader",
        "AGM"                : "agm",
        "Site Visit Date"    : "site_visit_date",
        "Client Name"        : "client_name",
        "Client Number"      : "client_number",
        "Site Visit Slot"    : "site_visit_slot",
        "Client Status"      : "client_status",
        "Type of Site Visit" : "type_of_site_visit",
        "Project Name"       : "project_name",
        "Lead/Data"          : "lead_data",
    }
    df = df.rename(columns=rename_map)

    # ── STEP 5: Keep only known columns ──────────────────────
    known_cols = [c for c in rename_map.values() if c in df.columns]
    df = df[known_cols]

    # ── STEP 6: Parse Today's Date → derive month columns ─────
    if "today_date" in df.columns:
        parsed_date = pd.to_datetime(
            df["today_date"], errors='coerce', dayfirst=True, format='mixed'
        )
        # month_name → June, May, April
        df["month_name"] = parsed_date.dt.strftime('%B')
        # month_year → June-2026, May-2026
        df["month_year"] = parsed_date.dt.strftime('%B-%Y')
        # Clean today_date to YYYY-MM-DD
        df["today_date"] = parsed_date.dt.strftime('%Y-%m-%d')

    # ── STEP 7: Clean site_visit_date ─────────────────────────
    if "site_visit_date" in df.columns:
        df["site_visit_date"] = pd.to_datetime(
            df["site_visit_date"], errors='coerce', dayfirst=True, format='mixed'
        ).dt.strftime('%Y-%m-%d')

    # ── STEP 8: Title case text columns ──────────────────────
    title_cols = ["associate", "team_leader", "agm", "client_name",
                  "site_visit_slot", "client_status", "type_of_site_visit",
                  "project_name", "lead_data"]
    for col in title_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: str(x).strip().title()
                if x and str(x).strip() not in ("", "nan", "None")
                else None
            )

    # ── STEP 9: String cleanup ────────────────────────────────
    str_cols = [c for c in df.columns if c not in ["sv_schedule_key"]]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_str)

    # ── STEP 10: Build composite primary key ──────────────────
    df["sv_schedule_key"] = (
        df["timestamp"].astype(str).str.strip() + "_" +
        df["associate"].astype(str).str.strip()
    )

    df["sv_schedule_key"] = df["sv_schedule_key"].apply(
        lambda x: None if str(x).strip() in (
            "_", "None_None", ""
        ) else x
    )

    # ── STEP 11: Drop rows with no sv_schedule_key ────────────
    df = df[df["sv_schedule_key"].notna()]
    print(f"    ✅ Total rows ready: {len(df)}")

    # ── STEP 12: Final NaN removal ────────────────────────────
    df = remove_all_nan(df)

    print("    ✅ Site visit schedule data cleaned successfully")
    return df