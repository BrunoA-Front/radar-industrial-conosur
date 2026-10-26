"""Diccionario geográfico: países, provincias/regiones/estados y ciudades o polos industriales.

Formato de cada línea:  país | tipo | nombre | provincia | lat | lon | alias;alias | flags
  tipo:  prov (provincia, región, estado o departamento) o city (ciudad, polo o yacimiento)
  flags (separados por coma):
    raw  -> se busca respetando tildes (útil para "Pará", que si no choca con "para")
    ctx  -> nombre ambiguo (apellido, palabra común u homónimo en otro país): solo cuenta
            si la fuente es de ese país o la nota lo menciona

Las coordenadas de provincias son aproximadas al centro geográfico.
Para sumar un lugar, agregá una línea. Los nombres se buscan respetando mayúsculas.
"""

import re
import unicodedata

COUNTRY_CENTROIDS = {
    "AR": ("Argentina", -38.4, -63.6, ["Argentina"]),
    "CL": ("Chile", -30.0, -71.0, ["Chile"]),
    "BO": ("Bolivia", -16.3, -63.6, ["Bolivia"]),
    "PY": ("Paraguay", -23.4, -58.4, ["Paraguay"]),
    "UY": ("Uruguay", -32.5, -55.8, ["Uruguay"]),
    "BR": ("Brasil", -14.2, -51.9, ["Brasil", "Brazil"]),
}

