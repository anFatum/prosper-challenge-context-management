"""
Seed PostgreSQL from catalog.json and calendar.json.

Usage (from repo root):
    make db-seed
or:
    cd backend && ../.venv/bin/python -m db.seed
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import date, time, datetime, timedelta
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATA = Path(__file__).parent.parent / "data"
DATABASE_URL = os.environ["DATABASE_URL"]


async def seed() -> None:
    catalog = json.loads((DATA / "catalog.json").read_text())
    calendar = json.loads((DATA / "calendar.json").read_text())

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await _seed_catalog(conn, catalog)
        await _seed_calendar(conn, calendar)
        await conn.execute("REFRESH MATERIALIZED VIEW eligible_pairs")
        print("Done.")
    finally:
        await conn.close()


async def _seed_catalog(conn: asyncpg.Connection, catalog: dict) -> None:

    # ── appointment types ──────────────────────────────────────────────────
    for appt in catalog["appointment_types"]:
        await conn.execute(
            """
            INSERT INTO appointment_types
                (id, name, specialty, duration_min, required_capability,
                 requires_referral, new_patients_allowed)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (id) DO UPDATE SET
                name=$2, specialty=$3, duration_min=$4, required_capability=$5,
                requires_referral=$6, new_patients_allowed=$7
            """,
            appt["id"], appt["name"], appt.get("specialty"), appt["duration_min"],
            appt.get("required_capability"), appt.get("requires_referral", False),
            appt.get("new_patients_allowed", True),
        )

    print(f"  appointment_types: {len(catalog['appointment_types'])}")
    # ── locations ──────────────────────────────────────────────────────────
    for loc in catalog["locations"]:
        await conn.execute(
            """
            INSERT INTO locations (id, name, address, city, phone, hours, capabilities)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (id) DO UPDATE SET
                name=$2, address=$3, city=$4, phone=$5, hours=$6, capabilities=$7
            """,
            loc["id"], loc["name"], loc.get("address"), loc.get("city"),
            loc.get("phone"), loc.get("hours"), loc.get("capabilities", []),
        )

    print(f"  locations:     {len(catalog['locations'])}")

    # ── providers ──────────────────────────────────────────────────────────
    for prov in catalog["providers"]:
        await conn.execute(
            """
            INSERT INTO providers (id, name, title, specialty, languages, accepting_new)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (id) DO UPDATE SET
                name=$2, title=$3, specialty=$4, languages=$5, accepting_new=$6
            """,
            prov["id"], prov["name"], prov.get("title"), prov.get("specialty"),
            prov.get("languages", []), prov.get("accepting_new_patients", True),
        )
        for loc_id in prov.get("location_ids", []):
            await conn.execute(
                "INSERT INTO provider_locations VALUES ($1,$2) ON CONFLICT DO NOTHING",
                prov["id"], loc_id,
            )
        for appt_id in prov.get("appointment_type_ids", []):
            await conn.execute(
                "INSERT INTO provider_appointment_types VALUES ($1,$2) ON CONFLICT DO NOTHING",
                prov["id"], appt_id,
            )

    print(f"  providers:     {len(catalog['providers'])}")


async def _seed_calendar(conn: asyncpg.Connection, calendar: dict) -> None:
    slots = calendar["slots"]
    if not slots:
        return

    # Collect date range to create partitions
    dates = {s["date"] for s in slots}
    months = {d[:7] for d in dates}  # "YYYY-MM"
    for ym in sorted(months):
        year, month = ym.split("-")
        next_month = f"{int(year) + (int(month) == 12)}-{int(month) % 12 + 1:02d}"
        partition = f"slots_{year}_{month}"
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {partition}
            PARTITION OF calendar_slots
            FOR VALUES FROM ('{ym}-01') TO ('{next_month}-01')
        """)
        print(f"  partition:     {partition}")

    # Insert one row per (slot entry × slot object)
    rows = []
    for s in slots:
        d = date.fromisoformat(s["date"])
        for slot in s["slots"]:
            rows.append((
                str(uuid.uuid4()),
                s["provider_id"],
                s["location_id"],
                d,
                time.fromisoformat(slot["start_time"]),
                time.fromisoformat(slot["end_time"]),
            ))

    await conn.executemany(
        """
        INSERT INTO calendar_slots (id, provider_id, location_id, date, start_time, end_time)
        VALUES ($1,$2,$3,$4,$5,$6)
        ON CONFLICT DO NOTHING
        """,
        rows,
    )
    print(f"  calendar_slots: {len(rows)}")


if __name__ == "__main__":
    asyncio.run(seed())