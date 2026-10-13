#!/usr/bin/env python3
"""Build travel-times.json, headways.json and travel-times-compare.json from the official Subte GTFS feed.

Usage: python3 -I build-travel-times.py <subte-gtfs-dir> <subte.json> <out-dir>

Feed (BA Data, Gobierno de la Ciudad de Buenos Aires, licence CC-BY-2.5-AR, attribution required):
  subte-gtfs   https://cdn.buenosaires.gob.ar/datosabiertos/datasets/sbase/subte-gtfs/subte-gtfs-zip.zip   (Subte + Premetro, feed 2014-2019)
Unzip it yourself first (the zip contains another zip called subte_gtfs).

Edge time = arrival at B minus departure from A, median over weekday trips.
Our stations are matched to GTFS stops by coordinates (<= 200 m) on the same line."""
import csv, json, math, os, re, statistics, sys, unicodedata
from collections import defaultdict

sub_dir, subte_p, out_dir = sys.argv[1:4]
MAX_M = 200
DAY = (7 * 3600, 19 * 3600)
SRC_SUBTE = "BA Data subte-gtfs (CC-BY-2.5-AR)"
def rd(d, f):
    with open(os.path.join(d, f), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))

def t2s(t):
    h, m, s = t.strip().split(":"); return int(h) * 3600 + int(m) * 60 + int(s)

def hav_m(a, b):
    r = math.radians
    h = math.sin(r(b[1]-a[1])/2)**2 + math.cos(r(a[1]))*math.cos(r(b[1]))*math.sin(r(b[0]-a[0])/2)**2
    return 12742000 * math.asin(math.sqrt(h))

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", s).split()

def name_ok(a, b):
    na, nb = set(norm(a)) - {"de", "la", "del", "doctor", "dr", "general", "gral"}, set(norm(b)) - {"de", "la", "del", "doctor", "dr", "general", "gral"}
    return bool(na & nb)

# ---- our stations ----
subte = json.load(open(subte_p))
ours = {}   # id -> (lonlat, name, line key)
for f in subte["features"]:
    if f["geometry"]["type"] == "Point":
        p = f["properties"]
        ours[p["id"]] = (tuple(f["geometry"]["coordinates"]), p["name"], p["line"])
def key_line(i):
    return ("premetro-" if i.startswith("premetro") else i.split("-")[0] + "-") + i.split("-")[1]
by_line = defaultdict(list)
for i in ours: by_line[key_line(i)].append(i)
for v in by_line.values(): v.sort()
# A branched line numbers its main run first and the branch after it: the first stop of a branch hangs off the fork,
# not off the stop numbered before it. Premetro E2: 01-16 main run to General Savio, 17-18 Ana Díaz to Centro Cívico
# Lugano leaving from Pola (12); there is no track General Savio - Ana Díaz. Same table as LINE_FORKS in the app.
LINE_FORKS = {"premetro-E2": {17: 12}}
def seq(i): return int(re.search(r"(\d+)$", i).group(1))
def line_pairs(lk, ids):
    """neighbouring stops of one line as (stop before, stop); ids sorted by number"""
    forks = LINE_FORKS.get(lk, {})
    pairs = []
    for n in range(1, len(ids)):
        f = forks.get(seq(ids[n]))
        a = next((i for i in ids if seq(i) == f), None) if f is not None else ids[n - 1]
        if a: pairs.append((a, ids[n]))
    return pairs

def match(stop, lines, name=""):
    """same normalized name within 600 m wins; else nearest of our stations on the given lines within MAX_M"""
    best = None
    for lk in lines:
        for i in by_line.get(lk, []):
            d = hav_m(ours[i][0], stop)
            if name and norm(ours[i][1]) == norm(name) and d <= 600: return (d, i)
            if d <= MAX_M and (best is None or d < best[0]): best = (d, i)
    return best

unmatched_gtfs, name_mismatch = [], []
gtfs_ll = {}
edge_samples = defaultdict(list)   # (a,b sorted) -> [seconds]
dwell = defaultdict(list)          # station -> [seconds]
used_gtfs = defaultdict(set)       # our id -> gtfs stop names
covered_lines = set()

