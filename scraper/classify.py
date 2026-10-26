"""Clasificación por palabras clave (español y portugués), sin servicios pagos.

Una noticia entra al mapa si:
  1. habla de minería, energía u oil & gas, y
  2. tiene una señal de obra: RIGI, planta u obra nueva, expansión, o una
     inversión atada a un activo físico (planta, parque, gasoducto...), y
  3. no es solo una nota de producción, precios o mercado.

Todo se compara sin tildes y en minúscula. Para afinar resultados, editá las listas.
"""

import re

from gazetteer import strip_accents

SECTORS = {
    "mineria": [
        r"miner[ia]a?", r"mineros?", r"mineras?", r"minas?(?! gerais)", r"litio", r"cobre", r"oro", r"uranio",
        r"potasio", r"salar(es)?", r"carbonato de litio", r"concentradora", r"fundicion",
        r"mineracao", r"mineradora", r"minerio", r"minerio de ferro", r"niquel", r"zinc",
        r"plata metalica", r"yacimiento minero", r"tierras raras", r"terras raras", r"siderurgic\w*",
    ],
    "energia": [
        r"parques? solar(es)?", r"parques? eolicos?", r"eolic[oa]s?", r"fotovoltaic[oa]s?", r"solar(es)?",
        r"central(es)? termica", r"termoelectrica", r"termeletrica", r"hidroelectrica",
        r"hidreletrica", r"represas?", r"alta tension", r"lineas? de transmision",
        r"linhas? de transmissao", r"transmision electrica", r"subestacion", r"subestacao",
        r"hidrogeno( verde)?", r"hidrogenio( verde)?", r"almacenamiento de energia", r"baterias?",
        r"energias? renovables?", r"energias? renovaveis", r"usinas?", r"megawatts?", r"mw",
        r"biocombustibles?", r"biodiesel", r"bioetanol", r"etanol", r"nuclear", r"electricidad",
        r"energia electrica", r"energia eletrica", r"almacenamiento", r"\d+ ?kv", r"kv",
        r"combustibles? verdes?", r"combustiveis? verdes?",
    ],
    "oilgas": [
        r"petroleo", r"petroleras?", r"petrolifer[oa]s?", r"gas natural", r"gas", r"gasoductos?",
        r"gasodutos?", r"oleoductos?", r"oleodutos?", r"refinerias?", r"refinarias?", r"gnl", r"lng",
        r"vaca muerta", r"shale", r"upstream", r"midstream", r"downstream", r"hidrocarburos?",
        r"fpso", r"pre-?sal", r"petroquimic[oa]s?", r"poliductos?", r"crudo", r"oil",
        r"no convencional", r"pozos?", r"perforacion", r"terminal de exportacion", r"refino",
        r"petrobras", r"ypfb?", r"enap", r"tecpetrol", r"pluspetrol", r"vista energy",
        r"planta compresora", r"compresion de gas", r"urea", r"fertilizantes?", r"navio-plataforma",
    ],
}

SIGNALS = {
    "rigi": [r"rigi", r"regimen de incentivo para grandes inversiones"],
    "obra": [
        r"nuevas? plantas?", r"nuevas? fabricas?", r"nuevas? refinerias?", r"novas? plantas?",
        r"novas? usinas?", r"novas? fabricas?", r"novas? unidades?", r"construira", r"construiran",
        r"construccion de", r"construir (una|un|la|el)", r"construcao d[aeo]s?", r"construir (uma|um)",
        r"inicio de (la )?obras?", r"inicio de (la )?construccion", r"inicio das obras",
        r"comenzo la construccion", r"comenzaron las obras", r"arrancan? (la |las )?obras?",
        r"piedra fundamental", r"pedra fundamental", r"licitacion", r"licitacao", r"adjudic\w*",
        r"montaje", r"puesta en marcha", r"inaugur\w*", r"entrada em operacao",
        r"obras? de infraestructura", r"nuevo parque", r"novo parque", r"nueva central",
        r"nueva linea", r"nuevo gasoducto", r"nuevo oleoducto", r"desarrollo del proyecto",
        r"inicia(n|m)? (la |a )?(construccion|construcao|obras?)", r"comienza(n)? (la |las )?(construccion|obras?)", r"comeca(m)? (as )?obras",
        r"comecam as obras", r"inicio (da|de la) construc\w*", r"inicia(n|m)? obras", r"obras? de construc\w*",
        r"nova fpso", r"novo navio-plataforma", r"nueva planta compresora",
    ],
    "expansion": [
        r"ampli\w*", r"expansion", r"expandir\w*", r"expandira", r"ampliacao", r"expansao",
        r"expandir", r"aumentar (la|su) capacidad", r"aumento de (la )?capacidad",
        r"duplicar\w*", r"triplicar\w*", r"nueva etapa", r"segunda etapa", r"segunda fase",
        r"fase 2", r"repotenciacion", r"repotenciar",
    ],
    "inversion": [
        r"invertira", r"invertiran", r"inversion(es)? de", r"invertir", r"invierte",
        r"investimentos?", r"investira", r"investir", r"millones de dolares", r"us\$ ?\d",
        r"usd ?\d", r"milhoes", r"bilhoes", r"mil millones",
    ],
}