_TABLE = """
AR|prov|Buenos Aires|Buenos Aires|-36.6|-60.0|Provincia de Buenos Aires;bonaerense|
AR|prov|CABA|CABA|-34.60|-58.44|Ciudad de Buenos Aires;Ciudad Autónoma de Buenos Aires|
AR|prov|Catamarca|Catamarca|-27.3|-67.0|catamarqueño;catamarqueña|
AR|prov|Chaco|Chaco|-26.4|-60.8||ctx
AR|prov|Chubut|Chubut|-43.8|-68.5|chubutense|
AR|prov|Córdoba|Córdoba|-32.1|-63.8|cordobés;cordobesa|
AR|prov|Corrientes|Corrientes|-28.8|-57.9|correntino;correntina|ctx
AR|prov|Entre Ríos|Entre Ríos|-32.0|-59.2|entrerriano;entrerriana|
AR|prov|Formosa|Formosa|-24.9|-59.9||ctx
AR|prov|Jujuy|Jujuy|-23.3|-65.8|jujeño;jujeña|
AR|prov|La Pampa|La Pampa|-37.1|-65.4|pampeano;pampeana|
AR|prov|La Rioja|La Rioja|-29.7|-67.2|riojano;riojana|
AR|prov|Mendoza|Mendoza|-34.6|-68.6|mendocino;mendocina|
AR|prov|Misiones|Misiones|-26.9|-54.6|misionero;misionera|ctx
AR|prov|Neuquén|Neuquén|-38.6|-70.1|neuquino;neuquina|
AR|prov|Río Negro|Río Negro|-40.4|-67.2|rionegrino;rionegrina|ctx
AR|prov|Salta|Salta|-24.3|-65.3|salteño;salteña|
AR|prov|San Juan|San Juan|-30.9|-68.9|sanjuanino;sanjuanina|
AR|prov|San Luis|San Luis|-33.8|-66.0|puntano;puntana|
AR|prov|Santa Cruz|Santa Cruz|-48.8|-69.8|santacruceño;santacruceña|ctx
AR|prov|Santa Fe|Santa Fe|-30.7|-60.9|santafesino;santafesina|
AR|prov|Santiago del Estero|Santiago del Estero|-27.8|-63.3|santiagueño;santiagueña|
AR|prov|Tierra del Fuego|Tierra del Fuego|-54.3|-67.7|fueguino;fueguina|
AR|prov|Tucumán|Tucumán|-27.0|-65.3|tucumano;tucumana|
AR|city|Vaca Muerta|Neuquén|-38.35|-68.79||
AR|city|Añelo|Neuquén|-38.35|-68.79||
AR|city|Loma Campana|Neuquén|-38.27|-68.66||
AR|city|Tratayén|Neuquén|-38.40|-68.62|Tratayen|
AR|city|Los Azules|San Juan|-31.07|-70.23||
AR|city|Vicuña|San Juan|-28.40|-69.55|Josemaría;Filo del Sol|
AR|city|Rincón de los Sauces|Neuquén|-37.39|-68.93||
AR|city|Cutral Có|Neuquén|-38.93|-69.23|Cutral Co|
AR|city|Plaza Huincul|Neuquén|-38.93|-69.21||
AR|city|Ciudad de Neuquén|Neuquén|-38.95|-68.06|Neuquén capital|
AR|city|Allen|Río Negro|-38.98|-67.83||ctx
AR|city|Cipolletti|Río Negro|-38.94|-67.99||
AR|city|General Roca|Río Negro|-39.03|-67.58||
AR|city|Punta Colorada|Río Negro|-41.73|-65.00||
AR|city|San Antonio Oeste|Río Negro|-40.73|-64.95|Puerto San Antonio Este|
AR|city|Sierra Grande|Río Negro|-41.60|-65.36||
AR|city|Bahía Blanca|Buenos Aires|-38.72|-62.27|Ingeniero White|
AR|city|Puerto Rosales|Buenos Aires|-38.93|-62.07|Punta Alta|
AR|city|Campana|Buenos Aires|-34.16|-58.96||ctx
AR|city|Zárate|Buenos Aires|-34.10|-59.03||
AR|city|Ensenada|Buenos Aires|-34.86|-57.91||ctx
AR|city|La Plata|Buenos Aires|-34.92|-57.95||
AR|city|Dock Sud|Buenos Aires|-34.65|-58.34||
AR|city|San Nicolás|Buenos Aires|-33.33|-60.22||ctx
AR|city|Olavarría|Buenos Aires|-36.89|-60.32||
AR|city|Mar del Plata|Buenos Aires|-38.00|-57.55||
AR|city|Necochea|Buenos Aires|-38.55|-58.74|Quequén|
AR|city|Rosario|Santa Fe|-32.95|-60.64||ctx
AR|city|San Lorenzo|Santa Fe|-32.75|-60.73||ctx
AR|city|Timbúes|Santa Fe|-32.67|-60.79||
AR|city|Villa Constitución|Santa Fe|-33.23|-60.33||
AR|city|Reconquista|Santa Fe|-29.15|-59.65||
AR|city|Río Tercero|Córdoba|-32.17|-64.11||
AR|city|Villa María|Córdoba|-32.41|-63.24||
AR|city|Concepción del Uruguay|Entre Ríos|-32.48|-58.24||
AR|city|Comodoro Rivadavia|Chubut|-45.86|-67.48||
AR|city|Puerto Madryn|Chubut|-42.77|-65.04||
AR|city|Trelew|Chubut|-43.25|-65.31||
AR|city|Caleta Olivia|Santa Cruz|-46.44|-67.52||
AR|city|Río Gallegos|Santa Cruz|-51.62|-69.22||
AR|city|Puerto Deseado|Santa Cruz|-47.75|-65.90||
AR|city|Río Turbio|Santa Cruz|-51.53|-72.30||
AR|city|Perito Moreno|Santa Cruz|-46.59|-70.93||
AR|city|Gobernador Gregores|Santa Cruz|-48.75|-70.25||
AR|city|Ushuaia|Tierra del Fuego|-54.80|-68.30||
AR|city|Luján de Cuyo|Mendoza|-33.04|-68.88||
AR|city|Malargüe|Mendoza|-35.47|-69.58|Malargue|
AR|city|San Rafael|Mendoza|-34.62|-68.33||ctx
AR|city|Calingasta|San Juan|-31.33|-69.42||
AR|city|Jáchal|San Juan|-30.24|-68.75||
AR|city|Departamento Iglesia|San Juan|-30.41|-69.21||
AR|city|Tolar Grande|Salta|-24.59|-67.39||
AR|city|San Antonio de los Cobres|Salta|-24.22|-66.32||
AR|city|General Güemes|Salta|-24.67|-65.05||
AR|city|Susques|Jujuy|-23.40|-66.37||
AR|city|Perico|Jujuy|-24.38|-65.11||ctx
AR|city|Palpalá|Jujuy|-24.26|-65.21||
AR|city|Antofagasta de la Sierra|Catamarca|-26.06|-67.40|Salar del Hombre Muerto|
AR|city|Fiambalá|Catamarca|-27.69|-67.62||
AR|city|Andalgalá|Catamarca|-27.58|-66.32||
CL|prov|Arica y Parinacota|Arica y Parinacota|-18.5|-69.6|Arica|
CL|prov|Tarapacá|Tarapacá|-20.2|-69.3||
CL|prov|Antofagasta|Antofagasta|-23.6|-69.4|Región de Antofagasta|
CL|prov|Atacama|Atacama|-27.5|-70.2|Región de Atacama|ctx
CL|prov|Coquimbo|Coquimbo|-30.5|-71.0||ctx
CL|prov|Valparaíso|Valparaíso|-32.9|-71.0||
CL|prov|Región Metropolitana|Región Metropolitana|-33.45|-70.67|Santiago de Chile|
CL|prov|O'Higgins|O'Higgins|-34.4|-71.0|Rancagua|
CL|prov|Maule|Maule|-35.5|-71.5|Talca|
CL|prov|Ñuble|Ñuble|-36.6|-72.0|Chillán|
CL|prov|Biobío|Biobío|-37.4|-72.5|Bío Bío;Biobio|
CL|prov|Araucanía|Araucanía|-38.7|-72.5|Temuco|
CL|prov|Los Ríos|Los Ríos|-40.0|-72.6|Valdivia|
CL|prov|Los Lagos|Los Lagos|-41.5|-72.9|Puerto Montt|
CL|prov|Aysén|Aysén|-46.4|-72.5|Aysen|
CL|prov|Magallanes|Magallanes|-52.5|-71.5|Punta Arenas|
CL|city|Iquique|Tarapacá|-20.21|-70.15||
CL|city|Pozo Almonte|Tarapacá|-20.26|-69.79||
CL|city|Mejillones|Antofagasta|-23.10|-70.45||
CL|city|Calama|Antofagasta|-22.46|-68.93||
CL|city|Tocopilla|Antofagasta|-22.09|-70.19||
CL|city|Taltal|Antofagasta|-25.40|-70.48||
CL|city|Sierra Gorda|Antofagasta|-22.89|-69.32||ctx
CL|city|Salar de Atacama|Antofagasta|-23.50|-68.25|San Pedro de Atacama|
CL|city|Copiapó|Atacama|-27.37|-70.33||
CL|city|Caldera|Atacama|-27.07|-70.82||ctx
CL|city|Vallenar|Atacama|-28.58|-70.76||
CL|city|Diego de Almagro|Atacama|-26.39|-70.05||
CL|city|La Serena|Coquimbo|-29.90|-71.25||
CL|city|Los Vilos|Coquimbo|-31.91|-71.51||
CL|city|Quintero|Valparaíso|-32.78|-71.53|Puchuncaví|
CL|city|Talcahuano|Biobío|-36.72|-73.12||
CL|city|Coronel|Biobío|-37.03|-73.15||ctx
CL|city|Concepción|Biobío|-36.83|-73.05||ctx
BO|prov|La Paz|La Paz|-15.1|-68.5|El Alto|ctx
BO|prov|Oruro|Oruro|-18.3|-67.6||
BO|prov|Potosí|Potosí|-20.4|-66.8|Potosi|
BO|prov|Cochabamba|Cochabamba|-17.4|-65.8||
BO|prov|Chuquisaca|Chuquisaca|-20.0|-64.3|Sucre|
BO|prov|Tarija|Tarija|-21.6|-64.0||ctx
BO|prov|Santa Cruz|Santa Cruz|-17.5|-61.5|cruceño;cruceña|ctx
BO|prov|Beni|Beni|-14.5|-65.5||ctx
BO|prov|Pando|Pando|-11.2|-67.5||ctx
BO|city|Santa Cruz de la Sierra|Santa Cruz|-17.78|-63.18||
BO|city|Salar de Uyuni|Potosí|-20.13|-67.49|Uyuni|
BO|city|Yacuiba|Tarija|-22.01|-63.68||
BO|city|Villamontes|Tarija|-21.26|-63.47||
BO|city|Puerto Suárez|Santa Cruz|-18.96|-57.80|Mutún|
BO|city|Bulo Bulo|Cochabamba|-17.29|-64.33||
PY|prov|Asunción|Asunción|-25.28|-57.63||
PY|prov|Alto Paraná|Alto Paraná|-25.5|-54.9||
PY|prov|Itapúa|Itapúa|-26.8|-55.8||
PY|prov|Boquerón|Boquerón|-22.0|-60.5|Chaco paraguayo|
PY|prov|Presidente Hayes|Presidente Hayes|-23.5|-59.0||
PY|prov|Alto Paraguay|Alto Paraguay|-20.5|-59.0||
PY|prov|Concepción|Concepción|-23.0|-57.4||ctx
PY|prov|Amambay|Amambay|-22.7|-56.0||
PY|prov|Canindeyú|Canindeyú|-24.2|-55.2||
PY|prov|Caaguazú|Caaguazú|-25.4|-55.9||
PY|prov|Ñeembucú|Ñeembucú|-26.9|-57.9||
PY|prov|Paraguarí|Paraguarí|-26.0|-57.0||
PY|prov|Guairá|Guairá|-25.8|-56.4||ctx
PY|prov|Caazapá|Caazapá|-26.2|-56.0||
PY|prov|Misiones|Misiones|-26.8|-57.1||ctx
PY|city|Ciudad del Este|Alto Paraná|-25.51|-54.61||
PY|city|Encarnación|Itapúa|-27.33|-55.87||
PY|city|Villa Hayes|Presidente Hayes|-25.09|-57.53||
PY|city|Villeta|Asunción|-25.51|-57.56||
PY|city|Itaipú|Alto Paraná|-25.41|-54.59|Itaipu|
PY|city|Yacyretá|Misiones|-27.48|-56.73|Yacyreta|
UY|prov|Montevideo|Montevideo|-34.90|-56.16||
UY|prov|Canelones|Canelones|-34.52|-56.28||
UY|prov|Maldonado|Maldonado|-34.9|-54.95||ctx
UY|prov|Colonia|Colonia|-34.46|-57.84||ctx
UY|prov|Paysandú|Paysandú|-32.32|-58.08||
UY|prov|Río Negro|Río Negro|-32.8|-57.6|Fray Bentos|ctx
UY|prov|Durazno|Durazno|-33.38|-56.52||ctx
UY|prov|Tacuarembó|Tacuarembó|-31.71|-55.98||
UY|prov|Rivera|Rivera|-30.9|-55.55||ctx
UY|prov|Salto|Salto|-31.38|-57.96||ctx
UY|prov|Soriano|Soriano|-33.5|-57.7||ctx
UY|prov|Cerro Largo|Cerro Largo|-32.4|-54.4||
UY|prov|Treinta y Tres|Treinta y Tres|-33.23|-54.38||
UY|prov|Rocha|Rocha|-34.48|-54.33||ctx
UY|prov|Lavalleja|Lavalleja|-34.1|-55.0||ctx
UY|prov|Artigas|Artigas|-30.4|-56.47||ctx
UY|city|Paso de los Toros|Tacuarembó|-32.82|-56.51|Pueblo Centenario|
UY|city|La Teja|Montevideo|-34.86|-56.24||
UY|city|Punta del Tigre|San José|-34.75|-56.55||
UY|city|Nueva Palmira|Colonia|-33.87|-58.41||
BR|prov|Acre|Acre|-9.0|-70.5||ctx
BR|prov|Alagoas|Alagoas|-9.6|-36.6||
BR|prov|Amapá|Amapá|1.4|-51.8||raw
BR|prov|Amazonas|Amazonas|-4.0|-64.6||ctx
BR|prov|Bahia|Bahia|-12.5|-41.7|Bahía|ctx
BR|prov|Ceará|Ceará|-5.2|-39.5||
BR|prov|Distrito Federal|Distrito Federal|-15.8|-47.9|Brasília|
BR|prov|Espírito Santo|Espírito Santo|-19.6|-40.6||
BR|prov|Goiás|Goiás|-15.9|-49.6||
BR|prov|Maranhão|Maranhão|-5.0|-45.3||
BR|prov|Mato Grosso do Sul|Mato Grosso do Sul|-20.5|-54.8||
BR|prov|Mato Grosso|Mato Grosso|-12.9|-55.9||
BR|prov|Minas Gerais|Minas Gerais|-18.5|-44.6|mineiro;mineira|
BR|prov|Pará|Pará|-3.8|-52.5|paraense|raw
BR|prov|Paraíba|Paraíba|-7.2|-36.8||
BR|prov|Paraná|Paraná|-24.6|-51.6|paranaense|ctx
BR|prov|Pernambuco|Pernambuco|-8.4|-37.9||
BR|prov|Piauí|Piauí|-7.5|-42.9||
BR|prov|Rio de Janeiro|Rio de Janeiro|-22.4|-42.7|Río de Janeiro;fluminense|
BR|prov|Rio Grande do Norte|Rio Grande do Norte|-5.8|-36.6||
BR|prov|Rio Grande do Sul|Rio Grande do Sul|-29.8|-53.2|Río Grande do Sul;gaúcho;gaúcha|
BR|prov|Rondônia|Rondônia|-10.9|-62.8||
BR|prov|Roraima|Roraima|2.0|-61.4||
BR|prov|Santa Catarina|Santa Catarina|-27.3|-50.4|catarinense|
BR|prov|São Paulo|São Paulo|-22.3|-48.6|Sao Paulo;San Pablo;paulista|
BR|prov|Sergipe|Sergipe|-10.6|-37.4||
BR|prov|Tocantins|Tocantins|-10.2|-48.3||
BR|city|Macaé|Rio de Janeiro|-22.37|-41.79||
BR|city|Itaguaí|Rio de Janeiro|-22.86|-43.78||
BR|city|Angra dos Reis|Rio de Janeiro|-23.00|-44.32||
BR|city|Duque de Caxias|Rio de Janeiro|-22.79|-43.31||
BR|city|Itaboraí|Rio de Janeiro|-22.74|-42.86|Gaslub|
BR|city|Porto do Açu|Rio de Janeiro|-21.83|-41.00|São João da Barra|
BR|city|Bacia de Santos|São Paulo|-25.50|-44.50|Bacia de Campos;pré-sal;pre-sal;Cuenca de Santos|
BR|city|Porto de Santos|São Paulo|-23.96|-46.33|Puerto de Santos|
BR|city|Cubatão|São Paulo|-23.89|-46.43||
BR|city|Paulínia|São Paulo|-22.76|-47.15||
BR|city|Pecém|Ceará|-3.55|-38.81||
BR|city|Suape|Pernambuco|-8.39|-34.96||
BR|city|Camaçari|Bahia|-12.70|-38.32||
BR|city|São Luís|Maranhão|-2.53|-44.30||
BR|city|Itabira|Minas Gerais|-19.62|-43.23||
BR|city|Parauapebas|Pará|-6.07|-49.90|Carajás|
BR|city|Marabá|Pará|-5.37|-49.12||
BR|city|Belo Horizonte|Minas Gerais|-19.92|-43.94||
BR|city|Vale do Jequitinhonha|Minas Gerais|-16.60|-41.80|Vale do Lítio;Araçuaí|
BR|city|Araxá|Minas Gerais|-19.59|-46.94||
BR|city|Paracatu|Minas Gerais|-17.22|-46.87||
BR|city|Aracruz|Espírito Santo|-19.82|-40.27||
BR|city|Três Lagoas|Mato Grosso do Sul|-20.75|-51.68||
BR|city|Corumbá|Mato Grosso do Sul|-19.01|-57.65||
BR|city|Manaus|Amazonas|-3.12|-60.02||
BR|city|Mossoró|Rio Grande do Norte|-5.19|-37.34||
BR|city|Porto Alegre|Rio Grande do Sul|-30.03|-51.23||
BR|city|Curitiba|Paraná|-25.43|-49.27||
BR|city|Recife|Pernambuco|-8.05|-34.88||
BR|city|Fortaleza|Ceará|-3.73|-38.53||
"""


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


