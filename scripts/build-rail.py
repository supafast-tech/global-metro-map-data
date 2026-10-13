#!/usr/bin/env python3
"""Build rail.json (Buenos Aires commuter rail) from Overpass output + the app scheme.
Usage: python3 -I build-rail.py <raw/rail-relations.json> <scheme.json> <subte.json> <names.json> <out rail.json>
Only stations drawn in scheme.json are kept (scheme station name = match key).
Data: (c) OpenStreetMap contributors, ODbL 1.0."""
import json, sys, math, unicodedata

raw_p, scheme_p, subte_p, names_p, out_p = sys.argv[1:6]
raw = json.load(open(raw_p)); scheme = json.load(open(scheme_p))
subte = json.load(open(subte_p)); subte_names = json.load(open(names_p))["names"]

SPEED_KMH = 30      # rail average incl. stops (estimate)
WALK_M_PER_MIN = 75 # 4.5 km/h
DETOUR = 1.3        # street detour over straight line

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()

def hav_m(a, b):  # a,b = (lon, lat)
    r = math.radians
    h = math.sin(r(b[1]-a[1])/2)**2 + math.cos(r(a[1]))*math.cos(r(b[1]))*math.sin(r(b[0]-a[0])/2)**2
    return 12742000*math.asin(math.sqrt(h))

# line key -> (display name, colour (manual), operator, relation id(s) to look up stops in)
LINES = {
  "Mitre":        ("Mitre",         "#2A7FC1", "Trenes Argentinos", [4572178, 2953074]),
  "BelgranoNorte":("Belgrano Norte","#C8102E", "Ferrovías",         [129384]),
  "SanMartin":    ("San Martín",    "#1F4E9C", "Trenes Argentinos", [1894770]),
  "Sarmiento":    ("Sarmiento",     "#2E9E5B", "Trenes Argentinos", [1878867]),
  "Urquiza":      ("Urquiza",       "#E8742A", "Metrovías",         [1889579]),
  "BelgranoSur":  ("Belgrano Sur",  "#6C4B9E", "Trenes Argentinos", [3443503]),
  "Roca":         ("Roca",          "#F2C230", "Trenes Argentinos", [3737975]),
}
# Ordered stops as drawn in scheme.json: (scheme name, OSM name if different)
ORDER = {
  "Mitre": [("Retiro",), ("Lisandro de la Torre",), ("Belgrano R",), ("Núñez",), ("Rivadavia",)],
  "BelgranoNorte": [("Retiro",), ("Saldías",), ("Ciudad Universitaria",)],
  "SanMartin": [("Retiro",), ("Palermo",), ("Villa Crespo",), ("La Paternal",), ("Villa del Parque",), ("Devoto",)],
  "Sarmiento": [("Once de Septiembre", "Once"), ("Caballito",), ("Flores",), ("Floresta",), ("Villa Luro",), ("Liniers",)],
  "Urquiza": [("Federico Lacroze",), ("José Artigas",), ("Pedro Arata",), ("Doctor Francisco Beiró",), ("El Libertador",), ("Antonio Devoto",)],
  "BelgranoSur": [("Doctor Antonio Sáenz",), ("Villa Soldati",), ("Presidente Illia",), ("Lugano", "Villa Lugano")],
  "Roca": [("Constitución", "Plaza Constitución")],
}
RU = {  # manual transliteration / usual Russian spelling; flagged translit
  "Retiro": "Ретиро", "Lisandro de la Torre": "Лисандро де ла Торре", "Belgrano R": "Бельграно Р",
  "Núñez": "Нуньес", "Rivadavia": "Ривадавия", "Saldías": "Сальдиас", "Ciudad Universitaria": "Сьюдад-Университариа",
  "Palermo": "Палермо", "Villa Crespo": "Вилья-Креспо", "La Paternal": "Ла-Патерналь", "Villa del Parque": "Вилья-дель-Парке",
  "Devoto": "Девото", "Once de Septiembre": "Онсе-де-Септьембре", "Caballito": "Кабальито", "Flores": "Флорес",
  "Floresta": "Флореста", "Villa Luro": "Вилья-Луро", "Liniers": "Линьерс", "Federico Lacroze": "Федерико Лакросе",
  "José Artigas": "Хосе Артигас", "Pedro Arata": "Педро Арата", "Doctor Francisco Beiró": "Доктор Франсиско Бейро",
  "El Libertador": "Эль-Либертадор", "Antonio Devoto": "Антонио Девото", "Doctor Antonio Sáenz": "Доктор Антонио Саэнс",
  "Villa Soldati": "Вилья-Солдати", "Presidente Illia": "Президенте Ильиа", "Lugano": "Лугано", "Constitución": "Конститусьон",
}
RU_LINE = {"Mitre": "Митре", "BelgranoNorte": "Бельграно-Норте", "SanMartin": "Сан-Мартин", "Sarmiento": "Сармьенто",
           "Urquiza": "Уркиса", "BelgranoSur": "Бельграно-Сур", "Roca": "Рока"}

nodes = {e["id"]: e for e in raw["elements"] if e["type"] == "node"}
rels = {e["id"]: e for e in raw["elements"] if e["type"] == "relation"}

def find_node(rel_ids, osm_name):
    for rid in rel_ids:
        for m in rels[rid]["members"]:
            n = nodes.get(m["ref"]) if m["type"] == "node" else None
            if n and norm(n["tags"].get("name", "")) == norm(osm_name):
                return n, rid
    return None, None

scheme_names = {s["name"] for s in scheme["stations"]}
scheme_rail = [s["name"] for s in scheme["stations"] if s["kind"] == "rail"]