# Si aparece una inversión, debe estar atada a un activo físico para contar.
ASSET_WORDS = [
    r"plantas?", r"proyectos?", r"obras?", r"usinas?", r"parques?", r"central(es)?", r"minas?",
    r"gasoductos?", r"oleoductos?", r"refinerias?", r"refinarias?", r"fabricas?", r"terminal(es)?",
    r"projetos?", r"infraestructura", r"infraestrutura", r"lineas?", r"linhas?",
]

# Notas de mercado o producción pura: se descartan salvo que haya señal fuerte (RIGI u obra).
EXCLUDE = [
    r"precio del (barril|petroleo|crudo|oro|cobre|litio)", r"preco do (barril|petroleo)",
    r"cotizacion", r"cotacao", r"record de produccion", r"produccion record", r"producao recorde",
    r"exportaciones? (record|crecieron|cayeron)", r"acciones de", r"wall street", r"merval",
    r"bolsa de valores", r"dividendos", r"resultados trimestrales", r"balance trimestral",
    r"tarifas?", r"subsidios?", r"precio de la nafta", r"surtidor", r"naftas?",
]

SECTOR_LABELS = {"mineria": "Minería", "energia": "Energía", "oilgas": "Oil & Gas"}
SIGNAL_LABELS = {
    "rigi": "RIGI",
    "obra": "Obra o planta nueva",
    "expansion": "Expansión",
    "inversion": "Inversión anunciada",
}


def _rx(words):
    return re.compile(r"(?<![\w])(?:" + "|".join(words) + r")(?![\w])")


_SECTOR_RX = {k: [_rx([w]) for w in v] for k, v in SECTORS.items()}
_SIGNAL_RX = {k: _rx(v) for k, v in SIGNALS.items()}
_ASSET_RX = _rx(ASSET_WORDS)
_EXCLUDE_RX = _rx(EXCLUDE)


def normalize(text):
    return strip_accents(text).lower()


def classify(title, summary="", companies=()):
    """Devuelve dict con sectors, signals y score, o None si la noticia no aplica.

    Si la nota no nombra el sector pero sí una empresa conocida (ej: "Lundin
    presentó el RIGI para Vicuña"), se usa el sector de la empresa."""
    text = normalize(f"{title} . {summary}")
    title_n = normalize(title)

    sector_scores = {}
    for sector, patterns in _SECTOR_RX.items():
        hits = sum(1 for p in patterns if p.search(text))
        title_hits = sum(1 for p in patterns if p.search(title_n))
        if hits:
            sector_scores[sector] = hits + title_hits
    if not sector_scores:
        for c in companies:
            sector = COMPANY_SECTOR.get(c)
            if sector:
                sector_scores[sector] = sector_scores.get(sector, 0) + 1
    if not sector_scores:
        return None

    signals = [s for s, rx in _SIGNAL_RX.items() if rx.search(text)]
    if "inversion" in signals and not _ASSET_RX.search(text):
        signals.remove("inversion")
    if not signals:
        return None

    strong = "rigi" in signals or "obra" in signals
    if _EXCLUDE_RX.search(title_n) and not strong:
        return None

    sectors = sorted(sector_scores, key=lambda s: -sector_scores[s])
    # Sectores secundarios con una sola mención en el resumen no cuentan
    top = sector_scores[sectors[0]]
    sectors = [s for s in sectors if sector_scores[s] >= 2 or sector_scores[s] == top]

    score = len(signals) + (2 if strong else 0) + min(top, 4)
    return {"sectors": sectors, "signals": signals, "score": score}


# --- Empresas -----------------------------------------------------------------