def process(feed_dir, route_lines, src, trip_filter, daytime):
    stops = {r["stop_id"]: r for r in rd(feed_dir, "stops.txt")}
    trips = {r["trip_id"]: r for r in rd(feed_dir, "trips.txt") if trip_filter(r)}
    seqs = defaultdict(list)
    for r in rd(feed_dir, "stop_times.txt"):
        if r["trip_id"] in trips: seqs[r["trip_id"]].append(r)
    ntrips = 0
    for tid, rows in seqs.items():
        lines = route_lines(trips[tid]["route_id"])
        if not lines: continue
        rows.sort(key=lambda r: int(r["stop_sequence"]))
        seq = []
        for r in rows:
            s = stops[r["stop_id"]]; ll = (float(s["stop_lon"]), float(s["stop_lat"]))
            mm = match(ll, lines, s["stop_name"])
            gtfs_ll[r["stop_id"]] = ll
            if mm is None:
                unmatched_gtfs.append((src, "/".join(lines), s["stop_name"], r["stop_id"])); continue
            if not name_ok(s["stop_name"], ours[mm[1]][1]):
                name_mismatch.append((s["stop_name"], ours[mm[1]][1], round(mm[0])))
            seq.append((mm[1], t2s(r["arrival_time"]), t2s(r["departure_time"])))
            used_gtfs[mm[1]].add(s["stop_name"])
        for (a, _, da), (b, ab, _) in zip(seq, seq[1:]):
            if a == b: continue
            if daytime and not (DAY[0] <= da <= DAY[1]): continue
            edge_samples[tuple(sorted((a, b)))].append((ab - da, src))
        if not daytime:
            for a, aa, da in seq[1:-1]: dwell[a].append(da - aa)
        ntrips += 1
    return trips, seqs, stops

# ---- subte + premetro ----
SUBTE_ROUTES = {"LineaA": ["subte-A"], "LineaB": ["subte-B"], "LineaC": ["subte-C"], "LineaD": ["subte-D"],
                "LineaE": ["subte-E"], "LineaH": ["subte-H"], "PM-Civico": ["premetro-E2"], "PM-Savio": ["premetro-E2"]}
process(sub_dir, lambda r: SUBTE_ROUTES.get(r), SRC_SUBTE, lambda t: t["service_id"] == "5", daytime=False)

# ---- travel-times.json ----
def edge_src(a): return SRC_SUBTE
out = []
for (a, b), vals in sorted(edge_samples.items()):
    secs = [v for v, _ in vals]
    med = statistics.median(secs)
    row = {"line": key_line(a).split("-", 1)[1] if not a.startswith("premetro") else "E2", "from": a, "to": b,
           "minutes": round(med / 60, 1), "source": edge_src(a), "n": len(secs)}
    d = dwell.get(b, []) + dwell.get(a, [])
    row["dwell_min"] = round(statistics.median(d) / 60, 1) if d else None
    out.append(row)

# ---- headways ----
heads = []
freq = rd(sub_dir, "frequencies.txt"); strips = {r["trip_id"]: r for r in rd(sub_dir, "trips.txt")}
bylr = defaultdict(lambda: defaultdict(list))
for fr in freq:
    t = strips.get(fr["trip_id"])
    if not t or t["service_id"] != "5": continue
    s, e = max(t2s(fr["start_time"]), DAY[0]), min(t2s(fr["end_time"]), DAY[1])
    if e > s: bylr[t["route_id"]][t["direction_id"]].append((e - s, int(fr["headway_secs"])))
