# =============================================================
# sync.py — Valuepersqft Master Sync Script
# =============================================================
# THIS FILE NEVER NEEDS TO BE EDITED
# To add new tables → edit config.py only
# =============================================================

import gspread
import openpyxl
import io
import os
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from supabase import create_client, Client
from config import GOOGLE_SHEET_SOURCES, GOOGLE_DRIVE_SOURCES

# ─────────────────────────────────────────────
# ENVIRONMENT VARIABLES (from GitHub Secrets)
# ─────────────────────────────────────────────

SUPABASE_URL            = os.environ.get("SUPABASE_URL")
SUPABASE_KEY            = os.environ.get("SUPABASE_KEY")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ─────────────────────────────────────────────
# CONNECTION HELPERS
# ─────────────────────────────────────────────

def get_google_credentials():
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

def connect_to_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def connect_to_sheets(creds):
    return gspread.authorize(creds)

def connect_to_drive(creds):
    return build("drive", "v3", credentials=creds)

# ─────────────────────────────────────────────
# DATA CLEANING HELPERS
# ─────────────────────────────────────────────

def clean_date(value):
    """Convert DD/MM/YYYY → YYYY-MM-DD. Returns None if empty or invalid."""
    if not value or str(value).strip() == "":
        return None
    value = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None  # Invalid date → NULL

def clean_numeric(value):
    """Strip commas and convert to float. Returns None if empty."""
    if not value or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None  # Invalid number → NULL

def clean_text(value):
    """Strip whitespace. Returns None if empty."""
    if not value or str(value).strip() == "":
        return None
    return str(value).strip()

def clean_value(value, supabase_col, date_columns, numeric_columns):
    """Clean a value based on its column type."""
    if supabase_col in date_columns:
        return clean_date(value)
    elif supabase_col in numeric_columns:
        return clean_numeric(value)
    else:
        return clean_text(value)

# ─────────────────────────────────────────────
# MAP A ROW USING CONFIG COLUMNS
# ─────────────────────────────────────────────

def map_row(raw_row, column_map, date_columns, numeric_columns, missing_cols, sheet_headers):
    """Map a raw sheet/excel row to a Supabase row using config column mapping."""
    mapped = {}
    for sheet_col, supabase_col in column_map.items():

        # Check if column exists in the source
        if sheet_col not in sheet_headers:
            if sheet_col not in missing_cols:
                missing_cols.add(sheet_col)  # Track once, warn once
            mapped[supabase_col] = None
            continue

        raw_value = raw_row.get(sheet_col, "")
        mapped[supabase_col] = clean_value(raw_value, supabase_col, date_columns, numeric_columns)

    return mapped

# ─────────────────────────────────────────────
# SYNC ONE GOOGLE SHEET TABLE
# ─────────────────────────────────────────────

def sync_sheet_table(config, sheets_client, supabase):
    sheet_name   = config["sheet_name"]
    table_name   = config["table_name"]
    primary_key  = config["primary_key"]
    column_map   = config["columns"]
    date_cols    = config.get("date_columns", [])
    numeric_cols = config.get("numeric_columns", [])

    print(f"\n  📄 Connecting to sheet: '{sheet_name}'")

    try:
        sheet = sheets_client.open(sheet_name).sheet1
    except Exception as e:
        print(f"  ❌ Could not open sheet '{sheet_name}': {e}")
        return 0, 0, 1

    all_rows = sheet.get_all_records()
    if not all_rows:
        print(f"  ⚠️  Sheet '{sheet_name}' is empty — skipping")
        return 0, 0, 0

    sheet_headers = list(all_rows[0].keys()) if all_rows else []
    missing_cols  = set()
    success = 0
    warnings = 0
    failed = 0

    for i, row in enumerate(all_rows, start=2):
        primary_value = clean_text(row.get(
            next((k for k, v in column_map.items() if v == primary_key), ""), ""
        ))

        if not primary_value:
            print(f"  ⚠️  Row {i} — Skipped (no primary key value)")
            warnings += 1
            continue

        try:
            mapped = map_row(row, column_map, date_cols, numeric_cols, missing_cols, sheet_headers)
            supabase.table(table_name).upsert(mapped, on_conflict=primary_key).execute()
            full_name = mapped.get("full_name") or mapped.get(primary_key, "")
            print(f"  ✅ Row {i} — {primary_value} | {full_name} — Synced")
            success += 1
        except Exception as e:
            print(f"  ❌ Row {i} — {primary_value} — FAILED: {e}")
            failed += 1

    # Warn about missing columns once
    for col in missing_cols:
        print(f"  ⚠️  WARNING: Column '{col}' not found in sheet '{sheet_name}' — set to NULL")
        warnings += 1

    return success, warnings, failed

# ─────────────────────────────────────────────
# SYNC ONE GOOGLE DRIVE EXCEL TABLE
# ─────────────────────────────────────────────

def get_latest_excel_from_folder(drive_service, folder_name):
    """Find the most recently uploaded Excel file in a Drive folder."""

    # Find folder ID
    folder_query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    folders = drive_service.files().list(q=folder_query, fields="files(id, name)").execute()

    if not folders["files"]:
        print(f"  ❌ Folder '{folder_name}' not found in Google Drive")
        return None

    folder_id = folders["files"][0]["id"]

    # Get latest Excel file from folder
    file_query = (
        f"'{folder_id}' in parents and trashed=false and "
        f"mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"
    )
    files = drive_service.files().list(
        q=file_query,
        orderBy="modifiedTime desc",
        fields="files(id, name, modifiedTime)",
        pageSize=1
    ).execute()

    if not files["files"]:
        print(f"  ⚠️  No Excel files found in folder '{folder_name}' — skipping")
        return None

    latest_file = files["files"][0]
    print(f"  📂 Latest file: '{latest_file['name']}' (modified: {latest_file['modifiedTime'][:10]})")
    return latest_file["id"]

