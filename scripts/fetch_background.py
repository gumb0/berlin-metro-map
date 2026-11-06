#!/usr/bin/env python3
"""Fetch background shapes (water, parks, city boundary) from OpenStreetMap
via Nominatim and write data/background.json.

Usage: python3 scripts/fetch_background.py
Respects Nominatim's limit of one request per second.
"""
import json, os, time, urllib.parse, urllib.request

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "background.json"))
UA = "berlin-ubahn-map-prototype/0.1"
# (query, kind, accepted OSM categories)
FEATURES = [
    ("Berlin", "boundary", {"boundary"}),
    ("Havel, Berlin", "river", {"waterway"}),
    ("Landwehrkanal", "river", {"waterway"}),
    ("Berlin-Spandauer Schifffahrtskanal", "river", {"waterway"}),
    ("Teltowkanal", "river", {"waterway"}),
    ("Tegeler See", "lake", {"natural", "water"}),
    ("Großer Wannsee", "lake", {"natural", "water"}),
    ("Schlachtensee", "lake", {"natural", "water"}),
    ("Plötzensee, Berlin", "lake", {"natural", "water"}),
    ("Großer Tiergarten", "park", {"leisure", "landuse", "boundary"}),
    ("Tempelhofer Feld", "park", {"leisure", "landuse", "aeroway"}),
    ("Volkspark Friedrichshain", "park", {"leisure"}),
    ("Treptower Park", "park", {"leisure"}),
    ("Plänterwald", "park", {"landuse", "natural", "leisure"}),
    ("Volkspark Hasenheide", "park", {"leisure"}),
    ("Viktoriapark, Berlin", "park", {"leisure"}),
    ("Görlitzer Park", "park", {"leisure"}),
    ("Mauerpark", "park", {"leisure"}),
    ("Volkspark Humboldthain", "park", {"leisure"}),
    ("Volkspark Rehberge", "park", {"leisure"}),
    ("Volkspark Jungfernheide", "park", {"leisure"}),
    ("Tegeler Forst", "forest", {"landuse", "natural", "boundary"}),
    ("Tierpark Berlin", "park", {"tourism", "leisure"}),
    ("Gärten der Welt", "park", {"leisure", "tourism"}),
    ("Britzer Garten", "park", {"leisure"}),
    ("Volkspark Wuhlheide", "park", {"leisure", "landuse"}),
    ("Olympiapark Berlin", "park", {"leisure", "landuse"}),
    ("Volkspark Wilmersdorf", "park", {"leisure"}),
    ("Volkspark Mariendorf", "park", {"leisure"}),
    # Features that search does not find reliably are fetched by OSM id.
    ("R390274", "river", "Spree"),
    ("R412171", "river", "Neuköllner Schiffahrtskanal"),
    ("R3410", "forest", "Grunewald"),
    ("W815670035", "park", "Schlosspark Charlottenburg"),
    ("W125194752", "park", "Botanischer Garten"),
]
BBOX = (13.05, 52.33, 13.80, 52.70)   # lon/lat window kept in the output

out = []
for q, kind, cats in FEATURES:
    by_id = isinstance(cats, str)
    if by_id:
        url = "https://nominatim.openstreetmap.org/lookup?" + urllib.parse.urlencode(
            {"osm_ids": q, "format": "jsonv2", "polygon_geojson": 1, "polygon_threshold": 0.0002})
    else:
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": q, "format": "jsonv2", "polygon_geojson": 1, "polygon_threshold": 0.0002, "limit": 6,
             "viewbox": "13.05,52.70,13.80,52.33", "bounded": 1})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        res = json.load(urllib.request.urlopen(req, timeout=60))
    except Exception as e:
        print("FAILED", q, e)
        time.sleep(1.2)
        continue
    pick = None
    for r in res:
        g = r.get("geojson", {})
        if (by_id or r["category"] in cats) and g.get("type") not in (None, "Point"):
            pick = r
            break
    if pick:
        out.append({"name": cats if by_id else q.split(",")[0], "kind": kind, "osm": f'{pick["osm_type"]}/{pick["osm_id"]}',
                    "geometry": pick["geojson"]})
        print("ok  ", q, "->", pick["category"], pick["type"], pick["geojson"]["type"])
    else:
        print("none", q, [(r["category"], r["type"], r.get("geojson", {}).get("type")) for r in res])
    time.sleep(1.2)


def rnd(c):
    return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 5), round(c[1], 5)]


def inside(p):
    return BBOX[0] <= p[0] <= BBOX[2] and BBOX[1] <= p[1] <= BBOX[3]


def clip_lines(lines):
    """Split line strings into the runs that lie inside BBOX."""
    res = []
    for ln in lines:
        run = []
        for p in ln:
            if inside(p):
                run.append(p)
            else:
                if len(run) > 1:
                    res.append(run)
                run = []
        if len(run) > 1:
            res.append(run)
    return res


for f in out:
    g = f["geometry"]
    if g["type"] in ("LineString", "MultiLineString"):
        parts = clip_lines([g["coordinates"]] if g["type"] == "LineString" else g["coordinates"])
        g["type"], g["coordinates"] = "MultiLineString", parts
    g["coordinates"] = rnd(g["coordinates"]) if g["coordinates"] else []
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump({"source": "OpenStreetMap contributors (ODbL), via Nominatim", "features": out}, fh,
              ensure_ascii=False, separators=(",", ":"))
print("wrote", OUT, os.path.getsize(OUT), "bytes,", len(out), "features")