# Nombre canónico -> variantes. Se buscan respetando mayúsculas (sin tildes).
COMPANIES = {
    "YPF": ["YPF"],
    "Pan American Energy": ["Pan American Energy", "PAE"],
    "Vista Energy": ["Vista Energy", "Vista Oil"],
    "Tecpetrol": ["Tecpetrol"],
    "Techint": ["Techint", "Grupo Techint"],
    "Pampa Energía": ["Pampa Energia"],
    "TGS": ["TGS", "Transportadora de Gas del Sur"],
    "TGN": ["TGN", "Transportadora de Gas del Norte"],
    "Pluspetrol": ["Pluspetrol"],
    "CGC": ["CGC", "Compania General de Combustibles"],
    "Phoenix Global Resources": ["Phoenix Global Resources"],
    "Chevron": ["Chevron"],
    "Shell": ["Shell"],
    "TotalEnergies": ["TotalEnergies", "Total Austral"],
    "ExxonMobil": ["ExxonMobil", "Exxon"],
    "Equinor": ["Equinor"],
    "Harbour Energy": ["Harbour Energy", "Wintershall"],
    "Oldelval": ["Oldelval"],
    "VMOS": ["VMOS", "Vaca Muerta Oil Sur"],
    "Southern Energy": ["Southern Energy"],
    "Golar LNG": ["Golar"],
    "Raízen": ["Raizen"],
    "Trafigura": ["Trafigura", "Puma Energy"],
    "Petrobras": ["Petrobras"],
    "YPFB": ["YPFB"],
    "ENAP": ["ENAP"],
    "ANCAP": ["ANCAP"],
    "Petropar": ["Petropar"],
    "PRIO": ["PRIO"],
    "Braskem": ["Braskem"],
    "Central Puerto": ["Central Puerto"],
    "Genneia": ["Genneia"],
    "AES": ["AES Argentina", "AES Andes", "AES Brasil", "AES"],
    "Enel": ["Enel"],
    "Engie": ["Engie"],
    "Edenor": ["Edenor"],
    "Transener": ["Transener"],
    "YPF Luz": ["YPF Luz"],
    "MSU Green Energy": ["MSU Green Energy", "MSU Energy"],
    "360 Energy": ["360 Energy"],
    "Colbún": ["Colbun"],
    "Eletrobras": ["Eletrobras"],
    "Itaipú Binacional": ["Itaipu Binacional"],
    "Yacyretá (EBY)": ["Entidad Binacional Yacyreta", "EBY"],
    "ANDE": ["ANDE"],
    "UTE": ["UTE"],
    "Codelco": ["Codelco"],
    "SQM": ["SQM"],
    "Albemarle": ["Albemarle"],
    "Rio Tinto": ["Rio Tinto", "Arcadium Lithium", "Arcadium", "Livent", "Allkem"],
    "Glencore": ["Glencore"],
    "BHP": ["BHP", "Escondida"],
    "Anglo American": ["Anglo American"],
    "Antofagasta Minerals": ["Antofagasta Minerals", "Antofagasta plc"],
    "Lundin Mining": ["Lundin Mining", "Lundin", "Josemaria"],
    "Vicuña": ["Vicuna Corp", "Vicuna"],
    "Barrick": ["Barrick"],
    "Newmont": ["Newmont"],
    "McEwen Copper": ["McEwen Copper", "McEwen", "Los Azules"],
    "First Quantum": ["First Quantum", "Taca Taca"],
    "Eramet": ["Eramet", "Eramine"],
    "Ganfeng": ["Ganfeng", "Minera Exar"],
    "POSCO": ["POSCO"],
    "Tibet Summit": ["Tibet Summit"],
    "Zijin": ["Zijin", "Liex"],
    "Lithium Argentina": ["Lithium Argentina", "Lithium Americas"],
    "Galan Lithium": ["Galan Lithium"],
    "Rincon Lithium": ["Rincon Lithium"],
    "Pan American Silver": ["Pan American Silver"],
    "Cerro Moro / AngloGold": ["AngloGold", "Cerro Vanguardia"],
    "Yamana / Agua Rica": ["MARA", "Agua Rica", "Yamana"],
    "Minas Argentinas": ["Minas Argentinas", "Gualcamayo"],
    "Fortescue": ["Fortescue"],
    "Vale": ["Vale S.A.", "Vale SA", "Vale(?! do| dos| da| de| la| el)"],
    "CSN": ["CSN", "Companhia Siderurgica Nacional"],
    "Usiminas": ["Usiminas"],
    "Sigma Lithium": ["Sigma Lithium"],
    "CBMM": ["CBMM"],
    "Ternium": ["Ternium"],
    "Tenaris": ["Tenaris"],
    "Aluar": ["Aluar"],
    "Profertil": ["Profertil"],
    "Dow": ["Dow Argentina", "Dow"],
    "Bunge": ["Bunge"],
    "Cargill": ["Cargill"],
    "UPM": ["UPM"],
    "Arauco": ["Arauco"],
    "Suzano": ["Suzano"],
    "HIF Global": ["HIF Global", "HIF"],
    "Fortescue / Hidrógeno": ["Fortescue Future Industries"],
    "Sacde": ["SACDE"],
    "Contreras Hermanos": ["Contreras Hermanos"],
    "AESA": ["AESA"],
    "Burgwardt": ["Burgwardt"],
    "Milicic": ["Milicic"],
    "Saipem": ["Saipem"],
    "Bolland": ["Bolland"],
    "Halliburton": ["Halliburton"],
    "SLB": ["SLB", "Schlumberger"],
    "Baker Hughes": ["Baker Hughes"],
    "Excelerate": ["Excelerate"],
    "Camuzzi": ["Camuzzi"],
    "Capstone Copper": ["Capstone Copper", "Capstone"],
    "Kinross": ["Kinross"],
    "Teck": ["Teck"],
    "Cammesa": ["CAMMESA"],
    "Enarsa": ["ENARSA", "Energia Argentina"],
    "Distrigas / Naturgy": ["Naturgy"],
    "Gas Natural Ban": ["Metrogas"],
}