features, names, matched, problems = [], {}, set(), []
station_pts = {}  # id -> (lonlat, scheme name, line)
for key, stops in ORDER.items():
    disp, colour, op, rids = LINES[key]
    coords = []
    for i, st in enumerate(stops, 1):
        sname = st[0]; oname = st[1] if len(st) > 1 else st[0]
        if sname not in scheme_names:
            problems.append(f"{sname}: not in scheme.json"); continue
        n, rid = find_node(rids, oname)
        if not n:
            problems.append(f"{key}/{sname}: no OSM stop named {oname!r}"); continue
        sid = f"train-{key}-{i:02d}"
        ll = (round(n["lon"], 6), round(n["lat"], 6))
        coords.append(list(ll))
        matched.add(sname)
        features.append({"type": "Feature",
            "properties": {"id": sid, "name": sname, "line": key, "colour": colour, "network": "rail",
                           "osm_node": n["id"], "osm_relation": rid},
            "geometry": {"type": "Point", "coordinates": list(ll)}})
        station_pts[sid] = (ll, sname, key)
        names[sid] = {"es": sname, "en": sname, "ru": RU[sname], "translit": True, "source": "OSM name; ru manual transliteration"}
    features.insert(0, {"type": "Feature",
        "properties": {"line": key, "colour": colour, "network": "rail", "name": disp, "operator": op},
        "geometry": {"type": "LineString", "coordinates": coords}})

# Segments between consecutive drawn stops (estimated time)
segments = []
for key in ORDER:
    ids = sorted(i for i in station_pts if station_pts[i][2] == key)
    for a, b in zip(ids, ids[1:]):
        d = hav_m(station_pts[a][0], station_pts[b][0])
        segments.append({"line": key, "from": a, "to": b, "km": round(d/1000, 2),
                         "minutes": max(1, round(d/1000/SPEED_KMH*60)), "estimated": True})

# Interchanges with subte/premetro: only those drawn in scheme.json (walking links / transfer dots)
subte_pts = [(f["properties"], tuple(f["geometry"]["coordinates"])) for f in subte["features"] if f["geometry"]["type"] == "Point"]
def sp(es, line):
    for p, c in subte_pts:
        if p["line"] == line and subte_names.get(p["id"], {}).get("es", p["name"]) == es:
            return p["id"], c
    problems.append(f"subte {line}/{es} not found"); return None, None
WANT = [  # (rail scheme name, rail lines, subte es name, subte line)
  ("Retiro", ["Mitre", "BelgranoNorte", "SanMartin"], "Retiro", "C"),
  ("Retiro", ["Mitre", "BelgranoNorte", "SanMartin"], "Retiro", "E"),
  ("Constitución", ["Roca"], "Constitución", "C"),
  ("Once de Septiembre", ["Sarmiento"], "Plaza Miserere", "A"),
  ("Once de Septiembre", ["Sarmiento"], "Once - 30 de Diciembre", "H"),
  ("Federico Lacroze", ["Urquiza"], "Federico Lacroze", "B"),
  ("Palermo", ["SanMartin"], "Palermo", "D"),
  ("Presidente Illia", ["BelgranoSur"], "Presidente Illia", "E2"),
]
links = []
for rname, rlines, sname, sline in WANT:
    sid, sc = sp(sname, sline)
    if not sid: continue
    for rid_, (ll, nm, ln) in station_pts.items():
        if nm == rname and ln in rlines:
            d = hav_m(ll, sc)
            links.append({"from": rid_, "to": sid, "type": "walk", "meters": round(d),
                          "minutes": max(2, math.ceil(d*DETOUR/WALK_M_PER_MIN) + 1), "estimated": True})
# Rail-rail interchange inside the same station (Retiro): same station, handled by distance in app; list them
rr = []
for a in station_pts:
    for b in station_pts:
        if a < b and station_pts[a][1] == station_pts[b][1] and station_pts[a][2] != station_pts[b][2]:
            d = hav_m(station_pts[a][0], station_pts[b][0])
            rr.append({"from": a, "to": b, "type": "walk", "meters": round(d), "minutes": max(2, math.ceil(d*DETOUR/WALK_M_PER_MIN) + 1), "estimated": True})
links += rr

# undrawn-but-near candidates (reported, not included)
cand = []
for rid_, (ll, nm, ln) in station_pts.items():
    for p, c in subte_pts:
        d = hav_m(ll, c)
        if d < 500 and not any(l["from"] == rid_ and l["to"] == p["id"] for l in links) and (nm not in ("Retiro",)):
            cand.append((nm, ln, p["name"], p["line"], round(d)))

unmatched = [n for n in scheme_rail if n not in matched]
out = {"license": "ODbL-1.0", "attribution": "© OpenStreetMap contributors",
       "license_url": "https://opendatacommons.org/licenses/odbl/1-0/", "type": "FeatureCollection",
       "network": "rail",
       "estimates": {"speed_kmh": SPEED_KMH, "walk_m_per_min": WALK_M_PER_MIN, "walk_detour": DETOUR,
                     "note": "segment and walking times are estimates from straight-line distance, not timetables"},
       "line_names": {k: {"es": v[0], "en": v[0], "ru": RU_LINE[k]} for k, v in LINES.items()},
       "features": features, "segments": segments, "links": links, "names": names}
json.dump(out, open(out_p, "w"), ensure_ascii=False, separators=(",", ":"))
print("points", sum(1 for f in features if f["geometry"]["type"] == "Point"),
      "unique stations", len({v[1] for v in station_pts.values()}))
print("scheme rail", len(scheme_rail), "unmatched", unmatched, "problems", problems)
print("links", len(links)); [print(l) for l in links]
print("undrawn candidates <500m", cand)