class Place:
    __slots__ = ("country", "kind", "name", "admin1", "lat", "lon", "terms", "raw", "ctx")

    def __init__(self, country, kind, name, admin1, lat, lon, terms, flags):
        self.country, self.kind, self.name, self.admin1 = country, kind, name, admin1
        self.lat, self.lon, self.terms = lat, lon, terms
        self.raw, self.ctx = "raw" in flags, "ctx" in flags

    @property
    def key(self):
        return f"{self.country}|{self.admin1}|{self.name if self.kind == 'city' else ''}"


def _load():
    places = []
    for line in _TABLE.strip().splitlines():
        country, kind, name, admin1, lat, lon, aliases, flags = (p.strip() for p in line.split("|"))
        terms = [name] + [a for a in aliases.split(";") if a]
        places.append(Place(country, kind, name, admin1, float(lat), float(lon), terms, set(flags.split(","))))
    return places


PLACES = _load()


def _compile():
    """Un patrón por término (con todos los lugares que comparten ese nombre).
    Los términos largos van primero para que 'Rio Grande do Sul' gane sobre
    nombres más cortos contenidos en él."""
    groups = {}
    for place in PLACES:
        for term in place.terms:
            key = (term if place.raw else strip_accents(term), place.raw)
            groups.setdefault(key, []).append(place)
    for code, (_, _, _, names) in COUNTRY_CENTROIDS.items():
        for n in names:
            groups.setdefault((strip_accents(n), False), []).append(code)
    compiled = []
    for (pattern_text, raw), targets in sorted(groups.items(), key=lambda kv: -len(kv[0][0])):
        # gentilicios en minúscula (neuquino) se buscan sin distinguir mayúsculas
        flags = re.IGNORECASE if pattern_text[:1].islower() else 0
        rx = re.compile(r"(?<![\w])" + re.escape(pattern_text) + r"(?![\w])", flags)
        compiled.append((rx, raw, targets))
    return compiled


