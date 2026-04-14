# Camper Tracker MVP

> Agregador de anuncios de autocaravanas, caravanas y campers con histórico de precios y seguimiento de cambios.

---

## Descripción

Herramienta para recopilar, normalizar y trackear anuncios de compraventa de autocaravanas, caravanas y campers desde múltiples fuentes (portales estructurados + Facebook), con:

- Histórico de snapshots por anuncio
- Detección automática de cambios de precio
- Estado activo / desaparecido / republicado
- Deduplicación por URL, ID externo y heurística (precio + modelo + teléfono + imagen)
- Base de datos SQLite ligera, sin dependencias externas

---

## Estructura del proyecto

```
camper-tracker-mvp/
├── schema/
│   └── phase0_schema_seed.sql   # Esquema SQLite completo + seed de fuentes
├── scripts/
│   ├── init_db.py               # Inicializa y crea la base de datos
│   └── seed_check.py            # Verifica el estado e integridad de la DB
├── data/                        # Directorio generado (ignorado en git)
│   └── camper_tracker.db
├── .gitignore
└── README.md
```

---

## Instalación y uso rápido

### Requisitos

- Python 3.9+
- Sin dependencias externas (sólo stdlib)

### 1. Clonar el repositorio

```bash
git clone https://github.com/aquello/camper-tracker-mvp.git
cd camper-tracker-mvp
```

### 2. Inicializar la base de datos (Fase 0)

```bash
python scripts/init_db.py
```

Salida esperada:
```
[INFO] DB     : data/camper_tracker.db
[INFO] Schema : schema/phase0_schema_seed.sql
[OK] Base de datos creada: data/camper_tracker.db

--- Tablas en la base de datos ---
  crawl_run
  listing
  listing_event
  listing_image
  listing_snapshot
  source
  source_target

--- Seed: fuentes cargadas ---
  [1] mobile_de (portal) - DE
  [2] autoscout24 (portal) - EU
  [3] facebook_groups_es (facebook_group) - ES
  [4] facebook_marketplace_madrid (facebook_marketplace) - ES/Madrid
  [5] facebook_marketplace_bcn (facebook_marketplace) - ES/Barcelona

--- Seed: 13 targets cargados ---
  ...

[DONE] Fase 0 completada. Base de datos lista.
```

### 3. Verificar integridad

```bash
python scripts/seed_check.py
```

---

## Esquema de base de datos

### 4. Ejecutar primer crawl (Fase 1)

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar crawl de un target concreto (por ejemplo: AutoScout24 campers EU)
python scripts/run_crawl.py --source autoscout24 --target-id 3 --max-pages 2

# O ejecutar todos los targets de AutoScout24
python scripts/run_crawl.py --source autoscout24 --all --max-pages 2
```

Salida esperada:
```
2026-04-14 09:15:23 [INFO] AutoScout24Connector: Iniciando crawl: https://www.autoscout24.com/lst?body=7&atype=C
2026-04-14 09:15:26 [INFO] AutoScout24Connector: Crawl completado: 40 anuncios en 12.3s
2026-04-14 09:15:27 [INFO] __main__: === Crawl completado: 40 anuncios encontrados, 38 guardados ===
```

**Comandos útiles:**

```bash
# Ver targets disponibles
python scripts/seed_check.py

# Crawl directo de una URL sin guardar en DB (modo test)
python scripts/run_crawl.py --source autoscout24 --url "https://www.autoscout24.com/lst?body=7&atype=C"

# Ver anuncios en la DB
sqlite3 data/camper_tracker.db "SELECT id, title, price_amount, location_text FROM listing LIMIT 10;"

# Ver crawl_runs
sqlite3 data/camper_tracker.db "SELECT * FROM crawl_run ORDER BY started_at DESC LIMIT 5;"
```

| Tabla | Descripción |
|---|---|
| `source` | Fuentes de datos (portales, grupos FB, marketplace) |
| `source_target` | URLs concretas a escanear por fuente |
| `crawl_run` | Registro de cada ejecución de scraping |
| `listing` | Anuncio consolidado (estado actual) |
| `listing_snapshot` | Versión del anuncio en cada crawl |
| `listing_image` | Imágenes asociadas con hash para dedupe |
| `listing_event` | Eventos detectados (precio cambiado, desaparecido, etc.) |

---

## Fuentes configuradas

### Portales principales
| Fuente | Tipo | País | Frecuencia |
|---|---|---|---|
| mobile.de | portal | DE | 24h |
| AutoScout24 | portal | EU | 24h |

### Facebook (secundario)
| Fuente | Tipo | Zona | Frecuencia |
|---|---|---|---|
| Grupos compraventa ES | facebook_group | ES | 48h |
| Marketplace Madrid | facebook_marketplace | Madrid | 72h |
| Marketplace Barcelona | facebook_marketplace | Barcelona | 72h |

---

## Estados de un anuncio

| Estado | Significado |
|---|---|
| `active` | Visto en el último ciclo esperado |
| `missing` | No visto durante N ciclos consecutivos |
| `archived` | Cerrado o consolidado manualmente |

---

## Fases del proyecto

- [x] **Fase 0** — Base de datos SQLite + seed de fuentes y targets
- [x] **Fase 0** — Base de datos SQLite + seed de fuentes y targets
- [x] **Fase 1** — Conector AutoScout24 funcional con crawling y persistencia en DB
- [ ] **Fase 2** — Conector Facebook (grupos + marketplace)
- [ ] **Fase 3** — Reporting: nuevos anuncios, bajadas de precio, desaparecidos---

## Notas legales / técnicas

- El scraping de Facebook Marketplace puede requerir sesión activa y es más frágil.
- Respetar siempre los `robots.txt` y términos de uso de cada portal.
- La BD no se versiona (`data/*.db` en `.gitignore`); sólo se versiona el schema SQL.
