# =================================================================
# strategies/upsert.py — Upsert + Hard Delete Strategy
# =================================================================
# Hard delete: rows deleted from sheet/Drive are permanently
# deleted from Supabase on next sync
# Pagination: fetches ALL rows from Supabase (not just first 1000)
# =================================================================

import pandas as pd
import time


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
    # Paginated — fetches beyond 1000 row limit
    print(f"    🔍 Reading existing data from Supabase...")
    try:
        existing_rows = {}
        page          = 0
        page_size     = 1000

        while True:
            response = supabase.table(table_name)\
                .select("*")\
                .range(page * page_size, (page + 1) * page_size - 1)\
                .execute()

            for row in response.data:
                if row.get(primary_key):
                    existing_rows[str(row[primary_key])] = row

            if len(response.data) < page_size:
                break  # no more pages
            page += 1

        print(f"    📊 {len(existing_rows)} existing rows fetched from Supabase")

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
            inserted.append(record)
        else:
            existing = existing_rows[pk_val]
            changed  = False

            for field, new_val in record.items():
                if field in ("is_active",):
                    continue

                old_val = existing.get(field)
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

    for i in range(0, total_rows, batch_size):
        batch         = records[i : i + batch_size]
        batch_num     = (i // batch_size) + 1
        total_batches = (total_rows + batch_size - 1) // batch_size
        max_retries   = 3

        for attempt in range(1, max_retries + 1):
            try:
                supabase.table(table_name).upsert(
                    batch,
                    on_conflict=primary_key
                ).execute()

                upserted += len(batch)
                print(f"    ✅ Batch {batch_num}/{total_batches} — {len(batch)} rows pushed")
                break

            except Exception as e:
                print(f"    ⚠️  Batch {batch_num} attempt {attempt}/{max_retries} failed: {str(e)[:200]}")
                if attempt < max_retries:
                    wait = attempt * 5
                    print(f"    ⏳ Retrying in {wait} seconds...")
                    time.sleep(wait)
                else:
                    failed += len(batch)
                    print(f"    ❌ Batch {batch_num}/{total_batches} — FAILED after {max_retries} attempts")

        time.sleep(0.5)

    # ── STEP 6: Hard Delete safety check ──────────────────────
    if upserted == 0:
        print(f"    ⚠️  Skipping hard delete — no rows upserted")
        return {
            "total"        : total_rows,
            "inserted"     : len(inserted),
            "altered"      : len(altered),
            "unchanged"    : len(unchanged),
            "soft_deleted" : 0,
            "failed"       : failed,
        }

    if failed > upserted:
        print(f"    ⚠️  Skipping hard delete — too many failures")
        return {
            "total"        : total_rows,
            "inserted"     : len(inserted),
            "altered"      : len(altered),
            "unchanged"    : len(unchanged),
            "soft_deleted" : 0,
            "failed"       : failed,
        }

    # ── STEP 7: Hard Delete ────────────────────────────────────
    # Paginated — fetches ALL keys beyond 1000 row limit
    print(f"    🔍 Checking for hard deletes...")
    soft_deleted = 0

    try:
        supabase_all_keys = set()
        page              = 0
        page_size         = 1000

        while True:
            response = supabase.table(table_name)\
                .select(primary_key)\
                .range(page * page_size, (page + 1) * page_size - 1)\
                .execute()

            batch_keys = set(
                str(row[primary_key]) for row in response.data
                if row.get(primary_key)
            )
            supabase_all_keys.update(batch_keys)

            if len(response.data) < page_size:
                break  # no more pages
            page += 1

        keys_to_delete = supabase_all_keys - sheet_keys

        if keys_to_delete:
            # Delete in batches of 500 to avoid URL length limits
            keys_list     = list(keys_to_delete)
            delete_batch  = 500

            for i in range(0, len(keys_list), delete_batch):
                batch_keys = keys_list[i : i + delete_batch]
                supabase.table(table_name)\
                    .delete()\
                    .in_(primary_key, batch_keys)\
                    .execute()

            soft_deleted = len(keys_to_delete)
            print(f"    🗑️  Hard deleted: {soft_deleted} rows")
        else:
            print(f"    ✅ No rows to delete")

    except Exception as e:
        print(f"    ⚠️  Hard delete check failed: {e}")

    # ── STEP 8: Return Summary ─────────────────────────────────
    return {
        "total"        : total_rows,
        "inserted"     : len(inserted),
        "altered"      : len(altered),
        "unchanged"    : len(unchanged),
        "soft_deleted" : soft_deleted,
        "failed"       : failed,
    }