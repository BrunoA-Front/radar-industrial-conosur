"""Proyectos con nombre propio, para juntar en una sola ficha todas las noticias de la misma obra.

Nombre del proyecto -> variantes con que aparece en las noticias (sin tildes, respetando mayúsculas).
Las noticias que no nombran un proyecto conocido se agrupan solas en la web por
empresa + rubro + lugar. Para sumar un proyecto, agregá una línea.
"""

import re

from gazetteer import strip_accents

PROYECTOS = {
    # Oil & Gas, Argentina
    "VMOS (Vaca Muerta Oil Sur)": ["VMOS", "Vaca Muerta Oil Sur", "Vaca Muerta Sur", "oleoducto Vaca Muerta Sur"],
    "Duplicar Norte (Oldelval)": ["Duplicar Norte", "Duplicar Plus", "proyecto Duplicar"],
    "Gasoducto Perito Moreno": ["Gasoducto Perito Moreno", "GPM", "Gasoducto Presidente Nestor Kirchner", "GPNK"],
    "Reversión del Gasoducto Norte": ["Reversion del Gasoducto Norte", "Gasoducto Norte"],
    "Argentina LNG": ["Argentina LNG", "Argentina GNL", "GNL de YPF"],
    "Southern Energy FLNG": ["Southern Energy", "Hilli Episeyo", "MKII", "FLNG"],
    "Tratayén (planta de tratamiento)": ["Tratayen"],
    "Refinería Luján de Cuyo": ["refineria de Lujan de Cuyo", "Refineria Lujan de Cuyo"],
    # Minería, Argentina
    "Los Azules": ["Los Azules"],
    "Vicuña (Josemaría y Filo del Sol)": ["Vicuna", "Josemaria", "Filo del Sol"],
    "El Pachón": ["El Pachon", "Pachon"],
    "MARA (Agua Rica)": ["MARA", "Agua Rica", "Minera Alumbrera"],
    "Taca Taca": ["Taca Taca"],
    "Rincon (Rio Tinto)": ["proyecto Rincon", "Rincon Lithium", "Salar del Rincon"],
    "Fénix / Sal de Vida (Hombre Muerto)": ["proyecto Fenix", "Sal de Vida", "Hombre Muerto Norte"],
    "Hombre Muerto Oeste (Galan)": ["Hombre Muerto Oeste", "HMW"],
    "Mariana (Ganfeng)": ["proyecto Mariana"],
    "Cauchari-Olaroz": ["Cauchari-Olaroz", "Cauchari Olaroz", "Cauchari"],
    "Centenario-Ratones (Eramet)": ["Centenario-Ratones", "Centenario Ratones"],
    "Sal de Oro (POSCO)": ["Sal de Oro"],
    "Veladero": ["Veladero"],
    "Gualcamayo": ["Gualcamayo"],
    "Diablillos": ["Diablillos"],
    "Lindero": ["Lindero"],
    "Potasio Río Colorado": ["Potasio Rio Colorado", "PRC"],
    "Calcatreu": ["Calcatreu"],
    "Cerro Negro": ["Cerro Negro"],
    # Chile
    "Chuquicamata Subterránea": ["Chuquicamata"],
    "El Teniente": ["El Teniente"],
    "Quebrada Blanca 2": ["Quebrada Blanca", "QB2"],
    "Centinela (segunda concentradora)": ["Centinela"],
    "Los Bronces": ["Los Bronces"],
    "Rajo Inca": ["Rajo Inca"],
    "Mantoverde": ["Mantoverde"],
    "Escondida": ["Escondida"],
    # Brasil
    "Búzios": ["Buzios"],
    "Mero": ["campo de Mero"],
    "Polo Gaslub (Itaboraí)": ["Gaslub", "Boaventura"],
    "S11D Carajás": ["S11D"],
}

_RX = []
for _name, _aliases in PROYECTOS.items():
    _vs = sorted({strip_accents(a) for a in _aliases}, key=len, reverse=True)
    _RX.append((_name, re.compile(r"(?<![\w])(?:" + "|".join(re.escape(v) for v in _vs) + r")(?![\w])")))


def find_project(title, summary=""):
    """Devuelve el nombre del proyecto que nombra la noticia (el título manda), o None."""
    for text in (strip_accents(title), strip_accents(summary)):
        for name, rx in _RX:
            if rx.search(text):
                return name
    return None
