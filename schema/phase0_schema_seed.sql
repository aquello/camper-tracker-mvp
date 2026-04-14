-- =============================================================
-- Camper Tracker MVP — Fase 0
-- Schema SQLite + Seed inicial de fuentes y targets
-- =============================================================

PRAGMA foreign_keys = ON;

-- -------------------------------------------------------------
-- FUENTES
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source (
  id          INTEGER PRIMARY KEY,
  name        TEXT    NOT NULL,
  source_type TEXT    NOT NULL CHECK(source_type IN (
                'portal','facebook_group','facebook_marketplace','dealer_page'
              )),
  base_url    TEXT,
  country     TEXT,
  region      TEXT,
  active      INTEGER NOT NULL DEFAULT 1,
  priority    INTEGER NOT NULL DEFAULT 100,
  notes       TEXT,
  created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------------
-- TARGETS (URLs concretas a escanear por fuente)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_target (
  id                   INTEGER PRIMARY KEY,
  source_id            INTEGER NOT NULL REFERENCES source(id) ON DELETE CASCADE,
  label                TEXT    NOT NULL,
  target_url           TEXT    NOT NULL,
  vehicle_scope        TEXT,
  scan_frequency_hours INTEGER NOT NULL DEFAULT 24,
  enabled              INTEGER NOT NULL DEFAULT 1,
  created_at           TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------------
-- EJECUCIONES DE CRAWL
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS crawl_run (
  id               INTEGER PRIMARY KEY,
  source_target_id INTEGER NOT NULL REFERENCES source_target(id) ON DELETE CASCADE,
  started_at       TEXT    NOT NULL,
  finished_at      TEXT,
  status           TEXT    NOT NULL CHECK(status IN ('success','partial','failed')),
  items_seen       INTEGER DEFAULT 0,
  raw_store_path   TEXT,
  notes            TEXT
);

-- -------------------------------------------------------------
-- ANUNCIOS
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS listing (
  id               INTEGER PRIMARY KEY,
  source_id        INTEGER NOT NULL REFERENCES source(id),
  source_target_id INTEGER REFERENCES source_target(id),
  external_id      TEXT,
  canonical_url    TEXT,
  first_seen_at    TEXT    NOT NULL,
  last_seen_at     TEXT    NOT NULL,
  listing_status   TEXT    NOT NULL DEFAULT 'active'
                   CHECK(listing_status IN ('active','missing','archived')),
  vehicle_type     TEXT,
  title            TEXT,
  seller_name      TEXT,
  seller_type      TEXT    CHECK(seller_type IN ('private','dealer','unknown')),
  phone            TEXT,
  location_text    TEXT,
  country          TEXT,
  region           TEXT,
  brand            TEXT,
  model            TEXT,
  base_vehicle     TEXT,
  year             INTEGER,
  km               INTEGER,
  price_amount     REAL,
  price_currency   TEXT,
  description_text TEXT,
  image_count      INTEGER DEFAULT 0,
  fingerprint_text TEXT,
  fingerprint_images TEXT,
  dedupe_key       TEXT,
  created_at       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_listing_source_external
  ON listing(source_id, external_id) WHERE external_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_listing_url    ON listing(canonical_url);
CREATE INDEX IF NOT EXISTS idx_listing_dedupe ON listing(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_listing_last_seen ON listing(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_listing_price  ON listing(price_amount);

-- -------------------------------------------------------------
-- SNAPSHOTS (version de cada anuncio en cada crawl)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS listing_snapshot (
  id               INTEGER PRIMARY KEY,
  listing_id       INTEGER NOT NULL REFERENCES listing(id) ON DELETE CASCADE,
  crawl_run_id     INTEGER REFERENCES crawl_run(id) ON DELETE SET NULL,
  seen_at          TEXT    NOT NULL,
  listing_status   TEXT,
  title            TEXT,
  price_amount     REAL,
  price_currency   TEXT,
  location_text    TEXT,
  seller_name      TEXT,
  seller_type      TEXT,
  phone            TEXT,
  year             INTEGER,
  km               INTEGER,
  description_text TEXT,
  image_count      INTEGER,
  raw_hash         TEXT,
  raw_json         TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshot_listing_seen
  ON listing_snapshot(listing_id, seen_at DESC);

-- -------------------------------------------------------------
-- IMAGENES
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS listing_image (
  id          INTEGER PRIMARY KEY,
  listing_id  INTEGER NOT NULL REFERENCES listing(id) ON DELETE CASCADE,
  snapshot_id INTEGER REFERENCES listing_snapshot(id) ON DELETE SET NULL,
  image_url   TEXT,
  image_hash  TEXT,
  sort_order  INTEGER DEFAULT 0,
  created_at  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -------------------------------------------------------------
-- EVENTOS (cambios detectados)
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS listing_event (
  id          INTEGER PRIMARY KEY,
  listing_id  INTEGER NOT NULL REFERENCES listing(id) ON DELETE CASCADE,
  event_type  TEXT    NOT NULL CHECK(event_type IN (
                'first_seen','price_changed','became_missing',
                'relisted','seller_changed'
              )),
  event_at    TEXT    NOT NULL,
  old_value   TEXT,
  new_value   TEXT,
  snapshot_id INTEGER REFERENCES listing_snapshot(id) ON DELETE SET NULL,
  notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_listing_time
  ON listing_event(listing_id, event_at DESC);


-- =============================================================
-- SEED — Fuentes iniciales
-- =============================================================

INSERT INTO source(id, name, source_type, base_url, country, region, priority, notes)
VALUES
  (1, 'mobile_de',                    'portal',               'https://www.mobile.de',       'DE',  NULL,        10, 'Portal principal aleman, buena cobertura EU'),
  (2, 'autoscout24',                  'portal',               'https://www.autoscout24.com', 'EU',  NULL,        20, 'Portal pan-europeo con alertas nativas'),
  (3, 'facebook_groups_es',           'facebook_group',       'https://www.facebook.com',    'ES',  NULL,        50, 'Grupos publicos de compraventa en Espana'),
  (4, 'facebook_marketplace_madrid',  'facebook_marketplace', 'https://www.facebook.com/marketplace', 'ES', 'Madrid',    60, 'Marketplace FB zona Madrid'),
  (5, 'facebook_marketplace_bcn',     'facebook_marketplace', 'https://www.facebook.com/marketplace', 'ES', 'Barcelona', 60, 'Marketplace FB zona Barcelona')
ON CONFLICT(id) DO UPDATE SET
  name        = excluded.name,
  source_type = excluded.source_type,
  base_url    = excluded.base_url,
  country     = excluded.country,
  region      = excluded.region,
  priority    = excluded.priority,
  notes       = excluded.notes;


-- =============================================================
-- SEED — Targets iniciales
-- =============================================================

INSERT INTO source_target(source_id, label, target_url, vehicle_scope, scan_frequency_hours)
VALUES
  -- mobile.de
  (1, 'mobile_de_wohnmobile_de',
      'https://suchen.mobile.de/fahrzeuge/search.html?categories=Wohnmobile&isSearchRequest=true',
      'autocaravana', 24),
  (1, 'mobile_de_wohnwagen_de',
      'https://suchen.mobile.de/fahrzeuge/search.html?categories=Wohnwagen&isSearchRequest=true',
      'caravana', 24),

  -- autoscout24
  (2, 'autoscout24_camper_eu',
      'https://www.autoscout24.com/lst?body=7&atype=C',
      'camper', 24),
  (2, 'autoscout24_caravan_eu',
      'https://www.autoscout24.com/lst?body=7&atype=C&fregfrom=2000',
      'caravana', 24),

  -- Facebook Grupos ES
  (3, 'fb_grupo_autocaravanas_venta',
      'https://www.facebook.com/groups/autocaravanasventa',
      'mixto', 48),
  (3, 'fb_grupo_autocaravanas_ocasion',
      'https://www.facebook.com/groups/autocaravanaocasion',
      'mixto', 48),
  (3, 'fb_grupo_campers_segunda_mano',
      'https://www.facebook.com/groups/campersegundamano',
      'camper', 48),
  (3, 'fb_grupo_compraventa_caravanas',
      'https://www.facebook.com/groups/compraventacaravanas',
      'caravana', 48),
  (3, 'fb_grupo_venta_camper_autocaravana',
      'https://www.facebook.com/groups/ventacamperautocaravana',
      'mixto', 48),

  -- Facebook Marketplace
  (4, 'fb_mkt_madrid_camper',
      'https://www.facebook.com/marketplace/madrid/search/?query=autocaravana',
      'autocaravana', 72),
  (4, 'fb_mkt_madrid_furgoneta',
      'https://www.facebook.com/marketplace/madrid/search/?query=furgoneta+camper',
      'camper', 72),
  (5, 'fb_mkt_bcn_camper',
      'https://www.facebook.com/marketplace/barcelona/search/?query=autocaravana',
      'autocaravana', 72),
  (5, 'fb_mkt_bcn_furgoneta',
      'https://www.facebook.com/marketplace/barcelona/search/?query=furgoneta+camper',
      'camper', 72);
