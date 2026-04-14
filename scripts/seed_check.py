"""
Camper Tracker MVP - Fase 0
seed_check.py: Verifica el estado de la DB y lista fuentes, targets e integridad.

Uso:
    python scripts/seed_check.py [--db ruta/camper.db]
"""

import sqlite3
import argparse
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).parent.parent / "data" / "camper_tracker.db"

SEPARATOR = "-" * 65


def get_connection(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        print(f"[ERROR] Base de datos no encontrada: {db_path}")
        print("        Ejecuta primero: python scripts/init_db.py")
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def check_tables(conn: sqlite3.Connection) -> list:
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    )]
    expected = {
        "source", "source_target", "crawl_run",
        "listing", "listing_snapshot", "listing_image", "listing_event"
    }
    print(SEPARATOR)
    print("TABLAS")
    print(SEPARATOR)
    for t in tables:
        mark = "OK" if t in expected else "??"
        print(f"  [{mark}] {t}")
    missing = expected - set(tables)
    if missing:
        print(f"\n  [WARN] Tablas esperadas no encontradas: {', '.join(sorted(missing))}")
    return tables


def check_indexes(conn: sqlite3.Connection) -> None:
    indexes = conn.execute(
        "SELECT name, tbl_name FROM sqlite_master WHERE type='index' ORDER BY tbl_name, name;"
    ).fetchall()
    print(f"\n{SEPARATOR}")
    print("INDICES")
    print(SEPARATOR)
    for idx in indexes:
        print(f"  {idx['tbl_name']:25s}  {idx['name']}")


def check_sources(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, name, source_type, country, region, priority, active FROM source ORDER BY priority;"
    ).fetchall()
    print(f"\n{SEPARATOR}")
    print(f"FUENTES ({len(rows)} registros)")
    print(SEPARATOR)
    for r in rows:
        region = r['region'] or '-'
        active = 'activo' if r['active'] else 'inactivo'
        print(f"  [{r['id']:>2}] {r['name']:<35s} {r['source_type']:<22s} {r['country']}/{region:<12s} pri={r['priority']} [{active}]")


def check_targets(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT
            st.id,
            s.name   AS source_name,
            st.label,
            st.vehicle_scope,
            st.scan_frequency_hours,
            st.enabled
        FROM source_target st
        JOIN source s ON s.id = st.source_id
        ORDER BY s.priority, st.id;
        """
    ).fetchall()
    print(f"\n{SEPARATOR}")
    print(f"TARGETS ({len(rows)} registros)")
    print(SEPARATOR)
    for r in rows:
        enabled = 'ON ' if r['enabled'] else 'OFF'
        print(f"  [{r['id']:>2}] [{enabled}] {r['source_name']:<28s} {r['vehicle_scope']:<14s} {r['scan_frequency_hours']:>3}h  {r['label']}")


def check_counts(conn: sqlite3.Connection) -> None:
    tables = ["source", "source_target", "crawl_run",
              "listing", "listing_snapshot", "listing_image", "listing_event"]
    print(f"\n{SEPARATOR}")
    print("RECUENTOS")
    print(SEPARATOR)
    for t in tables:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {t};").fetchone()[0]
            print(f"  {t:<25s} {n:>6} filas")
        except Exception as e:
            print(f"  {t:<25s} ERROR: {e}")


def check_pragma(conn: sqlite3.Connection) -> None:
    fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
    print(f"\n{SEPARATOR}")
    print("PRAGMA / INTEGRIDAD")
    print(SEPARATOR)
    print(f"  foreign_keys    : {fk} ({'ON' if fk else 'OFF - ATENCION'})")
    print(f"  integrity_check : {integrity}")


def main():
    parser = argparse.ArgumentParser(description="Camper Tracker MVP - Verificador de seed")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Ruta a la base de datos SQLite")
    args = parser.parse_args()

    print(f"\nCamper Tracker MVP - seed_check")
    print(f"DB: {args.db}\n")

    conn = get_connection(args.db)
    try:
        check_tables(conn)
        check_indexes(conn)
        check_sources(conn)
        check_targets(conn)
        check_counts(conn)
        check_pragma(conn)
    finally:
        conn.close()

    print(f"\n{SEPARATOR}")
    print("[DONE] Verificacion completada.")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
