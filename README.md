# Global Metro Map: open map data

Open data behind the Global Metro Map app. This repository holds only the
parts of the app's dataset that are derived from OpenStreetMap, published so
that the Open Database License (ODbL) 1.0 share-alike terms are met.

The current dataset covers Buenos Aires (the Subte, its neighbourhoods, and
station names).

## Attribution

Contains information from OpenStreetMap: **© OpenStreetMap contributors**.
See https://www.openstreetmap.org/copyright.

## License

The data is available under the Open Database License (ODbL) 1.0
(https://opendatacommons.org/licenses/odbl/1-0/). The full text is in
[LICENSE](LICENSE). In short: you may copy, share, and adapt the data, you must
credit OpenStreetMap contributors, and if you publish an adapted database you
must offer it under the same license.

Some station names come from Wikidata, whose structured data is CC0 1.0. Those
rows are marked in the `source` field (see below).

## Files

| File | Contents |
|---|---|
| `subte.json` | GeoJSON FeatureCollection: metro line geometries and station points |
| `districts.json` | GeoJSON FeatureCollection: neighbourhood (barrio) polygons |
| `rail.json` | Rail (Trenes Argentinos) stations, segments and walking links, derived from OpenStreetMap |
| `travel-times.json` | Ride minutes between neighbouring stations, from the BA Data GTFS feeds (rail calibrated to 2026 timetables); built by `scripts/build-travel-times.py` |
| `headways.json` | Typical weekday gap between trains per line, same source |
| `travel-times-compare.json` | Old estimate against feed value, coverage gaps |
| `names.json` | Localised display names (es, en, ru) for stations, districts, and map labels |

Every file starts with `license`, `attribution`, and `license_url` fields.
Coordinates are WGS84 `[longitude, latitude]`.

### subte.json

- `LineString` features: one per metro line. Properties: `line` (A, B, C, D,
  E, E2, H) and `colour` (hex).
- `Point` features: stations. Properties: `id` (for example `subte-A-01`),
  `name`, `line`, `colour`.

### districts.json

`MultiPolygon` features. Properties: `id` (OSM relation id), `name`, and
`label` (`[lon, lat]` point where the name is placed).

### names.json

An object `names` keyed by feature id. The key prefix tells the kind:
`subte-` stations, `barrio-` districts, `label-` map labels, and `train-`,
`premetro-`, `landmark-` for other transit and place names. Each value:

```json
{
  "es": "Plaza de Mayo",
  "en": "Plaza de Mayo",
  "ru": "Площадь Мая",
  "translit": false,
  "source": "Wikidata Q3232735"
}
```

- `source` says where the name came from: `Wikidata Q...` (CC0), `OSM name`,
  `composite of station labels`, or `manual` (hand cleaning). A Wikidata value
  can end in `(no ru label)`, as in `Wikidata Q8878157 (no ru label)`. That
  means the item has no Russian label in Wikidata, so the `ru` field was
  filled in separately and is a transliteration.
- `translit: true` means the Russian name is a transliteration, not an
  official name.

## How the data was made

1. Metro lines, stations, and neighbourhood boundaries were taken from
   OpenStreetMap. Each district `id` is an OSM relation id.
2. The geometry was cleaned for map display, and the properties were cut
   down to the fields listed above.
3. Names come from Wikidata labels where they exist. Where Wikidata has no
   usable label, the OSM `name` tag is used. A small number of names were
   cleaned by hand because the two sources were missing or disagreed. The
   `source` field of each row records which of these was used.
4. Russian names without a Wikidata label are transliterations and are marked
   with `translit: true`.

Errors and corrections are welcome by email.

## Usage

```js
const subte = await (await fetch("subte.json")).json();
const stations = subte.features.filter(f => f.geometry.type === "Point");
const names = (await (await fetch("names.json")).json()).names;
console.log(names[stations[0].properties.id].en);
```

The files load in any GeoJSON tool (QGIS, geojson.io, Leaflet, MapLibre).
When you use or redistribute them, keep the attribution above and the ODbL
terms.

## What is not here

The Global Metro Map application code, design, and design tokens are
proprietary and are not part of this repository. Only the OpenStreetMap-derived
data is published here.

## Maintainer and contact

Maintained by SupafastTech. Contact: contact@globalmetromap.com

## Schedule data (not OpenStreetMap)

`travel-times.json`, `headways.json` and `travel-times-compare.json` are derived from the
open GTFS feeds of the Government of the City of Buenos Aires (BA Data), published under
CC BY 2.5 AR (https://creativecommons.org/licenses/by/2.5/ar/). Attribution: Gobierno de la
Ciudad de Buenos Aires, BA Data. Rail times are scaled with per-line coefficients to match
the 2026 timetables of Trenes Argentinos; rows say so in `source`.
