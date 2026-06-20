# =================================================================
# cleaners/marketing_campaign_expenses.py — Marketing Campaign Expenses Cleaner
# =================================================================
# Reads from Google Sheet "Marketing Campaign Expences (DB)"
# Tab: "Marketing_expences"
# Primary key = month + campaigns + platform + cpl (campaign_key)
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


def safe_num(val):
    if val is None:
        return None
    try:
        f = float(str(val).replace(",", "").replace("₹", "").strip())
        return None if np.isnan(f) else f
    except (ValueError, TypeError):
        return None


def safe_int(val):
    if val is None:
        return None
    try:
        f = float(str(val).replace(",", "").strip())
        return None if np.isnan(f) else int(f)
    except (ValueError, TypeError):
        return None


def remove_all_nan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace({np.nan: None, float('inf'): None, float('-inf'): None})
    df = df.where(pd.notnull(df), None)
    return df


# ─────────────────────────────────────────────────────────────────
# MAIN CLEAN FUNCTION
# ─────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame, supabase=None) -> pd.DataFrame:

    print("    🧹 Cleaning marketing campaign expenses data...")

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
        "Month"     : "month",
        "Campaigns" : "campaigns",
        "Platform"  : "platform",
        "Budget"    : "budget",
        "Spend"     : "spend",
        "Leads"     : "leads",
        "CPL"       : "cpl",
    }
    df = df.rename(columns=rename_map)

    # ── STEP 5: Keep only known columns ──────────────────────
    known_cols = [c for c in rename_map.values() if c in df.columns]
    df = df[known_cols]

    # ── STEP 6: Title case text columns ──────────────────────
    title_cols = ["month", "campaigns", "platform"]
    for col in title_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: str(x).strip().title()
                if x and str(x).strip() not in ("", "nan", "None")
                else None
            )

    # ── STEP 7: Numeric columns ───────────────────────────────
    for col in ["budget", "spend", "cpl"]:
        if col in df.columns:
            df[col] = df[col].apply(safe_num)

    # ── STEP 8: Integer column ────────────────────────────────
    if "leads" in df.columns:
        df["leads"] = df["leads"].apply(safe_int)

    # ── STEP 9: String columns ────────────────────────────────
    str_cols = [c for c in df.columns
                if c not in ["budget", "spend", "cpl", "leads", "campaign_key"]]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_str)

    # ── STEP 10: Build composite primary key ──────────────────
    df["campaign_key"] = (
        df["month"].astype(str).str.strip() + "_" +
        df["campaigns"].astype(str).str.strip() + "_" +
        df["platform"].astype(str).str.strip() + "_" +
        df["cpl"].astype(str).str.strip()
    )

    df["campaign_key"] = df["campaign_key"].apply(
        lambda x: None if str(x).strip() in (
            "_", "__", "___", "None_None_None_None", ""
        ) else x
    )

    # ── STEP 11: Drop rows with no campaign_key ───────────────
    df = df[df["campaign_key"].notna()]
    print(f"    ✅ Total rows ready: {len(df)}")

    # ── STEP 12: Final NaN removal ────────────────────────────
    df = remove_all_nan(df)

    print("    ✅ Marketing campaign expenses cleaned successfully")
    return df