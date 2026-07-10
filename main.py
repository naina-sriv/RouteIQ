import logging
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import MAX_STOPS
from models import (
    OptimizeRequest, OptimizeResponse, Leg,
    FleetRequest, FleetResponse, VehicleRoute as VehicleRouteModel,
    GeocodeRequest, GeocodeResponse,
    ReverseGeocodeRequest, ReverseGeocodeResponse,
)
from utils.osrm import get_distance_matrix, get_route_polyline
from utils.solver import solve_tsp
from utils.vrp_solver import solve_vrp, VehicleSpec, StopSpec
from utils.geocoder import geocode, reverse_geocode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RouteIQ v2", version="2.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")



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
    matrix, used_fallback = await get_distance_matrix(coords)

    ordered = solve_tsp(matrix, start_index=req.start_index, end_index=req.end_index)

    legs: list[Leg] = []
    any_fallback = used_fallback
    
    tasks = []
    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        tasks.append(get_route_polyline(
            coords[a][0], coords[a][1], coords[b][0], coords[b][1]
        ))
    
    results = await asyncio.gather(*tasks)
    
    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        polyline, poly_fallback = results[i]
        if poly_fallback:
            any_fallback = True
        legs.append(Leg(
            from_index=a,
            to_index=b,
            duration_seconds=matrix[a][b],
            polyline=polyline,
        ))

    total = sum(leg.duration_seconds for leg in legs)
    return OptimizeResponse(
        ordered_indices=ordered,
        total_duration_seconds=total,
        legs=legs,
        used_fallback=any_fallback,
    )



@app.post("/optimize/fleet", response_model=FleetResponse)
async def optimize_fleet(req: FleetRequest):
    if len(req.stops) > MAX_STOPS:
        raise HTTPException(400, f"Maximum {MAX_STOPS} stops allowed")

    coords = [(s.lat, s.lng) for s in req.stops]
    matrix, used_fallback = await get_distance_matrix(coords)

    vehicle_specs = [VehicleSpec(capacity=v.capacity, label=v.label) for v in req.vehicles]
    stop_specs = [
        StopSpec(
            demand=s.demand,
            time_window_open=s.time_window_open,
            time_window_close=s.time_window_close,
        )
        for s in req.stops
    ]

    raw_routes, unassigned = solve_vrp(
        matrix, vehicle_specs, stop_specs, depot_index=req.depot_index
    )

    route_models: list[VehicleRouteModel] = []
    any_fallback = used_fallback

    for r in raw_routes:
        legs: list[Leg] = []
        tasks = []
        for i in range(len(r.ordered_indices) - 1):
            a, b = r.ordered_indices[i], r.ordered_indices[i + 1]
            tasks.append(get_route_polyline(
                coords[a][0], coords[a][1], coords[b][0], coords[b][1]
            ))
            
        results = await asyncio.gather(*tasks)
        
        for i in range(len(r.ordered_indices) - 1):
            a, b = r.ordered_indices[i], r.ordered_indices[i + 1]
            polyline, poly_fallback = results[i]
            if poly_fallback:
                any_fallback = True
            legs.append(Leg(
                from_index=a,
                to_index=b,
                duration_seconds=matrix[a][b],
                polyline=polyline,
            ))

        route_models.append(VehicleRouteModel(
            vehicle_index=r.vehicle_index,
            label=r.label,
            ordered_indices=r.ordered_indices,
            total_duration_seconds=r.total_duration_seconds,
            total_load=r.total_load,
            legs=legs,
        ))

    total = sum(r.total_duration_seconds for r in raw_routes)
    return FleetResponse(
        routes=route_models,
        total_duration_seconds=total,
        unassigned_stops=unassigned,
        used_fallback=any_fallback,
    )



@app.post("/geocode", response_model=GeocodeResponse)
async def geocode_endpoint(req: GeocodeRequest):
    try:
        result = await geocode(req.query)
        return GeocodeResponse(**result)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, f"Geocoding service error: {e}")


@app.post("/reverse-geocode", response_model=ReverseGeocodeResponse)
async def reverse_geocode_endpoint(req: ReverseGeocodeRequest):
    try:
        name = await reverse_geocode(req.lat, req.lng)
        return ReverseGeocodeResponse(display_name=name)
    except Exception as e:
        raise HTTPException(502, f"Reverse geocoding error: {e}")
