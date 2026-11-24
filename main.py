import asyncio
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import MAX_STOPS
from models import (
    FleetRequest, FleetResponse, GeocodeRequest, GeocodeResponse, Leg,
    OptimizeRequest, OptimizeResponse, ReverseGeocodeRequest, ReverseGeocodeResponse,
    VehicleRoute as VehicleRouteModel,
)
from utils.geocoder import geocode, reverse_geocode
from utils.osrm import get_distance_matrix, get_route_polyline
from utils.solver import solve_tsp
from utils.vrp_solver import StopSpec, VehicleSpec, solve_vrp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("routeiq")

app = FastAPI(title="RouteIQ v2", description="Route planning and fleet optimization", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


async def _build_route_legs(ordered: list[int], coords: list[tuple[float, float]], matrix: list[list[int]]) -> tuple[list[Leg], bool]:
    if len(ordered) < 2:
        return [], False

    tasks = [get_route_polyline(coords[a][0], coords[a][1], coords[b][0], coords[b][1]) for a, b in zip(ordered, ordered[1:])]
    results = await asyncio.gather(*tasks)

    legs = [Leg(from_index=a, to_index=b, duration_seconds=matrix[a][b], polyline=poly) for (a, b), (poly, _) in zip(zip(ordered, ordered[1:]), results)]
    used_fallback = any(fallback for _, fallback in results)
    return legs, used_fallback


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/optimize", response_model=OptimizeResponse)
async def optimize(req: OptimizeRequest):
    if len(req.stops) > MAX_STOPS:
        raise HTTPException(400, f"Maximum {MAX_STOPS} stops allowed")

    coords = [(s.lat, s.lng) for s in req.stops]
    matrix, used_matrix_fallback = await get_distance_matrix(coords)
    ordered = solve_tsp(matrix, start_index=req.start_index, end_index=req.end_index)
    legs, used_poly_fallback = await _build_route_legs(ordered, coords, matrix)

    total_duration = sum(leg.duration_seconds for leg in legs)
    return OptimizeResponse(
        ordered_indices=ordered,
        total_duration_seconds=total_duration,
        legs=legs,
        used_fallback=used_matrix_fallback or used_poly_fallback,
    )


@app.post("/optimize/fleet", response_model=FleetResponse)
async def optimize_fleet(req: FleetRequest):
    if len(req.stops) > MAX_STOPS:
        raise HTTPException(400, f"Maximum {MAX_STOPS} stops allowed")

    coords = [(s.lat, s.lng) for s in req.stops]
    matrix, used_matrix_fallback = await get_distance_matrix(coords)

    vehicle_specs = [VehicleSpec(capacity=v.capacity, label=v.label) for v in req.vehicles]
    stop_specs = [StopSpec(demand=s.demand, time_window_open=s.time_window_open, time_window_close=s.time_window_close) for s in req.stops]

    raw_routes, unassigned = solve_vrp(matrix, vehicle_specs, stop_specs, depot_index=req.depot_index)

    route_models: list[VehicleRouteModel] = []
    any_poly_fallback = False

    for r in raw_routes:
        legs, poly_fallback = await _build_route_legs(r.ordered_indices, coords, matrix)
        if poly_fallback:
            any_poly_fallback = True
        route_models.append(VehicleRouteModel(
            vehicle_index=r.vehicle_index,
            label=r.label,
            ordered_indices=r.ordered_indices,
            total_duration_seconds=r.total_duration_seconds,
            total_load=r.total_load,
            legs=legs,
        ))

    total_duration = sum(r.total_duration_seconds for r in raw_routes)
    return FleetResponse(
        routes=route_models,
        total_duration_seconds=total_duration,
        unassigned_stops=unassigned,
        used_fallback=used_matrix_fallback or any_poly_fallback,
    )


@app.post("/geocode", response_model=GeocodeResponse)
async def geocode_endpoint(req: GeocodeRequest):
    try:
        return GeocodeResponse(**(await geocode(req.query)))
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, f"Geocoding service error: {e}")


@app.post("/reverse-geocode", response_model=ReverseGeocodeResponse)
async def reverse_geocode_endpoint(req: ReverseGeocodeRequest):
    try:
        return ReverseGeocodeResponse(display_name=await reverse_geocode(req.lat, req.lng))
    except Exception as e:
        raise HTTPException(502, f"Reverse geocoding error: {e}")
