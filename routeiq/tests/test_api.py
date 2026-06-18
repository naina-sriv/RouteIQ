import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Fake matrix and polyline so tests don't hit OSRM/Redis
FAKE_MATRIX = [[0, 300, 600, 900, 1200],
               [300, 0, 300, 600, 900],
               [600, 300, 0, 300, 600],
               [900, 600, 300, 0, 300],
               [1200, 900, 600, 300, 0]]

FAKE_POLYLINE = [[12.0, 77.0], [12.1, 77.1]]

STOPS_5 = [
    {"lat": 12.9716, "lng": 77.5946},
    {"lat": 13.0827, "lng": 80.2707},
    {"lat": 28.7041, "lng": 77.1025},
    {"lat": 19.0760, "lng": 72.8777},
    {"lat": 17.3850, "lng": 78.4867},
]


def mock_matrix(*args, **kwargs):
    return FAKE_MATRIX[:len(args[0])][:len(args[0])], False


def mock_polyline(*args, **kwargs):
    return FAKE_POLYLINE, False


@patch("main.get_distance_matrix", new_callable=lambda: lambda: AsyncMock(side_effect=mock_matrix))
@patch("main.get_route_polyline", new_callable=lambda: lambda: AsyncMock(return_value=(FAKE_POLYLINE, False)))
def test_optimize_returns_200(mock_poly, mock_mat):
    resp = client.post("/optimize", json={"stops": STOPS_5, "start_index": 0, "end_index": 0})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ordered_indices"][0] == 0
    assert data["ordered_indices"][-1] == 0
    assert "legs" in data


@patch("main.get_distance_matrix", new_callable=lambda: lambda: AsyncMock(side_effect=mock_matrix))
@patch("main.get_route_polyline", new_callable=lambda: lambda: AsyncMock(return_value=(FAKE_POLYLINE, False)))
def test_optimize_fleet_splits_stops(mock_poly, mock_mat):
    payload = {
        "stops": STOPS_5,
        "vehicles": [{"capacity": 5}, {"capacity": 5}],
        "depot_index": 0,
    }
    resp = client.post("/optimize/fleet", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "routes" in data


def test_optimize_with_one_stop_returns_422():
    resp = client.post("/optimize", json={"stops": [{"lat": 12.0, "lng": 77.0}]})
    assert resp.status_code == 422


@patch("main.get_distance_matrix", new_callable=lambda: lambda: AsyncMock(return_value=([[0]*21]*21, False)))
@patch("main.get_route_polyline", new_callable=lambda: lambda: AsyncMock(return_value=(FAKE_POLYLINE, False)))
def test_optimize_with_21_stops_returns_400(mock_poly, mock_mat):
    stops_21 = [{"lat": 12.0 + i * 0.1, "lng": 77.0} for i in range(21)]
    resp = client.post("/optimize", json={"stops": stops_21, "start_index": 0, "end_index": 0})
    assert resp.status_code == 400


def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
