"""
Camper Tracker MVP - Fase 1
base.py: Clase base abstracta para todos los conectores de fuentes.

Cada conector hereda de BaseConnector e implementa:
  - fetch_listings()  -> lista de dicts normalizados
  - parse_listing()   -> normaliza un item crudo a esquema comun
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclass de listing normalizado
# ---------------------------------------------------------------------------

@dataclass
class NormalizedListing:
    """Representacion normalizada de un anuncio, independiente de la fuente."""

    # Identificacion
    source_name:      str  = ""
    source_target_label: str = ""
    external_id:      Optional[str] = None
    canonical_url:    Optional[str] = None

    # Vehiculo
    vehicle_type:     Optional[str] = None   # autocaravana, caravana, camper, mixto
    title:            Optional[str] = None
    brand:            Optional[str] = None
    model:            Optional[str] = None
    base_vehicle:     Optional[str] = None
    year:             Optional[int] = None
    km:               Optional[int] = None

    # Precio
    price_amount:     Optional[float] = None
    price_currency:   str = "EUR"

    # Vendedor
    seller_name:      Optional[str] = None
    seller_type:      str = "unknown"        # private, dealer, unknown
    phone:            Optional[str] = None

    # Ubicacion
    location_text:    Optional[str] = None
    country:          Optional[str] = None
    region:           Optional[str] = None

    # Contenido
    description_text: Optional[str] = None
    image_urls:       list = field(default_factory=list)
    image_count:      int = 0

    # Metadatos internos
    seen_at:          str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_json:         Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def compute_fingerprints(self) -> tuple[str, str]:
        """Devuelve (fingerprint_text, fingerprint_images) como hashes MD5."""
        text_parts = " | ".join(filter(None, [
            self.brand, self.model, self.base_vehicle,
            str(self.year) if self.year else None,
            str(round(self.price_amount / 1000) * 1000) if self.price_amount else None,
            self.location_text
        ]))
        fp_text = hashlib.md5(text_parts.lower().encode()).hexdigest() if text_parts.strip() else ""

        img_parts = "|".join(sorted(self.image_urls[:3]))
        fp_images = hashlib.md5(img_parts.encode()).hexdigest() if img_parts else ""

        return fp_text, fp_images

    def compute_dedupe_key(self) -> str:
        """Clave de deduplicacion: URL canonica o fingerprint_text como fallback."""
        if self.canonical_url:
            return hashlib.md5(self.canonical_url.encode()).hexdigest()
        fp_text, _ = self.compute_fingerprints()
        return fp_text or ""

    def compute_raw_hash(self) -> str:
        """Hash del JSON crudo para detectar cambios entre snapshots."""
        raw = self.raw_json or json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Clase base abstracta
# ---------------------------------------------------------------------------

class BaseConnector(ABC):
    """
    Clase base para todos los conectores de fuentes del Camper Tracker.

    Subclases deben implementar:
      - fetch_page(url, params)  -> dict con html/json crudo y metadatos
      - parse_listing(raw_item)  -> NormalizedListing
      - get_listing_urls(target_url) -> lista de URLs de detalle

    El flujo estandar es:
      connector.run(source_target_row, db_conn) -> list[NormalizedListing]
    """

    SOURCE_NAME: str = "base"            # sobreescribir en cada subclase
    DEFAULT_DELAY: float = 2.0           # segundos entre peticiones
    MAX_PAGES: int = 10                  # paginas maximas por target
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(self, delay: float = None, max_pages: int = None):
        self.delay     = delay     or self.DEFAULT_DELAY
        self.max_pages = max_pages or self.MAX_PAGES
        self.session   = self._build_session()
        self.logger    = logging.getLogger(self.__class__.__name__)

    def _build_session(self):
        """Crea una sesion requests con cabeceras basicas."""
        try:
            import requests
            s = requests.Session()
            s.headers.update({
                "User-Agent": self.USER_AGENT,
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
            return s
        except ImportError:
            self.logger.warning("requests no disponible, sesion HTTP no inicializada")
            return None

    def _get(self, url: str, params: dict = None, timeout: int = 15) -> Optional[str]:
        """GET con reintentos simples y delay cortesia."""
        import requests
        for attempt in range(3):
            try:
                resp = self.session.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                time.sleep(self.delay)
                return resp.text
            except requests.RequestException as e:
                wait = self.delay * (attempt + 2)
                self.logger.warning(f"GET {url} fallo (intento {attempt+1}): {e} — reintento en {wait}s")
                time.sleep(wait)
        self.logger.error(f"GET {url} fallo tras 3 intentos")
        return None

    # --- Metodos abstractos que cada conector debe implementar ---

    @abstractmethod
    def fetch_listings(self, target_url: str, max_pages: int = None) -> list[NormalizedListing]:
        """
        Obtiene todos los anuncios de una URL target, paginando si es necesario.
        Devuelve lista de NormalizedListing.
        """
        ...

    @abstractmethod
    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        """
        Convierte un item crudo (dict con campos del portal) en NormalizedListing.
        Devuelve None si el item no es valido o debe ignorarse.
        """
        ...

    # --- Metodo de entrada principal ---

    def run(
        self,
        target_url: str,
        source_target_label: str = "",
        max_pages: int = None,
    ) -> list[NormalizedListing]:
        """
        Ejecuta el crawl completo para un target.
        Registra inicio/fin y devuelve los listings normalizados.
        """
        self.logger.info(f"[{self.SOURCE_NAME}] Iniciando crawl: {target_url}")
        start = time.monotonic()

        listings = self.fetch_listings(target_url, max_pages=max_pages or self.max_pages)

        elapsed = time.monotonic() - start
        self.logger.info(
            f"[{self.SOURCE_NAME}] Crawl completado: {len(listings)} anuncios "
            f"en {elapsed:.1f}s ({target_url})"
        )
        return listings
