#!/usr/bin/env python3
"""Build data/network.json (U-Bahn and S-Bahn) from the VBB GTFS feed.

Usage: python3 scripts/build_data.py <path-to-unzipped-gtfs>

Get the feed from https://www.vbb.de/vbbgtfs (zip, about 85 MB).

- Line structure (stations in order) comes from the whole feed period, so a
  temporary closure does not shorten a line.
- Travel times and headways come from a typical Tuesday-Thursday (the most
  common number of full-line trips among those days, so holidays and
  construction days are skipped), using trips that start 07:00-20:00.
- Headways are stored per station, because many S-Bahn lines run more often
  on their inner section than at the outer ends.
- Track shapes come from shapes.txt, cut at each station and simplified.
- Ring lines (S41, S42) are stored as loops: first station == last station,
  and they only run in the stored direction.
- Stations with the same cleaned name are merged (e.g. U and S at Alexanderplatz).
  WALK_LINKS adds interchanges between stations with different names.
"""
import csv, datetime, json, math, os, re, statistics, sys
from collections import Counter, defaultdict

GTFS = sys.argv[1]
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "network.json"))
DAY_FROM, DAY_TO = 7 * 3600, 20 * 3600


def rows(name):
    with open(os.path.join(GTFS, name), encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def secs(t):
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


# ---------- service days: service_id -> set of dates ----------
service_dates = defaultdict(set)
for c in rows("calendar.txt"):
    days = [c[k] == "1" for k in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")]
    if any(days):
        d = datetime.datetime.strptime(c["start_date"], "%Y%m%d").date()
        e = datetime.datetime.strptime(c["end_date"], "%Y%m%d").date()
        while d <= e:
            if days[d.weekday()]:
                service_dates[c["service_id"]].add(d.strftime("%Y%m%d"))
            d += datetime.timedelta(days=1)
for c in rows("calendar_dates.txt"):
    if c["exception_type"] == "1":
        service_dates[c["service_id"]].add(c["date"])
    else:
        service_dates[c["service_id"]].discard(c["date"])


def is_weekday(d):
    return datetime.datetime.strptime(d, "%Y%m%d").weekday() < 5


def is_midweek(d):
    return datetime.datetime.strptime(d, "%Y%m%d").weekday() in (1, 2, 3)


# ---------- U-Bahn and S-Bahn routes and trips ----------
# (route_type, agency_id, line name pattern, mode)
MODES = [("400", "796", r"U\d+", "U"),     # BVG U-Bahn
         ("109", "1", r"S\d+", "S")]       # S-Bahn Berlin GmbH
# Interchanges between stations with different names: (station, station, walking minutes).
WALK_LINKS = [
    ("Spandau", "Rathaus Spandau", 4),
    ("Yorckstraße", "Yorckstraße (Großgörschenstraße)", 6),
    ("Charlottenburg", "Wilmersdorfer Straße", 4),
    ("Messe Nord/ZOB", "Kaiserdamm", 5),
]

routes, line_style = {}, {}
for r in rows("routes.txt"):
    for rtype, agency, pat, mode in MODES:
        if r["route_type"] == rtype and r["agency_id"] == agency and re.fullmatch(pat, r["route_short_name"]):
            line = r["route_short_name"]
            routes[r["route_id"]] = {"id": line, "mode": mode}
            st_ = line_style.setdefault(line, {"mode": mode, "color": None, "text": "#FFFFFF"})
            if r["route_color"] and not st_["color"]:
                st_["color"] = "#" + r["route_color"]
                st_["text"] = "#" + (r["route_text_color"] or "FFFFFF")
trips = {t["trip_id"]: t for t in rows("trips.txt") if t["route_id"] in routes}
print("U-Bahn and S-Bahn trips in feed:", len(trips))

stops = {s["stop_id"]: s for s in rows("stops.txt")}


def parent(stop_id):
    return stops[stop_id]["parent_station"] or stop_id


NAME_FIX = {"Berlin Hauptbahnhof": "Hauptbahnhof"}


def clean(name):
    n = re.sub(r"^(S\+U|U|S)\s+", "", name)
    n = re.sub(r"\s*\(Berlin\)\s*$", "", n)
    n = re.sub(r"\s+Bhf\b", "", n)
    n = n.replace("str.", "straße").replace("Str.", "Straße").replace("Pl.", "Platz")
    n = n.strip()
    return NAME_FIX.get(n, n)


stop_times = defaultdict(list)
with open(os.path.join(GTFS, "stop_times.txt"), encoding="utf-8-sig", newline="") as f:
    rd = csv.reader(f)
    head = next(rd)
    i_trip, i_stop, i_seq = head.index("trip_id"), head.index("stop_id"), head.index("stop_sequence")
    i_dep = head.index("departure_time")
    for row in rd:
        if row[i_trip] in trips:
            stop_times[row[i_trip]].append((int(row[i_seq]), row[i_stop], secs(row[i_dep])))
for v in stop_times.values():
    v.sort()

# ---------- lines ----------
by_line = defaultdict(list)
for tid, t in trips.items():
    by_line[routes[t["route_id"]]["id"]].append(tid)

stations = {}   # display name -> {name, pts, lines}


def station_for(stop_id, line):
    name = clean(stops[parent(stop_id)]["stop_name"])
    st = stations.setdefault(name, {"name": name, "pts": [], "lines": []})
    s = stops[stop_id]
    st["pts"].append((float(s["stop_lat"]), float(s["stop_lon"])))
    if line not in st["lines"]:
        st["lines"].append(line)
    return name


line_info = {}
def line_order(x):
    return (x[0] != "U", int(x[1:]))


for line in sorted(by_line, key=line_order):
    tids = by_line[line]
    pats, rep, trip_pat = Counter(), {}, {}
    for tid in tids:
        key = (trips[tid]["direction_id"], tuple(parent(s[1]) for s in stop_times[tid]))
        pats[key] += 1
        rep.setdefault(key, tid)
        trip_pat[tid] = key
    top = pats.most_common(1)[0][1]
    cands = [k for k, c in pats.items() if c >= 0.2 * top]
    best = max(cands, key=lambda k: (len(k[1]), pats[k]))     # longest regular pattern = full line
    full = {best} | {k for k in cands if k[1] == best[1][::-1]}
    tid = rep[best]
    seq_st = stop_times[tid]
    # A ring trip may go round more than once: keep one lap, ending where it started.
    seen, cut = set(), len(seq_st)
    for i, s_ in enumerate(seq_st):
        p_ = parent(s_[1])
        if p_ in seen:
            cut = i + 1
            break
        seen.add(p_)
    loop = cut < len(seq_st) or (len(seq_st) > 2 and parent(seq_st[0][1]) == parent(seq_st[-1][1]))
    names = [station_for(s[1], line) for s in seq_st[:cut]]

    per_day = Counter()
    for day_ok in (is_midweek, is_weekday, lambda d: True):    # prefer Tue-Thu, then any weekday, then any day
        for t2 in tids:
            if trip_pat[t2] in full:
                for d in service_dates[trips[t2]["service_id"]]:
                    if day_ok(d):
                        per_day[d] += 1
        if per_day:
            break
    # Typical day: the most common trip count among midweek days (ties: more trips).
    count_freq = Counter(per_day.values())
    typical = max(count_freq, key=lambda c: (count_freq[c], c))
    day = min(d for d, c in per_day.items() if c == typical)

    seg_t, seg_any, first_deps = defaultdict(list), defaultdict(list), defaultdict(list)
    calls = Counter()     # (station, direction) -> departures in the daytime window
    for t2 in tids:
        st_list = stop_times[t2]
        if not (DAY_FROM <= st_list[0][2] <= DAY_TO):
            continue
        on_day = day in service_dates[trips[t2]["service_id"]]
        if on_day:
            first_deps[(trips[t2]["direction_id"], parent(st_list[0][1]))].append(st_list[0][2])
            for n_ in {clean(stops[parent(s_[1])]["stop_name"]) for s_ in st_list}:   # once per trip
                calls[(n_, trips[t2]["direction_id"])] += 1
        for a, b in zip(st_list, st_list[1:]):
            na, nb = clean(stops[parent(a[1])]["stop_name"]), clean(stops[parent(b[1])]["stop_name"])
            key = frozenset((na, nb))
            if on_day:
                seg_t[key].append((b[2] - a[2]) / 60)
            elif len(seg_any[key]) < 200:
                seg_any[key].append((b[2] - a[2]) / 60)
    for key, v in seg_any.items():      # segments not served on the reference day
        if key not in seg_t:
            seg_t[key] = v
    deps = max(first_deps.values(), key=len)
    headway = (DAY_TO - DAY_FROM) / 60 / max(1, len(deps))
    window = (DAY_TO - DAY_FROM) / 60
    st_head = []
    for n in names:
        c = max(calls.get((n, "0"), 0), calls.get((n, "1"), 0))
        st_head.append(round(window / c, 1) if c else round(headway, 1))
    line_info[line] = {"names": names, "shape": trips[tid]["shape_id"], "seg_t": seg_t,
                       "headway": headway, "st_head": st_head, "loop": loop, "style": line_style[line]}
    print(f"{line}: {len(names)} stations, {names[0]} -> {names[-1]}{' (loop)' if loop else ''}, "
          f"interval {min(st_head)}-{max(st_head)} min, reference day {day}")

# ---------- shapes ----------
needed = {i["shape"] for i in line_info.values()}
shapes = defaultdict(list)
with open(os.path.join(GTFS, "shapes.txt"), encoding="utf-8-sig", newline="") as f:
    rd = csv.reader(f)
    next(rd)
    for sid, lat, lon, seq in rd:
        if sid in needed:
            shapes[sid].append((int(seq), float(lat), float(lon)))
for v in shapes.values():
    v.sort()


def rdp(pts, eps_m):
    """Douglas-Peucker simplification with tolerance in metres."""
    if len(pts) < 3:
        return pts
    k = math.cos(math.radians(pts[0][0]))
    P = [(p[1] * 111320 * k, p[0] * 110540) for p in pts]

    def dist(i, a, b):
        (x, y), (x1, y1), (x2, y2) = P[i], P[a], P[b]
        dx, dy = x2 - x1, y2 - y1
        return abs(dy * x - dx * y + x2 * y1 - y2 * x1) / (math.hypot(dx, dy) or 1)

    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        best, idx = 0, None
        for i in range(a + 1, b):
            d = dist(i, a, b)
            if d > best:
                best, idx = d, i
        if idx is not None and best > eps_m:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, kk in zip(pts, keep) if kk]


for st in stations.values():   # station position = mean of its platforms
    st["lat"] = sum(p[0] for p in st["pts"]) / len(st["pts"])
    st["lon"] = sum(p[1] for p in st["pts"]) / len(st["pts"])

lines_out = []
for line, info in line_info.items():
    pts = [(p[1], p[2]) for p in shapes[info["shape"]]]
    names = info["names"]
    # Cut the track at the exact closest point to each station (moving forward only),
    # then join that point to the station position with a short straight piece.
    k = math.cos(math.radians(pts[0][0]))
    XY = [(p[1] * k, p[0]) for p in pts]
    cuts, lo = [], 0
    for j, n in enumerate(names):
        st = stations[n]
        sx, sy = st["lon"] * k, st["lat"]
        best = (1e18, lo, 0.0)
        # On a loop the first station is also near the end of the shape: search the first half only.
        hi = len(XY) // 2 if info["loop"] and j == 0 else len(XY) - 1
        for i in range(lo, hi):
            (x1, y1), (x2, y2) = XY[i], XY[i + 1]
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((sx - x1) * dx + (sy - y1) * dy) / L2))
            d = (x1 + t * dx - sx) ** 2 + (y1 + t * dy - sy) ** 2
            if d < best[0] - 1e-18:
                best = (d, i, t)
        _, i, t = best
        if (i, t) < cuts[-1][:2] if cuts else False:
            i, t = cuts[-1][0], cuts[-1][1]
        p = (pts[i][0] + t * (pts[i + 1][0] - pts[i][0]), pts[i][1] + t * (pts[i + 1][1] - pts[i][1]))
        cuts.append((i, t, p))
        lo = i
    segs = []
    for j in range(len(names) - 1):
        a_st, b_st = stations[names[j]], stations[names[j + 1]]
        (ia, ta, pa), (ib, tb, pb) = cuts[j], cuts[j + 1]
        inner = pts[ia + 1:ib + 1] if ib > ia else []
        piece = [(a_st["lat"], a_st["lon"]), pa] + inner + [pb, (b_st["lat"], b_st["lon"])]
        dedup = [piece[0]]
        for q in piece[1:]:
            if abs(q[0] - dedup[-1][0]) > 1e-7 or abs(q[1] - dedup[-1][1]) > 1e-7:
                dedup.append(q)
        piece = rdp(dedup, 6)
        times = info["seg_t"].get(frozenset((names[j], names[j + 1])), [])
        segs.append({"min": round(statistics.mean(times), 2) if times else None,
                     "shape": [[round(q[0], 5), round(q[1], 5)] for q in piece]})
    sty = info["style"]
    lines_out.append({"id": line, "mode": sty["mode"], "color": sty["color"] or "#888888", "text": sty["text"],
                      "headways": info["st_head"], "loop": info["loop"], "stations": names, "segments": segs})

# Same name but far apart would mean two different places were merged.
for st in stations.values():
    far = max(math.hypot((p[0] - st["lat"]) * 110540, (p[1] - st["lon"]) * 68000) for p in st["pts"])
    if far > 600:
        print(f"WARNING: platforms of {st['name']} spread {far:.0f} m from its centre")
walks = []
for a, b, m in WALK_LINKS:
    if a in stations and b in stations:
        walks.append({"a": a, "b": b, "min": m})
    else:
        print("WARNING: walk link skipped, station missing:", a if a not in stations else b)

out_st = [{"name": s["name"], "lat": round(s["lat"], 6), "lon": round(s["lon"], 6), "lines": s["lines"]}
          for s in sorted(stations.values(), key=lambda s: s["name"])]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"source": "VBB GTFS", "built": datetime.date.today().isoformat(),
               "stations": out_st, "lines": lines_out, "walks": walks}, f, ensure_ascii=False, separators=(",", ":"))
print("wrote", OUT, os.path.getsize(OUT), "bytes,", len(out_st), "stations")
print("segments without times:", [(l["id"], i) for l in lines_out for i, s in enumerate(l["segments"]) if s["min"] is None])
print("interchanges:", sum(1 for s in out_st if len(s["lines"]) > 1))
