from pydantic import BaseModel, Field, model_validator
from typing import Optional


class Stop(BaseModel):
    lat: float
    lng: float
    label: Optional[str] = None

    time_window_open: Optional[int] = None
    time_window_close: Optional[int] = None
    demand: int = 1


class OptimizeRequest(BaseModel):
    stops: list[Stop] = Field(..., min_length=2)
    start_index: int = 0
    end_index: int = 0

    @model_validator(mode="after")
    def validate_indices(self):
        n = len(self.stops)
        if self.start_index >= n or self.start_index < 0:
            raise ValueError(f"start_index must be 0..{n-1}")
        if self.end_index >= n or self.end_index < 0:
            raise ValueError(f"end_index must be 0..{n-1}")
        return self


class Vehicle(BaseModel):
    capacity: int = Field(default=10, ge=1)
    label: Optional[str] = None


class FleetRequest(BaseModel):
    stops: list[Stop] = Field(..., min_length=2)
    vehicles: list[Vehicle] = Field(..., min_length=1, max_length=5)
    depot_index: int = 0

    @model_validator(mode="after")
    def validate_depot(self):
        n = len(self.stops)
        if self.depot_index >= n or self.depot_index < 0:
            raise ValueError(f"depot_index must be 0..{n-1}")
        return self


class Leg(BaseModel):
    from_index: int
    to_index: int
    duration_seconds: int
    polyline: list[list[float]]



class OptimizeResponse(BaseModel):
    ordered_indices: list[int]
    total_duration_seconds: int
    legs: list[Leg]
    used_fallback: bool = False


class VehicleRoute(BaseModel):
    vehicle_index: int
    label: Optional[str]
    ordered_indices: list[int]
    total_duration_seconds: int
    total_load: int
    legs: list[Leg]


class FleetResponse(BaseModel):
    routes: list[VehicleRoute]
    total_duration_seconds: int
    unassigned_stops: list[int]
    used_fallback: bool = False


class GeocodeRequest(BaseModel):
    query: str


class GeocodeResponse(BaseModel):
    lat: float
    lng: float
    display_name: str


class ReverseGeocodeRequest(BaseModel):
    lat: float
    lng: float


class ReverseGeocodeResponse(BaseModel):
    display_name: str
