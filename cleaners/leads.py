# =================================================================
# cleaners/leads.py — Leads Data Cleaner
# =================================================================

import pandas as pd
import numpy as np
import re
import io
from datetime import time as dtime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────

PARENT_FOLDER_NAME = "Valuepersqft_DB"
LEADS_FOLDER_NAME  = "LEADS RAW DATA"
MAPPING_SHEET_NAME = "project mapping"

REQUIRED_COLUMNS = [
    'Received On', 'Name', 'Contact No', 'Lead Source', 'Sub Source',
    'Status', 'Reason', 'Assigned User Name', 'Assigned User Email',
    'Assigned User Phone Number', 'Projects', 'Serial Numbers',
    'Last Modified On', 'Original User', 'Picked Date',
    'Meetings Done Count', 'Meetings Not Done Count',
    'Site Visits Done Count', 'Site Visits Not Done Count', 'Tags'
]


# ─────────────────────────────────────────────────────────────────
# GOOGLE DRIVE HELPERS
# ─────────────────────────────────────────────────────────────────

def get_folder_id(drive_service, folder_name, parent_id=None):
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    result = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files  = result.get("files", [])
    if not files:
        raise Exception(f"Folder '{folder_name}' not found in Google Drive")
    return files[0]["id"]


def get_excel_files_in_folder(drive_service, folder_id):
    query  = (
        f"'{folder_id}' in parents and trashed=false and "
        f"mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"
    )
    result = drive_service.files().list(
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc"
    ).execute()
    return result.get("files", [])


def download_excel(drive_service, file_id):
    request    = drive_service.files().get_media(fileId=file_id)
    buffer     = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done       = False
    while not done:
        _, done = downloader.next_chunk()
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────────────────────────
# AUTO DETECT HEADER ROW
# ─────────────────────────────────────────────────────────────────

def detect_header_row(buffer):
    buffer.seek(0)
    df_raw     = pd.read_excel(buffer, header=None)
    header_row = None
    for idx, row in df_raw.iterrows():
        row_values = row.astype(str).str.strip().tolist()
        if "Name" in row_values and "Sub Source" in row_values:
            header_row = idx
            break
    if header_row is None:
        raise Exception("Could not find header row in Excel file")
    buffer.seek(0)
    return header_row


# ─────────────────────────────────────────────────────────────────
# MAPPING DATA — Using gspread
# ─────────────────────────────────────────────────────────────────

def get_sv_codes(supabase):
    try:
        response = supabase.table("site_visit_data")            .select("serial_numbers")            .execute()
        codes = set(
            str(row["serial_numbers"]).strip()
            for row in response.data
            if row.get("serial_numbers")
        )
        print(f"    ✅ Loaded {len(codes)} SV codes from Supabase site_visit_data")
        return codes
    except Exception as e:
        print(f"    ⚠️  Could not load SV codes from Supabase: {e}")
        return set()


def get_project_mapping(sheets_client):
    try:
        sh   = sheets_client.open(MAPPING_SHEET_NAME)
        ws   = sh.worksheet("project mapping")
        data = ws.get_all_records()
        df   = pd.DataFrame(data)
        df.columns = df.columns.str.strip().str.lower()
        df["project"]         = df["project"].astype(str).str.strip().str.title()
        df["correct project"] = df["correct project"].astype(str).str.strip().str.title()
        df = df.rename(columns={"correct project": "correct_project"})
        print(f"    ✅ Loaded {len(df)} project mappings")
        return df
    except Exception as e:
        print(f"    ⚠️  Could not load project mapping: {e}")
        return pd.DataFrame(columns=["project", "correct_project"])


def get_sub_source_mapping(sheets_client):
    try:
        sh   = sheets_client.open(MAPPING_SHEET_NAME)
        ws   = sh.worksheet("sub source- mapping")
        data = ws.get_all_records()
        df   = pd.DataFrame(data)
        df.columns = df.columns.str.strip().str.lower()
        df["sub source name"] = df["sub source name"].astype(str).str.strip().str.title()
        df["lead project"]    = df["lead project"].astype(str).str.strip().str.title()
        df = df.rename(columns={"sub source name": "sub_source_name", "lead project": "lead_project"})
        print(f"    ✅ Loaded {len(df)} sub source mappings")
        return df
    except Exception as e:
        print(f"    ⚠️  Could not load sub source mapping: {e}")
        return pd.DataFrame(columns=["sub_source_name", "lead_project"])


