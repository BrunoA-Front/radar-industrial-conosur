"""Recolecta noticias, las clasifica y actualiza docs/data/news.json.

Uso:
    python scraper/collect.py              # corrida diaria (últimos 3 días)
    python scraper/collect.py --days 30    # carga inicial con más historia
    python scraper/collect.py --fixtures tests/fixtures   # prueba sin internet
"""

import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config  # noqa: E402
from classify import classify, find_companies, normalize  # noqa: E402
from gazetteer import COUNTRY_CENTROIDS, PLACES, resolve_location  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
NEWS_FILE = DATA_DIR / "news.json"
META_FILE = DATA_DIR / "meta.json"
USER_AGENT = "Mozilla/5.0 (compatible; RadarObrasBot/1.0; +https://github.com/BrunoA-Front/radar-industrial-conosur)"

_TAG_RX = re.compile(r"<[^>]+>")
_SPACE_RX = re.compile(r"\s+")


# --- Descarga y lectura de RSS -----------------------------------------------

def http_get(url, retries=2):
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.read()
        except Exception as exc:  # red, timeout, HTTP 4xx/5xx
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise last_error


def clean_text(value):
    value = html.unescape(_TAG_RX.sub(" ", value or ""))
    return _SPACE_RX.sub(" ", value).strip()


def parse_date(value):
    if not value:
        return None
    try:
        d = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def parse_feed(xml_bytes):
    """Lee RSS 2.0 o Atom y devuelve una lista de dicts simples."""
    root = ET.fromstring(xml_bytes)
    items = []
    atom = "{http://www.w3.org/2005/Atom}"
    for node in root.iter("item"):
        source = node.find("source")
        items.append({
            "title": clean_text(node.findtext("title")),
            "url": (node.findtext("link") or "").strip(),
            "summary": clean_text(node.findtext("description")),
            "date": parse_date(node.findtext("pubDate")),
            "source": clean_text(source.text) if source is not None and source.text else None,
        })
    for node in root.iter(atom + "entry"):
        link = node.find(atom + "link")
        items.append({
            "title": clean_text(node.findtext(atom + "title")),
            "url": link.get("href") if link is not None else "",
            "summary": clean_text(node.findtext(atom + "summary") or node.findtext(atom + "content")),
            "date": parse_date(node.findtext(atom + "published") or node.findtext(atom + "updated")),
            "source": None,
        })
    return items


# --- Fuentes -------------------------------------------------------------------

def google_news_url(query, country, days):
    lang = config.COUNTRIES[country]["lang"]
    if lang == "pt":
        hl, ceid = "pt-BR", f"{country}:pt-419"
    else:
        hl, ceid = "es-419", f"{country}:es-419"
    q = f"{query} when:{days}d"
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": hl, "gl": country, "ceid": ceid})


def build_sources(days):
    sources = []
    for code, info in config.COUNTRIES.items():
        queries = list(config.QUERIES_PT if info["lang"] == "pt" else config.QUERIES_ES)
        if code == "AR":
            queries += config.QUERIES_AR_EXTRA
        for i, q in enumerate(queries, 1):
            sources.append({
                "name": f"Google News {info['name']} #{i}",
                "url": google_news_url(q, code, days),
                "country": code,
                "kind": "google",
            })
    for feed in config.SECTOR_FEEDS:
        sources.append({**feed, "kind": "sector"})
    return sources


def strip_source_suffix(title, source):
    """Google News agrega ' - Medio' al final del título."""
    if source and title.endswith(" - " + source):
        return title[: -len(source) - 3].strip()
    m = re.match(r"^(.*\S)\s+-\s+([^-]{2,60})$", title)
    if m and source is None:
        return m.group(1)
    return title


