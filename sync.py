# =================================================================
# sync.py — Valuepersqft Master Sync Script
# =================================================================
# THIS FILE NEVER NEEDS TO BE EDITED
# To add new tables → edit config.py only
# To change cleaning → edit cleaners/ files only
#
# HOW TO RUN:
#   python sync.py --all                    → sync all tables
#   python sync.py --table employees_data   → sync only employees
#   python sync.py --table booking_data     → sync only bookings
# =================================================================

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import argparse
import importlib
import numpy as np
import pandas as pd
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials
from supabase import create_client, Client
from config import GOOGLE_SHEET_SOURCES, GOOGLE_DRIVE_SOURCES, BATCH_SIZE
from strategies.upsert import sync as upsert_sync

# ─────────────────────────────────────────────────────────────────
# ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────────────────────────

SUPABASE_URL            = os.environ.get("SUPABASE_URL")
SUPABASE_KEY            = os.environ.get("SUPABASE_KEY")
GOOGLE_CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ─────────────────────────────────────────────────────────────────
# CONNECTIONS
# ─────────────────────────────────────────────────────────────────

def get_google_credentials():
    return Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
    )

def connect_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def connect_sheets(creds):
    return gspread.authorize(creds)

# ─────────────────────────────────────────────────────────────────
# DATA CLEANING HELPERS
# ─────────────────────────────────────────────────────────────────

def clean_date(value):
    if value is None:
        return None
    value = str(value).strip()
    if value in ("", "nan", "None", "NaT"):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def clean_numeric(value):
    if value is None:
        return None
    value = str(value).strip()
    if value in ("", "nan", "None"):
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None

def safe_value(value):
    if value is None:
        return None
    value = str(value).strip()
    if value in ("", "nan", "None", "NaT", "NaN"):
        return None
    return value

# ─────────────────────────────────────────────────────────────────
# COLUMN MAPPING
# ─────────────────────────────────────────────────────────────────

