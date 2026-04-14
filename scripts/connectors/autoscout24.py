"""
Camper Tracker MVP - Fase 1
autoscout24.py: Conector para AutoScout24 (pan-europeo).

Este conector parsea la pagina de resultados HTML de AutoScout24.
Puede adaptarse mas adelante para usar su API interna si es necesaria.
"""

import re
import json
from typing import Optional
from bs4 import BeautifulSoup
from .base import BaseConnector, NormalizedListing


class AutoScout24Connector(BaseConnector):
    SOURCE_NAME = "autoscout24"
    BASE_URL = "https://www.autoscout24.com"

    def fetch_listings(self, target_url: str, max_pages: int = None) -> list[NormalizedListing]:
        """
        Scrapea AutoScout24 desde target_url, pagina a pagina.
        Devuelve lista de NormalizedListing.
        """
        listings = []
        max_p = max_pages or self.max_pages

        for page in range(1, max_p + 1):
            self.logger.info(f"Fetching page {page}/{max_p}: {target_url}")
            url = f"{target_url}&page={page}" if page > 1 else target_url
            html = self._get(url)
            if not html:
                self.logger.warning(f"No se pudo obtener pagina {page}, abortando")
                break

            page_listings = self._parse_search_page(html)
            if not page_listings:
                self.logger.info(f"Pagina {page} sin resultados, fin de paginacion")
                break

            listings.extend(page_listings)
            self.logger.debug(f"Pagina {page}: {len(page_listings)} anuncios")

        return listings

    def _parse_search_page(self, html: str) -> list[NormalizedListing]:
        """
        Parsea la pagina de resultados de AutoScout24 y devuelve lista de NormalizedListing.
        AutoScout24 usa un structure HTML de tarjetas de anuncio.
        """
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("article[data-item-name]") or soup.select("article.ListItem_article__qyYw7")

        listings = []
        for art in articles:
            try:
                raw = self._extract_article_data(art)
                nl = self.parse_listing(raw)
                if nl:
                    listings.append(nl)
            except Exception as e:
                self.logger.warning(f"Error parseando articulo: {e}")
                continue

        return listings

    def _extract_article_data(self, article) -> dict:
        """
        Extrae datos crudos de un <article> de AutoScout24.
        Devuelve dict con campos detectados.
        """
        raw = {}

        # URL y ID externo
        link_tag = article.select_one("a[href*='/listings/']")
        if link_tag:
            href = link_tag.get("href", "")
            raw["url"] = self.BASE_URL + href if href.startswith("/") else href
            match = re.search(r"/listings/(\d+)", href)
            if match:
                raw["external_id"] = match.group(1)

        # Titulo
        title_tag = article.select_one("h2") or article.select_one("[data-testid='title']") or article.select_one(".ListItem_title__ndA4s")
        if title_tag:
            raw["title"] = title_tag.get_text(strip=True)

        # Precio
        price_tag = article.select_one("[data-testid='price']") or article.select_one(".PriceAndSeals_current_price__ykUpx")
        if price_tag:
            price_str = price_tag.get_text(strip=True)
            raw["price_str"] = price_str
            raw["price_amount"] = self._parse_price(price_str)

        # Ubicacion
        loc_tag = article.select_one("[data-testid='seller-location']") or article.select_one(".VehicleDetailTable_item__O8Y_H")
        if loc_tag:
            raw["location"] = loc_tag.get_text(strip=True)

        # Kilometros, año, etc.
        details = article.select("li") or article.select(".VehicleDetailTable_item__O8Y_H")
        for det in details:
            text = det.get_text(" ", strip=True)
            # Ejemplo: "120.000 km" o "2018" o "Diesel"
            if "km" in text.lower():
                raw["km_str"] = text
                raw["km"] = self._parse_km(text)
            elif re.search(r"\b(19|20)\d{2}\b", text):
                year_match = re.search(r"\b(19|20)\d{2}\b", text)
                if year_match:
                    raw["year"] = int(year_match.group())
            if "kw" in text.lower() or "hp" in text.lower() or "ps" in text.lower():
                raw["power"] = text

        # Imagenes
        img_tags = article.select("img[src]")
        raw["image_urls"] = [img["src"] for img in img_tags if "http" in img.get("src", "")]

        # Vendedor (dealer/private)
        dealer_tag = article.select_one("[data-testid='dealer-name']") or article.select_one(".SellerInfo_name__MkJKs")
        if dealer_tag:
            raw["seller_name"] = dealer_tag.get_text(strip=True)
            raw["seller_type"] = "dealer"
        else:
            raw["seller_type"] = "unknown"

        return raw

    def parse_listing(self, raw: dict) -> Optional[NormalizedListing]:
        """
        Convierte el dict crudo extraido de AutoScout24 en NormalizedListing.
        """
        if not raw.get("url") or not raw.get("title"):
            return None

        nl = NormalizedListing(
            source_name="autoscout24",
            external_id=raw.get("external_id"),
            canonical_url=raw.get("url"),
            vehicle_type="autocaravana",  # AutoScout24 suele clasificar camper/rv juntos
            title=raw.get("title"),
            year=raw.get("year"),
            km=raw.get("km"),
            price_amount=raw.get("price_amount"),
            price_currency="EUR",
            seller_name=raw.get("seller_name"),
            seller_type=raw.get("seller_type", "unknown"),
            location_text=raw.get("location"),
            image_urls=raw.get("image_urls", []),
            image_count=len(raw.get("image_urls", [])),
            raw_json=json.dumps(raw, ensure_ascii=False),
        )

        # Intentar extraer brand/model del titulo
        parts = nl.title.split()
        if len(parts) >= 2:
            nl.brand = parts[0]
            nl.model = " ".join(parts[1:3]) if len(parts) > 2 else parts[1]

        return nl

    # --- Helpers de parseo ---

    def _parse_price(self, price_str: str) -> Optional[float]:
        """
        Extrae numero de precio desde string tipo: '€ 45.900', '45900 EUR', etc.
        """
        clean = re.sub(r"[^\d,.-]", "", price_str)
        clean = clean.replace(".", "").replace(",", ".")  # asume formato europeo
        try:
            return float(clean)
        except ValueError:
            return None

    def _parse_km(self, km_str: str) -> Optional[int]:
        """
        Extrae kilometros desde string tipo: '120.000 km' o '120000 km'.
        """
        clean = re.sub(r"[^\d]", "", km_str)
        try:
            return int(clean)
        except ValueError:
            return None