_COMPANY_RX = []
for _canonical, _variants in COMPANIES.items():
    _vs = sorted({strip_accents(v) for v in _variants}, key=len, reverse=True)
    # una variante con "(?" se toma como expresión regular; el resto, como texto literal
    _parts = [v if "(?" in v else re.escape(v) for v in _vs]
    _COMPANY_RX.append((_canonical, re.compile(r"(?<![\w])(?:" + "|".join(_parts) + r")(?![\w])")))

# Captura nombres propios después de "la empresa X", "a mineradora X"...
_GENERIC_RX = re.compile(
    r"(?:empresa|compania|firma|minera|petrolera|energetica|operadora|mineradora|petroleira|companhia|grupo)\s+"
    r"((?:[A-Z][A-Za-z0-9&\-\.]+)(?:\s+(?:[A-Z][A-Za-z0-9&\-\.]+|de|del|y|do|da)){0,3})"
)
_GENERIC_STOP = {
    "El", "La", "Los", "Las", "Gobierno", "Estado", "Provincia", "Nacion", "Ministerio",
    "Secretaria", "Argentina", "Chile", "Brasil", "Bolivia", "Paraguay", "Uruguay", "Este", "Esta",
    "Su", "Sus", "Una", "Un", "Que", "Para", "Por", "En", "Con", "Federal", "Estatal", "Nacional",
    "Provincial", "Publica", "Privada", "Brasileira", "Chilena", "Argentina", "Boliviana",
}


def find_companies(title, summary=""):
    text = strip_accents(f"{title} . {summary}")
    found = []
    for canonical, rx in _COMPANY_RX:
        if rx.search(text):
            found.append(canonical)
    if not found:
        for m in _GENERIC_RX.finditer(text):
            name = re.sub(r"\s+(de|del|y|do|da)$", "", m.group(1).strip(" .")).strip()
            first = name.split()[0]
            if first in _GENERIC_STOP or len(name) < 3:
                continue
            found.append(name)
            break
    # quitar duplicados conservando el orden
    seen, out = set(), []
    for c in found:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:4]


# Sector principal de cada empresa, para notas que no nombran el sector.
_MINING = ["Codelco", "SQM", "Albemarle", "Rio Tinto", "Glencore", "BHP", "Anglo American",
           "Antofagasta Minerals", "Lundin Mining", "Vicuña", "Barrick", "Newmont", "McEwen Copper",
           "First Quantum", "Eramet", "Ganfeng", "POSCO", "Tibet Summit", "Zijin", "Lithium Argentina",
           "Galan Lithium", "Rincon Lithium", "Pan American Silver", "Cerro Moro / AngloGold",
           "Yamana / Agua Rica", "Minas Argentinas", "Fortescue", "Vale", "CSN", "Sigma Lithium", "CBMM",
           "Capstone Copper", "Kinross", "Teck"]
_OILGAS = ["YPF", "Pan American Energy", "Vista Energy", "Tecpetrol", "TGS", "TGN", "Pluspetrol", "CGC",
           "Phoenix Global Resources", "Chevron", "Shell", "TotalEnergies", "ExxonMobil", "Equinor",
           "Harbour Energy", "Oldelval", "VMOS", "Southern Energy", "Golar LNG", "Raízen", "Trafigura",
           "Petrobras", "YPFB", "ENAP", "ANCAP", "Petropar", "PRIO", "Braskem", "Profertil", "Excelerate",
           "Halliburton", "SLB", "Baker Hughes", "Saipem", "Camuzzi", "Enarsa", "Distrigas / Naturgy", "Gas Natural Ban"]
_ENERGY = ["Central Puerto", "Genneia", "AES", "Enel", "Engie", "Edenor", "Transener", "YPF Luz",
           "MSU Green Energy", "360 Energy", "Colbún", "Eletrobras", "Itaipú Binacional", "Yacyretá (EBY)",
           "ANDE", "UTE", "HIF Global", "Fortescue / Hidrógeno", "Cammesa"]
COMPANY_SECTOR = {**{c: "mineria" for c in _MINING}, **{c: "oilgas" for c in _OILGAS}, **{c: "energia" for c in _ENERGY}}
