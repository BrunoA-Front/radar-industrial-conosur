"""Fuentes de noticias: búsquedas de Google News por país y RSS de medios del sector.

Para sumar un medio, agregá su RSS a SECTOR_FEEDS con el país al que pertenece.
Para afinar las búsquedas, editá QUERIES_ES / QUERIES_PT.
"""

COUNTRIES = {
    "AR": {"name": "Argentina", "lang": "es"},
    "CL": {"name": "Chile", "lang": "es"},
    "BO": {"name": "Bolivia", "lang": "es"},
    "PY": {"name": "Paraguay", "lang": "es"},
    "UY": {"name": "Uruguay", "lang": "es"},
    "BR": {"name": "Brasil", "lang": "pt"},
}

_OBRA_ES = '("nueva planta" OR ampliación OR expansión OR construcción OR "inicio de obra" OR "piedra fundamental" OR "puesta en marcha")'
_OBRA_PT = '("nova planta" OR ampliação OR expansão OR construção OR "início das obras" OR "pedra fundamental" OR "nova usina")'

QUERIES_ES = [
    _OBRA_ES + " (minería OR minera OR litio OR cobre OR oro)",
    _OBRA_ES + ' ("parque solar" OR "parque eólico" OR "central térmica" OR "alta tensión" OR "hidrógeno verde" OR hidroeléctrica)',
    _OBRA_ES + " (petróleo OR petrolera OR gasoducto OR oleoducto OR refinería OR GNL OR \"Vaca Muerta\")",
    '(invertirá OR inversión) (planta OR proyecto OR obra) (minería OR energía OR petróleo OR gas) millones',
]

# Solo Argentina: Régimen de Incentivo para Grandes Inversiones
QUERIES_AR_EXTRA = [
    'RIGI (aprobó OR aprobación OR adhesión OR presentó OR proyecto)',
]

QUERIES_PT = [
    _OBRA_PT + " (mineração OR mineradora OR lítio OR cobre OR \"minério de ferro\")",
    _OBRA_PT + ' ("usina solar" OR "parque eólico" OR termelétrica OR "linha de transmissão" OR hidrogênio)',
    _OBRA_PT + " (petróleo OR gasoduto OR oleoduto OR refinaria OR GNL OR FPSO)",
    'investimento (usina OR fábrica OR planta) (mineração OR energia OR petróleo OR gás) milhões',
]

# RSS de medios especializados. Si alguno deja de funcionar, el recolector lo
# saltea y lo informa en docs/data/meta.json.
SECTOR_FEEDS = [
    {"name": "EconoJournal", "url": "https://econojournal.com.ar/feed/", "country": "AR"},
    {"name": "Energía Estratégica", "url": "https://www.energiaestrategica.com/feed/", "country": "AR"},
    {"name": "Surtidores", "url": "https://www.surtidores.com.ar/feed/", "country": "AR"},
    {"name": "Panorama Minero", "url": "https://www.panorama-minero.com/feed/", "country": "AR"},
    {"name": "Minería Chilena", "url": "https://www.mch.cl/feed/", "country": "CL"},
    {"name": "Reporte Minero", "url": "https://www.reporteminero.cl/feed/", "country": "CL"},
    {"name": "epbr", "url": "https://epbr.com.br/feed/", "country": "BR"},
    {"name": "Notícias de Mineração Brasil", "url": "https://www.noticiasdemineracao.com/feed/", "country": "BR"},
]

# Ventana de búsqueda de Google News en cada corrida diaria (con solapamiento).
DEFAULT_DAYS = 3
# Cuántos días de historia guardar.
RETENTION_DAYS = 400
