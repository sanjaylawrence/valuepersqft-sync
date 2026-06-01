# =================================================================
# cleaners/team_structure.py — Team Structure Cleaner
# =================================================================
# Primary key = month + tl_name + associate_name
# Delete works correctly — stable ID
# =================================================================

import pandas as pd
import numpy as np


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


def safe_num(val):
    if val is None:
        return None
    try:
        f = float(str(val).replace(",", ""))
        return None if np.isnan(f) else f
    except (ValueError, TypeError):
        return None


def remove_all_nan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace({np.nan: None, float('inf'): None, float('-inf'): None})
    df = df.where(pd.notnull(df), None)
    return df


def clean(df: pd.DataFrame, supabase=None) -> pd.DataFrame:

    print("    🧹 Cleaning team structure data...")

    # ── STEP 1: Reset index ───────────────────────────────────
    df = df.reset_index(drop=True)

    # ── STEP 2: Basic text cleaning ───────────────────────────
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "": None})

    # ── STEP 3: Title case text columns ──────────────────────
    title_cols = ["gm", "agm", "tl_name", "associate_name",
                  "project_tagged", "project_tagged_2",
                  "project_tagged_3", "status"]
    for col in title_cols:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: str(x).strip().title()
                if x and str(x).strip() not in ("", "nan", "None")
                else None
            )

    # ── STEP 4: Date columns ──────────────────────────────────
    for col in ["doj", "dol"]:
        if col in df.columns:
            df[col] = df[col].apply(safe_date)

    # ── STEP 5: Numeric columns ──────────────────────────────
    for col in ["revenue_target", "sales_target"]:
        if col in df.columns:
            df[col] = df[col].apply(safe_num)

    # ── STEP 6: String columns ────────────────────────────────
    str_cols = [c for c in df.columns
                if c not in ["doj", "dol", "team_id",
                              "revenue_target", "sales_target"]]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].apply(safe_str)

    # ── STEP 7: Create team_id ────────────────────────────────
    # Stable ID: month + tl_name + associate_name
    # No row_number — delete works correctly
    df["team_id"] = (
        df["month"].astype(str).str.strip()
        + "_"
        + df["tl_name"].astype(str).str.strip()
        + "_"
        + df["associate_name"].astype(str).str.strip()
    )

    df["team_id"] = df["team_id"].apply(
        lambda x: None if str(x).strip() in (
            "_", "__", "___", "None_None_None", ""
        ) else x
    )

    # ── STEP 8: Drop rows with no team_id ─────────────────────
    df = df[df["team_id"].notna()]
    print(f"    ✅ Total rows ready: {len(df)}")

    # ── STEP 9: Final NaN removal ─────────────────────────────
    df = remove_all_nan(df)

    print("    ✅ Team structure cleaned successfully")
    return df