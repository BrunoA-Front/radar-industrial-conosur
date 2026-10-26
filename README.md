# Radar de obras industriales: Cono Sur

Mapa de calor de los proyectos de **construcción y expansión de plantas** en minería, energía y oil & gas en Argentina, Chile, Bolivia, Paraguay, Uruguay y Brasil, armado automáticamente a partir de noticias.

No mide extracción ni producción: mide dónde se están anunciando obras. Entra una noticia cuando habla de una aprobación o presentación al **RIGI**, una planta u obra nueva, una licitación, una expansión o una inversión atada a una instalación.

**Web:** https://brunoa-front.github.io/radar-industrial-conosur/

## Qué muestra

- Pantalla de inicio con un radar: al tocar **Iniciar radar** cuenta las noticias del día, la semana y el mes, y después abre el mapa.
- Mapa 3D de Latinoamérica en bloque, con tres niveles según el zoom: **países**, **provincias** y **ciudades o polos**.
- Cada punto es una columna: el color indica el rubro (oil & gas, minería, energía) y la altura, la cantidad de noticias.
- Al pasar el mouse: rubro, cantidad de noticias, empresas y si hay RIGI. Al hacer clic: las noticias de las que sale ese punto, con enlace a la fuente.
- Filtros por rubro y período, ranking de zonas y de empresas.

## Cómo funciona

```
GitHub Actions (todos los días, 06:17 ART)
  └─ scraper/collect.py
       ├─ Google News RSS: 4 búsquedas por país (+1 de RIGI en Argentina)
       ├─ RSS de medios especializados (EconoJournal, Energía Estratégica, Minería Chilena, epbr…)
       ├─ classify.py   → ¿es del sector? ¿anuncia una obra? ¿es solo precios/producción?
       ├─ gazetteer.py  → ¿dónde? (ciudad o polo > provincia, resuelve homónimos por país)
       └─ docs/data/news.json  (se acumulan 400 días)
  └─ scraper/build_geo.py (solo la primera vez) → mapas base de Natural Earth
  └─ publica docs/ en GitHub Pages
```

Todo es gratis: sin servidor, sin base de datos y sin APIs pagas. La clasificación es por palabras clave en español y portugués, así que puede haber errores; cada noticia enlaza a su fuente para verificarla.

## Primera puesta en marcha

1. En el repositorio: **Settings → Pages → Source: GitHub Actions**.
2. **Actions → Actualizar noticias → Run workflow**, con `30` en "Días hacia atrás" para una carga inicial.
3. Cuando termine (unos 2 minutos), la web queda publicada en la dirección de arriba. Desde ahí se actualiza sola todos los días.

## Cómo ajustarlo

| Para… | Editá |
|---|---|
| Sumar o quitar medios, cambiar búsquedas | `scraper/config.py` |
| Afinar qué cuenta como obra, sector o nota descartable | `scraper/classify.py` (listas `SECTORS`, `SIGNALS`, `EXCLUDE`) |
| Sumar empresas al ranking | `scraper/classify.py` (`COMPANIES` y su sector en `COMPANY_SECTOR`) |
| Sumar ciudades, polos o yacimientos | `scraper/gazetteer.py` (una línea por lugar) |
| Diseño de la web | `docs/style.css`, `docs/app.js` |

Después de cambiar el clasificador, corré las pruebas:

```bash
python -m unittest discover tests
```

Y para probar sin internet con noticias de ejemplo:

```bash
python scraper/collect.py --fixtures tests/fixtures --out /tmp/demo
```

Para ver la web en tu compu: `python -m http.server -d docs` y abrí http://localhost:8000.

El estado de cada fuente en la última corrida (cuántas notas leyó, cuántas sumó, si falló) queda en `docs/data/meta.json`.

## Limitaciones conocidas

- Google News devuelve como máximo unas 100 notas por búsqueda, así que la cobertura es amplia pero no total.
- Una noticia se ubica en un solo lugar (el más específico que menciona). Notas sin ningún lugar explícito se descartan.
- Los posteos de LinkedIn no se incluyen: LinkedIn no permite leerlos de forma automática.
