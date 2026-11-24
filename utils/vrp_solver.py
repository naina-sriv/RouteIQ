import logging
from dataclasses import dataclass
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from config import SOLVER_TIME_LIMIT_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class VehicleSpec:
    capacity: int
    label: str | None = None


@dataclass
class StopSpec:
    demand: int = 1
    time_window_open: int | None = None   # Minutes from midnight (e.g. 540 = 09:00 AM)
    time_window_close: int | None = None  # Minutes from midnight (e.g. 1020 = 05:00 PM)


@dataclass
class VehicleRoute:
    vehicle_index: int
    label: str | None
    ordered_indices: list[int]
    total_duration_seconds: int
    total_load: int


def solve_vrp(matrix: list[list[int]], vehicles: list[VehicleSpec], stops: list[StopSpec], depot_index: int = 0) -> tuple[list[VehicleRoute], list[int]]:
    n, num_vehicles = len(matrix), len(vehicles)
    manager = pywrapcp.RoutingIndexManager(n, num_vehicles, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    transit_cb = routing.RegisterTransitCallback(lambda from_idx, to_idx: matrix[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)])
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    demand_cb = routing.RegisterUnaryTransitCallback(lambda from_idx: 0 if manager.IndexToNode(from_idx) == depot_index else stops[manager.IndexToNode(from_idx)].demand)
    routing.AddDimensionWithVehicleCapacity(demand_cb, 0, [v.capacity for v in vehicles], True, "Capacity")

    if any(s.time_window_open is not None or s.time_window_close is not None for s in stops):
        routing.AddDimension(transit_cb, 30 * 60, 24 * 3600, False, "Time")
        time_dim = routing.GetDimensionOrDie("Time")
        for idx, s in enumerate(stops):
            if idx != depot_index and (s.time_window_open is not None or s.time_window_close is not None):
                open_s = (s.time_window_open or 0) * 60
                close_s = (s.time_window_close or 24 * 60) * 60
                time_dim.CumulVar(manager.NodeToIndex(idx)).SetRange(open_s, close_s)

    for node in range(n):
        if node != depot_index:
            routing.AddDisjunction([manager.NodeToIndex(node)], 10**6)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = SOLVER_TIME_LIMIT_SECONDS

    solution = routing.SolveWithParameters(params)
    if not solution:
        logger.error("VRP solver returned no solution")
        return [], list(range(n))

    routes: list[VehicleRoute] = []
    assigned: set[int] = {depot_index}

    for v in range(num_vehicles):
        index = routing.Start(v)
        nodes, total_time = [], 0

        while not routing.IsEnd(index):
            current_node = manager.IndexToNode(index)
            nodes.append(current_node)
            next_index = solution.Value(routing.NextVar(index))
            total_time += matrix[current_node][manager.IndexToNode(next_index)]
            index = next_index

        nodes.append(manager.IndexToNode(index))
        if len(nodes) <= 2:
            continue

        delivery_stops = [node for node in nodes if node != depot_index]
        load = sum(stops[node].demand for node in delivery_stops)
        assigned.update(delivery_stops)

        routes.append(VehicleRoute(vehicle_index=v, label=vehicles[v].label, ordered_indices=nodes, total_duration_seconds=total_time, total_load=load))

    unassigned = [i for i in range(n) if i not in assigned]
    return routes, unassigned