def apply_column_mapping(raw_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    column_map   = config["columns"]
    date_cols    = config.get("date_columns", [])
    numeric_cols = config.get("numeric_columns", [])
    mapped       = {}

    for sheet_col, supabase_col in column_map.items():
        if sheet_col not in raw_df.columns:
            print(f"    ⚠️  Column '{sheet_col}' not found — set to NULL")
            mapped[supabase_col] = [None] * len(raw_df)
            continue

        if supabase_col in date_cols:
            mapped[supabase_col] = raw_df[sheet_col].apply(clean_date)
        elif supabase_col in numeric_cols:
            mapped[supabase_col] = raw_df[sheet_col].apply(clean_numeric)
        else:
            mapped[supabase_col] = raw_df[sheet_col].apply(safe_value)

    return pd.DataFrame(mapped, index=raw_df.index)

# ─────────────────────────────────────────────────────────────────
# LOAD CLEANER
# ─────────────────────────────────────────────────────────────────

def load_cleaner(cleaner_name: str):
    if not cleaner_name:
        return None
    try:
        return importlib.import_module(f"cleaners.{cleaner_name}")
    except ModuleNotFoundError:
        print(f"    ⚠️  No cleaner found for '{cleaner_name}' — skipping")
        return None

# ─────────────────────────────────────────────────────────────────
# READ GOOGLE SHEET — HANDLES EMPTY/DUPLICATE HEADERS
# ─────────────────────────────────────────────────────────────────

def read_sheet(sheets_client, sheet_name, sheet_tab=None):
    """
    Read Google Sheet safely.
    Handles empty trailing columns and duplicate headers.
    Supports specific sheet tabs.
    """
    if sheet_tab:
        sheet = sheets_client.open(sheet_name).worksheet(sheet_tab)
    else:
        sheet = sheets_client.open(sheet_name).sheet1
    all_values = sheet.get_all_values()

    if not all_values:
        return []

    headers = all_values[0]

    # Remove empty trailing columns
    while headers and not str(headers[-1]).strip():
        headers = headers[:-1]

    # Make all headers unique
    seen           = {}
    unique_headers = []
    for h in headers:
        h = str(h).strip()
        if h in seen:
            seen[h] += 1
            unique_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            unique_headers.append(h)

    # Build records — skip fully empty rows
    raw_data = []
    for row in all_values[1:]:
        if not any(str(v).strip() for v in row):
            continue
        row = list(row)[:len(unique_headers)]
        while len(row) < len(unique_headers):
            row.append("")
        raw_data.append(dict(zip(unique_headers, row)))

    return raw_data

# ─────────────────────────────────────────────────────────────────
# SYNC GOOGLE SHEET TABLE
# ─────────────────────────────────────────────────────────────────

def sync_sheet_table(config: dict, sheets_client, supabase) -> dict:

    sheet_name   = config["sheet_name"]
    table_name   = config["table_name"]
    primary_key  = config["primary_key"]
    cleaner_name = config.get("cleaner", "")

    sheet_tab = config.get("sheet_tab", None)
    tab_info  = f" → tab: '{sheet_tab}'" if sheet_tab else ""
    print(f"\n  📄 Reading sheet: '{sheet_name}'{tab_info}")
    try:
        raw_data = read_sheet(sheets_client, sheet_name, sheet_tab)
    except Exception as e:
        print(f"  ❌ Could not open sheet: {e}")
        return {"total": 0, "inserted": 0, "altered": 0,
                "unchanged": 0, "soft_deleted": 0, "failed": 1}

    if not raw_data:
        print(f"  ⚠️  Sheet is empty — skipping")
        return {"total": 0, "inserted": 0, "altered": 0,
                "unchanged": 0, "soft_deleted": 0, "failed": 0}

    raw_df = pd.DataFrame(raw_data)
    print(f"  📊 {len(raw_df)} rows found")

    # ── For tables with generated primary keys ─────────────────
    # booking_data: primary key = booking_date + associate_name
    if table_name == "booking_data" and primary_key == "booking_id":
        date_col = config["columns"].get("Booking Date", "")
        name_col = config["columns"].get("Associate name", "")
        if date_col and name_col:
            raw_df["booking_id_temp"] = (
                raw_df.get("Booking Date", pd.Series([""] * len(raw_df)))\
                    .astype(str).str.strip()
                + "_"
                + raw_df.get("Associate name ", pd.Series([""] * len(raw_df)))\
                    .astype(str).str.strip()
            )

    # ── Find primary key sheet column ─────────────────────────
    sheet_pk_col = next(
        (k for k, v in config["columns"].items() if v == primary_key), None
    )

    # ── Map columns ────────────────────────────────────────────
    print(f"  🔄 Mapping {len(config['columns'])} columns...")
    df = apply_column_mapping(raw_df, config)

    # ── Generate booking_id after mapping ──────────────────────
    if table_name == "booking_data" and primary_key == "booking_id":
        df["booking_id"] = (
            df.get("booking_date", pd.Series([""] * len(df))).astype(str).str.strip()
            + "_"
            + df.get("associate_name", pd.Series([""] * len(df))).astype(str).str.strip()
            + "_"
            + df.get("customer_number", pd.Series([""] * len(df))).astype(str).str.strip()
        )
        df["booking_id"] = df["booking_id"].apply(
            lambda x: None if x in ("_", "None_None_None", "") else x
        )
    # ── Drop rows with empty primary key ──────────────────────
    if primary_key in df.columns:
        df = df[df[primary_key].notna()]
        df = df[df[primary_key].astype(str).str.strip() != ""]

    print(f"  ✅ {len(df)} valid rows ready")

    # ── Apply cleaner ──────────────────────────────────────────
    cleaner = load_cleaner(cleaner_name)
    if cleaner:
        try:
            df = cleaner.clean(df, supabase)
        except TypeError:
            df = cleaner.clean(df)

    # ── Remove NaN values before pushing ─────────────────────
    df = df.replace({np.nan: None, float('inf'): None, float('-inf'): None})
    df = df.where(pd.notnull(df), None)

    # ── Upsert + Soft Delete ───────────────────────────────────
    config["batch_size"] = BATCH_SIZE
    result = upsert_sync(df, config, supabase)
    return result

# ─────────────────────────────────────────────────────────────────
# SYNC GOOGLE DRIVE TABLE
# ─────────────────────────────────────────────────────────────────

def sync_drive_table(config: dict, creds, sheets_client, supabase) -> dict:

    table_name   = config["table_name"]
    cleaner_name = config.get("cleaner", "")

    print(f"\n  📂 Processing Drive table: '{table_name}'")

    cleaner = load_cleaner(cleaner_name)
    if not cleaner:
        print(f"  ❌ No cleaner found for '{cleaner_name}'")
        return {"total": 0, "inserted": 0, "altered": 0,
                "unchanged": 0, "soft_deleted": 0, "failed": 1}

    try:
        df = cleaner.clean(pd.DataFrame(), creds, sheets_client, supabase)
    except Exception as e:
        print(f"  ❌ Cleaner failed: {e}")
        import traceback
        traceback.print_exc()
        return {"total": 0, "inserted": 0, "altered": 0,
                "unchanged": 0, "soft_deleted": 0, "failed": 1}

    if df.empty:
        print(f"  ⚠️  No data returned from cleaner")
        return {"total": 0, "inserted": 0, "altered": 0,
                "unchanged": 0, "soft_deleted": 0, "failed": 0}

    print(f"  ✅ {len(df)} rows cleaned and ready")
    config["batch_size"] = BATCH_SIZE
    result = upsert_sync(df, config, supabase)
    return result

# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all",   action="store_true")
    parser.add_argument("--table", type=str)
    args = parser.parse_args()

    if args.all:
        sheet_tables = GOOGLE_SHEET_SOURCES
        drive_tables = GOOGLE_DRIVE_SOURCES
    elif args.table:
        sheet_tables = [c for c in GOOGLE_SHEET_SOURCES if c["table_name"] == args.table]
        drive_tables = [c for c in GOOGLE_DRIVE_SOURCES if c["table_name"] == args.table]
        if not sheet_tables and not drive_tables:
            print(f"❌ Table '{args.table}' not found in config.py")
            sys.exit(1)
    else:
        print("❌ Please use --all or --table <table_name>")
        print("   Example: python sync.py --all")
        print("   Example: python sync.py --table employees_data")
        print("   Example: python sync.py --table booking_data")
        sys.exit(1)

    start_time   = datetime.now()
    total_tables = len(sheet_tables) + len(drive_tables)

    print("\n" + "=" * 60)
    print(f"🚀 VALUEPERSQFT SYNC STARTED")
    print(f"   {start_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"   Tables to sync: {total_tables}")
    print("=" * 60)

    creds         = get_google_credentials()
    supabase      = connect_supabase()
    sheets_client = connect_sheets(creds)
    results       = []

    # ── Sync Google Sheet tables ───────────────────────────────
    for idx, config in enumerate(sheet_tables, start=1):
        print(f"\n{'─' * 60}")
        print(f"📋 TABLE {idx}/{total_tables} — {config['sheet_name']} → {config['table_name']}")
        print(f"{'─' * 60}")
        result          = sync_sheet_table(config, sheets_client, supabase)
        result["table"] = config["table_name"]
        results.append(result)

    # ── Sync Google Drive tables ───────────────────────────────
    for idx, config in enumerate(drive_tables, start=len(sheet_tables) + 1):
        print(f"\n{'─' * 60}")
        print(f"📋 TABLE {idx}/{total_tables} — Drive → {config['table_name']}")
        print(f"{'─' * 60}")
        result          = sync_drive_table(config, creds, sheets_client, supabase)
        result["table"] = config["table_name"]
        results.append(result)

    # ── Final Summary ──────────────────────────────────────────
    end_time = datetime.now()
    duration = round((end_time - start_time).total_seconds())

    print(f"\n{'=' * 60}")
    print("📋 FINAL SUMMARY")
    print(f"{'=' * 60}")
    print(f"  {'TABLE':<25} {'INSERTED':<10} {'ALTERED':<10} {'UNCHANGED':<10} {'DELETED':<10} {'FAILED':<10}")
    print(f"  {'─'*25} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")

    for r in results:
        status = "✅" if r.get("failed", 0) == 0 else "❌"
        print(
            f"  {status} {r['table']:<23} "
            f"{r.get('inserted', 0):<10} "
            f"{r.get('altered', 0):<10} "
            f"{r.get('unchanged', 0):<10} "
            f"{r.get('soft_deleted', 0):<10} "
            f"{r.get('failed', 0):<10}"
        )

    print(f"{'─' * 60}")
    print(f"  Total inserted  : {sum(r.get('inserted', 0) for r in results)}")
    print(f"  Total altered   : {sum(r.get('altered', 0) for r in results)}")
    print(f"  Total unchanged : {sum(r.get('unchanged', 0) for r in results)}")
    print(f"  Total deleted   : {sum(r.get('soft_deleted', 0) for r in results)}")
    print(f"  Total failed    : {sum(r.get('failed', 0) for r in results)}")
    print(f"  Time taken      : {duration} seconds")
    print(f"  Completed at    : {end_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'=' * 60}\n")

    if any(r.get("failed", 0) > 0 for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()