def get_ivr_mapping(sheets_client):
    try:
        sh   = sheets_client.open(MAPPING_SHEET_NAME)
        ws   = sh.worksheet("IVR Number")
        data = ws.get_all_records()
        df   = pd.DataFrame(data)
        df.columns = df.columns.str.strip().str.lower()
        df["month"]        = df["month"].astype(str).str.strip().str.title()
        df["ivr number"]   = df["ivr number"].astype(str).str.strip().str.title()
        df["lead project"] = df["lead project"].astype(str).str.strip().str.title()
        df = df.rename(columns={"ivr number": "ivr_number", "lead project": "ivr_lead_project"})
        print(f"    ✅ Loaded {len(df)} IVR mappings")
        return df
    except Exception as e:
        print(f"    ⚠️  Could not load IVR mapping: {e}")
        return pd.DataFrame(columns=["month", "ivr_number", "ivr_lead_project"])


# ─────────────────────────────────────────────────────────────────
# CLEANING HELPERS
# ─────────────────────────────────────────────────────────────────

def clean_sub_source(text):
    if pd.isna(text) or str(text).strip() == "":
        return ""
    text = str(text).strip()
    mcube_match = re.match(r"(?i)(mcube)\s*[-–]\s*(\d+)", text)
    if mcube_match:
        return f"Mcube - {mcube_match.group(2)}"
    text = text.lower()
    text = re.sub(r"\b(lead|leads|video|static|copy|ad|otp|x+)\w*\b", "", text)
    text = re.sub(r"[^a-z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.title()


def get_time_zone(dt):
    if pd.isna(dt):
        return None
    t = dt.time()
    if dtime(0,0)  <= t < dtime(4,0):  return "12AM - 4AM"
    if dtime(4,0)  <= t < dtime(8,0):  return "4AM - 8AM"
    if dtime(8,0)  <= t < dtime(12,0): return "8AM - 12PM"
    if dtime(12,0) <= t < dtime(16,0): return "12PM - 4PM"
    if dtime(16,0) <= t < dtime(20,0): return "4PM - 8PM"
    return "8PM - 11:59PM"


def calc_lead_status(row):
    if row.get('Status') == "New":           return "New"
    if row.get('Reason') == "RNR":           return "RNR"
    if row.get('Status') == "RNR":           return "RNR"
    if row.get('Status') in ["Dropped", "Not Interested"]: return "Dropped"
    if row.get('Status') in ["Booked", "Invoiced"]:        return "Booked"
    return "Alive"


def to_hhmmss(td):
    if pd.isna(td):
        return None
    total   = int(td.total_seconds())
    hours   = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def resolve_lead_project(row):
    if re.match(r"(?i)mcube\s*-\s*\d+", str(row.get('cleaned_sub_source', ''))):
        return row.get('ivr_lead_project') or row.get('lead_project')
    return row.get('lead_project')


def safe_str(val):
    """Convert value to string or None — never NaN."""
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    s = str(val).strip()
    if s in ("", "nan", "None", "NaT", "NaN", "<NA>"):
        return None
    return s


def safe_num(val):
    """Convert value to float or None — never NaN."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if np.isnan(f) else f
    except (ValueError, TypeError):
        return None


def safe_date(val):
    """Convert value to YYYY-MM-DD string or None."""
    if val is None:
        return None
    try:
        d = pd.to_datetime(val, errors='coerce')
        if pd.isna(d):
            return None
        return d.strftime('%Y-%m-%d')
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────
# FINAL CLEANUP — Remove all NaN from DataFrame
# ─────────────────────────────────────────────────────────────────

def remove_all_nan(df: pd.DataFrame) -> pd.DataFrame:
    """Replace ALL NaN/NaT/inf values with None across entire DataFrame."""
    df = df.replace({np.nan: None, float('inf'): None, float('-inf'): None})
    df = df.where(pd.notnull(df), None)
    return df


# ─────────────────────────────────────────────────────────────────
# MAIN CLEAN FUNCTION
# ─────────────────────────────────────────────────────────────────

def clean(df: pd.DataFrame, creds, sheets_client, supabase=None) -> pd.DataFrame:

    print("    🧹 Starting leads data cleaning...")

    # ── Build Drive service ───────────────────────────────────
    drive_service = build("drive", "v3", credentials=creds)

    # ── Get folder ────────────────────────────────────────────
    print("    📂 Finding Google Drive folder...")
    parent_id = get_folder_id(drive_service, PARENT_FOLDER_NAME)
    folder_id = get_folder_id(drive_service, LEADS_FOLDER_NAME, parent_id=parent_id)

    # ── Get Excel files ───────────────────────────────────────
    excel_files = get_excel_files_in_folder(drive_service, folder_id)
    if not excel_files:
        raise Exception(f"No Excel files found in '{LEADS_FOLDER_NAME}'")
    print(f"    📊 Found {len(excel_files)} Excel files")

    # ── Load mapping data ─────────────────────────────────────
    print("    📋 Loading mapping data...")
    sv_codes       = get_sv_codes(supabase) if supabase else set()
    project_map    = get_project_mapping(sheets_client)
    sub_source_map = get_sub_source_mapping(sheets_client)
    ivr_map        = get_ivr_mapping(sheets_client)

    # ── Process each Excel file ───────────────────────────────
    all_data = []

    for file_info in excel_files:
        file_name = file_info["name"]
        file_id   = file_info["id"]
        print(f"    📄 Processing: {file_name}")

        try:
            buffer     = download_excel(drive_service, file_id)
            header_row = detect_header_row(buffer)
            buffer.seek(0)
            df_file    = pd.read_excel(buffer, skiprows=header_row)
            df_file    = df_file[[c for c in REQUIRED_COLUMNS if c in df_file.columns]]

            if df_file.empty:
                print(f"    ⚠️  Empty file — skipping")
                continue

            # Clean names
            for col in ['Assigned User Name', 'Original User']:
                if col in df_file.columns:
                    df_file[col] = df_file[col].astype(str)\
                        .str.replace('.', '', regex=False)\
                        .str.strip().str.title()

            # Clean sub source
            if 'Sub Source' in df_file.columns:
                df_file['cleaned_sub_source'] = df_file['Sub Source'].apply(clean_sub_source)

            # Parse dates
            if 'Received On' in df_file.columns:
                df_file['Received On'] = pd.to_datetime(
                    df_file['Received On'], errors='coerce', dayfirst=True, format='mixed'
                )
            if 'Picked Date' in df_file.columns:
                df_file['Picked Date'] = pd.to_datetime(
                    df_file['Picked Date'], errors='coerce', dayfirst=True, format='mixed'
                )

            # Derived date columns
            if 'Received On' in df_file.columns:
                df_file['week']          = df_file['Received On'].apply(
                    lambda d: f"Week {((d.day - 1) // 7) + 1}" if pd.notna(d) else None
                )
                df_file['month_name']    = df_file['Received On'].dt.strftime('%B')
                df_file['received_time'] = df_file['Received On'].dt.strftime("%I:%M %p")
                df_file['received_on']   = df_file['Received On'].dt.strftime('%Y-%m-%d')
                df_file['day_name']      = df_file['Received On'].dt.day_name()
                df_file['time_zone']     = df_file['Received On'].apply(get_time_zone)

            if 'Picked Date' in df_file.columns:
                df_file['picked_time']    = df_file['Picked Date'].dt.strftime("%I:%M %p")
                df_file['pick_time_zone'] = df_file['Picked Date'].apply(get_time_zone)
                df_file['picked_date']    = df_file['Picked Date'].dt.strftime('%Y-%m-%d')

            # Lead status
            df_file['lead_status'] = df_file.apply(calc_lead_status, axis=1)

            # SV status
            if 'Serial Numbers' in df_file.columns:
                df_file['Serial Numbers'] = df_file['Serial Numbers'].astype(str).str.strip()
                df_file['sv_status']      = df_file['Serial Numbers'].apply(
                    lambda x: "SV Done" if x in sv_codes else "SV Not Done"
                )

            # Lead pick duration
            if 'Received On' in df_file.columns and 'Picked Date' in df_file.columns:
                df_file['lead_pick_duration'] = (
                    df_file['Picked Date'] - df_file['Received On']
                ).apply(to_hhmmss)

            # Explode projects
            if 'Projects' in df_file.columns:
                df_file['Projects'] = df_file['Projects']\
                    .astype(str)\
                    .str.replace('(M)', '', regex=False)\
                    .str.split(',')
                df_file = df_file.explode('Projects')
                df_file['Projects'] = df_file['Projects'].str.strip().str.title()

            all_data.append(df_file)
            print(f"    ✅ {len(df_file)} rows from {file_name}")

        except Exception as e:
            print(f"    ❌ Error in {file_name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if not all_data:
        raise Exception("No data processed from any file")

    # ── Combine all files ─────────────────────────────────────
    print("    🔗 Combining all files...")
    final_df = pd.concat(all_data, ignore_index=True)
    print(f"    📊 Total rows: {len(final_df)}")

    # ── Apply project mapping ─────────────────────────────────
    if not project_map.empty and 'Projects' in final_df.columns:
        final_df = final_df.merge(
            project_map, left_on='Projects', right_on='project', how='left'
        )
        final_df['correct_project_name'] = final_df['correct_project']
        final_df.drop(columns=['project', 'correct_project'], inplace=True, errors='ignore')

    # ── Apply sub source mapping ──────────────────────────────
    if not sub_source_map.empty and 'cleaned_sub_source' in final_df.columns:
        final_df = final_df.merge(
            sub_source_map, left_on='cleaned_sub_source', right_on='sub_source_name', how='left'
        )
        final_df.drop(columns=['sub_source_name'], inplace=True, errors='ignore')

    # ── Apply IVR mapping ─────────────────────────────────────
    if not ivr_map.empty and 'cleaned_sub_source' in final_df.columns:
        final_df = final_df.merge(
            ivr_map,
            left_on=['month_name', 'cleaned_sub_source'],
            right_on=['month', 'ivr_number'],
            how='left'
        )
        final_df.drop(columns=['month', 'ivr_number'], inplace=True, errors='ignore')

    # ── Resolve lead project ──────────────────────────────────
    final_df['lead_project'] = final_df.apply(resolve_lead_project, axis=1)
    final_df.drop(columns=['ivr_lead_project'], inplace=True, errors='ignore')

    # ── Create unique lead_id (serial + project + received_date) ─
    final_df['lead_id'] = (
        final_df['Serial Numbers'].astype(str).str.strip()
        + "_"
        + final_df['Projects'].astype(str).str.strip()
        + "_"
        + final_df['received_on'].astype(str).str.strip()
    )

    # ── Remove duplicates — keep last occurrence ───────────────
    before_dedup = len(final_df)
    final_df = final_df.drop_duplicates(subset=['lead_id'], keep='last')
    after_dedup  = len(final_df)
    if before_dedup != after_dedup:
        print(f"    ⚠️  Removed {before_dedup - after_dedup} duplicate lead_ids")
    print(f"    ✅ Unique rows after dedup: {len(final_df)}")

    # ── Rename to Supabase column names ───────────────────────
    final_df = final_df.rename(columns={
        'Name'                       : 'name',
        'Contact No'                 : 'contact_no',
        'Lead Source'                : 'lead_source',
        'Sub Source'                 : 'sub_source',
        'Status'                     : 'status',
        'Reason'                     : 'reason',
        'Assigned User Name'         : 'assigned_user_name',
        'Assigned User Email'        : 'assigned_user_email',
        'Assigned User Phone Number' : 'assigned_user_phone',
        'Projects'                   : 'projects',
        'Serial Numbers'             : 'serial_numbers',
        'Last Modified On'           : 'last_modified_on',
        'Original User'              : 'original_user',
        'Meetings Done Count'        : 'meetings_done_count',
        'Meetings Not Done Count'    : 'meetings_not_done_count',
        'Site Visits Done Count'     : 'site_visits_done_count',
        'Site Visits Not Done Count' : 'site_visits_not_done_count',
        'Tags'                       : 'tags',
    })

    # ── Keep only Supabase columns ────────────────────────────
    final_columns = [
        'lead_id', 'received_on', 'name', 'contact_no',
        'lead_source', 'sub_source', 'status', 'reason',
        'assigned_user_name', 'assigned_user_email', 'assigned_user_phone',
        'projects', 'serial_numbers', 'last_modified_on', 'original_user',
        'week', 'month_name', 'lead_status', 'correct_project_name',
        'cleaned_sub_source', 'lead_project', 'received_time', 'picked_time',
        'picked_date', 'time_zone', 'lead_pick_duration', 'day_name',
        'sv_status', 'pick_time_zone', 'meetings_done_count',
        'meetings_not_done_count', 'site_visits_done_count',
        'site_visits_not_done_count', 'tags',
    ]

    final_df = final_df[[c for c in final_columns if c in final_df.columns]]

    # ── Apply safe conversion to ALL columns ──────────────────
    numeric_cols = [
        'meetings_done_count', 'meetings_not_done_count',
        'site_visits_done_count', 'site_visits_not_done_count'
    ]
    date_cols = ['received_on', 'picked_date']
    str_cols  = [c for c in final_df.columns if c not in numeric_cols + date_cols]

    for col in str_cols:
        final_df[col] = final_df[col].apply(safe_str)

    for col in numeric_cols:
        if col in final_df.columns:
            final_df[col] = final_df[col].apply(safe_num)

    for col in date_cols:
        if col in final_df.columns:
            final_df[col] = final_df[col].apply(safe_date)

    # ── Final NaN removal ─────────────────────────────────────
    final_df = remove_all_nan(final_df)

    # ── Drop rows with no lead_id ─────────────────────────────
    final_df = final_df[final_df['lead_id'].notna()]
    final_df = final_df[~final_df['lead_id'].str.startswith('_')]
    final_df = final_df[final_df['lead_id'] != "nan_nan"]

    print(f"    ✅ Leads cleaning complete — {len(final_df)} rows ready")
    return final_df