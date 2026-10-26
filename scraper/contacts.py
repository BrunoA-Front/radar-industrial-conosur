"""Busca contactos públicos de las empresas que aparecen en el radar y los guarda en docs/data/contactos.json.

Solo canales de empresa: portal de proveedores, mails genéricos (compras@, proveedores@,
contacto@, info@...) del mismo dominio de la empresa y teléfonos publicados en su web.
Nunca guarda mails personales (nombre.apellido@).

  - Empresas con web cargada en empresas.py -> "web oficial"
  - Empresas sin web cargada -> se busca su web en Wikidata -> "sin verificar"

Cada empresa se revisa de nuevo a los 30 días (7 si no se encontró nada).
Uso:  python scraper/contacts.py [--limit 60]
"""

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from empresas import WEBS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
OUT = DATA / "contactos.json"
UA = "Mozilla/5.0 (compatible; RadarObrasBot/1.0; +https://github.com/BrunoA-Front/radar-industrial-conosur)"

KEY_LINK = re.compile(r"proveedor|supplier|compras|procurement|abastecimiento|suministro|fornecedor|contact|contacto|fale-conosco|fale conosco", re.I)
SUPPLIER = re.compile(r"proveedor|supplier|compras|procurement|abastecimiento|suministro|fornecedor|vendor", re.I)
HREF = re.compile(r"""<a\b[^>]*?href\s*=\s*["']([^"'#]+)["'][^>]*>(.*?)</a>""", re.I | re.S)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TEL_HREF = re.compile(r"""href\s*=\s*["']tel:([^"']+)["']""", re.I)
PHONE = re.compile(
    r"(?:\+\s?(?:54|56|55|591|595|598)[\s\-().]*\d[\d\s\-().]{6,16}\d"
    r"|\(0\d{2,4}\)\s?\d[\d\s\-]{5,10}\d"
    r"|0800[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
    r"|\b0\d{2,4}[\s\-]\d{3,4}[\s\-]?\d{4}\b)"
)
TAGS = re.compile(r"<[^>]+>")

EMAIL_KIND = [
    ("compras", re.compile(r"compra|proveedor|procure|purchas|suministr|abastec|supply|vendor|fornecedor|suprimento", re.I)),
    ("general", re.compile(r"^(info|contacto|contact|contato|consultas|comercial|ventas|administracion|recepcion|prensa|atencion)", re.I)),
]


