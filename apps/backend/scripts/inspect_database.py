"""Print PostgreSQL schema metadata without changing database state."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from sqlalchemy import Connection, inspect, text

from app.db.session import dispose_engine, get_engine

SchemaMetadata = dict[str, Any]


def _inspect_schema(connection: Connection) -> SchemaMetadata:
    inspector = inspect(connection)
    schema = "public"
    tables: list[dict[str, Any]] = []

    for table_name in sorted(inspector.get_table_names(schema=schema)):
        tables.append(
            {
                "name": table_name,
                "columns": [
                    {
                        "name": column["name"],
                        "type": str(column["type"]),
                        "nullable": column["nullable"],
                        "default": column["default"],
                    }
                    for column in inspector.get_columns(table_name, schema=schema)
                ],
                "primary_key": inspector.get_pk_constraint(table_name, schema=schema),
                "unique_constraints": inspector.get_unique_constraints(
                    table_name,
                    schema=schema,
                ),
                "foreign_keys": inspector.get_foreign_keys(table_name, schema=schema),
                "indexes": inspector.get_indexes(table_name, schema=schema),
                "check_constraints": inspector.get_check_constraints(
                    table_name,
                    schema=schema,
                ),
            }
        )

    extensions = [
        dict(row)
        for row in connection.execute(
            text(
                """
                SELECT extname AS name, extversion AS version
                FROM pg_extension
                ORDER BY extname
                """
            )
        ).mappings()
    ]
    server_version = connection.execute(
        text("SELECT current_setting('server_version') AS version")
    ).scalar_one()

    return {
        "schema": schema,
        "server_version": server_version,
        "extensions": extensions,
        "tables": tables,
    }


async def inspect_database() -> SchemaMetadata:
    engine = get_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")

    async with engine.connect() as connection:
        return await connection.run_sync(_inspect_schema)


async def _run() -> int:
    try:
        metadata = await inspect_database()
    except Exception as exc:
        print(f"Database inspection failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await dispose_engine()

    print(json.dumps(metadata, indent=2, ensure_ascii=False, default=str))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
