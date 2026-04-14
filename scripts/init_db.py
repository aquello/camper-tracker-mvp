"""
Camper Tracker MVP - Fase 0
init_db.py: Inicializa la base de datos SQLite ejecutando el schema + seed.

Uso:
    python scripts/init_db.py [--db ruta/camper.db] [--schema ruta/schema.sql]
"""

import sqlite3
import argparse
import os
import sys
from pathlib import Path

# Rutas por defecto (relativas a la raiz del proyecto)
DEFAULT_DB     = Path(__file__).parent.parent / "data" / "camper_tracker.db"
DEFAULT_SCHEMA = Path(__file__).parent.parent / "schema" / "phase0_schema_seed.sql"


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Abre conexion SQLite con foreign_keys activado."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path, schema_path: Path) -> None:
    """Crea o actualiza la DB ejecutando el fichero SQL de schema+seed."""
    # Crear directorio data/ si no existe
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not schema_path.exists():
        print(f"[ERROR] Schema no encontrado: {schema_path}")
        sys.exit(1)

    sql = schema_path.read_text(encoding="utf-8")

    is_new = not db_path.exists()
    conn = get_connection(db_path)

    try:
        conn.executescript(sql)
        conn.commit()
        action = "creada" if is_new else "actualizada"
        print(f"[OK] Base de datos {action}: {db_path}")
    except sqlite3.Error as e:
        print(f"[ERROR] Fallo al ejecutar schema: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


def verify_tables(db_path: Path) -> None:
    """Lista las tablas creadas y muestra recuento de filas en source y source_target."""
    conn = get_connection(db_path)
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        ).fetchall()
        print("\n--- Tablas en la base de datos ---")
        for t in tables:
            print(f"  {t['name']}")

        print("\n--- Seed: fuentes cargadas ---")
        for row in conn.execute("SELECT id, name, source_type, country FROM source ORDER BY priority;"):
            print(f"  [{row['id']}] {row['name']} ({row['source_type']}) - {row['country']}")

        count_st = conn.execute("SELECT COUNT(*) AS n FROM source_target;").fetchone()['n']
        print(f"\n--- Seed: {count_st} targets cargados ---")
        for row in conn.execute(
            """
            SELECT st.label, s.name AS source_name, st.vehicle_scope, st.scan_frequency_hours
            FROM source_target st
            JOIN source s ON s.id = st.source_id
            ORDER BY s.priority, st.id;
            """
        ):
            print(f"  {row['source_name']} | {row['label']} | {row['vehicle_scope']} | {row['scan_frequency_hours']}h")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Camper Tracker MVP - Inicializador de base de datos")
    parser.add_argument("--db",     type=Path, default=DEFAULT_DB,     help="Ruta a la base de datos SQLite")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Ruta al fichero SQL de schema")
    args = parser.parse_args()

    print(f"[INFO] DB     : {args.db}")
    print(f"[INFO] Schema : {args.schema}")

    init_db(args.db, args.schema)
    verify_tables(args.db)

    print("\n[DONE] Fase 0 completada. Base de datos lista.")


if __name__ == "__main__":
    main()
