# =================================================================
# cleaners/financial_incentives.py — Financial Incentives Cleaner
# =================================================================
# Reads from Google Sheet "Finance Incentives" → "Incentive" tab
# Primary key = month + name (incentive_key)
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


def remove_all_nan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace({np.nan: None, float('inf'): None, float('-inf'): None})
    df = df.where(pd.notnull(df), None)
    return df


# ─────────────────────────────────────────────────────────────────
# MAIN CLEAN FUNCTION
# ─────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame, supabase=None) -> pd.DataFrame:

    print("    🧹 Cleaning financial incentives data...")

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
        "Month"                             : "month",
        "Name"                              : "name",
        "Position"                          : "position",
        "Total Incentives Eligible"         : "total_incentives_eligible",
        "Incentives Paid"                   : "incentives_paid",
        "Incentives Payable"                : "incentives_payable",
        "Builder Payment Received"          : "builder_payment_received",
        "Builder Payment Pending"           : "builder_payment_pending",
        "Advance PSTC Payable for this month" : "advance_pstc_payable",
        "Month - Year"                      : "month_year",
    }
    df = df.rename(columns=rename_map)

    # ── STEP 5: Keep only known columns ──────────────────────
    known_cols = [c for c in rename_map.values() if c in df.columns]
    df = df[known_cols]

    # ── STEP 6: Title case text columns ──────────────────────
    for col in ["month", "name", "position"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: str(x).strip().title()
                if x and str(x).strip() not in ("", "nan", "None")
                else None
            )

    # ── STEP 7: Numeric columns ───────────────────────────────
    numeric_cols = [
        "total_incentives_eligible",
        "incentives_paid",
        "incentives_payable",
        "builder_payment_received",
        "builder_payment_pending",
        "advance_pstc_payable",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_num)

    # ── STEP 8: String columns ────────────────────────────────
    str_cols = [c for c in df.columns
                if c not in numeric_cols + ["incentive_key"]]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_str)

    # ── STEP 9: Build composite primary key ──────────────────
    df["incentive_key"] = (
        df["month"].astype(str).str.strip() + "_" +
        df["name"].astype(str).str.strip()
    )

    df["incentive_key"] = df["incentive_key"].apply(
        lambda x: None if str(x).strip() in (
            "_", "None_None", ""
        ) else x
    )

    # ── STEP 10: Drop rows with no incentive_key ──────────────
    df = df[df["incentive_key"].notna()]
    print(f"    ✅ Total rows ready: {len(df)}")

    # ── STEP 11: Final NaN removal ────────────────────────────
    df = remove_all_nan(df)

    print("    ✅ Financial incentives data cleaned successfully")
    return df
