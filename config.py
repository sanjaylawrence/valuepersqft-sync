# =================================================================
# config.py — Valuepersqft Sync Configuration
# =================================================================
# HOW TO ADD A NEW GOOGLE SHEET TABLE:
#   1. Copy one block below
#   2. Fill in sheet_name, table_name, primary_key, columns
#   3. Add cleaner file in cleaners/ folder
#   4. That's it — sync.py handles everything automatically
#
# HOW TO ADD A NEW GOOGLE DRIVE TABLE:
#   1. Copy one block from GOOGLE_DRIVE_SOURCES below
#   2. Fill in folder_name, table_name, primary_key, columns
#   3. Add cleaner file in cleaners/ folder
#   4. That's it — sync.py handles everything automatically
#
# COLUMN MAPPING FORMAT:
#   "Google Sheet Column Name" : "supabase_column_name"
# =================================================================


# ─────────────────────────────────────────────────────────────────
# GOOGLE SHEET SOURCES
# ─────────────────────────────────────────────────────────────────

GOOGLE_SHEET_SOURCES = [

    # ── TABLE 1: Employee Data ───────────────────────────────────
    {
        # Google Sheet exact name
        "sheet_name"  : "Employee data (DB)",

        # Supabase table exact name
        "table_name"  : "employees_data",

        # Unique column used for upsert + soft delete
        "primary_key" : "employee_code",

        # Cleaner file name inside cleaners/ folder
        "cleaner"     : "employees",

        # Column mapping → "Sheet Column" : "supabase_column"
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

        # Date columns → will be converted from DD/MM/YYYY to YYYY-MM-DD
        "date_columns": [
            "date_of_birth",
            "date_of_joining",
            "date_of_confirmation",
            "date_of_resignation",
            "date_of_leaving",
        ],

        # Numeric columns → commas removed, converted to float
        "numeric_columns": [
            "monthly_ctc",
            "yearly_ctc",
            "old_ctc",
        ],
    },


    # ── TABLE 2: Booking Data ────────────────────────────────────
    {
        "sheet_name"  : "Booking_data_DB",
        "table_name"  : "booking_data",
        "primary_key" : "booking_id",
        "cleaner"     : "booking",

        "columns": {
            "Booking Month"          : "booking_month",
            "Associate name"         : "associate_name",
            "Team Leader"            : "team_leader",
            "AGM"                    : "agm",
            "Booking Date"           : "booking_date",
            "Customer Name"          : "customer_name",
            "Customer Number"        : "customer_number",
            "Booking Project"        : "booking_project",
            "Agreement value"        : "agreement_value",
            "RTC"                    : "rtc",
            "RTC (Management)"       : "rtc_management",
            "RTC (Organisation)"     : "rtc_organisation",
            "Outflow"                : "outflow",
            "Sales Done"             : "sales_done",
            "Revenue"                : "revenue",
            "Revenue (Management)"   : "revenue_management",
            "Revenue (Organisation)" : "revenue_organisation",
            "LEAD PROJECT"           : "lead_project",
            "LEAD DATE"              : "lead_date",
            "LEAD SOURCE"            : "lead_source",
            "LEAD MONTH"             : "lead_month",
            "Status"                 : "status",
            "Week"                   : "week",
        },

        "date_columns"    : ["booking_date", "lead_date"],
        "numeric_columns" : [
            "agreement_value", "rtc", "rtc_management", "rtc_organisation",
            "outflow", "sales_done", "revenue", "revenue_management",
            "revenue_organisation"
        ],
    },


    # ── TABLE 3: Team Structure ──────────────────────────────────
    {
        "sheet_name"  : "Booking_data_DB",
        "sheet_tab"   : "Team_structure",
        "table_name"  : "team_structure",
        "primary_key" : "team_id",
        "cleaner"     : "team_structure",

        "columns": {
            "Month"             : "month",
            "GM"                : "gm",
            "AGM"               : "agm",
            "TL Name"           : "tl_name",
            "Associate Name"    : "associate_name",
            "Project Tagged"    : "project_tagged",
            "Project Tagged 2"  : "project_tagged_2",
            "Project Tagged 3"  : "project_tagged_3",
            "Status"            : "status",
            "DOJ"               : "doj",
            "DOL"               : "dol",
            "Revenue Target"    : "revenue_target",
            "Sales Target"      : "sales_target",
            "Site Visit Target" : "site_visit_target",
        },

        "date_columns"    : ["doj", "dol"],
        "numeric_columns" : ["revenue_target", "sales_target", "site_visit_target"],
    },


    # ── TABLE 4: Associate SV Data ──────────────────────────────
    {
        "sheet_name"  : "Associate_SV_Data",
        "sheet_tab"   : "Associate_sv",
        "table_name"  : "associate_sv_data",
        "primary_key" : "sv_id",
        "cleaner"     : "associate_sv",

        "columns": {
            "Month"       : "month",
            "Week"        : "week",
            "AGM"         : "agm",
            "Team Leader" : "team_leader",
            "Associate"   : "associate",
            "Visit Count" : "visit_count",
            "date"        : "date",
        },

        "date_columns"    : ["date"],
        "numeric_columns" : ["visit_count"],
    },


    # ── TABLE 5: Marketing Campaign Expenses ─────────────────────
    {
        "sheet_name"  : "Marketing Campaign Expences (DB)",
        "sheet_tab"   : "Marketing_expences",
        "table_name"  : "marketing_campaign_expenses_data",
        "primary_key" : "campaign_key",
        "cleaner"     : "marketing_campaign_expenses",

        "columns": {
            "Month"     : "month",
            "Campaigns" : "campaigns",
            "Platform"  : "platform",
            "Budget"    : "budget",
            "Spend"     : "spend",
            "Leads"     : "leads",
            "CPL"       : "cpl",
        },

        "date_columns"    : [],
        "numeric_columns" : ["budget", "spend", "cpl"],
    },


    # ── TABLE 6: Financial Incentives ────────────────────────────
    {
        "sheet_name"  : "Finance Incentives",
        "sheet_tab"   : "Incentive",
        "table_name"  : "financial_incentives_data",
        "primary_key" : "incentive_key",
        "cleaner"     : "financial_incentives",

        "columns": {
            "Month"                               : "month",
            "Name"                                : "name",
            "Position"                            : "position",
            "Total Incentives Eligible"           : "total_incentives_eligible",
            "Incentives Paid"                     : "incentives_paid",
            "Incentives Payable"                  : "incentives_payable",
            "Builder Payment Received"            : "builder_payment_received",
            "Builder Payment Pending"             : "builder_payment_pending",
            "Advance PSTC Payable for this month" : "advance_pstc_payable",
            "Month - Year"                        : "month_year",
        },

        "date_columns"    : [],
        "numeric_columns" : [
            "total_incentives_eligible",
            "incentives_paid",
            "incentives_payable",
            "builder_payment_received",
            "builder_payment_pending",
            "advance_pstc_payable",
        ],
    },


    # ── TABLE 7: Site Visit Schedule ─────────────────────────────
    {
        "sheet_name"  : "Site Visit Form — Valuepersqft (Responses)",
        "sheet_tab"   : "Form Responses 1",
        "table_name"  : "site_visit_schedule",
        "primary_key" : "sv_schedule_key",
        "cleaner"     : "site_visit_schedule",

        "columns": {
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
        },

        "date_columns"    : ["today_date", "site_visit_date"],
        "numeric_columns" : [],
    },

]


