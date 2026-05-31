# =================================================================
# cleaners/site_visit.py — Site Visit Data Cleaner
# =================================================================

import pandas as pd
import numpy as np
import re
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# ─────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────

PARENT_FOLDER_NAME = "Valuepersqft_DB"
SV_FOLDER_NAME     = "M_SV_DATA"
MAPPING_SHEET_NAME = "project mapping"

REQUIRED_COLUMNS = [
    'Sv Month', 'Received On', 'Name', 'Contact No',
    'Lead Source', 'Sub Source', 'Status', 'Reason',
    'Assigned User Name', 'Assigned User Email',
    'Assigned User Phone Number', 'Projects',
    'Serial Numbers', 'Last Modified On',
    'Original User', 'Tags'
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


def calc_lead_status(row):
    if row.get('Status') == "New":                              return "New"
    if row.get('Reason') == "RNR":                             return "RNR"
    if row.get('Status') == "RNR":                             return "RNR"
    if row.get('Status') in ["Dropped", "Not Interested"]:     return "Dropped"
    if row.get('Status') in ["Booked", "Invoiced"]:            return "Booked"
    return "Alive"


def resolve_lead_project(row):
    if re.match(r"(?i)mcube\s*-\s*\d+", str(row.get('cleaned_sub_source', ''))):
        return row.get('ivr_lead_project') or row.get('lead_project')
    return row.get('lead_project')


def safe_str(val):
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    s = str(val).strip()
    if s in ("", "nan", "None", "NaT", "NaN", "<NA>"):
        return None
    return s


def safe_date(val):
    if val is None:
        return None
    try:
        d = pd.to_datetime(val, errors='coerce')
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

def clean(df: pd.DataFrame, creds, sheets_client) -> pd.DataFrame:

    print("    🧹 Starting site visit data cleaning...")

    # ── Build Drive service ───────────────────────────────────
    drive_service = build("drive", "v3", credentials=creds)

    # ── Get folder ────────────────────────────────────────────
    print("    📂 Finding Google Drive folder...")
    parent_id = get_folder_id(drive_service, PARENT_FOLDER_NAME)
    folder_id = get_folder_id(drive_service, SV_FOLDER_NAME, parent_id=parent_id)

    # ── Get Excel files ───────────────────────────────────────
    excel_files = get_excel_files_in_folder(drive_service, folder_id)
    if not excel_files:
        raise Exception(f"No Excel files found in '{SV_FOLDER_NAME}'")
    print(f"    📊 Found {len(excel_files)} Excel files")

    # ── Load mapping data ─────────────────────────────────────
    print("    📋 Loading mapping data...")
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

            # Title case all columns
            df_file.columns = df_file.columns.str.strip().str.title()

            # Keep only required columns
            df_file = df_file[[c for c in REQUIRED_COLUMNS if c in df_file.columns]]

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
                    df_file['Received On'], errors='coerce',
                    dayfirst=True, format='mixed'
                )

            # Derived date columns
            if 'Received On' in df_file.columns:
                df_file['week']        = df_file['Received On'].apply(
                    lambda d: f"Week {((d.day - 1) // 7) + 1}" if pd.notna(d) else None
                )
                df_file['month_name']  = df_file['Received On'].dt.strftime('%B')
                df_file['received_on'] = df_file['Received On'].dt.strftime('%Y-%m-%d')

            # Lead status
            df_file['lead_status'] = df_file.apply(calc_lead_status, axis=1)

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

    # ── Create unique sv_id ───────────────────────────────────
    final_df['sv_id'] = (
        final_df['Serial Numbers'].astype(str).str.strip()
        + "_"
        + final_df['Projects'].astype(str).str.strip()
        + "_"
        + final_df['received_on'].astype(str).str.strip()
    )

    # ── Remove duplicates ─────────────────────────────────────
    before_dedup = len(final_df)
    final_df     = final_df.drop_duplicates(subset=['sv_id'], keep='last')
    after_dedup  = len(final_df)
    if before_dedup != after_dedup:
        print(f"    ⚠️  Removed {before_dedup - after_dedup} duplicate sv_ids")
    print(f"    ✅ Unique rows after dedup: {len(final_df)}")

    # ── Rename to Supabase column names ───────────────────────
    final_df = final_df.rename(columns={
        'Sv Month'                   : 'sv_month',
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
        'Tags'                       : 'tags',
    })

    # ── Keep only Supabase columns ────────────────────────────
    final_columns = [
        'sv_id', 'sv_month', 'received_on', 'name', 'contact_no',
        'lead_source', 'sub_source', 'status', 'reason',
        'assigned_user_name', 'assigned_user_email', 'assigned_user_phone',
        'projects', 'serial_numbers', 'last_modified_on', 'original_user',
        'week', 'month_name', 'lead_status', 'correct_project_name',
        'cleaned_sub_source', 'lead_project', 'tags',
    ]

    final_df = final_df[[c for c in final_columns if c in final_df.columns]]

    # ── Safe conversion for all columns ──────────────────────
    date_cols = ['received_on']
    str_cols  = [c for c in final_df.columns if c not in date_cols]

    for col in str_cols:
        final_df[col] = final_df[col].apply(safe_str)

    for col in date_cols:
        if col in final_df.columns:
            final_df[col] = final_df[col].apply(safe_date)

    # ── Final NaN removal ─────────────────────────────────────
    final_df = remove_all_nan(final_df)

    # ── Drop rows with no sv_id ───────────────────────────────
    final_df = final_df[final_df['sv_id'].notna()]
    final_df = final_df[~final_df['sv_id'].str.startswith('_')]
    final_df = final_df[final_df['sv_id'] != "nan_nan_nan"]

    print(f"    ✅ Site visit cleaning complete — {len(final_df)} rows ready")
    return final_df