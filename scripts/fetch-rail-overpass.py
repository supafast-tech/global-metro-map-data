#!/usr/bin/env python3
"""Fetch OSM data for Buenos Aires commuter rail (Overpass). Output: raw/rail-relations.json.
Usage: python3 -I fetch-rail-overpass.py <out_dir>
Budget: at most MAX_REQ requests, 1 s pause between them. ODbL data, (c) OpenStreetMap contributors."""
import json, sys, time, urllib.request, urllib.parse, os

MAX_REQ = 12
URLS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
# Chosen route relations (one direction per branch, commuter service).
RELS = {4572178: "Mitre", 2953074: "Mitre (Belgrano R branch)", 129384: "Belgrano Norte", 1894770: "San Martín", 1878867: "Sarmiento",
        1889579: "Urquiza", 3443503: "Belgrano Sur", 3737975: "Roca"}
used = 0

def q(data):
    global used
    for attempt in range(MAX_REQ):
        if used >= MAX_REQ:
            raise SystemExit("request budget exhausted")
        used += 1
        time.sleep(1)
        url = URLS[attempt % len(URLS)]
        req = urllib.request.Request(url, urllib.parse.urlencode({"data": data}).encode(),
                                     {"User-Agent": "supafast-gmm/1.0 (admin@supafast.tech)"})
        try:
            body = urllib.request.urlopen(req, timeout=150).read()
            return json.loads(body)
        except Exception as e:
            print("retry", attempt, type(e).__name__, file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise SystemExit("failed")

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
ids = ",".join(map(str, RELS))
d = q(f"[out:json][timeout:120];rel(id:{ids})->.r;.r out body;node(r.r);out body;")
json.dump(d, open(os.path.join(out, "rail-relations.json"), "w"), ensure_ascii=False)
print("elements", len(d["elements"]), "requests", used)
