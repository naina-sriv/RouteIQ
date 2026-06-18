import logging
from dataclasses import dataclass
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from config import SOLVER_TIME_LIMIT_SECONDS

logger = logging.getLogger(__name__)

BIG_M = 10**7


@dataclass
class VehicleSpec:
    capacity: int
    label: str | None = None


@dataclass
class StopSpec:
    demand: int = 1
    time_window_open: int | None = None
    time_window_close: int | None = None


@dataclass
class VehicleRoute:
    vehicle_index: int
    label: str | None
    ordered_indices: list[int]
    total_duration_seconds: int
    total_load: int


def solve_vrp(
    matrix: list[list[int]],
    vehicles: list[VehicleSpec],
    stops: list[StopSpec],
    depot_index: int = 0,
) -> tuple[list[VehicleRoute], list[int]]:
    """
    Solve VRP with capacity constraints and optional per-stop time windows.
    Returns (routes, unassigned_stop_indices).
    """
    n = len(matrix)
    num_vehicles = len(vehicles)

    manager = pywrapcp.RoutingIndexManager(n, num_vehicles, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_idx, to_idx):
        i = manager.IndexToNode(from_idx)
        j = manager.IndexToNode(to_idx)
        return matrix[i][j]

    transit_cb = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    def demand_callback(from_idx):
        node = manager.IndexToNode(from_idx)
        if node == depot_index:
            return 0
        return stops[node].demand

    demand_cb = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb,
        0,
        [v.capacity for v in vehicles],
        True,
        "Capacity",
    )


    has_time_windows = any(
        s.time_window_open is not None or s.time_window_close is not None
        for s in stops
    )
    if has_time_windows:
        # Convert minutes → seconds for consistency with travel matrix
        max_time = 24 * 3600
        routing.AddDimension(
            transit_cb,
            30 * 60,     # max waiting time: 30 minutes
            max_time,    # maximum time per vehicle
            False,       # don't force start cumul to zero (vehicles can start later)
            "Time",
        )
        time_dimension = routing.GetDimensionOrDie("Time")
        for stop_idx, stop in enumerate(stops):
            if stop_idx == depot_index:
                continue
            if stop.time_window_open is None and stop.time_window_close is None:
                continue
            open_s = (stop.time_window_open or 0) * 60
            close_s = (stop.time_window_close or 24 * 60) * 60
            index = manager.NodeToIndex(stop_idx)
            time_dimension.CumulVar(index).SetRange(open_s, close_s)

    penalty = 10**6
    for node in range(n):
        if node == depot_index:
            continue
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.seconds = SOLVER_TIME_LIMIT_SECONDS

    solution = routing.SolveWithParameters(params)
    if not solution:
        logger.error("VRP solver returned no solution")
        return [], list(range(n))

    routes: list[VehicleRoute] = []
    assigned: set[int] = {depot_index}

    for v in range(num_vehicles):
        index = routing.Start(v)
        node_list: list[int] = []
        total_time = 0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            node_list.append(node)
            next_index = solution.Value(routing.NextVar(index))
            total_time += matrix[manager.IndexToNode(index)][manager.IndexToNode(next_index)]
            index = next_index

        node_list.append(manager.IndexToNode(index))  # depot end

        if len(node_list) <= 2:
            continue


        stop_nodes = [n for n in node_list if n != depot_index]
        load = sum(stops[n].demand for n in stop_nodes)
        assigned.update(stop_nodes)

        routes.append(
            VehicleRoute(
                vehicle_index=v,
                label=vehicles[v].label,
                ordered_indices=node_list,
                total_duration_seconds=total_time,
                total_load=load,
            )
        )

    unassigned = [i for i in range(n) if i not in assigned]
    return routes, unassigned
