"""Genera los mapas base de la web a partir de Natural Earth (dominio público).

  docs/data/paises.geojson      -> países de Latinoamérica (México hacia el sur)
  docs/data/provincias.geojson  -> provincias/estados/regiones de AR, CL, BO, PY, UY y BR

Se corre una sola vez (el workflow lo hace si faltan los archivos):
    python scraper/build_geo.py
"""

import json
import math
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data"
BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
COUNTRIES_URL = BASE + "ne_50m_admin_0_countries.geojson"
PROVINCES_URL = BASE + "ne_10m_admin_1_states_provinces.geojson"
FOCUS = {"AR", "CL", "BO", "PY", "UY", "BR"}


def download(url):
    print("Descargando", url)
    req = urllib.request.Request(url, headers={"User-Agent": "radar-industrial-conosur"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())


# --- Simplificación (Douglas-Peucker) ------------------------------------------

def _perp_dist(p, a, b):
    if a == b:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    (x, y), (x1, y1), (x2, y2) = p, a, b
    return abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / math.hypot(x2 - x1, y2 - y1)


def simplify_line(points, tol):
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        best, idx = 0.0, None
        for i in range(start + 1, end):
            d = _perp_dist(points[i], points[start], points[end])
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol:
            keep[idx] = True
            stack.append((start, idx))
            stack.append((idx, end))
    return [p for p, k in zip(points, keep) if k]


def simplify_ring(ring, tol):
    pts = [(round(x, 3), round(y, 3)) for x, y in ring[:-1]] if len(ring) > 3 else [(round(x, 3), round(y, 3)) for x, y in ring]
    out = simplify_line(pts, tol)
    if len(out) < 3:
        return None
    out.append(out[0])
    return [list(p) for p in out]


def ring_area(ring):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:]))) / 2


def simplify_geometry(geom, tol, min_area):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    out = []
    for poly in polys:
        outer = simplify_ring(poly[0], tol)
        if not outer or ring_area(outer) < min_area:
            continue
        holes = [h for h in (simplify_ring(r, tol) for r in poly[1:]) if h and ring_area(h) >= min_area]
        out.append([outer] + holes)
    if not out:
        return None
    return {"type": "MultiPolygon", "coordinates": out}


def save(name, features):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{path.relative_to(ROOT)}: {len(features)} polígonos, {path.stat().st_size // 1024} KB")


def build_countries():
    data = download(COUNTRIES_URL)
    feats = []
    for f in data["features"]:
        p = f["properties"]
        if p.get("REGION_UN") != "Americas" or p.get("SUBREGION") == "Northern America":
            continue
        iso = p.get("ISO_A2_EH") or p.get("ISO_A2")
        geom = simplify_geometry(f["geometry"], 0.03, 0.02)
        if not geom:
            continue
        feats.append({
            "type": "Feature",
            "properties": {"iso": iso, "name": p.get("NAME_ES") or p.get("NAME"), "focus": iso in FOCUS},
            "geometry": geom,
        })
    save("paises.geojson", feats)


def build_provinces():
    data = download(PROVINCES_URL)
    feats = []
    for f in data["features"]:
        p = f["properties"]
        iso = p.get("iso_a2")
        if iso not in FOCUS:
            continue
        geom = simplify_geometry(f["geometry"], 0.02, 0.005)
        if not geom:
            continue
        feats.append({
            "type": "Feature",
            "properties": {"iso": iso, "name": p.get("name") or p.get("name_es")},
            "geometry": geom,
        })
    # tono alternado para que se distingan provincias vecinas
    for i, f in enumerate(sorted(feats, key=lambda f: (f["properties"]["iso"], f["properties"]["name"] or ""))):
        f["properties"]["tone"] = i % 4
    save("provincias.geojson", feats)


if __name__ == "__main__":
    only_missing = "--if-missing" in sys.argv
    if not (only_missing and (OUT / "paises.geojson").exists()):
        build_countries()
    if not (only_missing and (OUT / "provincias.geojson").exists()):
        build_provinces()