def item_id(title):
    key = re.sub(r"[^a-z0-9 ]", "", normalize(title))[:90]
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def process(raw, feed_country, feed_name):
    source = raw.get("source") or feed_name
    title = strip_source_suffix(raw["title"], raw.get("source"))
    if not title:
        return None
    summary = raw.get("summary") or ""
    # En Google News el resumen repite el título: no aporta
    if normalize(summary).startswith(normalize(title)[:40]):
        summary = ""
    summary = summary[:600]

    companies = find_companies(title, summary)
    tags = classify(title, summary, companies)
    if not tags:
        return None
    location = resolve_location(f"{title} . {summary}", len(title), feed_country)
    if not location:
        return None
    date = raw.get("date") or dt.datetime.now(dt.timezone.utc)
    return {
        "id": item_id(title),
        "title": title,
        "url": raw.get("url"),
        "source": source,
        "date": date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary[:280],
        **location,
        "sectors": tags["sectors"],
        "signals": tags["signals"],
        "score": tags["score"],
        "companies": companies,
    }


# --- Guardado ------------------------------------------------------------------

def load_existing():
    if NEWS_FILE.exists():
        try:
            return json.loads(NEWS_FILE.read_text(encoding="utf-8")).get("items", [])
        except json.JSONDecodeError:
            print("news.json dañado; se empieza de cero", file=sys.stderr)
    return []


def save(items, source_report, started):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    NEWS_FILE.write_text(
        json.dumps({"updated": now, "count": len(items), "items": items}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (DATA_DIR / "lugares.json").write_text(json.dumps(places_index(), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    META_FILE.write_text(
        json.dumps({
            "updated": now,
            "duration_s": round(time.time() - started, 1),
            "total_items": len(items),
            "sources": source_report,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


def places_index():
    """Coordenadas de países y provincias, para ubicar los puntos de cada nivel del mapa."""
    provinces = {f"{p.country}|{p.name}": [p.lat, p.lon] for p in PLACES if p.kind == "prov"}
    countries = {code: {"name": name, "lat": lat, "lon": lon} for code, (name, lat, lon, _) in COUNTRY_CENTROIDS.items()}
    return {"countries": countries, "provinces": provinces}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=config.DEFAULT_DAYS)
    parser.add_argument("--fixtures", help="Carpeta con archivos .xml para probar sin internet (nombre: PAIS_algo.xml)")
    parser.add_argument("--out", help="Carpeta de salida (por defecto docs/data)")
    args = parser.parse_args()
    if args.out:
        global DATA_DIR, NEWS_FILE, META_FILE
        DATA_DIR = Path(args.out)
        NEWS_FILE, META_FILE = DATA_DIR / "news.json", DATA_DIR / "meta.json"
    started = time.time()

    if args.fixtures:
        sources = [
            {"name": p.stem, "url": str(p), "country": p.stem.split("_")[0].upper(), "kind": "fixture"}
            for p in sorted(Path(args.fixtures).glob("*.xml"))
        ]
    else:
        sources = build_sources(args.days)

    existing = {it["id"]: it for it in load_existing()}
    before = len(existing)
    report = []
    for src in sources:
        entry = {"name": src["name"], "country": src["country"], "kind": src["kind"], "ok": True, "fetched": 0, "kept": 0}
        try:
            data = Path(src["url"]).read_bytes() if src["kind"] == "fixture" else http_get(src["url"])
            raw_items = parse_feed(data)
            entry["fetched"] = len(raw_items)
            for raw in raw_items:
                item = process(raw, src["country"], src["name"])
                if item and item["id"] not in existing:
                    existing[item["id"]] = item
                    entry["kept"] += 1
        except Exception as exc:
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"[:200]
        report.append(entry)
        status = "ok" if entry["ok"] else "ERROR " + entry.get("error", "")
        print(f"{src['name']:<40} {entry['fetched']:>4} leídas {entry['kept']:>3} nuevas  {status}")
        if src["kind"] == "google":
            time.sleep(1.5)

    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=config.RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = sorted((it for it in existing.values() if it["date"] >= cutoff), key=lambda it: it["date"], reverse=True)
    save(items, report, started)
    print(f"\nTotal: {len(items)} noticias ({len(items) - before:+d} respecto de la corrida anterior)")
    if all(not r["ok"] for r in report):
        sys.exit("Ninguna fuente respondió")


if __name__ == "__main__":
    main()
