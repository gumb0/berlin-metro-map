# Berlin U-Bahn map

An interactive map of the Berlin U-Bahn with a simple route planner: click a start
station, click a destination, and the map highlights the fastest route with the lines,
changes and travel time.

The map is drawn on real geography. Stations and tracks are at their true positions,
with the Spree, canals, lakes and large parks in the background. The centre is enlarged
with a radial stretch so Mitte stays readable.

## How it works

| File | Purpose |
| --- | --- |
| `src/template.html` | The page: map drawing, label placement, routing, UI |
| `data/ubahn.json` | Stations, lines, track shapes, travel times (generated) |
| `data/background.json` | Rivers, lakes, parks, city boundary (generated) |
| `index.html` | Built page with the data inlined; open it directly in a browser |

Routing runs Dijkstra on a graph where each node is a station on a specific line.
Riding between stations costs the timetable time; changing lines costs 3 minutes
walking plus half the interval of the line you change to.

## Rebuilding

Requires Python 3 (standard library only).

```bash
# 1. Timetable data: download and unpack the VBB GTFS feed
curl -L -o gtfs.zip https://www.vbb.de/vbbgtfs
unzip -o gtfs.zip -d gtfs
python3 scripts/build_data.py gtfs

# 2. Background shapes from OpenStreetMap (only needed rarely; about 40 requests to Nominatim)
python3 scripts/fetch_background.py

# 3. Build the page
python3 scripts/build_page.py
```

`build_data.py` takes the line structure from the whole feed period, so temporary
closures do not shorten a line. Travel times and headways come from the weekday on
which each full line has the most trips (trips starting 07:00–20:00).

## Settings

At the top of the script in `src/template.html`:

- `STRETCH_P`: 1 draws exact geography; lower values give the centre more room (default 0.72).
- `STRETCH_R`: radius in metres inside which the map is enlarged (default 3500).
- `TRANSFER_WALK_MIN`: walking time assumed for every change (default 3).

## Known limitations

- Walking time for a change is the same at every station. Per-station times could come
  from `pathways.txt` in the GTFS feed.
- Planned closures in the timetable are not shown.
- U-Bahn only. The S-Bahn is the next step and fits the same data format.

## Data sources

- Timetable, stations and track shapes: [VBB GTFS](https://www.vbb.de/vbbgtfs),
  Verkehrsverbund Berlin-Brandenburg. See VBB's open data terms for reuse.
- Background: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors,
  available under the Open Database License, fetched via Nominatim.

## License

Code: Apache License 2.0, see `LICENSE`. The data files keep the terms of their sources above.
