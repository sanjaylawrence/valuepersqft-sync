# =================================================================
# strategies/upsert.py — Upsert + Soft Delete Strategy
# =================================================================

import pandas as pd
import traceback


def sync(df: pd.DataFrame, config: dict, supabase) -> dict:

    table_name  = config["table_name"]
    primary_key = config["primary_key"]
    batch_size  = config.get("batch_size", 1000)

    print(f"    📤 Syncing to Supabase table: {table_name}")

    # ── STEP 1: Add is_active = True ──────────────────────────
    df["is_active"] = True

    # ── STEP 2: Get sheet keys ─────────────────────────────────
    sheet_keys = set(df[primary_key].dropna().astype(str).tolist())

    # ── STEP 3: Fetch ALL existing rows from Supabase ─────────
    print(f"    🔍 Reading existing data from Supabase...")
    try:
        response      = supabase.table(table_name).select("*").execute()
        existing_rows = {
            str(row[primary_key]): row
            for row in response.data
            if row.get(primary_key)
        }
    except Exception as e:
        print(f"    ⚠️  Could not fetch existing data: {e}")
        existing_rows = {}

    # ── STEP 4: Compare rows to find inserted vs altered ──────
    records   = df.where(pd.notnull(df), None).to_dict(orient="records")
    inserted  = []
    altered   = []
    unchanged = []

    for record in records:
        pk_val = str(record.get(primary_key, ""))

        if pk_val not in existing_rows:
            # New row
            inserted.append(record)
        else:
            # Existing row — compare field by field
            existing = existing_rows[pk_val]
            changed  = False

            for field, new_val in record.items():
                if field in ("is_active",):
                    continue  # skip internal fields

                old_val = existing.get(field)

                # Normalize both to string for comparison
                old_str = str(old_val).strip() if old_val is not None else ""
                new_str = str(new_val).strip() if new_val is not None else ""

                if old_str != new_str:
                    changed = True
                    break

            if changed:
                altered.append(record)
            else:
                unchanged.append(record)

    print(f"    📊 {len(inserted)} new rows to INSERT")
    print(f"    📊 {len(altered)} existing rows ALTERED")
    print(f"    📊 {len(unchanged)} rows unchanged")

    # ── STEP 5: Upsert in batches ─────────────────────────────
    total_rows    = len(records)
    upserted      = 0
    failed        = 0

    print(f"    📦 Pushing {total_rows} rows in batches of {batch_size}...")

    import time

    for i in range(0, total_rows, batch_size):
        batch         = records[i : i + batch_size]
        batch_num     = (i // batch_size) + 1
        total_batches = (total_rows + batch_size - 1) // batch_size

        # Retry up to 3 times on failure
        max_retries = 3
        success     = False

        for attempt in range(1, max_retries + 1):
            try:
                supabase.table(table_name).upsert(
                    batch,
                    on_conflict=primary_key
                ).execute()

                upserted += len(batch)
                print(f"    ✅ Batch {batch_num}/{total_batches} — {len(batch)} rows pushed")
                success = True
                break

            except Exception as e:
                print(f"    ⚠️  Batch {batch_num} attempt {attempt}/{max_retries} failed: {str(e)[:200]}")
                if attempt < max_retries:
                    wait = attempt * 5  # wait 5s, 10s, 15s
                    print(f"    ⏳ Retrying in {wait} seconds...")
                    time.sleep(wait)
                else:
                    failed += len(batch)
                    print(f"    ❌ Batch {batch_num}/{total_batches} — FAILED after {max_retries} attempts")

        # Small delay between batches to avoid overwhelming Supabase
        time.sleep(0.5)

    # ── STEP 6: Soft Delete safety check ──────────────────────
    if upserted == 0:
        print(f"    ⚠️  Skipping soft delete — no rows upserted")
        return {
            "total"        : total_rows,
            "inserted"     : len(inserted),
            "altered"      : len(altered),
            "unchanged"    : len(unchanged),
            "soft_deleted" : 0,
            "failed"       : failed,
        }

    if failed > upserted:
        print(f"    ⚠️  Skipping soft delete — too many failures")
        return {
            "total"        : total_rows,
            "inserted"     : len(inserted),
            "altered"      : len(altered),
            "unchanged"    : len(unchanged),
            "soft_deleted" : 0,
            "failed"       : failed,
        }

    # ── STEP 7: Soft Delete ────────────────────────────────────
    print(f"    🔍 Checking for soft deletes...")
    soft_deleted = 0

    try:
        active_response = supabase.table(table_name)\
            .select(primary_key)\
            .eq("is_active", True)\
            .execute()

        supabase_active_keys = set(
            str(row[primary_key]) for row in active_response.data
        )
        keys_to_deactivate = supabase_active_keys - sheet_keys

        if keys_to_deactivate:
            supabase.table(table_name)\
                .update({"is_active": False})\
                .in_(primary_key, list(keys_to_deactivate))\
                .execute()
            soft_deleted = len(keys_to_deactivate)
            print(f"    🗑️  Soft deleted: {soft_deleted} rows")
        else:
            print(f"    ✅ No rows to soft delete")

    except Exception as e:
        print(f"    ⚠️  Soft delete check failed: {e}")

    # ── STEP 8: Return Summary ─────────────────────────────────
    return {
        "total"        : total_rows,
        "inserted"     : len(inserted),
        "altered"      : len(altered),
        "unchanged"    : len(unchanged),
        "soft_deleted" : soft_deleted,
        "failed"       : failed,
    }