def get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-AR,es;q=0.9,en;q=0.6"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        final = resp.geturl()
        raw = resp.read(1_500_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    return final, raw.decode(charset, errors="replace")


def base_domain(host):
    host = host.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    # ejemplo.com.ar -> ejemplo.com.ar ; sub.ejemplo.com -> ejemplo.com
    if len(parts) >= 3 and parts[-2] in {"com", "gob", "gov", "net", "org", "co"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def kind_of(email):
    local = email.split("@")[0]
    for kind, rx in EMAIL_KIND:
        if rx.search(local):
            return kind
    # nombre.apellido o similares: personales, no se guardan
    if "." in local or "_" in local or len(local) > 14:
        return None
    return "otro"


def clean_phone(p):
    p = re.sub(r"[^\d+()\- ]", "", p).strip()
    p = re.sub(r"\s+", " ", p)
    digits = re.sub(r"\D", "", p)
    return p if 8 <= len(digits) <= 15 else None


def extract(page_html, domain):
    text = html.unescape(TAGS.sub(" ", page_html))
    emails = {}
    for e in set(EMAIL.findall(page_html + " " + text)):
        e = e.strip(".").lower()
        if re.search(r"\.(png|jpe?g|gif|webp|svg)$", e) or not base_domain(e.split("@")[1]) == domain:
            continue
        k = kind_of(e)
        if k:
            emails[e] = k
    phones = [clean_phone(urllib.parse.unquote(t)) for t in TEL_HREF.findall(page_html)]
    phones += [clean_phone(p) for p in PHONE.findall(text)]
    return emails, [p for p in dict.fromkeys(phones) if p]


def links_of(page_html, page_url):
    out = []
    for href, label in HREF.findall(page_html):
        label = html.unescape(TAGS.sub(" ", label)).strip()
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        if KEY_LINK.search(href) or KEY_LINK.search(label):
            out.append((urllib.parse.urljoin(page_url, href), label[:60]))
    seen, uniq = set(), []
    for u, l in out:
        if u not in seen:
            seen.add(u)
            uniq.append((u, l))
    return uniq


def scan_site(start_url):
    """Lee la portada y hasta 6 páginas de contacto o proveedores del mismo sitio."""
    final, home = get(start_url)
    domain = base_domain(urllib.parse.urlparse(final).hostname or "")
    emails, phones = extract(home, domain)
    sources, portal = [final], None
    candidates = links_of(home, final)
    # páginas típicas por si el menú se arma con JavaScript
    for path in ("/contacto", "/proveedores", "/contact", "/suppliers", "/es/contacto", "/es/proveedores"):
        candidates.append((urllib.parse.urljoin(final, path), path))
    visited = 0
    for url, label in candidates:
        host = urllib.parse.urlparse(url).hostname or ""
        if SUPPLIER.search(url + " " + label) and not portal and host and (base_domain(host) == domain or "ariba" in host or "coupa" in host):
            if label.startswith("/"):
                pass  # ruta adivinada: solo cuenta si la página existe (se confirma abajo)
            else:
                portal = url
        if visited >= 6 or not host or base_domain(host) != domain:
            continue
        try:
            u2, page = get(url)
        except Exception:
            continue
        visited += 1
        e2, p2 = extract(page, domain)
        if e2 or p2:
            sources.append(u2)
        emails.update(e2)
        phones.extend(p for p in p2 if p not in phones)
        if not portal and label.startswith("/") and SUPPLIER.search(label) and len(page) > 3000 and u2.rstrip("/") != final.rstrip("/"):
            portal = u2
    order = {"compras": 0, "general": 1, "otro": 2}
    return {
        "web": final,
        "portal": portal,
        "emails": [{"email": e, "tipo": k} for e, k in sorted(emails.items(), key=lambda x: (order[x[1]], x[0]))][:4],
        "telefonos": phones[:3],
        "fuentes": list(dict.fromkeys(sources))[:4],
    }


def wikidata_site(name):
    """Busca la web oficial de una empresa en Wikidata (propiedad P856)."""
    q = urllib.parse.urlencode({"action": "wbsearchentities", "search": name, "language": "es", "format": "json", "limit": 5, "type": "item"})
    _, body = get("https://www.wikidata.org/w/api.php?" + q)
    for hit in json.loads(body).get("search", []):
        desc = (hit.get("description") or "").lower()
        if not re.search(r"empresa|compañía|company|firm|corporation|constructora|minera|petrolera|sociedad|enterprise|business", desc):
            continue
        q2 = urllib.parse.urlencode({"action": "wbgetentities", "ids": hit["id"], "props": "claims", "format": "json"})
        _, body2 = get("https://www.wikidata.org/w/api.php?" + q2)
        claims = json.loads(body2)["entities"][hit["id"]]["claims"].get("P856", [])
        for c in claims:
            url = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if url:
                return url
    return None


def lookup(name):
    today = dt.date.today().isoformat()
    entry = {"revisado": today}
    try:
        if name in WEBS:
            entry.update(scan_site("https://" + WEBS[name]))
            entry["metodo"] = "web oficial"
        else:
            site = wikidata_site(name)
            if not site:
                return name, {**entry, "metodo": "sin datos"}
            entry.update(scan_site(site))
            entry["metodo"] = "wikidata"
    except Exception as exc:
        entry["metodo"] = "web oficial" if name in WEBS else "sin datos"
        entry["error"] = f"{type(exc).__name__}"[:60]
        if name in WEBS:
            entry["web"] = "https://" + WEBS[name]
    return name, entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=60, help="máximo de empresas a revisar por corrida")
    args = ap.parse_args()

    news = json.loads((DATA / "news.json").read_text(encoding="utf-8"))["items"]
    counts = {}
    for it in news:
        for c in it.get("companies", []) + it.get("contractors", []):
            counts[c] = counts.get(c, 0) + 1
    # el directorio completo también se revisa, aunque la empresa todavía no salió en noticias
    for name in WEBS:
        counts.setdefault(name, 0)
    cache = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}

    today = dt.date.today()
    def due(name):
        e = cache.get(name)
        if not e:
            return True
        age = (today - dt.date.fromisoformat(e["revisado"])).days
        found = e.get("emails") or e.get("telefonos") or e.get("portal")
        return age >= (30 if found else 7)

    todo = [n for n in sorted(counts, key=lambda n: -counts[n]) if due(n)][: args.limit]
    print(f"{len(counts)} empresas en el radar, {len(todo)} para revisar")
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name, entry in pool.map(lookup, todo):
            cache[name] = entry
            got = len(entry.get("emails", [])), len(entry.get("telefonos", [])), bool(entry.get("portal"))
            print(f"  {name:<40} {entry['metodo']:<12} mails={got[0]} tel={got[1]} portal={'sí' if got[2] else 'no'} {entry.get('error', '')}")
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