for route, dirs in bylr.items():
    per = {}
    for d, items in dirs.items():
        vals = [h for w, h in items for _ in range(max(1, w // 600))]   # weight by duration
        per[d] = round(statistics.median(vals) / 60, 1)
    line = SUBTE_ROUTES[route][0].split("-", 1)[1] if route.startswith("Linea") else "E2"
    m_ = round(statistics.median(per.values()), 1)
    entry = next((h for h in heads if h["line"] == line), None)
    if entry: entry["minutes"] = round(statistics.median([entry["minutes"], m_]), 1); entry["by_direction"].update({f"{route}:{d}": v for d, v in per.items()})
    else: heads.append({"line": line, "minutes": m_, "by_direction": {f"{route}:{d}": v for d, v in per.items()}, "window": "weekday 07:00-19:00", "source": SRC_SUBTE, "kind": "frequencies.txt"})

# ---- interpolation: our stations that no GTFS trip serves (stop listed but unused, or missing) ----
in_edges = {i for e in edge_samples for i in e}
for lk, ids in by_line.items():
    idx = {i: n for n, i in enumerate(ids)}
    for a, b in line_pairs(lk, ids):
        n = idx[a]
        if idx[b] != n + 1: continue  # a branch start: the linear span below does not apply (12-17 has feed times)
        if tuple(sorted((a, b))) in edge_samples: continue
        # smallest observed edge on this line spanning the pair
        spans = [(idx[y] - idx[x], x, y) for (x, y) in edge_samples if x in idx and y in idx and idx[x] <= n and idx[y] >= n + 1]
        if not spans: continue
        _, x, y = min(spans)
        seg = ids[idx[x]: idx[y] + 1]
        d = [hav_m(ours[u][0], ours[v][0]) for u, v in zip(seg, seg[1:])]
        total = statistics.median([v for v, _ in edge_samples[(x, y)]])
        known = sum(statistics.median([v for v, _ in edge_samples[tuple(sorted((u, v2))) ]]) for u, v2 in zip(seg, seg[1:]) if tuple(sorted((u, v2))) in edge_samples)
        gap = [(u, v2, dd) for (u, v2), dd in zip(zip(seg, seg[1:]), d) if tuple(sorted((u, v2))) not in edge_samples]
        rest = max(total - known, 0)
        sd = sum(dd for _, _, dd in gap)
        for u, v2, dd in gap:
            if tuple(sorted((u, v2))) == (a, b) or tuple(sorted((u, v2))) == tuple(sorted((a, b))):
                sec = rest * dd / sd if sd else 0
                if sec < 30: sec = 30
                out.append({"line": "E2" if a.startswith("premetro") else key_line(a).split("-", 1)[1], "from": a, "to": b, "minutes": round(sec / 60, 1),
                            "source": edge_src(a) + ", interpolated by distance between " + ours[x][1] + " and " + ours[y][1] + " (" + ('no trip stops at ' + ours[a if a not in in_edges else b][1] if (a not in in_edges or b not in in_edges) else 'skipped by the feed in one direction') + ")", "n": 0, "interpolated": True})
                edge_samples[tuple(sorted((a, b)))] = [(sec, "interp")]

out.sort(key=lambda r: (r["from"], r["to"]))

# ---- compare with the distance estimate used before the feed ----
SPEED_KMH = 25
compare = []
for row in out:
    w = round(hav_m(ours[row["from"]][0], ours[row["to"]][0]) / 1000 / SPEED_KMH * 60, 1)
    compare.append({"line": row["line"], "from": row["from"], "to": row["to"], "from_name": ours[row["from"]][1], "to_name": ours[row["to"]][1],
                    "was": w, "now": row["minutes"], "diff": round(row["minutes"] - w, 1), "was_basis": "lib/route.ts: distance at 25 km/h"})
big = [c for c in compare if abs(c["diff"]) > 1]

# ---- coverage: our consecutive pairs with no GTFS time ----
have = set(edge_samples)
missing = []
for lk, ids in by_line.items():
    for a, b in line_pairs(lk, ids):
        if tuple(sorted((a, b))) not in have: missing.append({"line": lk.split("-", 1)[1], "from": a, "to": b, "from_name": ours[a][1], "to_name": ours[b][1]})
total_pairs = sum(len(line_pairs(lk, v)) for lk, v in by_line.items())
unm_ours = sorted(i for i in ours if i not in used_gtfs)

os.makedirs(out_dir, exist_ok=True)
json.dump({"attribution": "Schedule data: Gobierno de la Ciudad de Buenos Aires (BA Data), CC-BY-2.5-AR", "edges": out}, open(os.path.join(out_dir, "travel-times.json"), "w"), ensure_ascii=False, indent=1)
json.dump({"attribution": "Schedule data: Gobierno de la Ciudad de Buenos Aires (BA Data), CC-BY-2.5-AR", "headways": heads}, open(os.path.join(out_dir, "headways.json"), "w"), ensure_ascii=False, indent=1)
json.dump({"changed_over_1_min": big, "no_gtfs_time": missing, "our_stations_without_gtfs_stop": unm_ours,
           "gtfs_stops_not_matched_near_scheme": sorted(set(u for u in unmatched_gtfs if any(hav_m(ours[i][0], gtfs_ll[u[3]]) <= 1500 for i in ours))), "gtfs_stops_outside_scheme_count": len(set(unmatched_gtfs)), "name_mismatch_on_coord_match": sorted(set(name_mismatch))},
          open(os.path.join(out_dir, "travel-times-compare.json"), "w"), ensure_ascii=False, indent=1)
print(f"edges with time: {len(out)}; our consecutive pairs: {total_pairs}; of them without GTFS time: {len(missing)}")
print(f"differences > 1 min: {len(big)} of {len(compare)}")
