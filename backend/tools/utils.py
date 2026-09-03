"""
Async name → ID resolution against PostgreSQL.

Users always refer to entities by name, never internal IDs.

Resolution order (all case-insensitive):
  1. Exact name match via lower(name) B-tree index
  2. Substring match — returns shortest (most specific) when multiple match
  3. Trigram similarity > 0.3 via gin_trgm_ops index
"""

import asyncpg

_PREFIX_TO_TABLE = {
    "loc":  "locations",
    "prov": "providers",
    "appt": "appointment_types",
}


async def resolve_id(query: str, prefix: str, pool: asyncpg.Pool) -> str | None:
    """Return the catalog ID for a spoken name, or None if not found."""
    table = _PREFIX_TO_TABLE.get(prefix)
    if not table:
        raise ValueError(f"Unknown prefix '{prefix}' — use loc / prov / appt")

    q = query.strip()
    if not q:
        return None

    # 1. Exact case-insensitive name (B-tree index on lower(name))
    row = await pool.fetchrow(
        f"SELECT id FROM {table} WHERE lower(name) = lower($1)", q  # noqa: S608
    )
    if row:
        return row["id"]

    # 2. Substring — ORDER BY length(name) so shortest (most specific) wins
    rows = await pool.fetch(
        f"SELECT id FROM {table} WHERE lower(name) LIKE '%' || lower($1) || '%' ORDER BY length(name) LIMIT 2",  # noqa: S608
        q,
    )
    if rows:
        return rows[0]["id"]

    # 3. Trigram similarity (gin_trgm_ops index, cutoff 0.3)
    row = await pool.fetchrow(
        f"SELECT id FROM {table} WHERE similarity(name, $1) > 0.3 ORDER BY similarity(name, $1) DESC LIMIT 1",  # noqa: S608
        q,
    )
    return row["id"] if row else None