# ─────────────────────────────────────────────────────────────────
# GOOGLE DRIVE FOLDER SOURCES (Excel files)
# ─────────────────────────────────────────────────────────────────

GOOGLE_DRIVE_SOURCES = [

    # ── TABLE 6: Leads Data ──────────────────────────────────────
    {
        "folder_name" : "LEADS RAW DATA",
        "table_name"  : "leads_data",
        "primary_key" : "lead_id",
        "cleaner"     : "leads",

        # Leads cleaner handles all column mapping internally
        # No columns needed here — cleaner returns final DataFrame
        "columns"         : {},
        "date_columns"    : [],
        "numeric_columns" : [],
    },


    # ── TABLE 7: Site Visit Data ─────────────────────────────────
    {
        "folder_name"     : "M_SV_DATA",
        "table_name"      : "site_visit_data",
        "primary_key"     : "sv_id",
        "cleaner"         : "site_visit",
        "columns"         : {},
        "date_columns"    : [],
        "numeric_columns" : [],
    },


    # ── TABLE 8: Call Data ───────────────────────────────────────
    {
        "folder_name"     : "CALL_REPORT",
        "table_name"      : "call_data",
        "primary_key"     : "call_id",
        "cleaner"         : "call_data",
        "columns"         : {},
        "date_columns"    : [],
        "numeric_columns" : [],
    },

]


# ─────────────────────────────────────────────────────────────────
# BATCH SIZE — How many rows to push to Supabase at once
# 1000 is optimal for most cases
# ─────────────────────────────────────────────────────────────────
BATCH_SIZE = 500