_PATTERNS = _compile()


def find_places(text):
    """Devuelve (lugares encontrados con posición, países mencionados)."""
    text = unicodedata.normalize("NFC", text)
    plain = strip_accents(text)
    taken = [False] * len(text)
    places, countries = [], []
    for rx, raw, targets in _PATTERNS:
        source = text if raw else plain
        for m in rx.finditer(source):
            if any(taken[m.start():m.end()]):
                continue
            for i in range(m.start(), m.end()):
                taken[i] = True
            for target in targets:
                if isinstance(target, Place):
                    places.append((m.start(), target))
                else:
                    countries.append((m.start(), target))
    return places, countries


def resolve_location(text, title_len, feed_country):
    """Elige la ubicación principal de una noticia.

    - Nombres ambiguos (Santa Cruz, Misiones, Río Negro...) se resuelven a favor
      del país de la fuente o de los países mencionados.
    - Una ciudad o polo gana sobre una provincia.
    - Lo que aparece en el título pesa más que lo del resumen.
    Devuelve None si no hay ninguna ubicación explícita en los 6 países.
    """
    places, countries = find_places(text)
    mentioned = [c for _, c in sorted(countries)]
    priority = []
    for c in [feed_country] + mentioned:
        if c and c not in priority:
            priority.append(c)
    # Si la nota menciona explícitamente otro país y no el de la fuente,
    # ese país va primero (ej: medio argentino hablando de Chile).
    if mentioned and feed_country not in mentioned:
        priority = mentioned + [c for c in priority if c not in mentioned]

    by_name = {}
    for pos, place in places:
        by_name.setdefault((pos, place.name), []).append(place)

    def rank_country(p):
        return priority.index(p.country) if p.country in priority else 99

    candidates = []
    for (pos, _), group in by_name.items():
        best = min(group, key=rank_country)
        if rank_country(best) == 99 and (len(group) > 1 or best.ctx):
            continue
        candidates.append((pos, best))

    if candidates:
        def score(item):
            pos, p = item
            in_title = pos < title_len
            return (
                rank_country(p) if p.country in priority else 50,
                0 if in_title else 1,
                0 if p.kind == "city" else 1,
                pos,
            )
        _, best = min(candidates, key=score)
        # Si hay una ciudad de la misma provincia, preferirla
        for pos, p in sorted(candidates, key=score):
            if p.kind == "city" and p.admin1 == best.admin1 and p.country == best.country:
                best = p
                break
        return {
            "country": best.country,
            "admin1": best.admin1,
            "city": best.name if best.kind == "city" else None,
            "level": best.kind,
            "lat": best.lat,
            "lon": best.lon,
        }

    if mentioned:
        code = mentioned[0]
        name, lat, lon, _ = COUNTRY_CENTROIDS[code]
        return {"country": code, "admin1": None, "city": None, "level": "country", "lat": lat, "lon": lon}
    return None
