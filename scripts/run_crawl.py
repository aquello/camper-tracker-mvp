"""
Camper Tracker MVP - Fase 1
run_crawl.py: Punto de entrada CLI para ejecutar crawls de fuentes.

Uso:
    python scripts/run_crawl.py --source autoscout24 --target-id 3
    python scripts/run_crawl.py --source autoscout24 --url "https://..."
    python scripts/run_crawl.py --source autoscout24 --all
"""

import argparse
import logging
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone

# Ajuste de path para imports relativos
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.connectors import AutoScout24Connector
from scripts.init_db import get_connection

DEFAULT_DB = Path(__file__).parent.parent / "data" / "camper_tracker.db"

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO"):
    """Configura logging basico para consola."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def get_connector(source_name: str):
    """Factory de conectores por nombre de fuente."""
    connectors = {
        "autoscout24": AutoScout24Connector,
        # "mobile_de": MobileDeConnector,  # TODO Fase 1b
    }
    cls = connectors.get(source_name.lower())
    if not cls:
        raise ValueError(f"Conector desconocido: {source_name}. Disponibles: {list(connectors.keys())}")
    return cls()


def save_listings(conn: sqlite3.Connection, listings: list, source_id: int, source_target_id: int, crawl_run_id: int):
    """
    Guarda los listings normalizados en la BD.
    Inserta en listing + listing_snapshot + listing_image.
    """
    now = datetime.now(timezone.utc).isoformat()
    saved = 0

    for nl in listings:
        # Comprobar si existe por source_id + external_id o por canonical_url
        existing = None
        if nl.external_id:
            existing = conn.execute(
                "SELECT id FROM listing WHERE source_id = ? AND external_id = ?",
                (source_id, nl.external_id)
            ).fetchone()
        if not existing and nl.canonical_url:
            existing = conn.execute(
                "SELECT id FROM listing WHERE canonical_url = ?",
                (nl.canonical_url,)
            ).fetchone()

        if existing:
            listing_id = existing["id"]
            # Actualizar last_seen_at y otros campos que pueden cambiar
            conn.execute(
                """
                UPDATE listing
                SET last_seen_at = ?,
                    title = ?,
                    price_amount = ?,
                    km = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, nl.title, nl.price_amount, nl.km, now, listing_id)
            )
        else:
            # Crear nuevo listing
            fp_text, fp_images = nl.compute_fingerprints()
            dedupe_key = nl.compute_dedupe_key()
            conn.execute(
                """
                INSERT INTO listing (
                    source_id, source_target_id, external_id, canonical_url,
                    first_seen_at, last_seen_at, listing_status,
                    vehicle_type, title, brand, model, base_vehicle, year, km,
                    price_amount, price_currency,
                    seller_name, seller_type, phone,
                    location_text, country, region,
                    description_text, image_count,
                    fingerprint_text, fingerprint_images, dedupe_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id, source_target_id, nl.external_id, nl.canonical_url,
                    now, now, "active",
                    nl.vehicle_type, nl.title, nl.brand, nl.model, nl.base_vehicle, nl.year, nl.km,
                    nl.price_amount, nl.price_currency,
                    nl.seller_name, nl.seller_type, nl.phone,
                    nl.location_text, nl.country, nl.region,
                    nl.description_text, nl.image_count,
                    fp_text, fp_images, dedupe_key
                )
            )
            listing_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Crear snapshot
        raw_hash = nl.compute_raw_hash()
        conn.execute(
            """
            INSERT INTO listing_snapshot (
                listing_id, crawl_run_id, seen_at, listing_status,
                title, price_amount, price_currency, location_text,
                seller_name, seller_type, phone, year, km,
                description_text, image_count, raw_hash, raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing_id, crawl_run_id, now, "active",
                nl.title, nl.price_amount, nl.price_currency, nl.location_text,
                nl.seller_name, nl.seller_type, nl.phone, nl.year, nl.km,
                nl.description_text, nl.image_count, raw_hash, nl.raw_json
            )
        )
        snapshot_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Guardar imagenes
        for idx, img_url in enumerate(nl.image_urls[:5]):  # maximo 5 imagenes por ahora
            conn.execute(
                "INSERT INTO listing_image (listing_id, snapshot_id, image_url, sort_order) VALUES (?, ?, ?, ?)",
                (listing_id, snapshot_id, img_url, idx)
            )

        saved += 1

    conn.commit()
    return saved


