# =============================================================
# config.py — Valuepersqft DB Sync Configuration
# =============================================================
# HOW TO ADD A NEW GOOGLE SHEET TABLE:
#   1. Copy one block from GOOGLE_SHEET_SOURCES
#   2. Fill in sheet_name, table_name, primary_key, columns
#   3. Push to GitHub — sync.py handles the rest automatically
#
# HOW TO ADD A NEW EXCEL/FOLDER TABLE:
#   1. Copy one block from GOOGLE_DRIVE_SOURCES
#   2. Fill in folder_name, table_name, primary_key, columns
#   3. Push to GitHub — sync.py handles the rest automatically
#
# COLUMN MAPPING FORMAT:
#   "Google Sheet Column Name" : "supabase_column_name"
# =============================================================


# ─────────────────────────────────────────────────────────────
# GOOGLE SHEET SOURCES
# Add all Google Sheet → Supabase mappings here
# ─────────────────────────────────────────────────────────────

GOOGLE_SHEET_SOURCES = [

    # ── TABLE 1: Employee Data ──────────────────────────────
    {
        "sheet_name"  : "Employee data (DB)",   # Exact Google Sheet name
        "table_name"  : "employees",            # Exact Supabase table name
        "primary_key" : "employee_code",        # Supabase primary key column

        # Format → "Google Sheet Column" : "supabase_column"
        "columns": {
            "Employee Code"        : "employee_code",
            "Full name"            : "full_name",
            "Date of birth"        : "date_of_birth",
            "Gender"               : "gender",
            "Work email"           : "work_email",
            "Employment status"    : "employment_status",
            "Experience"           : "experience",
            "Date of joining"      : "date_of_joining",
            "Date of confirmation" : "date_of_confirmation",
            "Date of resignation"  : "date_of_resignation",
            "Date of leaving"      : "date_of_leaving",
            "Department"           : "department",
            "Designation"          : "designation",
            "Skill type"           : "skill_type",
            "Pay group"            : "pay_group",
            "Monthly CTC"          : "monthly_ctc",
            "Yearly CTC"           : "yearly_ctc",
            "Old CTC"              : "old_ctc",
        },

        # Which Supabase columns are DATE type (will be converted from DD/MM/YYYY)
        "date_columns": [
            "date_of_birth",
            "date_of_joining",
            "date_of_confirmation",
            "date_of_resignation",
            "date_of_leaving",
        ],

        # Which Supabase columns are NUMERIC type (will strip commas, convert to number)
        "numeric_columns": [
            "monthly_ctc",
            "yearly_ctc",
            "old_ctc",
        ],
    },

    # ── TABLE 2: Sales (ADD WHEN READY) ─────────────────────
    # {
    #     "sheet_name"  : "Sales (DB)",
    #     "table_name"  : "sales",
    #     "primary_key" : "sale_id",
    #     "columns": {
    #         "Sale ID"   : "sale_id",
    #         "Sale Date" : "sale_date",
    #         # Add all columns here...
    #     },
    #     "date_columns"    : ["sale_date"],
    #     "numeric_columns" : ["amount"],
    # },

    # ── TABLE 3: Team Structure (ADD WHEN READY) ─────────────
    # {
    #     "sheet_name"  : "Team Structure (DB)",
    #     "table_name"  : "team_structure",
    #     "primary_key" : "employee_code",
    #     "columns": {
    #         # Add all columns here...
    #     },
    #     "date_columns"    : [],
    #     "numeric_columns" : [],
    # },

    # ── TABLE 4: Associate SV (ADD WHEN READY) ───────────────
    # {
    #     "sheet_name"  : "Associate SV (DB)",
    #     "table_name"  : "associate_sv",
    #     "primary_key" : "associate_id",
    #     "columns": {
    #         # Add all columns here...
    #     },
    #     "date_columns"    : [],
    #     "numeric_columns" : [],
    # },

    # ── TABLE 5: Monthly Campaign (ADD WHEN READY) ───────────
    # {
    #     "sheet_name"  : "Monthly Campaign (DB)",
    #     "table_name"  : "monthly_campaign",
    #     "primary_key" : "campaign_id",
    #     "columns": {
    #         # Add all columns here...
    #     },
    #     "date_columns"    : [],
    #     "numeric_columns" : [],
    # },

]


# ─────────────────────────────────────────────────────────────
# GOOGLE DRIVE FOLDER SOURCES (Excel files)
# Add all Google Drive Folder → Supabase mappings here
# ─────────────────────────────────────────────────────────────

GOOGLE_DRIVE_SOURCES = [

    # ── TABLE 6: Leads (ADD WHEN READY) ──────────────────────
    # {
    #     "folder_name" : "Leads",         # Exact Google Drive folder name
    #     "table_name"  : "leads",         # Exact Supabase table name
    #     "primary_key" : "lead_id",       # Supabase primary key column
    #     "columns": {
    #         "Lead ID"   : "lead_id",
    #         # Add all columns here...
    #     },
    #     "date_columns"    : [],
    #     "numeric_columns" : [],
    # },

    # ── TABLE 7: Call Data (ADD WHEN READY) ──────────────────
    # {
    #     "folder_name" : "Call Data",
    #     "table_name"  : "call_data",
    #     "primary_key" : "call_id",
    #     "columns": {
    #         # Add all columns here...
    #     },
    #     "date_columns"    : [],
    #     "numeric_columns" : [],
    # },

    # ── TABLE 8: Site Visit (ADD WHEN READY) ─────────────────
    # {
    #     "folder_name" : "Site Visit",
    #     "table_name"  : "site_visit",
    #     "primary_key" : "visit_id",
    #     "columns": {
    #         # Add all columns here...
    #     },
    #     "date_columns"    : [],
    #     "numeric_columns" : [],
    # },

]
