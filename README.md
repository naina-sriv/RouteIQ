# RouteIQ v2

**Production-grade route optimizer for trips and delivery fleets.**
Solves TSP (single vehicle) and VRP with time windows (multi-vehicle) in under 5 seconds for 20 stops using Google OR-Tools, real road travel times from OSRM, and Redis matrix caching.

```
pip install -r requirements.txt && uvicorn main:app --reload --port 5000
```

---

## Table of Contents

1. [What this solves](#what-this-solves)
2. [Architecture overview](#architecture-overview)
3. [Request lifecycle](#request-lifecycle)
4. [Project structure](#project-structure)
5. [Data models](#data-models)
6. [API reference](#api-reference)
7. [Solver design](#solver-design)
8. [Caching layer](#caching-layer)
9. [Frontend architecture](#frontend-architecture)
10. [Docker setup](#docker-setup)
11. [Running the benchmark](#running-the-benchmark)
12. [Running tests](#running-tests)
13. [Environment variables](#environment-variables)
14. [Benchmark results](#benchmark-results)

---

## What this solves

| RouteIQ |
|---|
| Real road travel times via OSRM |
| OR-Tools with Guided Local Search |
| Haversine fallback, labeled in response |
| Multi-vehicle VRP with capacity constraints |
| Per-stop time windows ("arrive 10am–2pm") |
| Redis cache on distance matrix (same stops = instant) |
| Dockerized, self-hostable, zero API costs |

**Trip Planner (TSP):** One vehicle. Visit all stops in the optimal order. Fixed start and end.
Use case: road trips, field sales reps, last-mile delivery drivers with a fixed stop list.

**Fleet Optimizer (VRP):** Multiple vehicles. Split stops between them. Each vehicle has a
capacity limit and optional per-stop time windows.
Use case: delivery fleets, logistics companies, courier networks.

---

## Architecture overview

```
╔══════════════════════════════════════════════════════════════════════╗
║                           Browser / Client                           ║
║                                                                      ║
║   ┌──────────────────────┐      ┌──────────────────────────────┐     ║
║   │   Trip Planner UI    │      │   Fleet Optimizer UI         │     ║
║   │   (trip.js)          │      │   (fleet.js)                 │     ║ 
║   │                      │      │                              │     ║
║   │  • Stop list         │      │  • Vehicle builder           │     ║
║   │  • Start/end select  │      │  • Capacity inputs           │     ║
║   │  • Route polyline    │      │  • Color-coded routes        │     ║
║   │  • Travel time card  │      │  • Per-vehicle stat cards    │     ║
║   └──────────┬───────────┘      └──────────────┬───────────────┘     ║
║              │                                 │                     ║
║   ┌──────────▼─────────────────────────────────▼───────────────┐     ║
║   │                    app.js (shared state)                   │     ║
║   │   map · markers · stop list · geocoding · layer mgmt       │     ║
║   └──────────────────────────────┬─────────────────────────────┘     ║
║                                  │ fetch() HTTP                      ║
╚══════════════════════════════════╪═══════════════════════════════════╝
                                   │
                    ┌──────────────▼──────────────────┐
                    │         FastAPI Backend         │
                    │                                 │
                    │  POST /optimize         (TSP)   │
                    │  POST /optimize/fleet   (VRP)   │
                    │  POST /geocode                  │
                    │  POST /reverse-geocode          │
                    │  GET  /health                   │
                    └──────┬───────────────┬──────────┘
                           │               │
              ┌────────────▼──┐    ┌───────▼────────────┐
              │  utils/       │    │  utils/            │
              │  solver.py    │    │  vrp_solver.py     │
              │               │    │                    │
              │  OR-Tools TSP │    │  OR-Tools VRP      │
              │  GLS search   │    │  Capacity + time   │
              │  NN fallback  │    │  window dimensions │
              └────────┬──────┘    └──────────┬─────────┘
                       │                      │
                       └──────────┬───────────┘
                                  │
                    ┌─────────────▼────────────────────┐
                    │         utils/osrm.py            │
                    │                                  │
                    │  get_distance_matrix()           │
                    │  get_route_polyline()            │
                    │                                  │
                    │  ┌────────────────────────────┐  │
                    │  │     utils/cache.py         │  │
                    │  │  Redis · MD5 key · TTL 1h  │  │
                    │  └───────────┬────────────────┘  │
                    └─────────────┬┴───────────────────┘
                    cache HIT ◄───┘  cache MISS
                                         │
                         ┌───────────────▼──────────────┐
                         │             OSRM             │
                         │  /table/v1/driving/{coords}  │
                         │  /route/v1/driving/{a};{b}   │
                         │                              │
                         │  Self-hosted via Docker      │
                         │  or router.project-osrm.org  │
                         └──────────────────────────────┘
```

---

## Request lifecycle

### TSP: `POST /optimize`

```
Client                  FastAPI              Cache         OSRM          OR-Tools
  │                        │                   │              │               │
  │── POST /optimize ─────►│                   │              │               │
  │   {stops, start, end}  │                   │              │               │
  │                        │── get_matrix() ──►│              │               │
  │                        │                   │              │               │
  │                        │  ┌─ cache HIT ────┤              │               │
  │                        │  │ return matrix  │              │               │
  │                        │  └───────────────►│              │               │
  │                        │                   │              │               │
  │                        │  ┌─ cache MISS ───┤              │               │
  │                        │  │                │── /table ───►│               │
  │                        │  │                │  (1–3s)      │               │
  │                        │  │                │◄── matrix ───│               │
  │                        │  │ set_matrix()   │              │               │
  │                        │  └───────────────►│              │               │
  │                        │                   │              │               │
  │                        │─────── solve_tsp(matrix) ───────────────────────►│
  │                        │                   │              │   GLS ~1–5s   │
  │                        │◄───────────────────────────── ordered_indices ───│
  │                        │                   │              │               │
  │                        │── /route (per leg) ─────────────►│               │
  │                        │◄── polyline ─────────────────────│               │
  │                        │                   │              │               │
  │◄── OptimizeResponse ───│                   │              │               │
  │   {indices, legs,      │                   │              │               │
  │    total_duration,     │                   │              │               │
  │    used_fallback}      │                   │              │               │
```

### VRP: `POST /optimize/fleet`

```
Client                   FastAPI              OR-Tools VRP solver
  │                         │                       │
  │── POST /optimize/fleet ►│                       │
  │   {stops, vehicles,     │                       │
  │    depot_index}         │                       │
  │                         │                       │
  │                   (matrix fetch — same as TSP above)
  │                         │                       │
  │                         │── solve_vrp() ───────►│
  │                         │   vehicles + stops    │
  │                         │                       │── AddDimensionWithVehicleCapacity()
  │                         │                       │── AddDimension() [time windows]
  │                         │                       │── AddDisjunction() [droppable stops]
  │                         │                       │── GLS search
  │                         │                       │
  │                         │◄── routes[], unassigned[]
  │                         │                       │
  │                   (polyline fetch per leg — same as TSP)
  │                         │                       │
  │◄── FleetResponse ───────│                       │
  │   {routes[]: {          │                       │
  │     vehicle_index,      │                       │
  │     ordered_indices,    │                       │
  │     total_duration,     │                       │
  │     total_load, legs    │                       │
  │   }, unassigned_stops}  │                       │
```

---

## Project structure

```
routeiq/
│
├── main.py                    FastAPI app + all route handlers
├── models.py                  Pydantic request/response schemas
├── config.py                  Settings from environment variables
├── requirements.txt
├── Dockerfile
├── docker-compose.yml         App + Redis + OSRM in one command
├── .env.example
│
├── utils/
│   ├── __init__.py
│   ├── osrm.py                Distance matrix, road polylines, haversine fallback
│   ├── cache.py               Redis wrapper — MD5-keyed matrix cache with TTL
│   ├── geocoder.py            Nominatim forward + reverse geocoding
│   ├── solver.py              OR-Tools TSP solver (single vehicle)
│   └── vrp_solver.py          OR-Tools VRP solver (capacity + time windows)
│
├── benchmarks/
│   └── compare_algorithms.py  Nearest-neighbor vs OR-Tools comparison table
│
├── tests/
│   ├── __init__.py
│   ├── test_solver.py         Unit tests — TSP solver
│   ├── test_vrp_solver.py     Unit tests — VRP solver
│   └── test_api.py            Integration tests — all endpoints
│
├── templates/
│   └── index.html             Single-page frontend
│
└── static/
    ├── css/style.css
    └── js/
        ├── app.js             Shared map state, markers, geocoding
        ├── trip.js            Trip Planner mode (calls /optimize)
        └── fleet.js           Fleet Optimizer mode (calls /optimize/fleet)
```

---

## Data models

### Request schemas

```
OptimizeRequest                          FleetRequest
─────────────────────────────────        ─────────────────────────────────────
stops:       Stop[]      (2–20)          stops:         Stop[]     (2–20)
start_index: int         default 0       vehicles:      Vehicle[]  (1–5)
end_index:   int         default 0       depot_index:   int        default 0


Stop                                     Vehicle
─────────────────────────────────        ─────────────────────────────────────
lat:               float                 capacity:  int     (units, e.g. 10)
lng:               float                 label:     str?    (e.g. "Van 1")
label:             str?
time_window_open:  int?   (minutes from midnight, e.g. 600 = 10am)
time_window_close: int?   (e.g. 840 = 2pm)
demand:            int    default 1
```

### Response schemas

```
OptimizeResponse                         FleetResponse
─────────────────────────────────        ─────────────────────────────────────
ordered_indices:       int[]             routes:             VehicleRoute[]
total_duration_seconds: int             total_duration_seconds: int
legs:                  Leg[]            unassigned_stops:   int[]
used_fallback:         bool             used_fallback:      bool


Leg                                      VehicleRoute
─────────────────────────────────        ─────────────────────────────────────
from_index:        int                   vehicle_index:          int
to_index:          int                   label:                  str?
duration_seconds:  int                   ordered_indices:        int[]
polyline:          [lat, lng][]          total_duration_seconds: int
                                         total_load:             int
                                         legs:                   Leg[]
```

---

## API reference

### `GET /health`

Liveness check. Returns `{"status": "ok", "version": "2.0.0"}`.

---

### `POST /optimize`

Single-vehicle TSP. Finds the shortest route visiting all stops.

**Request**
```json
{
  "stops": [
    {"lat": 12.9716, "lng": 77.5946},
    {"lat": 13.0827, "lng": 80.2707},
    {"lat": 28.7041, "lng": 77.1025}
  ],
  "start_index": 0,
  "end_index": 0
}
```

**Response**
```json
{
  "ordered_indices": [0, 2, 1, 0],
  "total_duration_seconds": 14820,
  "used_fallback": false,
  "legs": [
    {
      "from_index": 0,
      "to_index": 2,
      "duration_seconds": 7200,
      "polyline": [[12.97, 77.59], [18.2, 76.1], [28.70, 77.10]]
    }
  ]
}
```

**Errors**

| Code | Reason                                         |
|------|------------------------------------------------|
| 400  | More than 20 stops                             |
| 422  | Fewer than 2 stops, or invalid start/end index |

---

### `POST /optimize/fleet`

Multi-vehicle VRP. Splits stops across vehicles respecting capacity and time windows.

**Request**
```json
{
  "stops": [
    {"lat": 12.97, "lng": 77.59, "demand": 1},
    {"lat": 13.08, "lng": 80.27, "demand": 2, "time_window_open": 600, "time_window_close": 840},
    {"lat": 19.07, "lng": 72.87, "demand": 1},
    {"lat": 28.70, "lng": 77.10, "demand": 3}
  ],
  "vehicles": [
    {"capacity": 5, "label": "Van 1"},
    {"capacity": 4, "label": "Van 2"}
  ],
  "depot_index": 0
}
```

**Response**
```json
{
  "routes": [
    {
      "vehicle_index": 0,
      "label": "Van 1",
      "ordered_indices": [0, 3, 0],
      "total_duration_seconds": 9600,
      "total_load": 3,
      "legs": [...]
    },
    {
      "vehicle_index": 1,
      "label": "Van 2",
      "ordered_indices": [0, 1, 2, 0],
      "total_duration_seconds": 7200,
      "total_load": 3,
      "legs": [...]
    }
  ],
  "total_duration_seconds": 16800,
  "unassigned_stops": [],
  "used_fallback": false
}
```

---

### `POST /geocode`

Forward geocoding via Nominatim. Name → coordinates.

```json
// Request
{"query": "Connaught Place, New Delhi"}

// Response
{"lat": 28.6328, "lng": 77.2197, "display_name": "Connaught Place, New Delhi, India"}
```

---

### `POST /reverse-geocode`

Coordinates → human-readable address. Called automatically when you drag a map pin.

```json
// Request
{"lat": 28.6328, "lng": 77.2197}

// Response
{"display_name": "Connaught Place, New Delhi 110001, India"}
```

---

## Solver design

### TSP solver (`utils/solver.py`)

```
Input: n×n distance matrix (seconds), start node, end node
         │
         ▼
OR-Tools RoutingIndexManager
  num_nodes = n
  num_vehicles = 1
  start = [start_index]
  end   = [end_index]
         │
         ▼
RegisterTransitCallback(matrix[i][j])
SetArcCostEvaluatorOfAllVehicles()
         │
         ▼
Search parameters:
  FirstSolutionStrategy  → PATH_CHEAPEST_ARC
  LocalSearchMetaheuristic → GUIDED_LOCAL_SEARCH
  time_limit             → SOLVER_TIME_LIMIT_SECONDS (default 5s)
         │
         ├─ solution found ──► extract route → ordered node list
         │
         └─ no solution ─────► nearest-neighbor fallback
```

**Why Guided Local Search?**
PATH_CHEAPEST_ARC builds an initial route greedily. GLS then escapes local optima by penalising frequently-used arcs, consistently producing 15–25% better routes than nearest-neighbor alone for 10+ stops.

---

### VRP solver (`utils/vrp_solver.py`)

```
Input: matrix, vehicles[], stops[], depot_index
         │
         ▼
OR-Tools RoutingIndexManager
  num_nodes    = len(stops)
  num_vehicles = len(vehicles)
  depot        = depot_index
         │
         ▼
RegisterTransitCallback(matrix[i][j])     ← arc cost = travel time
RegisterUnaryTransitCallback(stop.demand) ← for capacity dimension
         │
         ▼
AddDimensionWithVehicleCapacity(
  demand_callback,
  slack=0,
  capacities=[v.capacity for v in vehicles],
  fix_start_cumul_to_zero=True,
  name="Capacity"
)
         │
         ▼  (if any stop has time_window_open or time_window_close)
AddDimension(
  transit_callback,
  max_wait=30*60,     ← vehicle can wait up to 30 min
  max_time=24*3600,
  fix_start_cumul=False,
  name="Time"
)
CumulVar(node_index).SetRange(open_s, close_s)  ← per-stop window
         │
         ▼
AddDisjunction([node_index], penalty=1_000_000)
  ← lets solver drop stops rather than violate capacity,
    but at very high cost — routes drop stops only when
    no vehicle can physically carry that load
         │
         ▼
GLS search (same params as TSP)
         │
         ├─ extract per-vehicle routes
         └─ collect unassigned (dropped) stop indices
```

---

## Caching layer

```
Request arrives with coords [(lat, lng), ...]
                │
                ▼
         Sort coords
    (order-independent key)
                │
                ▼
       MD5 hash → Redis key
   "routeiq:matrix:<hash>"
                │
          ┌─────┴─────┐
          │           │
        HIT          MISS
          │           │
     return       call OSRM
     cached       /table/v1
     matrix       (1–3 sec)
          │           │
          │        store in
          │        Redis, TTL
          │        = 3600 s
          │           │
          └─────┬─────┘
                │
          matrix [][] int
          (seconds of
           travel time)
```

The key sorts coordinates before hashing, so `[A, B, C]` and `[C, A, B]` produce the same key. A 1-hour TTL covers a typical working day without going stale when road conditions change.

Haversine fallback results are deliberately **not cached** — the next request will retry OSRM.

---

## Frontend architecture

```
index.html
    │
    ├── Leaflet.js (CDN)      ← map, tile layer, markers, polylines
    │
    ├── app.js                ← loaded first
    │     state = { stops[], markers[], routeLayers[], mode, vehicles[] }
    │     map, addStop(), removeStop(), clearRoutes()
    │     makeIcon(idx, color) → numbered SVG pin
    │     switchMode('trip' | 'fleet')
    │     addStopFromInput() → POST /geocode
    │     map.on('click') → addStop()
    │     marker.on('dragend') → POST /reverse-geocode
    │
    ├── trip.js               ← trip planner
    │     optimizeTrip()      → POST /optimize
    │     renderTripResult()  → drawPolyline(), update results panel
    │
    └── fleet.js              ← fleet optimizer
          addVehicle(), removeVehicle(), renderVehicleList()
          optimizeFleet()     → POST /optimize/fleet
          renderFleetResult() → color-coded drawPolyline() per vehicle
                                color-coded makeIcon() per vehicle
                                per-vehicle stat cards in sidebar
```

**Color scheme (vehicles):**
```
Vehicle 0  ●  #5b7fff  (blue)
Vehicle 1  ●  #ff6b6b  (red)
Vehicle 2  ●  #ffd93d  (yellow)
Vehicle 3  ●  #6bcb77  (green)
Vehicle 4  ●  #c77dff  (purple)
```

---

## Docker setup

### Services

```
docker-compose.yml
│
├── app        FastAPI on :5000
│              OSRM_BASE = http://osrm:5000
│              REDIS_URL  = redis://redis:6379
│
├── redis      Redis 7 Alpine on :6379
│
└── osrm       OSRM backend on :5001 (→ internal :5000)
               Volume: ./osrm-data:/data
               Command: osrm-routed --algorithm mld /data/india-latest.osrm
```

### One-time OSRM data prep

```bash
# 1. Download the India OSM extract (~800 MB)
wget -P osrm-data https://download.geofabrik.de/asia/india-latest.osm.pbf

# 2. Extract road network
docker run -t -v $(pwd)/osrm-data:/data osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/india-latest.osm.pbf

# 3. Partition (multi-level Dijkstra preprocessing)
docker run -t -v $(pwd)/osrm-data:/data osrm/osrm-backend \
  osrm-partition /data/india-latest.osrm

# 4. Customize (metric weights)
docker run -t -v $(pwd)/osrm-data:/data osrm/osrm-backend \
  osrm-customize /data/india-latest.osrm

# 5. Start everything
docker-compose up
```

Open `http://localhost:5000`. Zero external API calls at any scale.

---

## Running the benchmark

```bash
python benchmarks/compare_algorithms.py
```

Output:
```
Stops    NN (s)   OR-Tools (s)   NN time    OR-Tools time   Improvement
────────────────────────────────────────────────────────────────────────
    5     0.000          0.312   240,266          197,481         17.8%
   10     0.000          1.104   287,263          231,090         19.6%
   15     0.000          2.871   319,247          256,112         19.8%
   20     0.000          4.938   398,521          307,433         22.9%
```

The benchmark uses a random set of points within the India bounding box and a haversine distance matrix (no OSRM required). Gap widens with stop count because the combinatorial search space grows faster than nearest-neighbor can track it.

---

## Running tests

```bash
pytest tests/ -v
```

**What each test file covers:**

`tests/test_solver.py`
- Start node is always first in output
- End node is always last in output
- All nodes appear exactly once (no duplicates, no missing)
- Different start and end nodes work correctly
- 2-stop edge case
- Raises `ValueError` on fewer than 2 stops
- Raises `ValueError` on more than 20 stops

`tests/test_vrp_solver.py`
- No vehicle exceeds its capacity
- Every stop appears exactly once across all vehicles
- Handles 3 vehicles, 12 stops, mixed capacities
- Time window dimension doesn't crash
- Unassigned stops returned when load exceeds total capacity

`tests/test_api.py`
- `POST /optimize` with 5 stops returns 200, correct start/end
- `POST /optimize/fleet` with 2 vehicles splits stops and returns 200
- `POST /optimize` with 1 stop returns 422
- `POST /optimize` with 21 stops returns 400
- `GET /health` returns 200

---

## Environment variables

| Variable                    | Default                          | Description                                                          |
|-----------------------------|----------------------------------|----------------------------------------------------------------------|
| `OSRM_BASE`                 | `http://router.project-osrm.org` | OSRM API base URL. Set to `http://osrm:5000` in Docker.              |
| `REDIS_URL`                 | `redis://localhost:6379`         | Redis connection string. App runs without Redis (caching disabled).  |
| `MAX_STOPS`                 | `20`                             | Maximum stops per request. OR-Tools is practical up to ~25.          |
| `SOLVER_TIME_LIMIT_SECONDS` | `5`                              | Hard cutoff for OR-Tools search. Returns best solution found so far. |
 
Copy `.env.example` to `.env` and adjust before running locally.

---


## Stack

| Layer        | Technology              | Why                                       |
|--------------|-------------------------|-------------------------------------------|
| Backend      | FastAPI + Python 3.12   | Async-native, Pydantic validation, fast   |
| Solver       | Google OR-Tools 9.10    | Industry-standard, handles VRP in <5s     |
| Road network | OSRM                    | Sub-second table queries, self-hostable   |
| Cache        | Redis 7                 | Matrix reuse: 1–3s → <100ms               |
| Frontend     | Leaflet.js + Vanilla JS | No framework overhead for a map-first app |
| Container    | Docker + Compose        | Single command for full stack             |
| Geocoding    | Nominatim (OSM)         | Zero cost, no API key required            |