def run_target(conn: sqlite3.Connection, source_name: str, target_row: dict, max_pages: int = None):
    """
    Ejecuta el crawl de un source_target concreto y guarda resultados en DB.
    """
    logger.info(f"=== Iniciando crawl: {source_name} / {target_row['label']} ===")

    connector = get_connector(source_name)
    target_url = target_row["target_url"]
    source_target_id = target_row["id"]
    source_id = target_row["source_id"]

    # Crear crawl_run
    started_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO crawl_run (source_target_id, started_at, status) VALUES (?, ?, ?)",
        (source_target_id, started_at, "running")
    )
    conn.commit()
    crawl_run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    try:
        listings = connector.run(target_url, source_target_label=target_row["label"], max_pages=max_pages)
        saved = save_listings(conn, listings, source_id, source_target_id, crawl_run_id)

        # Finalizar crawl_run
        finished_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE crawl_run SET finished_at = ?, status = ?, items_seen = ? WHERE id = ?",
            (finished_at, "success", len(listings), crawl_run_id)
        )
        conn.commit()

        logger.info(f"=== Crawl completado: {len(listings)} anuncios encontrados, {saved} guardados ===")
        return listings

    except Exception as e:
        logger.error(f"Error en crawl: {e}", exc_info=True)
        finished_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE crawl_run SET finished_at = ?, status = ?, notes = ? WHERE id = ?",
            (finished_at, "failed", str(e), crawl_run_id)
        )
        conn.commit()
        raise


def main():
    parser = argparse.ArgumentParser(description="Camper Tracker MVP - Ejecutar crawl")
    parser.add_argument("--source", required=True, help="Nombre de la fuente: autoscout24, mobile_de, etc.")
    parser.add_argument("--target-id", type=int, help="ID de source_target a procesar")
    parser.add_argument("--url", help="URL directa a crawl (sin guardar en source_target)")
    parser.add_argument("--all", action="store_true", help="Procesar todos los targets de la fuente")
    parser.add_argument("--max-pages", type=int, default=10, help="Maximo de paginas por target")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Ruta a la base de datos")
    parser.add_argument("--log-level", default="INFO", help="Nivel de log: DEBUG, INFO, WARNING, ERROR")
    args = parser.parse_args()

    setup_logging(args.log_level)

    if not args.db.exists():
        logger.error(f"Base de datos no encontrada: {args.db}")
        logger.info("Ejecuta primero: python scripts/init_db.py")
        sys.exit(1)

    conn = get_connection(args.db)

    try:
        if args.url:
            # Crawl directo de URL sin registro en DB
            logger.info(f"Modo directo: crawling {args.url}")
            connector = get_connector(args.source)
            listings = connector.run(args.url, max_pages=args.max_pages)
            print(json.dumps([l.to_dict() for l in listings], indent=2, ensure_ascii=False))

        elif args.target_id:
            # Procesar un target concreto
            row = conn.execute(
                """
                SELECT st.*, s.name AS source_name, s.id AS source_id
                FROM source_target st
                JOIN source s ON s.id = st.source_id
                WHERE st.id = ?
                """,
                (args.target_id,)
            ).fetchone()
            if not row:
                logger.error(f"source_target con id={args.target_id} no encontrado")
                sys.exit(1)

            run_target(conn, args.source, dict(row), max_pages=args.max_pages)

        elif args.all:
            # Procesar todos los targets activos de la fuente
            rows = conn.execute(
                """
                SELECT st.*, s.name AS source_name, s.id AS source_id
                FROM source_target st
                JOIN source s ON s.id = st.source_id
                WHERE s.name = ? AND st.enabled = 1
                ORDER BY s.priority, st.id
                """,
                (args.source,)
            ).fetchall()
            if not rows:
                logger.warning(f"No hay targets habilitados para la fuente: {args.source}")
                sys.exit(0)

            for row in rows:
                run_target(conn, args.source, dict(row), max_pages=args.max_pages)

        else:
            parser.print_help()
            sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