def read_excel_from_drive(drive_service, file_id):
    """Download and read Excel file from Drive into memory."""
    request = drive_service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buffer.seek(0)
    wb = openpyxl.load_workbook(buffer, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [str(h).strip() if h else "" for h in rows[0]]
    result = []
    for row in rows[1:]:
        result.append({headers[i]: (row[i] if row[i] is not None else "") for i in range(len(headers))})
    return result

def sync_drive_table(config, drive_service, supabase):
    folder_name  = config["folder_name"]
    table_name   = config["table_name"]
    primary_key  = config["primary_key"]
    column_map   = config["columns"]
    date_cols    = config.get("date_columns", [])
    numeric_cols = config.get("numeric_columns", [])

    print(f"\n  📂 Scanning Drive folder: '{folder_name}'")

    file_id = get_latest_excel_from_folder(drive_service, folder_name)
    if not file_id:
        return 0, 0, 1

    try:
        all_rows = read_excel_from_drive(drive_service, file_id)
    except Exception as e:
        print(f"  ❌ Could not read Excel file: {e}")
        return 0, 0, 1

    if not all_rows:
        print(f"  ⚠️  Excel file is empty — skipping")
        return 0, 0, 0

    sheet_headers = list(all_rows[0].keys()) if all_rows else []
    missing_cols  = set()
    success = 0
    warnings = 0
    failed = 0

    for i, row in enumerate(all_rows, start=2):
        primary_value = clean_text(str(row.get(
            next((k for k, v in column_map.items() if v == primary_key), ""), ""
        )))

        if not primary_value:
            print(f"  ⚠️  Row {i} — Skipped (no primary key value)")
            warnings += 1
            continue

        try:
            mapped = map_row(row, column_map, date_cols, numeric_cols, missing_cols, sheet_headers)
            supabase.table(table_name).upsert(mapped, on_conflict=primary_key).execute()
            print(f"  ✅ Row {i} — {primary_value} — Synced")
            success += 1
        except Exception as e:
            print(f"  ❌ Row {i} — {primary_value} — FAILED: {e}")
            failed += 1

    for col in missing_cols:
        print(f"  ⚠️  WARNING: Column '{col}' not found in Excel file — set to NULL")
        warnings += 1

    return success, warnings, failed

# ─────────────────────────────────────────────
# MAIN — RUNS ALL TABLES
# ─────────────────────────────────────────────

def main():
    start_time = datetime.now()

    print("\n" + "="*60)
    print(f"🚀 VALUEPERSQFT SYNC STARTED — {start_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print("="*60)

    # Connect once — reuse for all tables
    creds        = get_google_credentials()
    supabase     = connect_to_supabase()
    sheets_client = connect_to_sheets(creds)

    # Only connect to Drive if there are Drive sources configured
    drive_service = connect_to_drive(creds) if GOOGLE_DRIVE_SOURCES else None

    total_tables  = len(GOOGLE_SHEET_SOURCES) + len(GOOGLE_DRIVE_SOURCES)
    results       = []

    # ── SYNC GOOGLE SHEET TABLES ─────────────────────────────
    for idx, config in enumerate(GOOGLE_SHEET_SOURCES, start=1):
        print(f"\n{'─'*60}")
        print(f"📋 TABLE {idx}/{total_tables} — {config['sheet_name']} → {config['table_name']}")
        print(f"{'─'*60}")

        success, warnings, failed = sync_sheet_table(config, sheets_client, supabase)
        results.append({
            "table"    : config["table_name"],
            "source"   : config["sheet_name"],
            "success"  : success,
            "warnings" : warnings,
            "failed"   : failed,
        })

    # ── SYNC GOOGLE DRIVE / EXCEL TABLES ─────────────────────
    for idx, config in enumerate(GOOGLE_DRIVE_SOURCES, start=len(GOOGLE_SHEET_SOURCES) + 1):
        print(f"\n{'─'*60}")
        print(f"📋 TABLE {idx}/{total_tables} — {config['folder_name']} → {config['table_name']}")
        print(f"{'─'*60}")

        success, warnings, failed = sync_drive_table(config, drive_service, supabase)
        results.append({
            "table"    : config["table_name"],
            "source"   : config["folder_name"],
            "success"  : success,
            "warnings" : warnings,
            "failed"   : failed,
        })

    # ── FINAL SUMMARY ─────────────────────────────────────────
    end_time  = datetime.now()
    duration  = (end_time - start_time).seconds

    print(f"\n{'='*60}")
    print("📋 FINAL SUMMARY")
    print(f"{'='*60}")

    for r in results:
        status = "✅" if r["failed"] == 0 else "❌"
        print(
            f"  {status} {r['table']:<25} "
            f"Synced: {r['success']:<5} "
            f"Warnings: {r['warnings']:<5} "
            f"Failed: {r['failed']}"
        )

    total_success  = sum(r["success"] for r in results)
    total_warnings = sum(r["warnings"] for r in results)
    total_failed   = sum(r["failed"] for r in results)

    print(f"{'─'*60}")
    print(f"  Total rows synced  : {total_success}")
    print(f"  Total warnings     : {total_warnings}")
    print(f"  Total failed       : {total_failed}")
    print(f"  Time taken         : {duration} seconds")
    print(f"  Completed at       : {end_time.strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*60}\n")

    # Exit with error code if any failures (so GitHub Actions marks run as failed)
    if total_failed > 0:
        exit(1)


if __name__ == "__main__":
    main()
