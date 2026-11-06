# Berlin metro map

An interactive map of the Berlin U-Bahn and S-Bahn with a simple route planner: click a
start station, click a destination, and the map highlights the fastest route with the
lines, changes and travel time.

The map is drawn on real geography. Stations and tracks are at their true positions,
with the Spree, canals, lakes and large parks in the background. The centre is enlarged
with a radial stretch, so Mitte stays readable while the S-Bahn's outer ends (Oranienburg,
Strausberg, Potsdam, BER) still fit on the screen.

## How it works

| File | Purpose |
| --- | --- |
| `src/template.html` | The page: map drawing, label placement, routing, UI |
| `data/network.json` | Stations, lines, track shapes, travel times, intervals (generated) |
| `data/background.json` | Rivers, lakes, parks, city boundary (generated) |
| `index.html` | Built page with the data inlined; open it directly in a browser |

Routing runs Dijkstra on a graph where each node is a station on a specific line.

- Riding between two stations costs the timetable time.
- Changing lines costs walking time (3 min within U-Bahn or S-Bahn, 5 min between them)
  plus half the interval of the line you change to, at that station. Intervals are per
  station because many S-Bahn lines run more often in the city than at their outer ends.
- The Ring lines run one way only: S41 clockwise, S42 anticlockwise.
- A few interchanges between stations with different names are linked by walking, for
  example Spandau and Rathaus Spandau. They are listed in `WALK_LINKS` in
  `scripts/build_data.py`.

## Rebuilding

Requires Python 3 (standard library only).

```bash
# 1. Timetable data: download and unpack the VBB GTFS feed
curl -L -o gtfs.zip https://www.vbb.de/vbbgtfs
unzip -o gtfs.zip -d gtfs
python3 scripts/build_data.py gtfs

# 2. Background shapes from OpenStreetMap (only needed rarely; about 50 requests to Nominatim)
python3 scripts/fetch_background.py

# 3. Build the page
python3 scripts/build_page.py
```

`build_data.py` takes each line's stations from the longest pattern that runs regularly
over the whole feed period, so temporary closures do not shorten a line. Travel times and
intervals come from a typical Tuesday to Thursday (holidays and construction days are
skipped), using trips that start between 07:00 and 20:00.

## Settings

At the top of the script in `src/template.html`:

- `STRETCH_P`: 1 draws exact geography; lower values give the centre more room (default 0.72).
- `STRETCH_R`: radius in metres inside which the map is enlarged (default 3500).
- `WALK_SAME_MODE_MIN`, `WALK_U_S_MIN`: walking time assumed for a change (defaults 3 and 5).

## Known limitations

- Walking time for a change is a flat estimate. Per-station times could come from
  `pathways.txt` in the GTFS feed.
- Planned closures in the timetable are not shown.
- Lines are taken from the timetable as published. S45 does not appear in the current
  VBB feed, so it is not on the map.
- Regional trains (RE, RB) are not included.

## Data sources

- Timetable, stations and track shapes: [VBB GTFS](https://www.vbb.de/vbbgtfs),
  Verkehrsverbund Berlin-Brandenburg. See VBB's open data terms for reuse.
- Background: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors,
  available under the Open Database License, fetched via Nominatim.

## License

Code: Apache License 2.0, see `LICENSE`. The data files keep the terms of their sources above.
